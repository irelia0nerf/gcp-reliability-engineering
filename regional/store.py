"""PostgreSQL transactional admission, outbox leasing and synthetic effects.

No irreversible external effect is claimed. Cloud SQL availability is untested.
"""
import uuid
from pathlib import Path


class Collision(Exception):
    """Idempotency key was reused with different parameters."""


class Missing(Exception):
    """Job unavailable in the supplied tenant."""


class PgStore:
    def __init__(self, dsn):
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self.dsn = dsn

    def connect(self):
        import psycopg
        return psycopg.connect(self.dsn, connect_timeout=5)

    def bootstrap(self):
        sql = (Path(__file__).parent / "sql" / "001_init.sql").read_text(encoding="utf-8")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    def ping(self):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1

    def admit(self, tenant, principal, key, value):
        if not all(isinstance(x, str) and x for x in (tenant, principal, key)):
            raise ValueError("missing trusted context")
        if type(value) is not int or not -1000000 <= value <= 1000000:
            raise ValueError("invalid value")
        job_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  INSERT INTO atlas_jobs (id,tenant,principal,idempotency_key,value)
                  VALUES (%s,%s,%s,%s,%s)
                  ON CONFLICT (tenant,principal,idempotency_key) DO NOTHING
                  RETURNING id,status
                """, (job_id,tenant,principal,key,value))
                row = cur.fetchone()
                if row is not None:
                    cur.execute("INSERT INTO atlas_outbox (job_id) VALUES (%s)", (job_id,))
                    return {"id": str(row[0]), "status": row[1], "created": True}
                cur.execute("""
                  SELECT id,status,value FROM atlas_jobs
                  WHERE tenant=%s AND principal=%s AND idempotency_key=%s
                  FOR UPDATE
                """,(tenant,principal,key))
                old = cur.fetchone()
                if old is None:
                    raise RuntimeError("unique conflict without visible row")
                if old[2] != value:
                    raise Collision("conflicting idempotency payload")
                return {"id":str(old[0]),"status":old[1],"created":False}

    def get(self, tenant, principal, job_id):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT id,status,value FROM atlas_jobs
                  WHERE id=%s AND tenant=%s AND principal=%s
                """,(job_id,tenant,principal))
                row=cur.fetchone()
                if row is None:
                    raise Missing("job not found")
                return {"id":str(row[0]),"status":row[1],"value":row[2]}

    def claim(self, limit=10):
        if not 1 <= limit <= 100:
            raise ValueError("limit out of range")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT job_id FROM atlas_outbox
                  WHERE enqueued_at IS NULL
                    AND (lease_until IS NULL OR lease_until < clock_timestamp())
                  ORDER BY created_at, job_id
                  FOR UPDATE SKIP LOCKED LIMIT %s
                """,(limit,))
                ids=[str(row[0]) for row in cur.fetchall()]
                leased=[]
                for job_id in ids:
                    token=str(uuid.uuid4())
                    cur.execute("""
                      UPDATE atlas_outbox SET attempts=attempts+1,lease_token=%s,
                         lease_until=clock_timestamp()+interval '60 seconds',
                         last_error=NULL
                      WHERE job_id=%s
                    """,(token,job_id))
                    leased.append({"job_id":job_id,"lease_token":token})
                return leased

    def mark_enqueued(self, job_id, lease_token):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  UPDATE atlas_outbox SET enqueued_at=clock_timestamp(),
                    lease_until=NULL,lease_token=NULL,last_error=NULL
                  WHERE job_id=%s AND lease_token=%s AND enqueued_at IS NULL
                """,(job_id,lease_token))
                return cur.rowcount == 1

    def release_claim(self, job_id, lease_token, error):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  UPDATE atlas_outbox SET lease_until=NULL,lease_token=NULL,
                      last_error=%s
                  WHERE job_id=%s AND lease_token=%s AND enqueued_at IS NULL
                """,(str(error)[:256],job_id,lease_token))
                return cur.rowcount == 1

    def apply_effect(self, job_id):
        """One synthetic effect and SUCCEEDED transition in the same transaction."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tenant,value,status FROM atlas_jobs WHERE id=%s FOR UPDATE",(job_id,))
                row=cur.fetchone()
                if row is None:
                    raise Missing("job not found")
                tenant,value,status=row
                if status == "SUCCEEDED":
                    return "ALREADY_APPLIED"
                cur.execute("""
                  INSERT INTO atlas_effects (job_id,tenant,value) VALUES (%s,%s,%s)
                  ON CONFLICT (job_id) DO NOTHING
                """,(job_id,tenant,value))
                cur.execute("""
                  UPDATE atlas_jobs SET status='SUCCEEDED',
                         completed_at=clock_timestamp() WHERE id=%s
                """,(job_id,))
                return "SUCCEEDED"

    def stats(self):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM atlas_jobs")
                jobs=cur.fetchone()[0]
                cur.execute("SELECT COUNT(*),COALESCE(SUM(value),0) FROM atlas_effects")
                effects,total=cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM atlas_outbox WHERE enqueued_at IS NULL")
                pending=cur.fetchone()[0]
                return {"jobs":jobs,"effects":effects,"value_total":total,"pending_outbox":pending}
