from typing import Annotated, Any

import jsonref
from llama_cloud.types.configuration_response import ExtractV2Parameters
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent
from workflows.resource import ResourceConfig

from .clients import get_contracts_pipeline_id, get_llama_cloud_client, project_id
from .config import EXTRACTED_DATA_COLLECTION, ExtractConfig


class MetadataResponse(StopEvent):
    json_schema: dict[str, Any]
    extracted_data_collection: str
    contracts_pipeline_id: str


class MetadataWorkflow(Workflow):
    """Provide extraction schema and configuration to the workflow editor."""

    @step
    async def get_metadata(
        self,
        _: StartEvent,
        extract_config: Annotated[
            ExtractConfig,
            ResourceConfig(
                config_file="configs/config.json",
                path_selector="extract",
                label="Extraction Settings",
                description="Configuration for document extraction quality and features",
            ),
        ],
    ) -> MetadataResponse:
        """Return the data schema and storage settings for the review interface.

        When `configuration_id` is set, fetches the schema from the saved
        extract configuration so the UI always reflects what will actually be
        extracted. Otherwise uses the local schema from config.json.
        """
        if extract_config.configuration_id:
            client = get_llama_cloud_client()
            config_resp = await client.configurations.retrieve(
                extract_config.configuration_id,
                project_id=project_id,
            )
            params = config_resp.parameters
            if not isinstance(params, ExtractV2Parameters):
                raise ValueError(
                    f"Configuration {extract_config.configuration_id} is not extract_v2"
                )
            schema_dict = dict(params.data_schema)
        else:
            schema_dict = dict(extract_config.data_schema)

        json_schema = jsonref.replace_refs(schema_dict, proxies=False)
        contracts_pipeline_id = await get_contracts_pipeline_id()
        return MetadataResponse(
            json_schema=json_schema,
            extracted_data_collection=EXTRACTED_DATA_COLLECTION,
            contracts_pipeline_id=contracts_pipeline_id,
        )


workflow = MetadataWorkflow(timeout=None)
