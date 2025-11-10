import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

import httpx
from llama_cloud import ExtractRun
from llama_cloud_services.beta.agent_data import ExtractedData, InvalidExtractionData
from llama_cloud_services.extract import SourceText
from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .clients import (
    get_contracts_index,
    get_data_client,
    get_extract_agent,
    get_llama_cloud_client,
    get_llm,
)
from .config import Discrepancy, InvoiceExtractionSchema, InvoiceWithReconciliation

logger = logging.getLogger(__name__)


class FileEvent(StartEvent):
    file_id: str


class DownloadFileEvent(Event):
    pass


class FileDownloadedEvent(Event):
    pass


class Status(Event):
    level: Literal["info", "warning", "error"]
    message: str


class ExtractedEvent(Event):
    """Event when invoice data is successfully extracted"""

    invoice_data: InvoiceExtractionSchema
    field_metadata: dict[str, Any]


class ExtractedInvalidEvent(Event):
    """Event when extraction validation fails"""

    data: ExtractedData[dict[str, Any]]


class ReconciledEvent(Event):
    """Event when invoice is reconciled with contracts"""

    data: ExtractedData[InvoiceWithReconciliation]


class ExtractionState(BaseModel):
    file_id: str | None = None
    file_path: str | None = None
    filename: str | None = None


class ProcessFileWorkflow(Workflow):
    """
    Given a file path, this workflow will process a single file through the custom extraction logic.
    """

    @step()
    async def run_file(self, event: FileEvent, ctx: Context) -> DownloadFileEvent:
        logger.info(f"Running file {event.file_id}")
        async with ctx.store.edit_state() as state:
            state.file_id = event.file_id
        return DownloadFileEvent()

    @step()
    async def download_file(
        self, event: DownloadFileEvent, ctx: Context[ExtractionState]
    ) -> FileDownloadedEvent:
        """Download the file reference from the cloud storage"""
        state = await ctx.store.get_state()
        if state.file_id is None:
            raise ValueError("File ID is not set")
        try:
            file_metadata = await get_llama_cloud_client().files.get_file(
                id=state.file_id
            )
            file_url = await get_llama_cloud_client().files.read_file_content(
                state.file_id
            )

            temp_dir = tempfile.gettempdir()
            filename = file_metadata.name
            file_path = os.path.join(temp_dir, filename)
            client = httpx.AsyncClient()
            # Report progress to the UI
            logger.info(f"Downloading file {file_url.url} to {file_path}")

            async with client.stream("GET", file_url.url) as response:
                with open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
            logger.info(f"Downloaded file {file_url.url} to {file_path}")
            async with ctx.store.edit_state() as state:
                state.file_path = file_path
                state.filename = filename
            return FileDownloadedEvent()

        except Exception as e:
            logger.error(f"Error downloading file {state.file_id}: {e}", exc_info=True)
            ctx.write_event_to_stream(
                Status(
                    level="error",
                    message=f"Error downloading file {state.file_id}: {e}",
                )
            )
            raise e

    @step()
    async def process_file(
        self, event: FileDownloadedEvent, ctx: Context[ExtractionState]
    ) -> ExtractedEvent | ExtractedInvalidEvent:
        """Runs the extraction against the file"""
        state = await ctx.store.get_state()
        if state.file_path is None or state.filename is None:
            raise ValueError("File path or filename is not set")
        try:
            agent = get_extract_agent()
            source_text = SourceText(
                file=state.file_path,
                filename=state.filename,
            )
            logger.info(f"Extracting data from file {state.filename}")
            ctx.write_event_to_stream(
                Status(
                    level="info", message=f"Extracting data from file {state.filename}"
                )
            )
            extracted_result: ExtractRun = await agent.aextract(source_text)

            # Validate the extracted data
            if not extracted_result.data:
                raise ValueError("No data extracted from invoice")

            invoice_data = InvoiceExtractionSchema.model_validate(extracted_result.data)
            logger.info(f"Extracted invoice data: {invoice_data}")
            # Extract only the field_metadata we need, not the entire ExtractRun object
            field_metadata = extracted_result.extraction_metadata.get(
                "field_metadata", {}
            )
            return ExtractedEvent(
                invoice_data=invoice_data, field_metadata=field_metadata
            )
        except InvalidExtractionData as e:
            logger.error(f"Error validating extracted data: {e}", exc_info=True)
            return ExtractedInvalidEvent(data=e.invalid_item)
        except Exception as e:
            logger.error(
                f"Error extracting data from file {state.filename}: {e}",
                exc_info=True,
            )
            ctx.write_event_to_stream(
                Status(
                    level="error",
                    message=f"Error extracting data from file {state.filename}: {e}",
                )
            )
            raise e

    @step()
    async def reconcile_with_contract(
        self, event: ExtractedEvent, ctx: Context[ExtractionState]
    ) -> ReconciledEvent:
        """Reconcile the invoice with matching contracts using retrieval and LLM"""
        state = await ctx.store.get_state()
        invoice_data = event.invoice_data

        logger.info("Reconciling invoice with contracts")
        ctx.write_event_to_stream(
            Status(level="info", message="Matching invoice with contracts...")
        )

        try:
            # Build a query from invoice data for contract retrieval
            query_parts = []
            if invoice_data.vendor_name:
                query_parts.append(f"vendor: {invoice_data.vendor_name}")
            if invoice_data.purchase_order_number:
                query_parts.append(f"PO: {invoice_data.purchase_order_number}")
            if invoice_data.invoice_number:
                query_parts.append(f"invoice: {invoice_data.invoice_number}")

            query = " ".join(query_parts) if query_parts else "contract agreement"

            # Retrieve relevant contracts
            index = get_contracts_index()
            retriever = index.as_retriever(similarity_top_k=3)
            retrieved_nodes = await retriever.aretrieve(query)

            if not retrieved_nodes:
                logger.info("No contracts found in index")
                # No contracts available - create reconciliation data with no match
                reconciled_data = InvoiceWithReconciliation(
                    **invoice_data.model_dump(),
                    match_confidence="none",
                    match_rationale="No contracts found in the system",
                    discrepancies=[],
                )
            else:
                # Use LLM to match and reconcile
                reconciled_data = await self._match_and_reconcile(
                    invoice_data, retrieved_nodes
                )

            # Create ExtractedData with reconciliation information
            file_content = Path(state.file_path).read_bytes()
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Get field metadata from extraction event
            field_metadata = event.field_metadata

            extracted_data = ExtractedData.create(
                data=reconciled_data,
                file_id=state.file_id,
                file_name=state.filename,
                file_hash=file_hash,
                field_metadata=field_metadata,
            )

            logger.info(f"Reconciliation complete: {reconciled_data.match_confidence}")
            return ReconciledEvent(data=extracted_data)

        except Exception as e:
            logger.error(f"Error during reconciliation: {e}", exc_info=True)
            # If reconciliation fails, still create data without reconciliation
            reconciled_data = InvoiceWithReconciliation(
                **invoice_data.model_dump(),
                match_confidence="error",
                match_rationale=f"Error during reconciliation: {str(e)}",
                discrepancies=[],
            )

            file_content = Path(state.file_path).read_bytes()
            file_hash = hashlib.sha256(file_content).hexdigest()
            field_metadata = event.field_metadata

            extracted_data = ExtractedData.create(
                data=reconciled_data,
                file_id=state.file_id,
                file_name=state.filename,
                file_hash=file_hash,
                field_metadata=field_metadata,
            )

            return ReconciledEvent(data=extracted_data)

    async def _match_and_reconcile(
        self, invoice_data: InvoiceExtractionSchema, retrieved_nodes: list
    ) -> InvoiceWithReconciliation:
        """Use LLM to match invoice with contract and identify discrepancies"""

        # Define structured output schema for LLM
        class ContractMatchResult(BaseModel):
            """Result of matching invoice to contract"""

            is_match: bool = Field(
                description="Whether a plausible contract match was found"
            )
            matched_contract_index: int | None = Field(
                default=None,
                description="Index (0-based) of the matched contract in the provided list, or None if no match",
            )
            match_confidence: str = Field(
                description="Confidence level: 'high', 'medium', 'low', or 'none'"
            )
            match_rationale: str = Field(
                description="Explanation of why this contract was or was not matched"
            )
            contract_payment_terms: str | None = Field(
                default=None, description="Payment terms found in the matched contract"
            )
            discrepancies: list[Discrepancy] = Field(
                default_factory=list,
                description="List of discrepancies found between invoice and contract",
            )

        # Prepare contract context
        contracts_text = "\n\n".join(
            [
                f"Contract {i} (File: {node.metadata.get('filename', 'Unknown')}):\n{node.text[:1000]}"
                for i, node in enumerate(retrieved_nodes)
            ]
        )

        # Create prompt for matching
        prompt_template = PromptTemplate(
            """You are analyzing an invoice to match it with the correct contract and identify any discrepancies.

Invoice Details:
- Vendor: {vendor_name}
- Invoice Number: {invoice_number}
- Invoice Date: {invoice_date}
- PO Number: {po_number}
- Payment Terms: {payment_terms}
- Total: {total}

Retrieved Contracts:
{contracts_text}

Task:
1. Determine if any of the retrieved contracts plausibly matches this invoice based on:
   - Vendor name matching or similarity
   - PO number or invoice number references
   - Date ranges or validity periods
   - Any other relevant identifiers

2. If a match is found, identify discrepancies between invoice and contract, focusing on:
   - Payment terms differences (CRITICAL)
   - Total amount mismatches if contract specifies amounts
   - Vendor name discrepancies
   - Any other obvious conflicts

3. Assess match confidence:
   - 'high': Clear match with strong vendor/PO/identifier alignment
   - 'medium': Probable match with some uncertainty
   - 'low': Weak match, possibly relevant but uncertain
   - 'none': No plausible match found

Provide your analysis in the specified format."""
        )

        # Use LLM with structured prediction
        llm = get_llm()
        result = await llm.astructured_predict(
            ContractMatchResult,
            prompt_template,
            **{
                "vendor_name": invoice_data.vendor_name or "N/A",
                "invoice_number": invoice_data.invoice_number or "N/A",
                "invoice_date": invoice_data.invoice_date or "N/A",
                "po_number": invoice_data.purchase_order_number or "N/A",
                "payment_terms": invoice_data.payment_terms or "N/A",
                "total": invoice_data.total or "N/A",
                "contracts_text": contracts_text,
            },
        )

        # Build reconciled invoice data
        matched_contract_id = None
        matched_contract_name = None

        if result.is_match and result.matched_contract_index is not None:
            matched_node = retrieved_nodes[result.matched_contract_index]
            matched_contract_id = matched_node.metadata.get("file_id")
            matched_contract_name = matched_node.metadata.get("filename")

        return InvoiceWithReconciliation(
            **invoice_data.model_dump(),
            matched_contract_id=matched_contract_id,
            matched_contract_name=matched_contract_name,
            match_confidence=result.match_confidence,
            match_rationale=result.match_rationale,
            discrepancies=result.discrepancies,
        )

    @step()
    async def record_extracted_data(
        self, event: ReconciledEvent | ExtractedInvalidEvent, ctx: Context
    ) -> StopEvent:
        """Records the extracted data to the agent data API"""
        try:
            logger.info(f"Recorded extracted data for file {event.data.file_name}")
            ctx.write_event_to_stream(
                Status(
                    level="info",
                    message=f"Recorded extracted data for file {event.data.file_name}",
                )
            )
            # remove past data when reprocessing the same file
            if event.data.file_hash:
                await get_data_client().delete(
                    filter={
                        "file_hash": {
                            "eq": event.data.file_hash,
                        },
                    },
                )
                logger.info(
                    f"Removing past data for file {event.data.file_name} with hash {event.data.file_hash}"
                )
            # finally, save the new data
            item_id = await get_data_client().create_item(event.data)
            return StopEvent(
                result=item_id.id,
            )
        except Exception as e:
            logger.error(
                f"Error recording extracted data for file {event.data.file_name}: {e}",
                exc_info=True,
            )
            ctx.write_event_to_stream(
                Status(
                    level="error",
                    message=f"Error recording extracted data for file {event.data.file_name}: {e}",
                )
            )
            raise e


workflow = ProcessFileWorkflow(timeout=None)

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        file = await get_llama_cloud_client().files.upload_file(
            upload_file=Path("test.pdf").open("rb")
        )
        await workflow.run(start_event=FileEvent(file_id=file.id))

    asyncio.run(main())
