# ADR-002 — Durable admission and effects

**Status:** Accepted for local laboratory, not production. **Options:** local SQLite; Cloud SQL/PostgreSQL HA with transactional outbox; globally distributed managed database.

**Decision:** SQLite for local proof of duplicate-effect suppression, acceptance state and atomic effect+completion. This local file is not durable across Cloud Run instances. Managed store choice depends on measured admission, durability and cost requirements.

**Failure modes:** crash, local disk loss, concurrent writes, lost ACK and datastore outage. **Tests:** R02/R03/R04/R05, but only simulated. **Cost:** no cloud spend here.
