import pytest
from extraction_review.config import EXTRACTED_DATA_COLLECTION, Reconciliation
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
    """The contract indexer must run LlamaParse and upsert real markdown text.

    Earlier versions read PDFs via `Path(...).read_text(errors="ignore")` and
    upserted the resulting binary garbage into the contracts pipeline, so the
    matching LLM saw stream-decoded bytes instead of contract content. Lock
    the fix: the upserted document must not be raw PDF bytes.
    """
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "fake-api-key")
    file_id = fake.files.preload(path="tests/files/test.pdf")
    result = await index_contract_workflow.run(
        start_event=ContractFileEvent(file_ids=[file_id])
    )
    assert result is not None
    assert result["total"] == 1
    assert result["contracts"][0]["file_id"] == file_id

    # The fake stores upserted documents under pipelines._documents; pull the
    # contract-tagged ones and verify the indexed text is parsed markdown,
    # not the raw PDF stream.
    indexed_texts = [
        doc.text
        for store in fake.pipelines._documents.values()
        for doc in store.values()
        if doc.metadata.get("file_id") == file_id
    ]
    assert indexed_texts, "expected at least one upserted contract document"
    for text in indexed_texts:
        assert text, "indexed contract text is empty"
        assert not text.startswith("%PDF"), (
            f"contract was indexed as raw PDF bytes: {text[:40]!r}"
        )


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

    # Reconciliation overlay: presence guards the regression that dropped the
    # linkage fields entirely; ordering guards a "cleanup" that silently moves
    # the verdict to the bottom of the form.
    properties = result.json_schema["properties"]
    reconciliation_fields = set(Reconciliation.model_fields)
    assert reconciliation_fields.issubset(properties.keys())
    assert next(iter(properties)) in reconciliation_fields
