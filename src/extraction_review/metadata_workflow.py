from typing import Any

from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent

from extraction_review.schema import get_extraction_schema_json

from .clients import get_contracts_index
from .config import EXTRACTED_DATA_COLLECTION


class MetadataResponse(StopEvent):
    json_schema: dict[str, Any]
    extracted_data_collection: str
    contracts_pipeline_id: str


class MetadataWorkflow(Workflow):
    """
    Simple single step workflow to expose configuration to the UI, such as the JSON schema and collection name.
    """

    @step
    async def get_metadata(self, _: StartEvent) -> MetadataResponse:
        json_schema = await get_extraction_schema_json()
        contracts_index = get_contracts_index()
        return MetadataResponse(
            json_schema=json_schema,
            extracted_data_collection=EXTRACTED_DATA_COLLECTION,
            contracts_pipeline_id=contracts_index.id,
        )


workflow = MetadataWorkflow(timeout=None)
