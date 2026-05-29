# Technical Trade-Offs

During the development of this platform, we had to balance feature completeness against the time constraints of an MVP assignment. Here are three things we deliberately did **not** build and why:

### 1. Dedicated Audit Log Database Table
- **What we didn't build:** A comprehensive, separate relational table (e.g., `AuditLogEntry`) tracking every single field-level `UPDATE` operation across all models.
- **Why:** While a dedicated audit table is the gold standard for enterprise compliance, it introduces massive query overhead and requires complex Django signal architectures to implement correctly. 
- **The Trade-off:** Instead, we utilized PostgreSQL's powerful `JSONField` to append a lightweight `history_log` directly to the `EmissionRecord` model. This satisfies the requirement of tracking *who* changed *what* and *when* without the engineering overhead of a full event-sourcing architecture. The trade-off is that querying historical states across thousands of records simultaneously is slower than querying an indexed relational table.

### 2. Algorithmic Duplicate Detection & Hashing
- **What we didn't build:** Automatic deduplication using cryptographic hashes (e.g., SHA-256) of row contents to silently drop duplicate uploads.
- **Why:** Real-world ESG data is notoriously difficult to deduplicate via pure algorithms. Two travel records might look identical (same employee, same distance, same date) but represent two distinct trips (e.g., a morning flight and an evening return flight). 
- **The Trade-off:** We traded algorithmic automation for human-in-the-loop verification. By routing all ingested data into an `AnalystGrid` with a `Pending` status, we empower a human analyst to spot anomalies and manually flag duplicates. This prevents valid data from being accidentally dropped by an overly aggressive deduplication script.

### 3. Dynamic Role-Based Access Control (RBAC) per Tenant
- **What we didn't build:** A complex permissions matrix allowing custom roles (e.g., "Data Entry Clerk", "Senior Approver", "Auditor") with distinct viewing/editing boundaries per tenant.
- **Why:** Implementing a secure, granular RBAC system (like Django-Guardian) requires extensive testing to ensure tenant boundaries are not breached. 
- **The Trade-off:** We assumed a basic "Admin vs. User" authorization model for the MVP. This allowed us to focus our limited development time on the core business logic: accurate CSV parsing, background task management via Celery, and correct Scope 1/2/3 carbon calculations. Building RBAC would have detracted from the core mathematical requirements of the assignment.
