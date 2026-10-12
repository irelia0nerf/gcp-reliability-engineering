# Regional readiness runbook — design review only

## Offline gate

```bash
python -m unittest discover -s tests -v
terraform -chdir=infra/terraform/regional init -backend=false -input=false
terraform -chdir=infra/terraform/regional validate -no-color
```

PostgreSQL integration requires a disposable PG instance; in GitHub Actions the test job provides this service and sets `ATLAS_TEST_PG_DSN` to a CI-only credential. No Google Cloud secrets are required for the tests.

## Post-release failure drilling (NOT RUN)

- Confirm caller permission, token validation and tenant-scoped read isolation.
- Admit twice with same key and same arguments: one persisted job; changed argument gives 409.
- Stop worker before commit: no effect; retry commits once.
- Interrupt worker after commit before task ACK: redelivery reports already applied; effect count remains one.
- Stop dispatcher after Cloud Tasks enqueue before marking outbox: expiration/lease recovery, deterministic task name, reconcile status.
- Disconnect Cloud SQL: admission returns 503 rather than fictional durable success.
- Exhaust Cloud Tasks retries and measure reconciliation backlog; escalation required until an actual dead-task recovery operator exists.
- Inject bounded load and measure p95, success SLI, Cloud SQL connection saturation and queue age.
- Test HA zone failure through supported safe methods, only with written authorization.
- Review costs and time to clean up; Cloud SQL deletion_protection is intentional and teardown requires a separate approved change.

**DO NOT** claim 99.95% SLO, production DR, RTO/RPO, cross-region recovery or operational readiness without measured evidence.
