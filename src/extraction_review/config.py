"""
Configuration for the extraction review application.

Configuration is loaded from configs/config.json via ResourceConfig.
The unified config contains both extraction settings and the JSON schema.

Extraction can run in two modes, controlled by the "extraction_agent_id" field
in configs/config.json:

  - Local (default): extraction_agent_id is null. Uses the json_schema and
    settings defined in config.json directly via extraction.run().

  - Remote agent: extraction_agent_id is set to a LlamaCloud extraction agent
    ID. Uses extraction.jobs.extract(extraction_agent_id=...) which delegates
    schema and settings to the remote agent. The local json_schema and settings
    in config.json are ignored — both extraction and the metadata workflow fetch
    the schema directly from the remote agent.
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from .json_util import get_extraction_schema as get_extraction_schema

logger = logging.getLogger(__name__)


# The name of the collection to use for storing extracted data.
EXTRACTED_DATA_COLLECTION: str = "invoices"

# The name of the LlamaCloud index for storing contracts
CONTRACTS_INDEX_NAME: str = "contracts"


class ExtractSettings(BaseModel):
    extraction_mode: Literal["FAST", "PREMIUM", "MULTIMODAL"]
    system_prompt: str | None = None
    citation_bbox: bool = False
    use_reasoning: bool = False
    cite_sources: bool = False
    confidence_scores: bool = False


class ExtractConfig(BaseModel):
    json_schema: dict[str, Any]
    settings: ExtractSettings
    # Set this to a LlamaCloud extraction agent ID to use a remote agent's
    # schema and settings instead of the local json_schema/settings above.
    # When set, extraction uses extraction.jobs.extract(extraction_agent_id=...)
    # and the local settings are ignored for extraction.
    extraction_agent_id: str | None = None


class JsonSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = {}
    required: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


# Invoice extraction schema - extracted from invoice documents
class LineItem(BaseModel):
    description: str | None = Field(
        default=None, description="Description of the line item"
    )
    quantity: float | None = Field(default=None, description="Quantity of the item")
    unit_price: float | None = Field(
        default=None, description="Price per unit of the item"
    )
    total: float | None = Field(
        default=None, description="Total price for this line item"
    )


class InvoiceExtractionSchema(BaseModel):
    """Schema for extracting invoice data"""

    invoice_number: str | None = Field(
        default=None, description="Invoice number or identifier"
    )
    invoice_date: str | None = Field(
        default=None, description="Date of the invoice (YYYY-MM-DD format if possible)"
    )
    vendor_name: str | None = Field(
        default=None, description="Name of the vendor or supplier"
    )
    vendor_address: str | None = Field(
        default=None, description="Address of the vendor"
    )
    purchase_order_number: str | None = Field(
        default=None, description="Purchase order (PO) number if present"
    )
    payment_terms: str | None = Field(
        default=None,
        description="Payment terms (e.g., Net 30, Net 60, Due on receipt)",
    )
    line_items: list[LineItem] | None = Field(
        default=None, description="List of line items on the invoice"
    )
    subtotal: float | None = Field(
        default=None, description="Subtotal before tax and other charges"
    )
    tax: float | None = Field(default=None, description="Tax amount")
    total: float | None = Field(
        default=None, description="Total amount due on the invoice"
    )


# For backward compatibility
ExtractionSchema = InvoiceExtractionSchema


# Reconciliation schema - extends invoice data with contract matching and discrepancy information
class Discrepancy(BaseModel):
    """Represents a single discrepancy between invoice and contract"""

    field: str = Field(description="Field name where discrepancy was found")
    invoice_value: str | None = Field(
        default=None, description="Value from the invoice"
    )
    contract_value: str | None = Field(
        default=None, description="Expected value from the contract"
    )
    severity: str | None = Field(
        default=None,
        description="Severity of the discrepancy (e.g., 'high', 'medium', 'low')",
    )
    note: str | None = Field(
        default=None, description="Additional notes about the discrepancy"
    )


class InvoiceWithReconciliation(InvoiceExtractionSchema):
    """Invoice data with reconciliation information"""

    matched_contract_id: str | None = Field(
        default=None, description="ID of the matched contract file in LlamaCloud"
    )
    matched_contract_name: str | None = Field(
        default=None, description="Name of the matched contract file"
    )
    match_confidence: str | None = Field(
        default=None,
        description="Confidence level of the match (e.g., 'high', 'medium', 'low', 'none')",
    )
    match_rationale: str | None = Field(
        default=None, description="Explanation of why this contract was matched"
    )
    discrepancies: list[Discrepancy] | None = Field(
        default=None,
        description="List of discrepancies found between invoice and contract",
    )
