# Decisions & Assumptions

This document outlines key ambiguities encountered during development, the choices made to resolve them, and questions that would require Product Management (PM) input in a real-world scenario.

## Ambiguities Resolved

### 1. Handling Invalid or Corrupted Rows in CSVs
- **Ambiguity:** If 3 rows out of a 10,000-row CSV are malformed (e.g., missing quantity, invalid date format), should we reject the entire file or ingest the valid rows?
- **Decision:** **Partial Ingestion.** We decided to process and ingest all valid rows while tracking the specific line numbers and error messages of the failed rows. 
- **Why:** In real-world ESG reporting, data is often dirty. Rejecting a massive file over a single typo causes immense user frustration. The `IngestionJob` model stores `records_processed` and `records_failed` with a JSON payload of errors, allowing the user to see exactly what failed and fix it later.

### 2. Idempotency & Duplicate Uploads
- **Ambiguity:** What happens if a user uploads the exact same utility bill CSV twice?
- **Decision:** **Rely on manual Analyst Review.** For the MVP, we did not implement strict cryptographic hashing of rows to block duplicates automatically.
- **Why:** Real-world data often contains rows that look identical but are actually separate transactions (e.g., two identical taxi receipts on the same day). Strict deduplication might falsely drop valid data. We rely on the `AnalystGrid` where an analyst can view "Pending" records and manually "Flag" duplicates.

### 3. Data Source Subsets Handled vs. Ignored
- **SAP Export:**
  - **Handled:** Standard material consumption columns (Material Code, Quantity, UOM, Plant).
  - **Ignored:** Complex financial data, currency conversions, and inter-company transfer codes, as they do not directly contribute to carbon footprint calculations.
- **Utility Bills:**
  - **Handled:** Total kWh, Billing Start/End Dates, Total Cost.
  - **Ignored:** Peak vs. Off-Peak usage splits, tariff codes, and tax breakdowns.
- **Travel Provider:**
  - **Handled:** Flight distances, travel classes (economy vs business).
  - **Ignored:** Hotel stays, car rentals, and multi-leg layover specifics (assuming the provider provides a pre-calculated total distance).

## Questions for the Product Manager (PM)
If this were a production sprint, I would ask the PM the following:
1. **Idempotency Threshold:** "Should we automatically block a file upload if a file with the exact same name and size was uploaded in the last 24 hours?"
2. **Failure Threshold:** "If a file has a 50% row failure rate, should we rollback the entire ingestion job instead of partially succeeding?"
3. **Audit Visibility:** "Do standard users need to see the audit trail of modifications made by Analysts, or is the audit trail strictly for system administrators and external auditors?"
