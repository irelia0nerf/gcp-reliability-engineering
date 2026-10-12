-- Regional Atlas PostgreSQL schema. Apply only to an isolated, approved lab DB.
CREATE TABLE IF NOT EXISTS atlas_jobs (
    id uuid PRIMARY KEY,
    tenant text NOT NULL,
    principal text NOT NULL,
    idempotency_key text NOT NULL,
    value integer NOT NULL,
    status text NOT NULL DEFAULT 'ACCEPTED'
      CHECK (status IN ('ACCEPTED','SUCCEEDED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (tenant, principal, idempotency_key)
);

CREATE TABLE IF NOT EXISTS atlas_effects (
    job_id uuid PRIMARY KEY REFERENCES atlas_jobs(id),
    tenant text NOT NULL,
    value integer NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS atlas_outbox (
    job_id uuid PRIMARY KEY REFERENCES atlas_jobs(id),
    attempts integer NOT NULL DEFAULT 0,
    lease_token uuid,
    lease_until timestamptz,
    enqueued_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS atlas_outbox_pending_idx
    ON atlas_outbox (lease_until, created_at)
    WHERE enqueued_at IS NULL;
