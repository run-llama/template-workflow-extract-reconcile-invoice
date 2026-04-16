import logging
import os

from llama_cloud import AsyncLlamaCloud
from llama_index.llms.openai import OpenAI

from extraction_review.config import CONTRACTS_INDEX_NAME

logger = logging.getLogger(__name__)

# deployed agents may infer their name from the deployment name
agent_name = os.getenv("LLAMA_DEPLOY_DEPLOYMENT_NAME")
# required for all llama cloud calls
api_key = os.getenv("LLAMA_CLOUD_API_KEY")
# get this in case running against a different environment than production
base_url = os.getenv("LLAMA_CLOUD_BASE_URL")
project_id = os.getenv("LLAMA_DEPLOY_PROJECT_ID")


def get_llama_cloud_client() -> AsyncLlamaCloud:
    """Cloud services connection for file storage and processing."""
    return AsyncLlamaCloud(
        api_key=api_key,
        base_url=base_url,
        default_headers={"Project-Id": project_id} if project_id else {},
    )


_contracts_pipeline_id: str | None = None


async def get_contracts_pipeline_id() -> str:
    """Get or create the contracts pipeline and return its ID."""
    global _contracts_pipeline_id
    if _contracts_pipeline_id is None:
        client = get_llama_cloud_client()
        # data_sink_id=None + transform_config are both required; omitting
        # either trips a misleading 409 "integrity constraint" error. Leaving
        # embedding_config unset lets the platform use managed OpenAI embeddings.
        pipeline = await client.pipelines.upsert(
            name=CONTRACTS_INDEX_NAME,
            project_id=project_id,
            data_sink_id=None,
            transform_config={"mode": "auto"},
        )
        _contracts_pipeline_id = pipeline.id
    return _contracts_pipeline_id


def get_llm() -> OpenAI:
    """Get OpenAI LLM for structured predictions"""
    return OpenAI(model="gpt-5-mini", temperature=0)
