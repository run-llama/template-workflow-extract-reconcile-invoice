import pytest
from extraction_review.process_file import FileEvent
from extraction_review.process_file import workflow as process_file_workflow
from llama_cloud_fake import FakeLlamaCloudServer


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


# metadata_workflow here calls `pipelines.upsert` to ensure the contracts
# index exists, which isn't covered by the fake in llama-cloud-fake<0.1.1.
# Add a test for it once the floor is bumped.
