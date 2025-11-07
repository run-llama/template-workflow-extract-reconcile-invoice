from typing import Any, Type

import jsonref
from pydantic import BaseModel, Field, create_model

from extraction_review.config import InvoiceWithReconciliation


async def get_extraction_schema_json() -> dict[str, Any]:
    json_schema = InvoiceWithReconciliation.model_json_schema()
    json_schema = jsonref.replace_refs(json_schema, proxies=False)
    return json_schema


def model_from_schema(schema: dict[str, Any]) -> Type[BaseModel]:
    """
    Converts a JSON schema back to a Pydantic model.
    """
    typemap = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    fields = {}
    for prop, meta in schema.get("properties", {}).items():
        py_type = typemap.get(meta.get("type"), Any)
        default = ... if prop in schema.get("required", []) else None
        fields[prop] = (py_type, Field(default, description=meta.get("description")))
    return create_model(schema.get("title", "DynamicModel"), **fields)
