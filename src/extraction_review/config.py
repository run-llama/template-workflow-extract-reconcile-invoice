"""
For simple configuration of the extraction review application, just customize this file.

If you need more control, feel free to edit the rest of the application
"""

from __future__ import annotations

import os

from llama_cloud import ExtractConfig
from llama_cloud_services.extract import ExtractMode
from pydantic import BaseModel, Field

# The name of the extraction agent to use. Prefers the name of this deployment when deployed to isolate environments.
# Note that the application will create a new agent from the below ExtractionSchema if the extraction agent does not yet exist.
EXTRACTION_AGENT_NAME: str = (
    os.getenv("LLAMA_DEPLOY_DEPLOYMENT_NAME") or "invoice-reconciliation"
)
# The name of the collection to use for storing extracted data. This will be qualified by the agent name.
# When developing locally, this will use the _public collection (shared within the project), otherwise agent
# data is isolated to each agent
EXTRACTED_DATA_COLLECTION: str = "invoices"

# The name of the LlamaCloud index for storing contracts
CONTRACTS_INDEX_NAME: str = "contracts"


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


EXTRACT_CONFIG = ExtractConfig(
    extraction_mode=ExtractMode.PREMIUM,
    system_prompt=None,
    # advanced. Only compatible with Premium mode.
    use_reasoning=False,
    cite_sources=False,
    confidence_scores=True,
)
