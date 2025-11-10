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

    file_id: str


class DownloadContractEvent(Event):
    """Event to trigger contract download"""

    pass


class ContractDownloadedEvent(Event):
    """Event indicating contract has been downloaded"""

    pass


class Status(Event):
    """Event to show toast notifications in the UI"""

    level: Literal["info", "warning", "error"]
    message: str


class ContractIndexState(BaseModel):
    """State for contract indexing workflow"""

    file_id: str | None = None
    file_path: str | None = None
    filename: str | None = None


class IndexContractWorkflow(Workflow):
    """
    Workflow to download and index a contract document into LlamaCloud Index.
    """

    @step()
    async def start_indexing(
        self, event: ContractFileEvent, ctx: Context[ContractIndexState]
    ) -> DownloadContractEvent:
        """Initialize the workflow with the file ID"""
        logger.info(f"Starting contract indexing for file {event.file_id}")
        async with ctx.store.edit_state() as state:
            state.file_id = event.file_id
        return DownloadContractEvent()

    @step()
    async def download_contract(
        self, event: DownloadContractEvent, ctx: Context[ContractIndexState]
    ) -> ContractDownloadedEvent:
        """Download the contract file from LlamaCloud storage"""
        state = await ctx.store.get_state()
        if state.file_id is None:
            raise ValueError("File ID is not set")

        file_metadata = await get_llama_cloud_client().files.get_file(id=state.file_id)
        file_url = await get_llama_cloud_client().files.read_file_content(state.file_id)

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
            state.file_path = file_path
            state.filename = filename

        return ContractDownloadedEvent()

    @step()
    async def index_contract(
        self, event: ContractDownloadedEvent, ctx: Context[ContractIndexState]
    ) -> StopEvent:
        """Index the contract document into LlamaCloud Index"""
        state = await ctx.store.get_state()
        if state.file_path is None or state.filename is None:
            raise ValueError("File path or filename is not set")

        logger.info(f"Indexing contract {state.filename}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Indexing contract: {state.filename}")
        )

        # Create a document with metadata
        file_content = Path(state.file_path).read_text(errors="ignore")
        document = Document(
            text=file_content,
            metadata={
                "filename": state.filename,
                "file_id": state.file_id,
                "document_type": "contract",
            },
        )

        # Get the contracts index and insert the document
        index = get_contracts_index()
        await index.ainsert(document)

        logger.info(f"Successfully indexed contract {state.filename}")
        ctx.write_event_to_stream(
            Status(
                level="info",
                message=f"Successfully indexed contract: {state.filename}",
            )
        )

        return StopEvent(result={"file_id": state.file_id, "filename": state.filename})


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
        result = await workflow.run(start_event=ContractFileEvent(file_id=file.id))
        print(f"Indexed contract: {result}")

    asyncio.run(main())
