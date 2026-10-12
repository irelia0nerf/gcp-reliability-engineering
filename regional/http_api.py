"""Regional HTTP facade for Cloud Run (not deployed).

Google ID token verification is mandatory even if Cloud Run IAM also enforces invoker.
"""
import json
import logging
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import UUID

from regional.identity import IdentityPolicy, IdentityRejected
from regional.store import Collision, Missing, PgStore
from regional.tasks import CloudTasksPublisher, dispatch_batch

LOG=logging.getLogger("atlas.regional")
JOB_PATH=re.compile(r"^/v1/jobs/([0-9a-fA-F-]{36})$")
TASK_PATH=re.compile(r"^/internal/tasks/([0-9a-fA-F-]{36})$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):
        pass  # Never log Authorization or a full request path with sensitive values.

    def reply(self,status,body):
        raw=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorization(self,scope):
        return self.server.identity.authorize(self.headers.get("Authorization"),scope)

    def body_json(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("transfer encoding unsupported")
        size=self.headers.get("Content-Length","")
        if not size.isascii() or not size.isdecimal() or not 0<int(size)<=4096:
            raise ValueError("invalid content length")
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            raise ValueError("invalid content type")
        def reject_duplicate(pairs):
            data={}
            for key,val in pairs:
                if key in data:
                    raise ValueError("duplicate JSON field")
                data[key]=val
            return data
        return json.loads(self.rfile.read(int(size)),object_pairs_hook=reject_duplicate)

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=="/health/live":
            return self.reply(200,{"live":True,"scope":"process"})
        if path=="/health/ready":
            try:
                if not self.server.store.ping():
                    raise RuntimeError("unready")
                return self.reply(200,{"ready":True,"scope":"postgres"})
            except Exception:
                return self.reply(503,{"ready":False})
        match=JOB_PATH.fullmatch(path)
        if not match:
            return self.reply(404,{"error":"not_found"})
        try:
            job_id=str(UUID(match.group(1)))
            actor=self.authorization("jobs:read")
            return self.reply(200,self.server.store.get(actor.tenant,actor.email,job_id))
        except IdentityRejected:
            return self.reply(401,{"error":"unauthorized"})
        except (ValueError,Missing):
            return self.reply(404,{"error":"not_found"})
        except Exception:
            LOG.exception("regional read dependency failure")
            return self.reply(503,{"error":"dependency_unavailable"})

    def do_POST(self):
        path=urlsplit(self.path).path
        if path=="/v1/jobs":
            return self.create_job()
        if path=="/internal/dispatch":
            return self.dispatch()
        match=TASK_PATH.fullmatch(path)
        if match:
            return self.execute(match.group(1))
        return self.reply(404,{"error":"not_found"})

    def create_job(self):
        try:
            actor=self.authorization("jobs:create")
        except IdentityRejected:
            return self.reply(401,{"error":"unauthorized"})
        key=self.headers.get("Idempotency-Key","")
        if not 1<=len(key)<=128 or not key.isascii() or not key.isprintable():
            return self.reply(400,{"error":"invalid_idempotency_key"})
        try:
            payload=self.body_json()
            if (not isinstance(payload,dict) or set(payload)!={"value"}
                    or type(payload["value"]) is not int
                    or not -1000000<=payload["value"]<=1000000):
                raise ValueError("invalid value")
            job=self.server.store.admit(actor.tenant,actor.email,key,payload["value"])
            return self.reply(202,job)
        except (ValueError,UnicodeError):
            return self.reply(400,{"error":"invalid_payload"})
        except Collision:
            return self.reply(409,{"error":"idempotency_collision"})
        except Exception:
            LOG.exception("regional admission unavailable")
            return self.reply(503,{"error":"dependency_unavailable"})

    def dispatch(self):
        try:
            self.authorization("dispatch")
        except IdentityRejected:
            return self.reply(401,{"error":"unauthorized"})
        try:
            result=dispatch_batch(self.server.store,self.server.publisher,limit=10)
            # A dispatch response is not proof that target effects executed.
            failed=any(x["delivery"]=="FAILED" for x in result)
            return self.reply(503 if failed else 200,{"dispatched":result})
        except Exception:
            LOG.exception("dispatcher dependency unavailable")
            return self.reply(503,{"error":"dependency_unavailable"})

    def execute(self,path_id):
        try:
            self.authorization("execute")
        except IdentityRejected:
            return self.reply(401,{"error":"unauthorized"})
        try:
            job_id=str(UUID(path_id))
            data=self.body_json()
            if not isinstance(data,dict) or data!={"job_id":job_id}:
                return self.reply(400,{"error":"invalid_task_body"})
            result=self.server.store.apply_effect(job_id)
            return self.reply(200,{"outcome":result})
        except (ValueError,Missing):
            # Poison inputs should not silently acknowledge a real missing job.
            return self.reply(400,{"error":"invalid_task"})
        except Exception:
            LOG.exception("worker dependency unavailable")
            return self.reply(503,{"error":"dependency_unavailable"})


def make_server(store,identity,publisher,host="127.0.0.1",port=0):
    if host not in ("127.0.0.1","localhost","0.0.0.0"):  # nosec B104 — private Cloud Run ingress
        raise ValueError("unsupported bind host")
    server=ThreadingHTTPServer((host,port),Handler)
    server.store,server.identity,server.publisher=store,identity,publisher
    return server


def main():
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(name)s %(message)s")
    store=PgStore(os.environ["ATLAS_DATABASE_URL"])
    identity=IdentityPolicy.from_env()
    publisher=CloudTasksPublisher(
        os.environ["ATLAS_PROJECT_ID"],os.environ["ATLAS_REGION"],
        os.environ["ATLAS_QUEUE_NAME"],os.environ["ATLAS_EXPECTED_AUDIENCE"],
        os.environ["ATLAS_TASK_SERVICE_ACCOUNT"])
    host=os.environ.get("ATLAS_BIND_HOST","0.0.0.0")  # nosec B104 — Cloud Run container bind
    server=make_server(store,identity,publisher,host,int(os.environ.get("PORT","8080")))
    LOG.info("Regional Atlas service started; cloud reliability NOT VERIFIED")
    server.serve_forever()


if __name__=="__main__":
    main()
