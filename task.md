We are building an invoice extraction and reconciliation workflow app.

Invoices are parsed into structured data, then compared against indexed contracts to reconcile the invoice with its matching contract. Update the invoice record with contract-derived information and any discrepancies.

Using the UI, the user should be able to:
- add and index new contracts
- add and reconcile new invoices

This should be based off of the base extraction review template, which has 2 pages, one that displays a table of all extracted items (one row per invoice), and one for the item details (the extracted data for one invoice, e.g. total and line items). The items and details view should show the invoices.

Contracts can remain largely invisible in the UI for now, but there should be a minimal way to add them. These should be placed into a LlamaCloud index (which parses PDFs to plain text for retrieval).

The stored schema should extend the extracted invoice schema with reconciliation fields, such as links to the matched contract, a match confidence/score, and a structured list of discrepancies.

Matching should retrieve candidate contracts and then use an LLM, with context for both the candidate contracts and the invoice data, to make the final selection and provide rationale. When no contract matches, record that outcome clearly.

When matching and reconciling, consider:
- Whether there is any plausible matching contract versus only irrelevant results (e.g., vendor name, contract dates/ranges, contract or PO numbers).
- Whether payment terms are matching (at minimum).
- Optionally, check other obvious alignments if cheaply available (e.g., totals, vendor identifiers).

Represent reconciliation results in the details view with a clear, structured list of discrepancies (e.g., field, invoice_value, contract_value, optional note/severity).

The vast majority of this change should be kept in the python codebase. Some minor changes may need to be added to the UI, however do not do anything complex, just a button or small widget.
