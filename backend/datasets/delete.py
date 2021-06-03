"""Delete dataset function."""
from http import HTTPStatus

import boto3
from jsonschema import ValidationError, validate  # type: ignore[import]
from pynamodb.exceptions import DoesNotExist

from ..api_responses import error_response, success_response
from ..datasets_model import datasets_model_with_meta
from ..models import DATASET_ID_PREFIX
from ..resources import ResourceName
from ..step_function import DATASET_ID_SHORT_KEY
from ..types import JsonObject

BOTO3_CLIENT = boto3.client("s3")


def delete_dataset(body: JsonObject) -> JsonObject:
    """DELETE: Delete Dataset."""

    body_schema = {
        "type": "object",
        "properties": {DATASET_ID_SHORT_KEY: {"type": "string"}},
        "required": [DATASET_ID_SHORT_KEY],
    }

    # request body validation
    try:
        validate(body, body_schema)
    except ValidationError as err:
        return error_response(HTTPStatus.BAD_REQUEST, err.message)

    datasets_model_class = datasets_model_with_meta()

    # get dataset to delete
    dataset_id = body[DATASET_ID_SHORT_KEY]
    try:
        dataset = datasets_model_class.get(
            hash_key=f"{DATASET_ID_PREFIX}{dataset_id}", consistent_read=True
        )
    except DoesNotExist:
        return error_response(HTTPStatus.NOT_FOUND, f"dataset '{dataset_id}' does not exist")

    # Verify that the dataset is empty
    list_objects_response = BOTO3_CLIENT.list_objects_v2(
        Bucket=ResourceName.STORAGE_BUCKET_NAME.value, MaxKeys=1, Prefix=f"{dataset_id}/"
    )
    if list_objects_response["KeyCount"]:
        return error_response(
            HTTPStatus.CONFLICT,
            f"Can’t delete dataset “{dataset_id}”: dataset versions still exist",
        )

    # delete dataset
    dataset.delete()

    return success_response(HTTPStatus.NO_CONTENT, {})
