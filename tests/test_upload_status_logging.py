from json import dumps
from unittest.mock import MagicMock, patch

from backend.api_keys import SUCCESS_KEY
from backend.import_file_batch_job_id_keys import ASSET_JOB_ID_KEY, METADATA_JOB_ID_KEY
from backend.step_function import DATASET_ID_KEY, IMPORT_DATASET_KEY, VALIDATION_KEY, VERSION_ID_KEY
from backend.upload_status.task import lambda_handler

from .aws_utils import any_job_id, any_lambda_context
from .stac_generators import any_dataset_id, any_dataset_version_id


@patch("backend.upload_status.task.get_tasks_status")
def should_log_event(get_tasks_status_mock: MagicMock) -> None:
    # Given
    get_tasks_status_mock.return_value = {}

    event = {
        DATASET_ID_KEY: any_dataset_id(),
        VERSION_ID_KEY: any_dataset_version_id(),
        VALIDATION_KEY: {SUCCESS_KEY: True},
        IMPORT_DATASET_KEY: {
            METADATA_JOB_ID_KEY: any_job_id(),
            ASSET_JOB_ID_KEY: any_job_id(),
        },
    }
    expected_log = dumps({"event": event})

    with patch("backend.upload_status.task.LOGGER.debug") as logger_mock:
        # When
        lambda_handler(event, any_lambda_context())

        # Then
        logger_mock.assert_any_call(expected_log)
