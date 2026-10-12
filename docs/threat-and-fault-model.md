# Threat and fault model

Assets: job admission record, synthetic target ledger, actor identity, tenant boundary and job outcome. Local storage is SQLite on a single host; this is *not* cloud durability.

Trust boundary: the HTTP API derives principal, tenant and scopes solely from a verified in-process fixture-signed bearer. A request field or `X-Demo-Tenant` header is untrusted; no HTTP endpoint mints tokens. Ephemeral signing keys are randomly generated and restart invalidates outstanding test tokens. This scheme is **not OAuth/OIDC, GCP IAM or production workload identity**.

Adversary cases: absent identity; forged header; altered/expired token; inadequate scope; cross-tenant job ID; same idempotency key with different data; malformed or duplicate JSON fields; crash before commit; ACK loss after commit; duplicate worker delivery; bounded poison retrial. For every DENY, assert no effect in the job ledger.

Failure domains: process, database file, queue/worker (simulated), false health, region (NOT TESTED). `/health/live` proves process alive; `/health/ready` only checks local SQLite. Neither establishes real load-balancer readiness or managed-store availability.

Out of scope: secrets/PII, production integration, cross-region data consistency, cloud IAM permissions, observable SLI over a 30-day window, GCP failures and deployment rollback.
