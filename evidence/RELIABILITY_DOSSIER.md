# Reliability Evidence Dossier

**Cloud readiness: HOLD.** All new R01–R08 proofs are `SIMULATED`. The original 14 baseline tests and the new adversarial HTTP suite validate local-only contracts.

Run `python -m unittest discover -s tests -v` and `python -m src.scenarios --scenario all`. Save the JSON and the GitHub Actions run URL for the same commit. CI must show four completed green jobs: `tests`, `lint`, `security`, `terraform`.

Target SLIs: admission/read 99.95%; completion p95<=60s and admission p95<=1s at specified loads, **not measured**. Real RTO, RPO, Cloud Run downtime, Cloud Tasks delivery, Cloud SQL HA and multi-region failover **NOT_TESTED**. R06 is a persisted poison fixture, not a real dead-letter queue. R08 is not a deployed rollback.

Risk register: SQLite ephemeral on Cloud Run, no managed datastore, HMAC test-only identities, no real async transport, no GCP credentials/billing configuration, no production observability or valid cloud resilience claim. **Main branch protection is administrative and not verified from this PR.**
