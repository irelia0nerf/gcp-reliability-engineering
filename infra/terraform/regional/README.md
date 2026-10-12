# Regional Google Cloud scaffold — NEVER AUTO-APPLY

**State:** Infrastructure-as-Code design only. No Google Cloud resources have been deployed.

This is a separate opt-in Terraform root. By default `enable_infra=false`; all resources have `count=0` / empty `for_each`. CI runs `fmt`, `init -backend=false` and `validate` only. It never runs `plan` with project credentials or `apply`.

## Proposed architecture

- Private, regional Cloud Run service running the `regional.http_api` container, with `roles/run.invoker` limited to explicitly provisioned principals.
- Cloud SQL PostgreSQL with regional high availability, encrypted connection through Cloud SQL socket, backups and PITR. Instance deletion protection enabled.
- PostgreSQL transactional admission + outbox + effect ledger.
- Cloud Tasks region-matched queue, deterministic task names and dedicated worker identity; Cloud Scheduler periodically requests dispatch using a distinct service account.
- Cloud Scheduler job is **PAUSED even if cloud resources are eventually provisioned**.
- Separate runtime and caller identities; server verifies Google-signed ID tokens and uses a configured email-to-tenant allowlist; request-provided tenant is never authority.

## Gate before *any* opt-in deployment

1. Dedicated billed project, approved spending limit/alerts and teardown plan. Billing alerts are not hard spending caps.
2. API enablement, IAM review, Cloud Tasks agent token-minting permissions, networking/ingress, and region placement review.
3. Build and scan a reproducible container; sign and pin immutable digest. `Dockerfile.regional` is a sample, not a signed artifact.
4. Create a Cloud SQL user and a **preexisting** Secret Manager secret containing a PostgreSQL DSN for database `atlas`, with the Cloud SQL Unix socket hostname, a dedicated username and a strong credential. Do not place example credentials in repository URLs. Secret bytes must be created out of band, not committed or passed through Terraform state. Test Cloud SQL socket connection separately.
5. Verify database schema migration is approved and applied in a controlled procedure; app never silently auto-migrates production.
6. Set `expected_audience` to a stable HTTPS custom audience supported by Cloud Run; verify issuer, `aud`, verified email and invoker IAM.
7. Validate Terraform changes including a manually reviewed **credentialed plan**. Only then obtain explicit permission for `terraform apply` and Cloud Scheduler unpause.
8. Run regional health, dispatch replay, outbox lease recovery, worker crash and restoration tests, measure SLIs and document findings.
9. Reconcile Cloud Tasks exhausted retries and orphaned outbox records; a successful enqueue alone is **not** proof of business completion.

## Offline checks

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform/regional init -backend=false -input=false
terraform -chdir=infra/terraform/regional validate -no-color
```

## Explicit limitations

No deployed service, no actual GCP OIDC test, no validated Cloud SQL migration, no failover or recovery SLO, no container digest or SBOM attested, no automatic reconciliation of permanently dead Cloud Tasks and no cost estimate. Cloud SQL regional HA does not provide independently verified cross-region DR.

Infrastructure is a prototype scaffold, not approval to operate a production system.

References: https://cloud.google.com/run/docs/configuring/custom-audiences and https://cloud.google.com/tasks/docs/creating-http-target-tasks.
