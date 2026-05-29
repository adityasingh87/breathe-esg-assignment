# Data Model Architecture

The data model was designed to handle the complexity of heterogeneous ESG data sources while maintaining strict data integrity, auditability, and multi-tenancy. 

## Core Principles & Requirements Addressed

### 1. Multi-Tenancy
- **Model:** `Tenant`
- **Why:** B2B SaaS platforms must strictly isolate customer data. Every core model (`IngestionJob`, `EmissionRecord`) has a foreign key to `Tenant`. This ensures that all database queries are naturally scoped to the active tenant, preventing cross-contamination of sensitive emissions data.

### 2. Scope 1, 2, and 3 Categorization
- **Models:** `EmissionFactor`, `EmissionRecord`
- **Why:** The Greenhouse Gas Protocol requires strict categorization. 
  - **Scope 1 (Direct):** Fuel combustion (e.g., Company-owned vehicles, generators).
  - **Scope 2 (Indirect):** Purchased electricity.
  - **Scope 3 (Value Chain):** Business travel.
- **Implementation:** The `EmissionFactor` model defines the `source_type` (electricity, fuel, travel_air) and `category`. When a parser processes a row, it tags the `EmissionRecord` with the appropriate scope based on this categorization, allowing the Analytics Dashboard to effortlessly aggregate emissions by Scope.

### 3. Source-of-Truth Tracking
- **Models:** `IngestionJob`, `EmissionRecord`
- **Why:** ESG auditors require proof of where a number came from.
- **Implementation:** 
  - Every time a user uploads a file, an `IngestionJob` is created (tracking filename, timestamp, user, and status).
  - Every resulting `EmissionRecord` contains a foreign key to `job_id` and stores the exact `raw_data` (JSON) from the original row. 
  - **Traceability:** If an auditor questions an emission value, they can trace it back to the exact row in the specific CSV file uploaded by a specific user at a specific time.

### 4. Unit Normalization
- **Model:** `UnitLookup`
- **Why:** Data arrives in disparate units (gallons, liters, miles, kilometers, MWh, kWh).
- **Implementation:** The `UnitLookup` model maintains conversion factors to a standard baseline unit (e.g., miles -> kilometers, MWh -> kWh). During ingestion, the parser queries this table. If a conversion factor exists, it multiplies the raw quantity by the factor and records the normalized `quantity` and `unit`. This guarantees that `EmissionRecord` always stores mathematically comparable values.

### 5. Audit Trail & Edits
- **Implementation:** 
  - **State Machine:** `EmissionRecord` uses a `review_status` field (`pending`, `approved`, `flagged`).
  - **Audit Logging:** We track `created_at` and `updated_at`. To track edits, we utilize a `history_log` JSON field on the `EmissionRecord` (or equivalent audit history mechanisms). If an analyst modifies a parsed value (e.g., fixing a typo), the old value, new value, timestamp, and analyst's user ID are appended to the log. This creates a tamper-evident timeline of human interventions.

## Entity Relationship Summary
* `Tenant` (1) -> (N) `User`
* `Tenant` (1) -> (N) `IngestionJob`
* `IngestionJob` (1) -> (N) `EmissionRecord`
* `UnitLookup` (Static Reference)
* `EmissionFactor` (Static Reference)
