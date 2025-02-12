from typing import Final

JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_SUCCEEDED = "SUCCEEDED"

S3_BATCH_STATUS_FAILED: Final = "Failed"
S3_BATCH_STATUS_CANCELLED: Final = "Cancelled"
S3_BATCH_STATUS_COMPLETE: Final = "Complete"

ASSET_UPLOAD_KEY = "asset_upload"
DATASET_ID_KEY = "dataset_id"
DATASET_ID_SHORT_KEY = "id"
DATASET_PREFIX_KEY = "dataset_prefix"
DESCRIPTION_KEY = "description"
ERRORS_KEY = "errors"
ERROR_CHECK_KEY = "check"
ERROR_DETAILS_KEY = "details"
ERROR_RESULT_KEY = "result"
ERROR_URL_KEY = "url"
EXECUTION_ARN_KEY = "execution_arn"
FAILED_TASKS_KEY = "failed_tasks"
FAILURE_REASONS_KEY = "failure_reasons"
IMPORT_DATASET_KEY = "import_dataset"
INPUT_KEY = "input"
METADATA_UPLOAD_KEY = "metadata_upload"
METADATA_URL_KEY = "metadata_url"
NEW_VERSION_S3_LOCATION = "new_version_s3_location"
NOW_KEY = "now"
OUTPUT_KEY = "output"
S3_BATCH_RESPONSE_KEY = "s3_batch_response"
S3_ROLE_ARN_KEY = "s3_role_arn"
STATUS_KEY = "status"
STEP_FUNCTION_KEY = "step_function"
TITLE_KEY = "title"
UPDATE_DATASET_KEY = "update_dataset_catalog"
UPLOAD_STATUS_KEY = "upload_status"
VALIDATION_KEY = "validation"
VERSION_ID_KEY = "version_id"
