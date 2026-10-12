# ADR-003 — Queue delivery and poison handling

**Status:** Design proposed, no managed queue deployed. **Options:** Cloud Tasks HTTP retry; Pub/Sub subscription; local worker.

**Decision:** Keep deterministic simulation. Later use an outbox backed by durable managed datastore and compare Cloud Tasks with Pub/Sub; neither guarantees exactly-once business effects under arbitrary failures.

**Failure modes:** redelivery, ACK loss, poison retry loop, hot backlog. **Tests:** R03/R04/R06, LOCAL_SIMULATION. R06 records three attempts then FAILED; this is **not** real DLQ or Cloud Tasks evidence. **Cost:** no billed services.
