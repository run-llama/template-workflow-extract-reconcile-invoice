import functools
import logging
import os

import httpx
from llama_cloud.client import AsyncLlamaCloud
from llama_cloud.core.api_error import ApiError
from llama_cloud_services import ExtractionAgent, LlamaExtract, LlamaCloudIndex
from llama_cloud_services.beta.agent_data import AsyncAgentDataClient, ExtractedData
from llama_index.llms.openai import OpenAI

from extraction_review.config import (
    CONTRACTS_INDEX_NAME,
    EXTRACTED_DATA_COLLECTION,
    EXTRACT_CONFIG,
    EXTRACTION_AGENT_NAME,
    InvoiceExtractionSchema,
    InvoiceWithReconciliation,
)

logger = logging.getLogger(__name__)

# deployed agents may infer their name from the deployment name
# Note: Make sure that an agent deployment with this name actually exists
# otherwise calls to get or set data will fail. You may need to adjust the `or `
# name for development
agent_name = os.getenv("LLAMA_DEPLOY_DEPLOYMENT_NAME")
# required for all llama cloud calls
api_key = os.getenv("LLAMA_CLOUD_API_KEY")
# get this in case running against a different environment than production
base_url = os.getenv("LLAMA_CLOUD_BASE_URL")
project_id = os.getenv("LLAMA_DEPLOY_PROJECT_ID")


@functools.lru_cache(maxsize=None)
def get_extract_agent() -> ExtractionAgent:
    extract_api = LlamaExtract(
        api_key=api_key, base_url=base_url, project_id=project_id
    )

    try:
        existing = extract_api.get_agent(EXTRACTION_AGENT_NAME)
        existing.data_schema = InvoiceExtractionSchema
        existing.config = EXTRACT_CONFIG
        return existing
    except ApiError as e:
        if e.status_code == 404:
            return extract_api.create_agent(
                name=EXTRACTION_AGENT_NAME,
                data_schema=InvoiceExtractionSchema,
                config=EXTRACT_CONFIG,
            )
        else:
            raise


@functools.lru_cache(maxsize=None)
def get_data_client() -> AsyncAgentDataClient[ExtractedData[InvoiceWithReconciliation]]:
    return AsyncAgentDataClient(
        deployment_name=agent_name,
        collection=EXTRACTED_DATA_COLLECTION,
        type=ExtractedData[InvoiceWithReconciliation],
        client=get_llama_cloud_client(),
    )


@functools.lru_cache(maxsize=None)
def get_llama_cloud_client():
    return AsyncLlamaCloud(
        base_url=base_url,
        token=api_key,
        httpx_client=httpx.AsyncClient(
            timeout=60, headers={"Project-Id": project_id} if project_id else None
        ),
    )


@functools.lru_cache(maxsize=None)
def get_contracts_index() -> LlamaCloudIndex:
    """Get or create the contracts index for storing and retrieving contract documents"""
    return LlamaCloudIndex.create_index(
        name=CONTRACTS_INDEX_NAME,
        project_id=project_id,
        api_key=api_key,
        base_url=base_url,
    )


@functools.lru_cache(maxsize=None)
def get_llm() -> OpenAI:
    """Get OpenAI LLM for structured predictions"""
    return OpenAI(model="gpt-5-mini", temperature=0)
