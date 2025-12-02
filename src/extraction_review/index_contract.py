"""
Workflow for indexing contract documents into LlamaCloud Index for retrieval.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Literal

import httpx
from llama_index.core import Document
from pydantic import BaseModel
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .clients import get_contracts_index, get_llama_cloud_client

logger = logging.getLogger(__name__)


class ContractFileEvent(StartEvent):
    """Event to start contract indexing with a file ID"""

    file_ids: list[str]


class DownloadContractEvent(Event):
    """Event to trigger contract download"""

    file_id: str


class ContractDownloadedEvent(Event):
    """Event indicating contract has been downloaded"""

    file_id: str
    file_path: str
    filename: str


class ContractIndexedEvent(Event):
    """Event indicating a single contract has been indexed"""

    file_id: str
    filename: str


class Status(Event):
    """Event to show toast notifications in the UI"""

    level: Literal["info", "warning", "error"]
    message: str


class ContractIndexState(BaseModel):
    """State for contract indexing workflow"""

    total_files: int = 0
    # Store file info keyed by file_id
    file_paths: dict[str, str] = {}
    filenames: dict[str, str] = {}


class IndexContractWorkflow(Workflow):
    """
    Workflow to download and index a contract document into LlamaCloud Index.
    """

    @step()
    async def start_indexing(
        self, event: ContractFileEvent, ctx: Context[ContractIndexState]
    ) -> DownloadContractEvent | None:
        """Initialize the workflow with multiple file IDs and fan out to parallel downloads"""
        logger.info(f"Starting contract indexing for {len(event.file_ids)} files")
        async with ctx.store.edit_state() as state:
            state.total_files = len(event.file_ids)

        # Fan out: emit one download event per file
        for file_id in event.file_ids:
            ctx.send_event(DownloadContractEvent(file_id=file_id))

        return None

    @step(num_workers=4)
    async def download_contract(
        self, event: DownloadContractEvent, ctx: Context[ContractIndexState]
    ) -> ContractDownloadedEvent:
        """Download the contract file from LlamaCloud storage (runs in parallel)"""
        file_id = event.file_id

        file_metadata = await get_llama_cloud_client().files.get_file(id=file_id)
        file_url = await get_llama_cloud_client().files.read_file_content(file_id)

        temp_dir = tempfile.gettempdir()
        filename = file_metadata.name
        file_path = os.path.join(temp_dir, filename)

        logger.info(f"Downloading contract {filename} from {file_url.url}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Downloading contract: {filename}")
        )

        client = httpx.AsyncClient()
        async with client.stream("GET", file_url.url) as response:
            with open(file_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        logger.info(f"Downloaded contract to {file_path}")
        async with ctx.store.edit_state() as state:
            state.file_paths[file_id] = file_path
            state.filenames[file_id] = filename

        return ContractDownloadedEvent(
            file_id=file_id, file_path=file_path, filename=filename
        )

    @step(num_workers=4)
    async def index_contract(
        self, event: ContractDownloadedEvent, ctx: Context[ContractIndexState]
    ) -> ContractIndexedEvent:
        """Index the contract document into LlamaCloud Index (runs in parallel)"""
        file_id = event.file_id
        file_path = event.file_path
        filename = event.filename

        logger.info(f"Indexing contract {filename}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Indexing contract: {filename}")
        )

        # Create a document with metadata
        file_content = Path(file_path).read_text(errors="ignore")
        document = Document(
            text=file_content,
            metadata={
                "filename": filename,
                "file_id": file_id,
                "document_type": "contract",
            },
        )

        # Get the contracts index and insert the document
        index = get_contracts_index()
        await index.ainsert(document)

        logger.info(f"Successfully indexed contract {filename}")
        ctx.write_event_to_stream(
            Status(
                level="info",
                message=f"Successfully indexed contract: {filename}",
            )
        )

        return ContractIndexedEvent(file_id=file_id, filename=filename)

    @step()
    async def collect_results(
        self, event: ContractIndexedEvent, ctx: Context[ContractIndexState]
    ) -> StopEvent | None:
        """Collect all indexed contracts and return final results (fan-in)"""
        state = await ctx.store.get_state()

        # Collect all ContractIndexedEvent events - one for each file
        events = ctx.collect_events(event, [ContractIndexedEvent] * state.total_files)

        if events is None:
            # Not all files have been indexed yet
            return None

        # All files have been indexed, return aggregated results
        results = [{"file_id": ev.file_id, "filename": ev.filename} for ev in events]

        logger.info(f"Successfully indexed all {len(results)} contracts")
        ctx.write_event_to_stream(
            Status(
                level="info",
                message=f"Successfully indexed all {len(results)} contracts",
            )
        )

        return StopEvent(result={"contracts": results, "total": len(results)})


workflow = IndexContractWorkflow(timeout=None)

if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Example usage - upload a contract and index it
        file = await get_llama_cloud_client().files.upload_file(
            upload_file=Path("sample_contract.pdf").open("rb")
        )
        result = await workflow.run(start_event=ContractFileEvent(file_ids=[file.id]))
        print(f"Indexed contract: {result}")

    asyncio.run(main())
