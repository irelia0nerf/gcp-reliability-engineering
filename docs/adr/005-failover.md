# ADR-005 — Region and recovery strategy

**Status:** Deferred. **Options:** regional HA; active-passive two-region health-aware routing; active-active with consistency/fencing.

**Decision:** start regional and do not claim failover until routing, data replication, split brain, recovered writes and failback are tested. Simply deploying two Cloud Run services does not guarantee failover.

**Failure modes:** stale health, shared dependencies, split brain, stale replication and cross-region write conflicts. **Tests:** R09–R12 NOT_TESTED. **Cost:** multi-region premium not estimated without specific service/capacity plan.
