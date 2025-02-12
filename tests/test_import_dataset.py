from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from json import dumps

import smart_open
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3control import S3ControlClient
from pytest import mark
from pytest_subtests import SubTests

from geostore.dataset_properties import DATASET_KEY_SEPARATOR
from geostore.error_response_keys import ERROR_MESSAGE_KEY
from geostore.import_dataset.task import lambda_handler
from geostore.models import DATASET_ID_PREFIX, DB_KEY_SEPARATOR, VERSION_ID_PREFIX
from geostore.resources import Resource
from geostore.s3 import S3_URL_PREFIX
from geostore.stac_format import (
    STAC_ASSETS_KEY,
    STAC_FILE_CHECKSUM_KEY,
    STAC_HREF_KEY,
    STAC_LINKS_KEY,
)
from geostore.step_function_keys import (
    DATASET_ID_KEY,
    DATASET_PREFIX_KEY,
    METADATA_URL_KEY,
    S3_ROLE_ARN_KEY,
    VERSION_ID_KEY,
)
from geostore.sts import get_account_number

from .aws_utils import (
    Dataset,
    ProcessingAsset,
    S3Object,
    any_lambda_context,
    any_role_arn,
    any_s3_url,
    delete_copy_job_files,
    delete_s3_key,
    get_s3_role_arn,
    wait_for_copy_jobs,
)
from .file_utils import json_dict_to_file_object
from .general_generators import any_file_contents, any_safe_filename
from .stac_generators import (
    any_asset_name,
    any_dataset_id,
    any_dataset_prefix,
    any_dataset_version_id,
    sha256_hex_digest_to_multihash,
)
from .stac_objects import MINIMAL_VALID_STAC_COLLECTION_OBJECT


def should_return_error_when_missing_required_property(subtests: SubTests) -> None:
    # Given
    minimal_body = {
        DATASET_ID_KEY: any_dataset_id(),
        DATASET_PREFIX_KEY: any_dataset_prefix(),
        METADATA_URL_KEY: any_s3_url(),
        S3_ROLE_ARN_KEY: any_role_arn(),
        VERSION_ID_KEY: any_dataset_version_id(),
    }

    # When
    for key in minimal_body:
        with subtests.test(msg=key):
            # Given a missing property in the body
            body = deepcopy(minimal_body)
            body.pop(key)

            response = lambda_handler(body, any_lambda_context())

            assert response == {ERROR_MESSAGE_KEY: f"'{key}' is a required property"}


@mark.timeout(timedelta(minutes=20).total_seconds())
@mark.infrastructure
def should_batch_copy_files_to_storage(
    s3_client: S3Client,
    s3_control_client: S3ControlClient,
    subtests: SubTests,
) -> None:
    # pylint: disable=too-many-locals
    # Given two metadata files with an asset each, all within a prefix
    original_prefix = any_safe_filename()

    root_asset_name = any_asset_name()
    root_asset_filename = any_safe_filename()
    root_asset_content = any_file_contents()
    root_asset_multihash = sha256_hex_digest_to_multihash(sha256(root_asset_content).hexdigest())
    child_asset_name = any_asset_name()
    child_asset_filename = any_safe_filename()
    child_asset_content = any_file_contents()
    child_asset_multihash = sha256_hex_digest_to_multihash(sha256(child_asset_content).hexdigest())

    root_metadata_filename = any_safe_filename()
    child_metadata_filename = any_safe_filename()

    with S3Object(
        BytesIO(initial_bytes=root_asset_content),
        Resource.STAGING_BUCKET_NAME.resource_name,
        f"{original_prefix}/{root_asset_filename}",
    ) as root_asset_s3_object, S3Object(
        BytesIO(initial_bytes=child_asset_content),
        Resource.STAGING_BUCKET_NAME.resource_name,
        f"{original_prefix}/{child_asset_filename}",
    ) as child_asset_s3_object, S3Object(
        json_dict_to_file_object(
            {
                **deepcopy(MINIMAL_VALID_STAC_COLLECTION_OBJECT),
                STAC_ASSETS_KEY: {
                    child_asset_name: {
                        STAC_HREF_KEY: f"./{child_asset_filename}",
                        STAC_FILE_CHECKSUM_KEY: child_asset_multihash,
                    }
                },
            }
        ),
        Resource.STAGING_BUCKET_NAME.resource_name,
        f"{original_prefix}/{child_metadata_filename}",
    ) as child_metadata_s3_object, S3Object(
        json_dict_to_file_object(
            {
                **deepcopy(MINIMAL_VALID_STAC_COLLECTION_OBJECT),
                STAC_ASSETS_KEY: {
                    root_asset_name: {
                        STAC_HREF_KEY: root_asset_s3_object.url,
                        STAC_FILE_CHECKSUM_KEY: root_asset_multihash,
                    },
                },
                STAC_LINKS_KEY: [{STAC_HREF_KEY: child_metadata_s3_object.url, "rel": "child"}],
            }
        ),
        Resource.STAGING_BUCKET_NAME.resource_name,
        f"{original_prefix}/{root_metadata_filename}",
    ) as root_metadata_s3_object, Dataset() as dataset:
        version_id = any_dataset_version_id()
        asset_id = (
            f"{DATASET_ID_PREFIX}{dataset.dataset_id}"
            f"{DB_KEY_SEPARATOR}{VERSION_ID_PREFIX}{version_id}"
        )

        with ProcessingAsset(asset_id=asset_id, url=root_metadata_s3_object.url), ProcessingAsset(
            asset_id=asset_id, url=child_metadata_s3_object.url
        ), ProcessingAsset(
            asset_id=asset_id, url=root_asset_s3_object.url, multihash=root_asset_multihash
        ), ProcessingAsset(
            asset_id=asset_id, url=child_asset_s3_object.url, multihash=child_asset_multihash
        ):
            # When
            try:
                response = lambda_handler(
                    {
                        DATASET_ID_KEY: dataset.dataset_id,
                        DATASET_PREFIX_KEY: dataset.dataset_prefix,
                        VERSION_ID_KEY: version_id,
                        METADATA_URL_KEY: root_metadata_s3_object.url,
                        S3_ROLE_ARN_KEY: get_s3_role_arn(),
                    },
                    any_lambda_context(),
                )

                account_id = get_account_number()

                metadata_copy_job_result, asset_copy_job_result = wait_for_copy_jobs(
                    response,
                    account_id,
                    s3_control_client,
                    subtests,
                )
            finally:
                # Then
                new_prefix = (
                    f"{dataset.title}{DATASET_KEY_SEPARATOR}{dataset.dataset_id}/{version_id}"
                )
                storage_bucket_prefix = (
                    f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}/"
                )

                new_root_metadata_key = f"{new_prefix}/{root_metadata_filename}"
                expected_root_metadata = dumps(
                    {
                        **deepcopy(MINIMAL_VALID_STAC_COLLECTION_OBJECT),
                        STAC_ASSETS_KEY: {
                            root_asset_name: {
                                STAC_HREF_KEY: root_asset_filename,
                                STAC_FILE_CHECKSUM_KEY: root_asset_multihash,
                            },
                        },
                        STAC_LINKS_KEY: [{STAC_HREF_KEY: child_metadata_filename, "rel": "child"}],
                    }
                ).encode()
                with subtests.test(msg="Root metadata content"), smart_open.open(
                    f"{storage_bucket_prefix}{new_root_metadata_key}", mode="rb"
                ) as new_root_metadata_file:
                    assert expected_root_metadata == new_root_metadata_file.read()

                with subtests.test(msg="Delete root metadata object"):
                    delete_s3_key(
                        Resource.STORAGE_BUCKET_NAME.resource_name, new_root_metadata_key, s3_client
                    )

                new_child_metadata_key = f"{new_prefix}/{child_metadata_filename}"
                expected_child_metadata = dumps(
                    {
                        **deepcopy(MINIMAL_VALID_STAC_COLLECTION_OBJECT),
                        STAC_ASSETS_KEY: {
                            child_asset_name: {
                                STAC_HREF_KEY: child_asset_filename,
                                STAC_FILE_CHECKSUM_KEY: child_asset_multihash,
                            }
                        },
                    }
                ).encode()
                with subtests.test(msg="Child metadata content"), smart_open.open(
                    f"{storage_bucket_prefix}{new_child_metadata_key}", mode="rb"
                ) as new_child_metadata_file:
                    assert expected_child_metadata == new_child_metadata_file.read()

                with subtests.test(msg="Delete child metadata object"):
                    delete_s3_key(
                        Resource.STORAGE_BUCKET_NAME.resource_name,
                        new_child_metadata_key,
                        s3_client,
                    )

                # Then the root asset file is in the root prefix
                with subtests.test(msg="Delete root asset object"):
                    delete_s3_key(
                        Resource.STORAGE_BUCKET_NAME.resource_name,
                        f"{new_prefix}/{root_asset_filename}",
                        s3_client,
                    )

                # Then the child asset file is in the root prefix
                with subtests.test(msg="Delete child asset object"):
                    delete_s3_key(
                        Resource.STORAGE_BUCKET_NAME.resource_name,
                        f"{new_prefix}/{child_asset_filename}",
                        s3_client,
                    )

                # Cleanup
                with subtests.test(msg="Delete copy job files"):
                    delete_copy_job_files(
                        metadata_copy_job_result,
                        asset_copy_job_result,
                        Resource.STORAGE_BUCKET_NAME.resource_name,
                        s3_client,
                        subtests,
                    )
