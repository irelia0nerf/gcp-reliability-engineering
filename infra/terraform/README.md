# Terraform scaffold — NO APPLY

**Default:** `enable_service = false`. This is an offline-checkable illustrative Cloud Run regional template, not an Atlas runtime deployment.

CI executes:
```bash
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate
```

The placeholder image is Google's hello sample **not the SQLite application**. There is no durable managed datastore, worker, network or IAM configuration ready for GCP reliability claims. The workflow has no Google Cloud authentication and does not execute `plan` or `apply`. Do not change the enablement flag until a separate approved deployment review covers billing, least privilege, networking, persistence, rollback, and teardown.
