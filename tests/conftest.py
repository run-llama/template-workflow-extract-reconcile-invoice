"""Pytest configuration: install the LlamaCloud fake server for all tests."""

import logging
import sys

import pytest
from llama_cloud_fake import FakeLlamaCloudServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

_fake = FakeLlamaCloudServer().install()


@pytest.fixture
def fake() -> FakeLlamaCloudServer:
    return _fake
