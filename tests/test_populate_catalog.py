from copy import deepcopy
from json import load

import smart_open
from _pytest.python_api import raises
from mypy_boto3_s3 import S3Client
from pytest import mark
from pytest_subtests import SubTests

from geostore.aws_keys import BODY_KEY
from geostore.aws_message_attributes import (
    DATA_TYPE_KEY,
    DATA_TYPE_STRING,
    MESSAGE_ATTRIBUTE_TYPE_KEY,
    MESSAGE_ATTRIBUTE_TYPE_ROOT,
    STRING_VALUE_KEY_LOWER,
)
from geostore.populate_catalog.task import (
    CATALOG_FILENAME,
    MESSAGE_ATTRIBUTES_KEY,
    RECORDS_KEY,
    ROOT_CATALOG_DESCRIPTION,
    ROOT_CATALOG_ID,
    ROOT_CATALOG_TITLE,
    UnhandledSQSMessageException,
    lambda_handler,
)
from geostore.resources import Resource
from geostore.s3 import S3_URL_PREFIX
from geostore.stac_format import (
    STAC_DESCRIPTION_KEY,
    STAC_HREF_KEY,
    STAC_ID_KEY,
    STAC_LINKS_KEY,
    STAC_MEDIA_TYPE_JSON,
    STAC_REL_CHILD,
    STAC_REL_KEY,
    STAC_REL_PARENT,
    STAC_REL_ROOT,
    STAC_TITLE_KEY,
    STAC_TYPE_KEY,
)
from geostore.types import JsonList
from tests.aws_utils import Dataset, S3Object, any_lambda_context, delete_s3_key
from tests.file_utils import json_dict_to_file_object
from tests.stac_generators import any_dataset_version_id
from tests.stac_objects import MINIMAL_VALID_STAC_CATALOG_OBJECT


@mark.infrastructure
def should_create_new_root_catalog_if_doesnt_exist(subtests: SubTests, s3_client: S3Client) -> None:

    with Dataset() as dataset, S3Object(
        file_object=json_dict_to_file_object(
            {
                **deepcopy(MINIMAL_VALID_STAC_CATALOG_OBJECT),
                STAC_ID_KEY: dataset.dataset_prefix,
                STAC_TITLE_KEY: dataset.title,
            }
        ),
        bucket_name=Resource.STORAGE_BUCKET_NAME.resource_name,
        key=f"{dataset.dataset_prefix}/{CATALOG_FILENAME}",
    ):

        expected_links: JsonList = [
            {
                STAC_REL_KEY: STAC_REL_ROOT,
                STAC_HREF_KEY: f"./{CATALOG_FILENAME}",
                STAC_TITLE_KEY: ROOT_CATALOG_TITLE,
                STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
            },
            {
                STAC_REL_KEY: STAC_REL_CHILD,
                STAC_HREF_KEY: f"./{dataset.dataset_prefix}/{CATALOG_FILENAME}",
                STAC_TITLE_KEY: dataset.title,
                STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
            },
        ]

        try:
            lambda_handler(
                {
                    RECORDS_KEY: [
                        {
                            BODY_KEY: dataset.dataset_prefix,
                            MESSAGE_ATTRIBUTES_KEY: {
                                MESSAGE_ATTRIBUTE_TYPE_KEY: {
                                    STRING_VALUE_KEY_LOWER: MESSAGE_ATTRIBUTE_TYPE_ROOT,
                                    DATA_TYPE_KEY: DATA_TYPE_STRING,
                                }
                            },
                        }
                    ]
                },
                any_lambda_context(),
            )

            with smart_open.open(
                f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}/{CATALOG_FILENAME}",
                mode="rb",
            ) as new_root_metadata_file:
                catalog_json = load(new_root_metadata_file)

                with subtests.test(msg="catalog title"):
                    assert catalog_json[STAC_TITLE_KEY] == ROOT_CATALOG_TITLE

                with subtests.test(msg="catalog description"):
                    assert catalog_json[STAC_DESCRIPTION_KEY] == ROOT_CATALOG_DESCRIPTION

                with subtests.test(msg="catalog links"):
                    assert catalog_json[STAC_LINKS_KEY] == expected_links

        finally:
            delete_s3_key(Resource.STORAGE_BUCKET_NAME.resource_name, CATALOG_FILENAME, s3_client)


@mark.infrastructure
def should_update_existing_root_catalog(subtests: SubTests) -> None:

    with Dataset() as existing_dataset, S3Object(
        file_object=json_dict_to_file_object(
            {
                **deepcopy(MINIMAL_VALID_STAC_CATALOG_OBJECT),
                STAC_ID_KEY: existing_dataset.dataset_prefix,
                STAC_TITLE_KEY: existing_dataset.title,
            }
        ),
        bucket_name=Resource.STORAGE_BUCKET_NAME.resource_name,
        key=f"{existing_dataset.dataset_prefix}/{CATALOG_FILENAME}",
    ):

        original_links: JsonList = [
            {
                STAC_REL_KEY: STAC_REL_ROOT,
                STAC_HREF_KEY: f"./{CATALOG_FILENAME}",
                STAC_TITLE_KEY: ROOT_CATALOG_TITLE,
                STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
            },
            {
                STAC_REL_KEY: STAC_REL_CHILD,
                STAC_HREF_KEY: f"./{existing_dataset.dataset_prefix}/{CATALOG_FILENAME}",
                STAC_TITLE_KEY: existing_dataset.title,
                STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
            },
        ]

        with Dataset() as dataset, S3Object(
            file_object=json_dict_to_file_object(
                {
                    **deepcopy(MINIMAL_VALID_STAC_CATALOG_OBJECT),
                    STAC_ID_KEY: dataset.dataset_prefix,
                    STAC_TITLE_KEY: dataset.title,
                }
            ),
            bucket_name=Resource.STORAGE_BUCKET_NAME.resource_name,
            key=f"{dataset.dataset_prefix}/{CATALOG_FILENAME}",
        ), S3Object(
            file_object=json_dict_to_file_object(
                {
                    **deepcopy(MINIMAL_VALID_STAC_CATALOG_OBJECT),
                    STAC_ID_KEY: ROOT_CATALOG_ID,
                    STAC_DESCRIPTION_KEY: ROOT_CATALOG_DESCRIPTION,
                    STAC_TITLE_KEY: ROOT_CATALOG_TITLE,
                    STAC_LINKS_KEY: original_links,
                }
            ),
            bucket_name=Resource.STORAGE_BUCKET_NAME.resource_name,
            key=CATALOG_FILENAME,
        ):

            expected_root_links: JsonList = original_links + [
                {
                    STAC_REL_KEY: STAC_REL_CHILD,
                    STAC_HREF_KEY: f"./{dataset.dataset_prefix}/{CATALOG_FILENAME}",
                    STAC_TITLE_KEY: dataset.title,
                    STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
                }
            ]

            expected_dataset_links: JsonList = [
                {
                    STAC_REL_KEY: STAC_REL_ROOT,
                    STAC_HREF_KEY: f"../{CATALOG_FILENAME}",
                    STAC_TITLE_KEY: ROOT_CATALOG_TITLE,
                    STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
                },
                {
                    STAC_REL_KEY: STAC_REL_PARENT,
                    STAC_HREF_KEY: f"../{CATALOG_FILENAME}",
                    STAC_TITLE_KEY: ROOT_CATALOG_TITLE,
                    STAC_TYPE_KEY: STAC_MEDIA_TYPE_JSON,
                },
            ]

            lambda_handler(
                {
                    RECORDS_KEY: [
                        {
                            BODY_KEY: dataset.dataset_prefix,
                            MESSAGE_ATTRIBUTES_KEY: {
                                MESSAGE_ATTRIBUTE_TYPE_KEY: {
                                    STRING_VALUE_KEY_LOWER: MESSAGE_ATTRIBUTE_TYPE_ROOT,
                                    DATA_TYPE_KEY: DATA_TYPE_STRING,
                                }
                            },
                        }
                    ]
                },
                any_lambda_context(),
            )

            with smart_open.open(
                f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}/{CATALOG_FILENAME}",
                mode="rb",
            ) as root_metadata_file, subtests.test(msg="root catalog links"):
                root_catalog_json = load(root_metadata_file)
                assert root_catalog_json[STAC_LINKS_KEY] == expected_root_links

            with smart_open.open(
                f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}"
                f"/{dataset.dataset_prefix}/{CATALOG_FILENAME}",
                mode="rb",
            ) as dataset_metadata_file, subtests.test(msg="dataset catalog links"):
                dataset_catalog_json = load(dataset_metadata_file)
                assert dataset_catalog_json[STAC_LINKS_KEY] == expected_dataset_links


def should_fail_if_unknown_sqs_message_type() -> None:
    with raises(UnhandledSQSMessageException):
        lambda_handler(
            {
                RECORDS_KEY: [
                    {
                        BODY_KEY: any_dataset_version_id(),
                        MESSAGE_ATTRIBUTES_KEY: {
                            MESSAGE_ATTRIBUTE_TYPE_KEY: {
                                STRING_VALUE_KEY_LOWER: "test",
                                DATA_TYPE_KEY: DATA_TYPE_STRING,
                            }
                        },
                    }
                ]
            },
            any_lambda_context(),
        )
