import pytest
from extraction_review.config import EXTRACTED_DATA_COLLECTION
from extraction_review.index_contract import ContractFileEvent
from extraction_review.index_contract import workflow as index_contract_workflow
from extraction_review.metadata_workflow import MetadataResponse
from extraction_review.metadata_workflow import workflow as metadata_workflow
from extraction_review.process_file import FileEvent
from extraction_review.process_file import workflow as process_file_workflow
from llama_cloud_fake import FakeLlamaCloudServer
from workflows.events import StartEvent


@pytest.mark.asyncio
async def test_process_file_workflow(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeLlamaCloudServer,
) -> None:
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "fake-api-key")
    file_id = fake.files.preload(path="tests/files/test.pdf")
    try:
        result = await process_file_workflow.run(start_event=FileEvent(file_id=file_id))
    except Exception:
        result = None
    assert result is not None
    assert isinstance(result, str)
    assert len(result) == 7


@pytest.mark.asyncio
async def test_index_contract_workflow(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeLlamaCloudServer,
) -> None:
    """Regression: index_contract previously called stale SDK methods
    (files.get_file / files.read_file_content) and died on any contract upload.
    """
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "fake-api-key")
    file_id = fake.files.preload(path="tests/files/test.pdf")
    result = await index_contract_workflow.run(
        start_event=ContractFileEvent(file_ids=[file_id])
    )
    assert result is not None
    assert result["total"] == 1
    assert result["contracts"][0]["file_id"] == file_id


@pytest.mark.asyncio
async def test_metadata_workflow(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeLlamaCloudServer,
) -> None:
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "fake-api-key")
    result = await metadata_workflow.run(start_event=StartEvent())
    assert isinstance(result, MetadataResponse)
    assert result.extracted_data_collection == EXTRACTED_DATA_COLLECTION
    assert isinstance(result.json_schema, dict)
    assert "properties" in result.json_schema
    assert result.contracts_pipeline_id
