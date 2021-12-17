from json import dumps
from typing import TYPE_CHECKING

import boto3
from linz_logger import get_log
from pystac import read_file
from pystac.catalog import Catalog, CatalogType
from pystac.collection import Collection
from pystac.item import Item
from pystac.layout import HrefLayoutStrategy
from pystac.stac_io import StacIO

from ..api_keys import EVENT_KEY
from ..aws_keys import BODY_KEY
from ..boto3_config import CONFIG
from ..pystac_io_methods import S3StacIO
from ..resources import Resource
from ..s3 import S3_URL_PREFIX
from ..types import JsonObject

if TYPE_CHECKING:
    # When type checking we want to use the third party package's stub
    from mypy_boto3_s3 import S3Client
else:
    # In production we want to avoid depending on a package which has no runtime impact
    S3Client = object  # pragma: no mutate

S3_CLIENT: S3Client = boto3.client("s3", config=CONFIG)

ROOT_CATALOG_ID = "root_catalog"
ROOT_CATALOG_TITLE = "LINZ Geostore"
ROOT_CATALOG_DESCRIPTION = (
    "The LINZ Geospatial Data Store (Geostore) contains all the important "
    "geospatial data held by Land Information New Zealand (LINZ).<br/>"
    "Please browse this catalog to find and access our data."
)
CATALOG_FILENAME = "catalog.json"
CONTENTS_KEY = "Contents"
RECORDS_KEY = "Records"

LOGGER = get_log()

StacIO.set_default(S3StacIO)


def lambda_handler(event: JsonObject, _context: bytes) -> JsonObject:
    """Main Lambda entry point."""

    LOGGER.debug(dumps({EVENT_KEY: event}))

    for message in event[RECORDS_KEY]:
        handle_dataset(message[BODY_KEY])

    return {}


class GeostoreSTACLayoutStrategy(HrefLayoutStrategy):
    def get_catalog_href(self, cat: Catalog, parent_dir: str, is_root: bool) -> str:
        return str(cat.get_self_href())

    def get_collection_href(self, col: Collection, parent_dir: str, is_root: bool) -> str:
        assert not is_root
        return str(col.get_self_href())

    def get_item_href(self, item: Item, parent_dir: str) -> str:
        return str(item.get_self_href())


def handle_dataset(dataset_metadata_key: str) -> None:
    """Handle writing a new dataset version to the dataset catalog"""
    results = S3_CLIENT.list_objects(
        Bucket=Resource.STORAGE_BUCKET_NAME.resource_name, Prefix=CATALOG_FILENAME
    )

    # create root catalog if it doesn't exist
    if CONTENTS_KEY in results:
        root_catalog = Catalog.from_file(
            f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}/{CATALOG_FILENAME}"
        )

    else:
        root_catalog = Catalog(
            id=ROOT_CATALOG_ID,
            title=ROOT_CATALOG_TITLE,
            description=ROOT_CATALOG_DESCRIPTION,
            catalog_type=CatalogType.SELF_CONTAINED,
        )
        root_catalog.set_self_href(
            f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}/{CATALOG_FILENAME}"
        )

    storage_bucket_path = f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}"
    dataset_metadata = read_file(f"{storage_bucket_path}/{dataset_metadata_key}")
    assert isinstance(dataset_metadata, (Catalog, Collection))

    root_catalog.add_child(dataset_metadata, strategy=GeostoreSTACLayoutStrategy())
    root_catalog.make_all_asset_hrefs_relative()
    root_catalog.normalize_hrefs(
        f"{S3_URL_PREFIX}{Resource.STORAGE_BUCKET_NAME.resource_name}",
        strategy=GeostoreSTACLayoutStrategy(),
    )
    root_catalog.save(catalog_type=CatalogType.SELF_CONTAINED)
