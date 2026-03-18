"""Utilities for working with JSON schemas."""

import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

from json_schema_to_pydantic import create_model
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _hash_schema(json_schema: dict[str, Any]) -> str:
    schema_str = json.dumps(json_schema, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()


@lru_cache(maxsize=16)
def _get_cached_model(schema_hash: str, schema_json: str) -> type[BaseModel]:
    schema = json.loads(schema_json)
    return create_model(schema)


def get_extraction_schema(json_schema: dict[str, Any]) -> type[BaseModel]:
    """Convert a JSON schema to a Pydantic model, cached by hash."""
    schema_hash = _hash_schema(json_schema)
    schema_json = json.dumps(json_schema, sort_keys=True)
    return _get_cached_model(schema_hash, schema_json)
