"""Dataset versions handler function."""
import json
import uuid

import boto3
from jsonschema import ValidationError, validate  # type: ignore[import]
from pynamodb.exceptions import DoesNotExist

from ..api_responses import error_response, success_response
from ..datasets_model import datasets_model_with_meta
from ..error_response_keys import ERROR_KEY
from ..log import set_up_logging
from ..parameter_store import ParameterName, get_param
from ..step_function_event_keys import DATASET_ID_KEY, METADATA_URL_KEY, VERSION_ID_KEY
from ..types import JsonObject

STEP_FUNCTIONS_CLIENT = boto3.client("stepfunctions")


def create_dataset_version(event: JsonObject) -> JsonObject:
    logger = set_up_logging(__name__)

    logger.debug(json.dumps({"event": event}))

    body_schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "metadata-url": {"type": "string"}},
        "required": ["id", "metadata-url"],
    }

    # validate input
    req_body = event["body"]
    try:
        validate(req_body, body_schema)
    except ValidationError as err:
        logger.warning(json.dumps({ERROR_KEY: err}, default=str))
        return error_response(400, err.message)

    datasets_model_class = datasets_model_with_meta()

    # validate dataset exists
    try:
        dataset = datasets_model_class.get(
            hash_key=f"DATASET#{req_body['id']}", consistent_read=True
        )
    except DoesNotExist as err:
        logger.warning(json.dumps({ERROR_KEY: err}, default=str))
        return error_response(404, f"dataset '{req_body['id']}' could not be found")

    dataset_version_id = uuid.uuid1().hex

    # execute step function
    step_functions_input = {
        DATASET_ID_KEY: dataset.dataset_id,
        VERSION_ID_KEY: dataset_version_id,
        METADATA_URL_KEY: req_body["metadata-url"],
    }
    state_machine_arn = get_param(ParameterName.DATASET_VERSION_CREATION_STEP_FUNCTION_ARN)

    step_functions_response = STEP_FUNCTIONS_CLIENT.start_execution(
        stateMachineArn=state_machine_arn,
        name=dataset_version_id,
        input=json.dumps(step_functions_input),
    )

    logger.debug(json.dumps({"response": step_functions_response}, default=str))

    # return arn of executing process
    return success_response(
        201,
        {
            "dataset_version": dataset_version_id,
            "execution_arn": step_functions_response["executionArn"],
        },
    )
