from typing import Any

from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent

from extraction_review.schema import get_extraction_schema_json

from .config import EXTRACTED_DATA_COLLECTION


class MetadataResponse(StopEvent):
    json_schema: dict[str, Any]
    extracted_data_collection: str


class MetadataWorkflow(Workflow):
    """
    Simple single step workflow to expose configuration to the UI, such as the JSON schema and collection name.
    """

    @step
    async def get_metadata(self, _: StartEvent) -> MetadataResponse:
        json_schema = await get_extraction_schema_json()
        return MetadataResponse(
            json_schema=json_schema,
            extracted_data_collection=EXTRACTED_DATA_COLLECTION,
        )


workflow = MetadataWorkflow(timeout=None)
