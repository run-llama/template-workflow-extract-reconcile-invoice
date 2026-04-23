import asyncio
import json
import logging
from typing import Annotated, Any, Literal

from llama_cloud import AsyncLlamaCloud
from llama_cloud.types.beta.extracted_data import ExtractedData, InvalidExtractionData
from llama_index.core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent
from workflows.resource import Resource, ResourceConfig

from .clients import (
    agent_name,
    get_contracts_pipeline_id,
    get_llama_cloud_client,
    get_llm,
    project_id,
)
from .config import (
    EXTRACTED_DATA_COLLECTION,
    Discrepancy,
    ExtractConfig,
    InvoiceExtractionSchema,
    InvoiceWithReconciliation,
)


def _field_metadata_dict(job: Any) -> dict[str, Any]:
    """Pull document-level per-field metadata from a v2 extract job.

    ExtractedData.create() only accepts dict/list/ExtractedFieldMetadata values,
    so None entries for unextracted fields must be dropped.
    """
    if job.extract_metadata is None or job.extract_metadata.field_metadata is None:
        return {}
    doc_metadata = job.extract_metadata.field_metadata.document_metadata or {}
    return {k: v for k, v in doc_metadata.items() if v is not None}


logger = logging.getLogger(__name__)


class FileEvent(StartEvent):
    file_id: str
    file_hash: str | None = None


class Status(Event):
    level: Literal["info", "warning", "error"]
    message: str


class ExtractJobStartedEvent(Event):
    pass


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
    filename: str | None = None
    file_hash: str | None = None
    extract_job_id: str | None = None


class ProcessFileWorkflow(Workflow):
    """Extract structured data from a document and save it for review."""

    @step()
    async def start_extraction(
        self,
        event: FileEvent,
        ctx: Context[ExtractionState],
        llama_cloud_client: Annotated[
            AsyncLlamaCloud, Resource(get_llama_cloud_client)
        ],
        extract_config: Annotated[
            ExtractConfig,
            ResourceConfig(
                config_file="configs/config.json",
                path_selector="extract",
                label="Extraction Settings",
                description="Configuration for document extraction quality and features",
            ),
        ],
    ) -> ExtractJobStartedEvent:
        """Start extraction job for the document."""
        file_id = event.file_id
        logger.info(f"Running file {file_id}")

        try:
            file_metadata = None
            async for f in llama_cloud_client.files.list(
                file_ids=[file_id], project_id=project_id
            ):
                file_metadata = f
                break
            if file_metadata is None:
                raise ValueError(f"File {file_id} not found")
            filename = file_metadata.name
        except Exception as e:
            logger.error(f"Error fetching file metadata {file_id}: {e}", exc_info=True)
            ctx.write_event_to_stream(
                Status(
                    level="error",
                    message=f"Error fetching file metadata {file_id}: {e}",
                )
            )
            raise e

        logger.info(f"Extracting data from file {filename}")
        ctx.write_event_to_stream(
            Status(level="info", message=f"Extracting data from file {filename}")
        )

        if extract_config.configuration_id:
            extract_job = await llama_cloud_client.extract.create(
                file_input=file_id,
                configuration_id=extract_config.configuration_id,
                project_id=project_id,
            )
        else:
            extract_job = await llama_cloud_client.extract.create(
                file_input=file_id,
                configuration=extract_config.model_dump(
                    exclude={"configuration_id", "product_type"},
                    exclude_none=True,
                ),
                project_id=project_id,
            )

        file_hash = event.file_hash or file_metadata.external_file_id

        async with ctx.store.edit_state() as state:
            state.file_id = file_id
            state.filename = filename
            state.file_hash = file_hash
            state.extract_job_id = extract_job.id

        return ExtractJobStartedEvent()

    @step()
    async def complete_extraction(
        self,
        event: ExtractJobStartedEvent,
        ctx: Context[ExtractionState],
        llama_cloud_client: Annotated[
            AsyncLlamaCloud, Resource(get_llama_cloud_client)
        ],
        extract_config: Annotated[
            ExtractConfig,
            ResourceConfig(
                config_file="configs/config.json",
                path_selector="extract",
                label="Extraction Settings",
                description="Configuration for document extraction quality and features",
            ),
        ],
    ) -> ExtractedEvent | ExtractedInvalidEvent:
        """Wait for extraction to complete and validate results."""
        state = await ctx.store.get_state()
        if state.extract_job_id is None:
            raise ValueError("Job ID cannot be null when waiting for its completion")

        await llama_cloud_client.extract.wait_for_completion(
            state.extract_job_id,
            project_id=project_id,
        )
        job = await llama_cloud_client.extract.get(
            state.extract_job_id,
            expand=["extract_metadata"],
            project_id=project_id,
        )

        try:
            logger.info(
                f"Extracted data: {json.dumps(job.model_dump(mode='json'), indent=2, default=str)}"
            )

            if not job.extract_result:
                raise ValueError("No data extracted from invoice")

            invoice_data = InvoiceExtractionSchema.model_validate(job.extract_result)
            logger.info(f"Extracted invoice data: {invoice_data}")
            field_metadata = _field_metadata_dict(job)
            return ExtractedEvent(
                invoice_data=invoice_data, field_metadata=field_metadata
            )
        except InvalidExtractionData as e:
            logger.error(f"Error validating extracted data: {e}", exc_info=True)
            return ExtractedInvalidEvent(data=e.invalid_item)
        except Exception as e:
            logger.error(
                f"Error extracting data from file {state.filename}: {e}", exc_info=True
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
            client = get_llama_cloud_client()
            pipeline_id = await get_contracts_pipeline_id()
            retrieve_response = await client.pipelines.retrieve(
                pipeline_id=pipeline_id,
                query=query,
                dense_similarity_top_k=3,
            )
            retrieved_nodes = [n.node for n in retrieve_response.retrieval_nodes]

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

            # Get field metadata from extraction event
            field_metadata = event.field_metadata

            extracted_data = ExtractedData.create(
                data=reconciled_data,
                file_id=state.file_id,
                file_name=state.filename,
                file_hash=state.file_hash,
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

            field_metadata = event.field_metadata

            extracted_data = ExtractedData.create(
                data=reconciled_data,
                file_id=state.file_id,
                file_name=state.filename,
                file_hash=state.file_hash,
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
                f"Contract {i} (File: {(node.extra_info or {}).get('filename', 'Unknown')}):\n{node.text[:1000]}"
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
            matched_contract_id = (matched_node.extra_info or {}).get("file_id")
            matched_contract_name = (matched_node.extra_info or {}).get("filename")

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
        self,
        event: ReconciledEvent | ExtractedInvalidEvent,
        ctx: Context[ExtractionState],
        llama_cloud_client: Annotated[
            AsyncLlamaCloud, Resource(get_llama_cloud_client)
        ],
    ) -> StopEvent:
        """Records the extracted data to the agent data API"""
        extracted_data = event.data
        data_dict = extracted_data.model_dump()

        logger.info(f"Recorded extracted data for file {extracted_data.file_name}")
        ctx.write_event_to_stream(
            Status(
                level="info",
                message=f"Recorded extracted data for file {extracted_data.file_name}",
            )
        )

        if extracted_data.file_hash is not None:
            delete_result = await llama_cloud_client.beta.agent_data.delete_by_query(
                deployment_name=agent_name or "_public",
                collection=EXTRACTED_DATA_COLLECTION,
                filter={
                    "file_hash": {
                        "eq": extracted_data.file_hash,
                    },
                },
            )
            if delete_result.deleted_count > 0:
                logger.info(
                    f"Removed {delete_result.deleted_count} existing record(s) "
                    f"for file {extracted_data.file_name}"
                )
        item = await llama_cloud_client.beta.agent_data.create(
            data=data_dict,
            deployment_name=agent_name or "_public",
            collection=EXTRACTED_DATA_COLLECTION,
        )
        logger.info(
            f"Recorded extracted data for file {extracted_data.file_name or ''}"
        )
        ctx.write_event_to_stream(
            Status(
                level="info",
                message=f"Recorded extracted data for file {extracted_data.file_name or ''}",
            )
        )
        return StopEvent(result=item.id)


workflow = ProcessFileWorkflow(timeout=None)

if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        file = await get_llama_cloud_client().files.create(
            file=Path("test.pdf").open("rb"),
            purpose="extract",
        )
        await workflow.run(start_event=FileEvent(file_id=file.id))

    asyncio.run(main())
