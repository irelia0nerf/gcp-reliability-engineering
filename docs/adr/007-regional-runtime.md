# ADR-007 — Regional runtime & data integrity

**State:** IMPLEMENTED OFFLINE / CLOUD GO HOLD.

**Primary design:** PostgreSQL transactions for admission+outbox and idempotent effect+status; Cloud Tasks deterministic task name and Google-signed OIDC bearer; Cloud Run internal ingress with explicit invoker roles, Google ID-token verification and tenant mapping; isolated runtime identities.

**Why:** SQLite per-instance file cannot guarantee state across autoscaled Cloud Run replicas. Cloud Tasks offers at-least-once task delivery; outcome idempotency is enforced at the datastore transaction boundary, never inferred from task ACK.

**Control boundaries:** user-supplied identities/tenants cannot grant authority; token audience, issuer and verified email bind identity. No generic forwarding of `X-CloudTasks-*` headers grants permission.

**Failure windows:** (1) crash after DB transaction before response -> retry same idempotency key returns same job; (2) after task create before outbox acknowledgement -> lease expires, retry same deterministic task name; (3) after effect DB commit before worker ACK -> Cloud Tasks redelivery returns `ALREADY_APPLIED`; (4) queued task exhausted retries -> still requires reconciliation, currently NOT IMPLEMENTED; (5) CloudSQL region outage -> Cloud SQL regional HA behavior and RTO not yet measured.

**Rational limits:** synthetic database effect only. For actual external side effects exactly-once semantics require independent effect adapter/outbox, target idempotency key and outcome reconciliation. Ingress internal alone does not establish safety of tenant authorization. Terraform resources are disabled by default. No apply.
