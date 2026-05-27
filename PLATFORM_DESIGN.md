# Breathe ESG — Platform Design

> Covers: Platform Scope · Database Design · API Design

---

## Table of Contents

1. [Platform Scope](#1-platform-scope)
2. [Ingestion Sources & Justifications](#2-ingestion-sources--justifications)
3. [Database Design](#3-database-design)
4. [API Design](#4-api-design)
5. [Key Design Decisions](#5-key-design-decisions)

---

## 1. Platform Scope

### Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Django 5 + Django REST Framework | Multi-tenancy, ORM, admin, robust auth |
| Task queue | Celery + Redis | Async file processing without blocking HTTP |
| Database | PostgreSQL | JSONB for raw payloads, strong FK support, row-level security |
| Frontend | React + Vite | SPA analyst dashboard, fast iteration |
| Auth | JWT (SimpleJWT) | Stateless, works cleanly with React |
| Deployment | Render / Railway | Managed Postgres + Redis, zero-ops |

### Bounded scope (what this prototype handles)

- Three ingestion sources: SAP flat file, utility portal CSV, corporate travel CSV
- One tenant per deployment (multi-tenancy schema is in place; tenant switcher UI is not)
- Analyst review workflow: pending → approved → locked
- Emission factor application at ingestion time (factors stored in DB, not hardcoded)
- Audit trail on every edit and status change
- No real-time SAP OData connection, no PDF bill parsing, no live Concur API pull

---

## 2. Ingestion Sources & Justifications

### 2.1 SAP — Fuel & Procurement

**Chosen format:** Flat file CSV (SE16N / SM35 export)

**Why:** SAP OData requires live system access and credentials the client must provision. IDocs in their raw EDI format require a middleware parser. The SE16N flat CSV export is the most common "get data out of SAP without IT involvement" path that a sustainability lead actually uses. It handles MARA/EKKO/EKPO table exports for procurement and MSEG for fuel consumption movements.

**What we handle:**
- Plant codes → country/region via a static lookup table (bundled as a fixture)
- Date formats: YYYYMMDD (SAP default) and DD.MM.YYYY (German locale)
- Units: L, m³, kg, t — normalised to kg CO₂e via emission factors
- German column headers: mapped via a header alias dict at parse time

**Scope assignment:** Scope 1 (direct fuel combustion), Scope 2 (purchased energy via procurement lines) depending on material group code.

---

### 2.2 Utility — Electricity

**Chosen format:** Portal CSV export (e.g. BESCOM, Con Edison download)

**Why:** PDF bill parsing is brittle — layout changes break extractors. Utility APIs exist (Green Button, ESPI) but require OAuth registration with each utility individually, impractical for a prototype. Portal CSVs are the de facto standard: every major utility offers a "Download usage data" button that produces a structured file.

**What we handle:**
- Multi-meter files (multiple `meter_id` rows in one CSV)
- Non-calendar billing periods (e.g. 18-Mar to 21-Apr) — stored as `activity_date` = period start, with `period_end` in raw payload
- Units: kWh, MWh — normalised to kWh, then to kg CO₂e via regional grid factor
- Tariff structure ignored (only consumption quantity matters for emissions)

**Scope assignment:** Scope 2 (purchased electricity).

---

### 2.3 Corporate Travel — Flights, Hotels, Ground Transport

**Chosen format:** CSV export from Concur Expense / Navan TRX report

**Why:** Concur's live API requires OAuth + admin provisioning. The standard Concur "Transaction Export" report is a flat CSV that sustainability teams already pull monthly. Navan has an equivalent. This is the realistic shape for an enterprise client's first data handoff.

**What we handle:**
- Flights: origin/destination IATA codes → great-circle distance via static IATA distance table; seat class multiplier applied (economy 1×, business 1.5×, first 2×)
- Hotels: room-nights × regional hotel emission factor
- Ground transport: taxi/rail/rental car by distance or cost proxy
- Rows with unresolvable airport pairs flagged as errors (not silently dropped)

**Scope assignment:** Scope 3, Category 6 (business travel).

---

## 3. Database Design

### Entity Relationship Overview

```
TENANT ──< INGESTION_JOB ──< EMISSION_RECORD ──< AUDIT_LOG
                    │
                    └──< INGESTION_ERROR

EMISSION_RECORD >── UNIT_LOOKUP
EMISSION_RECORD >── EMISSION_FACTOR
```

---

### 3.1 `tenant`

Represents a client organisation. All data is scoped to a tenant.

```sql
CREATE TABLE tenant (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,       -- used in URLs
    timezone    VARCHAR(50)  NOT NULL DEFAULT 'UTC',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

| Field | Purpose |
|---|---|
| `slug` | URL-safe identifier, e.g. `acme-corp` |
| `timezone` | For display of activity dates in the analyst dashboard |

---

### 3.2 `ingestion_job`

One row per file upload. Tracks the lifecycle of an ingestion run.

```sql
CREATE TABLE ingestion_job (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenant(id),
    source_type     VARCHAR(20) NOT NULL,   -- 'sap' | 'utility' | 'travel'
    file_name       VARCHAR(500) NOT NULL,
    file_hash       VARCHAR(64),            -- SHA-256, for dedup detection
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                                            -- pending | processing | done | failed
    total_rows      INTEGER,
    parsed_rows     INTEGER,
    error_rows      INTEGER,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_by     VARCHAR(255) NOT NULL   -- email of uploader
);

CREATE INDEX ON ingestion_job(tenant_id, source_type);
CREATE INDEX ON ingestion_job(tenant_id, status);
```

**Status machine:** `pending → processing → done | failed`

The `file_hash` field lets the backend warn if the same file is uploaded twice — it does not hard-block re-upload, because a re-run after a bug fix is a valid workflow.

---

### 3.3 `emission_record`

The central table. One row per normalised activity data point.

```sql
CREATE TABLE emission_record (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenant(id),
    job_id                  UUID NOT NULL REFERENCES ingestion_job(id),

    -- Scope & classification
    scope                   VARCHAR(10) NOT NULL,       -- 'scope_1' | 'scope_2' | 'scope_3'
    category                VARCHAR(100) NOT NULL,      -- e.g. 'business_travel_air'
    source_type             VARCHAR(20) NOT NULL,       -- 'sap' | 'utility' | 'travel'

    -- Activity data (as received, before normalisation)
    activity_date           DATE NOT NULL,
    raw_quantity            NUMERIC(18, 6) NOT NULL,
    raw_unit                VARCHAR(30) NOT NULL,       -- e.g. 'litres', 'kWh', 'km'
    description             TEXT,

    -- Normalised output
    normalized_quantity_kg  NUMERIC(18, 6),             -- kg CO₂e
    unit_lookup_id          UUID REFERENCES unit_lookup(id),
    emission_factor_id      UUID REFERENCES emission_factor(id),

    -- Source of truth tracking
    raw_payload             JSONB NOT NULL,             -- verbatim source row
    source_row_number       INTEGER,                    -- row number in original file

    -- Review workflow
    review_status           VARCHAR(20) NOT NULL DEFAULT 'pending',
                                                        -- pending | approved | flagged | locked
    flag_reason             TEXT,
    reviewed_by             VARCHAR(255),
    reviewed_at             TIMESTAMPTZ,
    locked_by               VARCHAR(255),
    locked_at               TIMESTAMPTZ,
    is_edited               BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON emission_record(tenant_id, review_status);
CREATE INDEX ON emission_record(tenant_id, scope, activity_date);
CREATE INDEX ON emission_record(job_id);
CREATE INDEX ON emission_record USING GIN (raw_payload);  -- for payload search
```

**Review status machine:**

```
pending ──→ approved ──→ locked
   │              │
   └──→ flagged ──┘
```

Once `locked`, no further edits are permitted at the API layer. The `raw_payload` JSONB column stores the original source row verbatim — if normalisation logic has a bug, records can be re-processed without re-uploading the file.

---

### 3.4 `ingestion_error`

Per-row errors from a failed or partially failed ingestion job.

```sql
CREATE TABLE ingestion_error (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES ingestion_job(id),
    row_number      INTEGER NOT NULL,
    raw_row         TEXT,                   -- original CSV row as string
    error_code      VARCHAR(50) NOT NULL,   -- e.g. 'MISSING_DATE', 'UNKNOWN_UNIT'
    error_message   TEXT NOT NULL
);

CREATE INDEX ON ingestion_error(job_id);
```

**Error codes used:**

| Code | Meaning |
|---|---|
| `MISSING_DATE` | Activity date column empty or unparseable |
| `UNKNOWN_UNIT` | Unit not found in `unit_lookup` |
| `UNKNOWN_PLANT` | SAP plant code not in reference table |
| `UNKNOWN_AIRPORT_PAIR` | IATA origin/destination pair not in distance table |
| `NEGATIVE_QUANTITY` | Quantity is zero or negative (suspicious) |
| `DUPLICATE_METER_PERIOD` | Utility meter + billing period already ingested in this tenant |

---

### 3.5 `audit_log`

Append-only. One row per change to an emission record.

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id       UUID NOT NULL REFERENCES emission_record(id),
    changed_by      VARCHAR(255) NOT NULL,
    action          VARCHAR(30) NOT NULL,   -- 'created' | 'edited' | 'approved' | 'flagged' | 'locked'
    before_state    JSONB,
    after_state     JSONB NOT NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON audit_log(record_id, changed_at);
```

`before_state` is NULL on the `created` action. The `before_state`/`after_state` diff is stored as full snapshots (not deltas) to make auditor review straightforward — no need to replay a chain of patches.

---

### 3.6 `unit_lookup`

Reference table for unit normalisation.

```sql
CREATE TABLE unit_lookup (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_unit       VARCHAR(30) UNIQUE NOT NULL,    -- e.g. 'kWh', 'litres', 'MWh'
    factor_to_base  NUMERIC(18, 10) NOT NULL,       -- multiplier to base unit (kWh for energy, km for distance, kg for mass)
    base_unit       VARCHAR(20) NOT NULL,
    notes           TEXT
);
```

Units are first converted to a base unit (kWh, km, kg), then to kg CO₂e via an emission factor. Two-step normalisation keeps the lookup table manageable.

---

### 3.7 `emission_factor`

Stores the emission factors used at calculation time. FK'd from `emission_record` so auditors can see exactly which factor was applied to each row.

```sql
CREATE TABLE emission_factor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     VARCHAR(20) NOT NULL,       -- 'electricity' | 'fuel' | 'travel_air' | ...
    category        VARCHAR(100) NOT NULL,
    region          VARCHAR(100),               -- 'IN', 'GB', 'US-CA', etc.
    kg_co2e_per_unit NUMERIC(18, 10) NOT NULL,
    unit            VARCHAR(30) NOT NULL,       -- the base unit this factor applies to
    year            INTEGER NOT NULL,
    source_ref      VARCHAR(255),               -- e.g. 'DEFRA 2023', 'IEA 2023'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON emission_factor(source_type, category, region, year);
```

---

## 4. API Design

### Base URL

```
/api/v1/
```

All endpoints require a valid JWT in the `Authorization: Bearer <token>` header, except the auth endpoints. All responses are JSON. All list endpoints are paginated (`?page=1&page_size=50`).

---

### 4.1 Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/token/` | Obtain JWT. Body: `{"username": "...", "password": "..."}`. Returns `access` + `refresh`. |
| `POST` | `/api/auth/token/refresh/` | Refresh access token. Body: `{"refresh": "..."}`. |

---

### 4.2 Ingestion — SAP (Fuel & Procurement)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/ingest/sap/` | Upload SAP flat file. `multipart/form-data`, field `file`. Returns `{"job_id": "..."}`. Async via Celery. |
| `GET` | `/api/v1/ingest/sap/{job_id}/` | Poll job status. Returns `status`, `total_rows`, `parsed_rows`, `error_rows`. |

**POST `/api/v1/ingest/sap/` — response:**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "file_name": "SAP_MSEG_export_2024_Q1.csv"
}
```

---

### 4.3 Ingestion — Utility (Electricity)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/ingest/utility/` | Upload utility portal CSV. Handles multi-meter, non-calendar billing periods. |
| `GET` | `/api/v1/ingest/utility/{job_id}/` | Job status + validation errors (unit mismatches, duplicate meter periods). |

---

### 4.4 Ingestion — Corporate Travel

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/ingest/travel/` | Upload Concur/Navan CSV export. Resolves IATA pairs → distance. Flags unresolvable pairs as errors. |
| `GET` | `/api/v1/ingest/travel/{job_id}/` | Job status. Lists rows flagged for missing distance. |

---

### 4.5 Ingestion Jobs (all sources)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/jobs/` | List all ingestion jobs for tenant. Query params: `source_type`, `status`, `date_from`, `date_to`. |
| `GET` | `/api/v1/jobs/{id}/errors/` | Paginated per-row error list for a job. Includes `row_number`, `raw_row`, `error_code`, `error_message`. |

**GET `/api/v1/jobs/` — response:**
```json
{
  "count": 12,
  "results": [
    {
      "id": "uuid",
      "source_type": "sap",
      "file_name": "SAP_MSEG_Q1.csv",
      "status": "done",
      "total_rows": 840,
      "parsed_rows": 831,
      "error_rows": 9,
      "ingested_at": "2024-04-01T10:22:00Z",
      "ingested_by": "analyst@acme.com"
    }
  ]
}
```

---

### 4.6 Emission Records — Review Dashboard

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/records/` | List records. Filters: `scope`, `source_type`, `review_status`, `date_from`, `date_to`, `job_id`, `is_edited`. |
| `GET` | `/api/v1/records/{id}/` | Single record with full raw payload, normalised values, and current review state. |
| `PATCH` | `/api/v1/records/{id}/` | Analyst correction. Editable fields: `raw_quantity`, `raw_unit`, `activity_date`, `description`. Triggers re-normalisation. Writes audit log entry. Sets `is_edited = true`. |
| `POST` | `/api/v1/records/{id}/approve/` | Approve record. Sets `review_status = approved`, records `reviewed_by` + `reviewed_at`. |
| `POST` | `/api/v1/records/{id}/flag/` | Flag as suspicious. Body: `{"reason": "..."}`. Sets `review_status = flagged`. |
| `POST` | `/api/v1/records/bulk-approve/` | Approve multiple records. Body: `{"ids": ["uuid", ...], "comment": "..."}`. |
| `POST` | `/api/v1/records/{id}/lock/` | Lock approved record for audit. Immutable after this — further edits return `403`. |

**GET `/api/v1/records/` — response:**
```json
{
  "count": 831,
  "results": [
    {
      "id": "uuid",
      "scope": "scope_1",
      "category": "fuel_combustion",
      "source_type": "sap",
      "activity_date": "2024-01-15",
      "raw_quantity": 1200.0,
      "raw_unit": "litres",
      "normalized_quantity_kg": 3168.0,
      "description": "Plant DE01 — diesel, Jan 2024",
      "review_status": "pending",
      "is_edited": false,
      "job_id": "uuid"
    }
  ]
}
```

**PATCH `/api/v1/records/{id}/` — request:**
```json
{
  "raw_quantity": 1100.0,
  "raw_unit": "litres",
  "description": "Corrected — meter reading error"
}
```

**POST `/api/v1/records/{id}/flag/` — request:**
```json
{
  "reason": "Quantity is 10× higher than same month last year — possible duplicate row"
}
```

---

### 4.7 Audit Log

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/records/{id}/audit/` | Full change history for a record. Returns ordered list of audit log entries with `before_state` / `after_state` JSON diffs. |

**GET `/api/v1/records/{id}/audit/` — response:**
```json
[
  {
    "action": "created",
    "changed_by": "system",
    "changed_at": "2024-04-01T10:22:05Z",
    "before_state": null,
    "after_state": { "raw_quantity": 1200.0, "review_status": "pending" }
  },
  {
    "action": "edited",
    "changed_by": "analyst@acme.com",
    "changed_at": "2024-04-02T14:10:00Z",
    "before_state": { "raw_quantity": 1200.0 },
    "after_state": { "raw_quantity": 1100.0 }
  },
  {
    "action": "approved",
    "changed_by": "analyst@acme.com",
    "changed_at": "2024-04-02T14:12:00Z",
    "before_state": { "review_status": "pending" },
    "after_state": { "review_status": "approved" }
  }
]
```

---

### 4.8 Analytics (Dashboard Summary)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/summary/` | Total emissions (kg CO₂e) by scope, by source type, by month. Query params: `date_from`, `date_to`. |
| `GET` | `/api/v1/summary/review-queue/` | Counts of pending / approved / flagged / locked per source. Used for KPI cards on the analyst dashboard. |

**GET `/api/v1/summary/review-queue/` — response:**
```json
{
  "sap":     { "pending": 120, "approved": 690, "flagged": 12, "locked": 9 },
  "utility": { "pending": 8,   "approved": 44,  "flagged": 2,  "locked": 0 },
  "travel":  { "pending": 55,  "approved": 210, "flagged": 7,  "locked": 0 }
}
```

---

### 4.9 Reference Data

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/emission-factors/` | List emission factors. Filter: `source_type`, `category`, `region`, `year`. |
| `GET` | `/api/v1/units/` | List all known unit conversions (kWh → kg, litres → kg, miles → km, etc.). |

---

## 5. Key Design Decisions

### Multi-tenancy: row-level, not schema-per-tenant

All tables carry `tenant_id`. A Django middleware injects the tenant filter on every ORM query derived from the request's JWT claim. Schema-per-tenant is operationally cleaner for large deployments but impractical on a single Render/Railway Postgres instance. This is noted as a scaling tradeoff in `TRADEOFFS.md`.

### `raw_payload` JSONB on every emission record

The original source row is stored verbatim. If normalisation logic has a bug, records can be re-processed without re-uploading files. Analysts can also see exactly what came in vs what was normalised.

### Emission factors stored in DB, not hardcoded

Each emission record holds a FK to the factor used at calculation time. Auditors can see which factor version was applied to each row. Factors can be updated without a code deploy; re-calculation requires a deliberate re-processing step (not automatic, to preserve the audit trail).

### Two-step unit normalisation

Raw units → base unit (kWh / km / kg) via `unit_lookup`, then base unit → kg CO₂e via `emission_factor`. This keeps the lookup table to ~20 rows instead of a combinatorial explosion of (raw unit × emission category) pairs.

### Scope assignment at ingestion time

Scope is written to `emission_record` at parse time based on `source_type` and category rules, not derived on the fly. This means the analyst sees scope immediately and corrections are explicit (edit + audit trail), not invisible query changes.

### Locked records are immutable at the API layer, not the DB layer

A `403 Forbidden` is returned on any edit attempt to a locked record. The DB itself has no trigger preventing it — which means a Django admin can unlock a record if there is a legitimate reason (data correction after a signing error). This is a deliberate tradeoff: auditability via the audit log beats DB-level immutability for a prototype where data correction workflows are not yet fully defined.

---

*Document version: 1.0 — generated for Breathe ESG Tech Intern Assignment*
