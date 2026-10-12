# GCP Reliability Engineering — FAILURE IS A CONTRACT

**Status: local reliability/security simulation, not Google Cloud deployment. CLOUD GO: HOLD.**

A synthetic multi-tenant Atlas Operations lab exercising durable *local* admission, idempotent effects, lost-ACK retries, bounded poison simulations, tenant-isolated reads, and a loopback-only HTTP API.

## Run (Python 3.12+)

```bash
python -m unittest discover -s tests -v
python -m src.scenarios --scenario all
python -m src.scenarios --scenario R04
```

R01–R08 produce structured **SIMULATED** evidence. R06 is a simplified persisted poison fixture; R07 is a *sequential local burst*; R08 does **not** perform a real CI/deployment rollback. R09–R12 remain **NOT_TESTED**.

The HTTP API (`python -m src.http_api`) binds loopback only and requires a short-lived, test-only HMAC bearer signed via `LabAuthority.issue_for_test` outside the HTTP request boundary. No public token-issuing API exists; test via the adversarial suite. Tenant headers cannot grant authority. These tokens are not production GCP/OIDC identity. Do not expose the lab to untrusted networks.

## Architecture & evidence

- [Full challenge](docs/challenge.md) and [reliability contract](docs/reliability-contract.md)
- [Threat and fault model](docs/threat-and-fault-model.md)
- [Architecture decisions](docs/adr/), [recovery runbook](docs/runbooks/local-recovery.md)
- [Evidence dossier](evidence/RELIABILITY_DOSSIER.md)
- [Terraform validate-only scaffold](infra/terraform/README.md)
- [Ruleset activation manual step](.github/rulesets/README.md)

The existing SQLite model is single-host and unsuitable as Cloud Run persistent storage. Terraform is disabled by default; CI runs `fmt`, `init -backend=false` and `validate` only. No GCP secrets, no apply, no SLO/RTO/RPO measurements.

## Regional GCP Runtime — candidate (OFFLINE / NO DEPLOY)

The proposed [regional runtime](regional/) is isolated from the original local SQLite lab. It includes PostgreSQL transactional admission and outbox, synthetic idempotent effects, fenced dispatcher leases, deterministic Cloud Tasks creation, Cloud Run-compatible HTTP endpoints, and a Google-signed ID-token trust boundary. The [opt-in Terraform module](infra/terraform/regional/) provides Cloud Run, Cloud SQL HA, Cloud Tasks and a **paused** Cloud Scheduler job, but defaults to **zero resources** and is never applied by CI.

```bash
python -m unittest discover -s tests -v
terraform -chdir=infra/terraform/regional init -backend=false -input=false
terraform -chdir=infra/terraform/regional validate -no-color
```

The regional PostgreSQL integration suite runs only with `ATLAS_TEST_PG_DSN` set to an **isolated disposable Postgres instance**. GitHub Actions provides it as a container service. This proves the SQL transaction contract in CI, **not** Cloud SQL / IAM / OIDC / Cloud Tasks integration on Google Cloud.

Runtime dependencies and a sample container build are in [requirements-regional.txt](requirements-regional.txt) and [Dockerfile.regional](Dockerfile.regional). Their supply-chain provenance and OCI digest are **not attested**. Review [ADR-007](docs/adr/007-regional-runtime.md) and [Regional Readiness Runbook](docs/runbooks/regional-readiness.md).

**Important failure mode:** Cloud Tasks enqueue acknowledgement does not imply business effect completion. Retry exhaustion and orphaned tasks still require an independent reconciliation worker / operational evidence before any production GO.

**Current gate:** REGIONAL CODE REVIEW pending; CLOUD GO: HOLD; RTO/RPO, SLI/SLO and live GCP recovery: NOT MEASURED. No GCP deployment or resource provisioning.
