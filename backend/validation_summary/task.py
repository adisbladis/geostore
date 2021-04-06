from json import dumps

from jsonschema import ValidationError, validate  # type: ignore[import]

from ..log import set_up_logging
from ..types import JsonObject
from ..validation_results_model import ValidationResult, validation_results_model_with_meta

LOGGER = set_up_logging(__name__)


def lambda_handler(event: JsonObject, _context: bytes) -> JsonObject:
    LOGGER.debug(dumps({"event": event}))

    try:
        validate(
            event,
            {
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}, "version_id": {"type": "string"}},
                "required": ["dataset_id", "version_id"],
            },
        )
    except ValidationError as error:
        return {"error message": error.message}

    validation_results_model = validation_results_model_with_meta()
    success = not bool(
        validation_results_model.validation_outcome_index.count(  # pylint: disable=no-member
            f"DATASET#{event['dataset_id']}#VERSION#{event['version_id']}",
            range_key_condition=validation_results_model.result == ValidationResult.FAILED.value,
            limit=1,
        )
    )

    result = {"success": success}
    LOGGER.debug(dumps(result))
    return result
