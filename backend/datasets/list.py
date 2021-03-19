"""List all datasets function."""

from ..api_responses import success_response
from ..dataset_model import DatasetModel
from ..types import JsonObject


def list_datasets() -> JsonObject:
    """GET: List all Datasets."""

    # list all datasets
    datasets = DatasetModel.scan(
        filter_condition=DatasetModel.id.startswith("DATASET#")
        & DatasetModel.type.startswith("TYPE#")
    )

    # return response
    resp_body = []
    for dataset in datasets:
        resp_item = dataset.as_dict()
        resp_body.append(resp_item)

    return success_response(200, resp_body)
