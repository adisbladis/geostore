"""
Pytest configuration file.
"""
from logging import INFO, basicConfig, getLogger

import boto3
import pytest
from mypy_boto3_lambda import LambdaClient
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3control import S3ControlClient
from mypy_boto3_ssm import SSMClient
from mypy_boto3_stepfunctions import SFNClient

basicConfig(level=INFO)
logger = getLogger(__name__)


@pytest.fixture()
def lambda_client() -> LambdaClient:
    return boto3.client("lambda")


@pytest.fixture()
def s3_client() -> S3Client:
    return boto3.client("s3")


@pytest.fixture()
def s3_control_client() -> S3ControlClient:
    return boto3.client("s3control")


@pytest.fixture()
def ssm_client() -> SSMClient:
    return boto3.client("ssm")


@pytest.fixture()
def step_functions_client() -> SFNClient:
    return boto3.client("stepfunctions")
