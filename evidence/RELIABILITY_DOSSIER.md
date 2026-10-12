# Reliability Evidence Dossier

**CLOUD GO: HOLD.** Current scope: local deterministic simulation only.

Reproduce:
```bash
python -m unittest discover -s tests -v
python -m src.demo --scenario R04
```

R01–R08 are lab approximations. They do **not** prove cloud instance termination, actual queue poison-message management, scale, deployment rollback, or managed-datastore outage behavior. R09–R12: **NOT_TESTED**.

The local target ledger guards effects under duplicate worker calls using SQLite transactions; a timeout after commit is reconcilable by read; when admission storage is intentionally unavailable, no false durable admission occurs.

Cloud Run deployment, availability SLI, measured RTO/RPO, real regional failover, production identity validation and real GCP Cloud Tasks/Pub/Sub delivery are all **NOT_VERIFIED**.
