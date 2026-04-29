"""
Workflow for indexing contract documents into LlamaCloud Index for retrieval.

Each contract is parsed via LlamaParse and the resulting markdown is upserted
into the contracts pipeline. The reconcile step retrieves and feeds that
markdown to the matching LLM, so it has to be human-readable text, not raw
PDF bytes.
"""

import logging
from typing import Annotated, Literal

from llama_cloud import AsyncLlamaCloud
from llama_cloud.types.pipelines import CloudDocumentCreateParam
from pydantic import BaseModel
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent
from workflows.resource import Resource, ResourceConfig

from .clients import get_contracts_pipeline_id, get_llama_cloud_client, project_id
from .config import ParseConfig

logger = logging.getLogger(__name__)


class ContractFileEvent(StartEvent):
    """Event to start contract indexing with file IDs."""

    file_ids: list[str]


class IndexContractFileEvent(Event):
    """Per-file fan-out event."""

    file_id: str


class ContractParseStartedEvent(Event):
    """Event indicating a contract parse job has started."""

    file_id: str
    filename: str
    parse_job_id: str


class ContractIndexedEvent(Event):
    """Event indicating a single contract has been parsed and indexed."""

    file_id: str
    filename: str


class Status(Event):
    """Toast notification for the UI."""

    level: Literal["info", "warning", "error"]
    message: str


class ContractIndexState(BaseModel):
    total_files: int = 0


class IndexContractWorkflow(Workflow):
    """Parse contracts via LlamaParse and index their markdown for retrieval."""

    @step()
    async def start_indexing(
        self, event: ContractFileEvent, ctx: Context[ContractIndexState]
    ) -> IndexContractFileEvent | None:
        """Fan out to one parse-and-index task per file."""
        logger.info(f"Starting contract indexing for {len(event.file_ids)} files")
        async with ctx.store.edit_state() as state:
            state.total_files = len(event.file_ids)
        for file_id in event.file_ids:
            ctx.send_event(IndexContractFileEvent(file_id=file_id))
        return None

    @step(num_workers=4)
    async def start_contract_parse(
        self,
        event: IndexContractFileEvent,
        ctx: Context[ContractIndexState],
        llama_cloud_client: Annotated[
            AsyncLlamaCloud, Resource(get_llama_cloud_client)
        ],
        parse_config: Annotated[
            ParseConfig,
            ResourceConfig(
                config_file="configs/config.json",
                path_selector="parse",
                label="Contract Parsing Settings",
                description="Parse settings used when indexing contract documents",
            ),
        ],
    ) -> ContractParseStartedEvent:
        """Start a LlamaParse job for the contract."""
        file_id = event.file_id

        file_metadata = None
        async for f in llama_cloud_client.files.list(
            file_ids=[file_id], project_id=project_id
        ):
            file_metadata = f
            break
        if file_metadata is None:
            raise ValueError(f"File {file_id} not found")
        filename = file_metadata.name

        logger.info(f"Parsing contract {filename}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Parsing contract: {filename}")
        )

        parse_kwargs = parse_config.model_dump(
            exclude={"configuration_id", "product_type"},
            exclude_none=True,
        )
        parse_job = await llama_cloud_client.parsing.create(
            file_id=file_id,
            project_id=project_id,
            **parse_kwargs,
        )

        return ContractParseStartedEvent(
            file_id=file_id,
            filename=filename,
            parse_job_id=parse_job.id,
        )

    @step(num_workers=4)
    async def index_parsed_contract(
        self,
        event: ContractParseStartedEvent,
        ctx: Context[ContractIndexState],
        llama_cloud_client: Annotated[
            AsyncLlamaCloud, Resource(get_llama_cloud_client)
        ],
    ) -> ContractIndexedEvent:
        """Wait for LlamaParse completion and upsert the contract markdown."""
        file_id = event.file_id
        filename = event.filename

        await llama_cloud_client.parsing.wait_for_completion(
            event.parse_job_id,
            project_id=project_id,
        )
        parse_result = await llama_cloud_client.parsing.get(
            event.parse_job_id,
            expand=["markdown"],
            project_id=project_id,
        )
        pages = parse_result.markdown.pages if parse_result.markdown else []
        markdown = "\n\n".join(page.markdown for page in pages if page.success)
        if not markdown:
            raise ValueError(f"Parse produced no markdown for contract {filename}")

        logger.info(f"Indexing contract {filename}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Indexing contract: {filename}")
        )

        document = CloudDocumentCreateParam(
            text=markdown,
            metadata={
                "filename": filename,
                "file_id": file_id,
                "document_type": "contract",
            },
        )
        pipeline_id = await get_contracts_pipeline_id()
        await llama_cloud_client.pipelines.documents.upsert(
            pipeline_id=pipeline_id,
            body=[document],
        )

        return ContractIndexedEvent(file_id=file_id, filename=filename)

    @step()
    async def collect_results(
        self, event: ContractIndexedEvent, ctx: Context[ContractIndexState]
    ) -> StopEvent | None:
        """Wait for every contract to finish, then return aggregated results."""
        state = await ctx.store.get_state()
        events = ctx.collect_events(event, [ContractIndexedEvent] * state.total_files)
        if events is None:
            return None
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
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        file = await get_llama_cloud_client().files.create(
            file=Path("sample_contract.pdf").open("rb"),
            purpose="extract",
        )
        result = await workflow.run(start_event=ContractFileEvent(file_ids=[file.id]))
        print(f"Indexed contract: {result}")

    asyncio.run(main())
