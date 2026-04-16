"""
Configuration for the extraction review application.

Configuration is loaded from configs/config.json via ResourceConfig.
Each top-level key in config.json maps to an SDK product-configuration type:
the discriminated union members returned by `client.configurations.retrieve`.
Each template-side subclass adds an optional `configuration_id` so a key
can either carry an inline snapshot OR point at a saved platform config.
"""

import logging
import os

from llama_cloud.types.beta.split_category import SplitCategory
from llama_cloud.types.classify_v2_parameters import ClassifyV2Parameters, Rule
from llama_cloud.types.extract_v2_parameters import ExtractV2Parameters
from llama_cloud.types.parse_v2_parameters import ParseV2Parameters
from llama_cloud.types.split_v1_parameters import SplitV1Parameters
from pydantic import BaseModel, Field

from .json_util import get_extraction_schema as get_extraction_schema

logger = logging.getLogger(__name__)


# The name of the collection to use for storing extracted data.
EXTRACTED_DATA_COLLECTION: str = "invoices"

# The name of the LlamaCloud index for storing contracts
# Override with CONTRACTS_INDEX_NAME env var (useful when running against a
# shared staging project where the default name may collide with other data).
CONTRACTS_INDEX_NAME: str = os.getenv("CONTRACTS_INDEX_NAME", "contracts")


class ExtractConfig(ExtractV2Parameters):
    """Extract product configuration.

    Inherits the SDK `ExtractV2Parameters` shape. Set `configuration_id`
    to a saved LlamaCloud configuration id (cfg-...) to pull parameters
    from the platform instead of using the local values.
    """

    configuration_id: str | None = None


class ClassifyConfig(ClassifyV2Parameters):
    """Classify product configuration (extension slot, unused by the workflow)."""

    rules: list[Rule] = []
    configuration_id: str | None = None


class ParseConfig(ParseV2Parameters):
    """Parse product configuration (extension slot)."""

    configuration_id: str | None = None


class SplitConfig(SplitV1Parameters):
    """Split product configuration (extension slot)."""

    categories: list[SplitCategory] = []
    configuration_id: str | None = None


class Config(BaseModel):
    """Root configuration model for configs/config.json."""

    extract: ExtractConfig
    classify: ClassifyConfig
    parse: ParseConfig
    split: SplitConfig


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
