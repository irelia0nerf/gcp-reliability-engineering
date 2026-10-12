# ADR-004 — Trusted identity

**Status:** Accepted for loopback-only simulation. **Options:** untrusted tenant headers; server-signed short-lived fixture tokens; production OIDC/mTLS/IAM.

**Decision:** Reject untrusted tenant headers and use a random in-process HMAC authority with separate scopes, tenant and principal; no HTTP token issuance. **Tests:** tampered/expired bearer, forged tenant, cross-tenant retrieval, anonymous and insufficient-scope DENY with unchanged ledger.

**Failure modes:** credential forgery, expired token, missing scopes, token reuse. **Limitation:** fixture HMAC is not real Google Cloud identity. **Cost:** zero.
