from json import dumps, load
from os.path import basename
from typing import TYPE_CHECKING, Dict, Iterable

import boto3

from ..import_dataset_file import get_import_result
from ..log import set_up_logging
from ..stac_format import STAC_ASSETS_KEY, STAC_HREF_KEY, STAC_LINKS_KEY
from ..types import JsonObject

S3_BODY_KEY = "Body"

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import PutObjectOutputTypeDef
else:
    PutObjectOutputTypeDef = JsonObject

S3_CLIENT = boto3.client("s3")
LOGGER = set_up_logging(__name__)


def lambda_handler(event: JsonObject, _context: bytes) -> JsonObject:
    return get_import_result(event, importer)


def importer(
    source_bucket_name: str, original_key: str, target_bucket_name: str, new_key: str
) -> PutObjectOutputTypeDef:
    get_object_response = S3_CLIENT.get_object(Bucket=source_bucket_name, Key=original_key)
    assert S3_BODY_KEY in get_object_response, get_object_response

    metadata = load(get_object_response["Body"])

    assets = metadata.get(STAC_ASSETS_KEY, {}).values()
    change_href_to_basename(assets)

    links = metadata.get(STAC_LINKS_KEY, [])
    change_href_to_basename(links)

    return S3_CLIENT.put_object(
        Bucket=target_bucket_name,
        Key=new_key,
        Body=dumps(metadata).encode(),
    )


def change_href_to_basename(items: Iterable[Dict[str, str]]) -> None:
    for item in items:
        item[STAC_HREF_KEY] = basename(item[STAC_HREF_KEY])
