# ADR-001: Local proof, regional-first cloud design

**Status:** Accepted for educational implementation, not production approval.

## Alternatives
1. Regional Cloud Run + managed transactional store + async queue.
2. Multi-region Cloud Run + health-aware routing + evaluated replication.

## Decision
Prove safe retries and transactional idempotency locally. Defer all billed cloud provisioning. Next milestone is disposable regional deployment using a GCP-compatible managed persistent backend. Multi-region requires explicit traffic health management, recovery/failback design and data consistency tests.

## Consequences
Low initial cost; no cloud reliability claims justified. SQLite cannot be the authoritative database on ephemeral Cloud Run instances. A second deployment region does not imply data-region failover.
