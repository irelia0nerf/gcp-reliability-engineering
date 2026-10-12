# ADR-006 — Release and rollback gates

**Status:** Proposed, no cloud release workflow. **Options:** unreviewed direct deploy; reviewed, protected PR with CI, immutable artifacts, canary and rollback.

**Decision:** require PR + four CI checks and reviewed infrastructure changes. R08 in this repo is only an application-state rollback simulation, **not a deployed bad revision**.

**Failure modes:** unprotected main, bypassed tests, non-backward-compatible schema, false green skipped check. **Tests:** CI execution and ruleset enforcement; later separate approved cloud rollback. **Cost:** CI minutes only.
