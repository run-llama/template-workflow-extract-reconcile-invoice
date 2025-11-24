# Invoice Extraction and Contract Reconciliation

This template provides a LlamaAgents application for extracting structured data from invoices
and reconciling it against contract documents using LlamaExtract, LlamaCloud Index, and Agent Data.
It helps finance and operations teams validate that incoming invoices comply with agreed contract terms
by automatically detecting mismatches in payment terms, totals, and other key fields.

# Running the application

This is a starter for LlamaAgents. See the
[LlamaAgents (llamactl) getting started guide](https://developers.llamaindex.ai/python/llamaagents/llamactl/getting-started/)
for context on local development and deployment.

To run the application locally, clone this repo, install [`uv`](https://docs.astral.sh/uv/) and run `uvx llamactl serve`.

This application can also be deployed directly to [LlamaCloud](https://cloud.llamaindex.ai) via the UI,
or with `llamactl deployment create`.

## Features

- **Invoice data extraction**: Uses a Pydantic `InvoiceExtractionSchema` to extract key invoice fields
  (vendor, dates, PO number, line items, subtotals, tax, totals, and more) via a LlamaExtract agent.
- **Contract indexing and retrieval**: Includes an `index-contract` workflow that downloads contract files
  from LlamaCloud and indexes them into a dedicated `contracts` LlamaCloud Index for retrieval.
- **Automated reconciliation**: Matches invoices to the most relevant contracts using retrieval plus an LLM,
  then produces an `InvoiceWithReconciliation` record with match confidence, rationale, and structured discrepancies.
- **Agent Data storage**: Stores reconciled invoice records in LlamaCloud Agent Data, deduplicated by file hash,
  so that re-processing the same file replaces prior results instead of duplicating them.
- **UI integration**: A web UI lets you upload invoices and contracts, monitor workflow progress,
  and review or edit extracted and reconciled data.

## Example Documents

You can find sample invoice and contract PDF files to test the application with
[here](https://github.com/run-llama/llama-datasets/tree/main/llama_agents/invoice-contracts).

## Configuration

All main configuration is in `src/extraction_review/config.py`.

## How It Works

The application uses a multi-step workflow powered by LlamaIndex:

1. **File Upload**: Users upload invoice or contract documents through the UI, which are stored in LlamaCloud.
2. **Index Contracts**: Contract files are processed by the `index-contract` workflow and indexed into
   the `contracts` LlamaCloud Index.
3. **Download Invoice**: The `process-file` workflow downloads the selected invoice file from LlamaCloud storage.
4. **Extraction**: A LlamaExtract agent runs against the invoice using `InvoiceExtractionSchema`, returning
   structured invoice data plus field-level metadata.
5. **Contract Retrieval**: The workflow queries the contracts index with a query built from invoice fields
   (vendor, PO number, invoice number, etc.) and retrieves the most relevant contracts.
6. **Reconciliation**: An LLM compares the invoice to the retrieved contracts, selects the best match,
   and produces an `InvoiceWithReconciliation` object with match confidence, rationale, and discrepancy list.
7. **Storage**: The reconciled invoice data is wrapped in an `ExtractedData` record (including file hash)
   and stored in Agent Data, replacing any previous records for the same file hash.
8. **Review**: The UI displays the stored data for review, editing, and export.

### Workflows

The application includes three main workflows:

- **`process-file`** (`src/extraction_review/process_file.py`): Main workflow for processing invoices
  end-to-end (download → extract → reconcile → store).
- **`index-contract`** (`src/extraction_review/index_contract.py`): Workflow for downloading and indexing
  contract documents into a LlamaCloud Index for later retrieval during reconciliation.
- **`metadata`** (`src/extraction_review/metadata_workflow.py`): Exposes configuration metadata to the UI,
  returning the JSON Schema for `InvoiceWithReconciliation` and the Agent Data collection name.

## Linting and type checking

Python and javascript packages contain helpful scripts to lint, format, and type check the code.

To check and fix python code:

```bash
uv run hatch run lint
uv run hatch run typecheck
uv run hatch run test
# run all at once
uv run hatch run all-fix
```

To check and fix javascript code, within the `ui` directory:

```bash
pnpm run lint
pnpm run typecheck
pnpm run test
# run all at once
pnpm run all-fix
```
