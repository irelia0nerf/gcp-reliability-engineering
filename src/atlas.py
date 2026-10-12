"""Local-only SQLite-backed synthetic reliability lab."""
import json, sqlite3, uuid
from contextlib import contextmanager

class Unavailable(Exception): pass
class Conflict(Exception): pass
class Forbidden(Exception): pass

class Atlas:
    def __init__(self, database):
        self.database = str(database)
        with self.tx() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, idem TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(tenant, idem))")
            db.execute("CREATE TABLE IF NOT EXISTS effects (job_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, value INTEGER NOT NULL)")

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.database,timeout=10,isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def admit(self, tenant, key, value, *, storage_available=True):
        if not storage_available: raise Unavailable("durable store unavailable")
        if not tenant or not key or not isinstance(value,int) or isinstance(value,bool): raise ValueError("invalid admission")
        payload=json.dumps({"value":value},sort_keys=True)
        with self.tx() as db:
            old=db.execute("SELECT id,payload,status FROM jobs WHERE tenant=? AND idem=?",(tenant,key)).fetchone()
            if old:
                if old[1]!=payload: raise Conflict("idempotency-key collision")
                return {"id":old[0],"status":old[2]}
            jid=str(uuid.uuid4())
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)",(jid,tenant,key,payload,"ACCEPTED"))
            return {"id":jid,"status":"ACCEPTED"}

    def get(self, tenant, job_id):
        with self.tx() as db:
            old=db.execute("SELECT status,payload FROM jobs WHERE id=? AND tenant=?",(job_id,tenant)).fetchone()
            if old is None: raise Forbidden("job unavailable")
            return {"id":job_id,"status":old[0],"payload":json.loads(old[1])}

    def process(self, job_id, *, fault=None):
        with self.tx() as db:
            old=db.execute("SELECT tenant,payload,status FROM jobs WHERE id=?",(job_id,)).fetchone()
            if old is None: raise KeyError(job_id)
            if old[2]=="SUCCEEDED": return "ALREADY_APPLIED"
            if fault=="before_commit": raise Unavailable("simulated pre-commit crash")
            db.execute("INSERT OR IGNORE INTO effects VALUES (?,?,?)",(job_id,old[0],json.loads(old[1])["value"]))
            db.execute("UPDATE jobs SET status='SUCCEEDED' WHERE id=?",(job_id,))
        if fault=="after_commit": raise Unavailable("simulated lost ACK after commit")
        return "SUCCEEDED"

    def snapshot(self):
        with self.tx() as db:
            return {"jobs":db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                    "effects":db.execute("SELECT COUNT(*) FROM effects").fetchone()[0],
                    "value_total":db.execute("SELECT COALESCE(SUM(value),0) FROM effects").fetchone()[0]}

    def pending(self):
        with self.tx() as db:
            return [row[0] for row in db.execute("SELECT id FROM jobs WHERE status != 'SUCCEEDED'")]
