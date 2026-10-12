"""Offline tests of role binding, HTTP boundary, leases and deterministic publisher."""
import http.client
import json
import threading
import unittest
import uuid

from regional.http_api import make_server
from regional.identity import IdentityPolicy, IdentityRejected
from regional.tasks import dispatch_batch, task_name


AUD="https://atlas.example.invalid"
TASK="tasks@example.iam.gserviceaccount.com"
DISPATCH="dispatcher@example.iam.gserviceaccount.com"
USER="api@example.iam.gserviceaccount.com"


def claims(email,**updates):
    result={"iss":"https://accounts.google.com","aud":AUD,
            "email":email,"email_verified":True}
    result.update(updates)
    return result


class MemoryStore:
    """Only an HTTP contract stub; PostgreSQL correctness is tested separately."""
    def __init__(self):
        self.jobs={}
        self.effects={}
        self.outbox={}
        self.fault=False

    def ping(self):
        if self.fault:
            raise RuntimeError("store failed")
        return True

    def admit(self,tenant,principal,key,value):
        if self.fault:
            raise RuntimeError("store failed")
        ident=(tenant,principal,key)
        existing=self.outbox.get(ident)
        if existing:
            if self.jobs[existing]["value"]!=value:
                from regional.store import Collision
                raise Collision()
            return {"id":existing,"status":self.jobs[existing]["status"],"created":False}
        job_id=str(uuid.uuid4())
        self.jobs[job_id]={"tenant":tenant,"principal":principal,"value":value,"status":"ACCEPTED"}
        self.outbox[ident]=job_id
        return {"id":job_id,"status":"ACCEPTED","created":True}

    def get(self,tenant,principal,job_id):
        from regional.store import Missing
        job=self.jobs.get(job_id)
        if not job or job["tenant"]!=tenant or job["principal"]!=principal:
            raise Missing()
        return {"id":job_id,"status":job["status"],"value":job["value"]}

    def apply_effect(self,job_id):
        from regional.store import Missing
        if self.fault:
            raise RuntimeError("store failed")
        job=self.jobs.get(job_id)
        if not job:
            raise Missing()
        if job_id in self.effects:
            return "ALREADY_APPLIED"
        self.effects[job_id]=job["value"]
        job["status"]="SUCCEEDED"
        return "SUCCEEDED"


class FakeDispatcher:
    def __init__(self):
        self.sent=[]
        self.fail=False

    def publish(self,job_id):
        if self.fail:
            raise RuntimeError("temporary dispatch failure")
        self.sent.append(job_id)
        return "CREATED"


class RegionalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryStore()
        self.publisher=FakeDispatcher()
        self.actor=IdentityPolicy(
            AUD,{USER:{"tenant":"tenant-a","scopes":["jobs:create","jobs:read"]}},
            TASK,DISPATCH,verifier=lambda token,aud: {
                "user":claims(USER),
                "worker":claims(TASK),
                "scheduler":claims(DISPATCH),
                "forged":claims(USER,email_verified=False),
                "wrong_issuer":claims(USER,iss="https://attacker.invalid"),
                "wrong_audience":claims(USER,aud="https://wrong.invalid")
            }[token])
        self.server=make_server(self.store,self.actor,self.publisher)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self,method,path,token=None,body=None,headers=None):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=4)
        h=dict(headers or {})
        if token is not None:
            h["Authorization"]="Bearer "+token
        if body is not None:
            h.setdefault("Content-Type","application/json")
        c.request(method,path,body=body,headers=h)
        res=c.getresponse()
        status,payload=res.status,json.loads(res.read())
        c.close()
        return status,payload

    def create(self,token="user",key="k",body=b'{"value":7}',headers=None):
        return self.call("POST","/v1/jobs",token,body,{"Idempotency-Key":key,**(headers or {})})

    def test_caller_can_admit_and_get(self):
        status,job=self.create()
        self.assertEqual(status,202)
        self.assertTrue(job["created"])
        status,got=self.call("GET","/v1/jobs/"+job["id"],"user")
        self.assertEqual(status,200)
        self.assertEqual(got["value"],7)

    def test_denied_anonymous_does_not_mutate(self):
        self.assertEqual(self.create(token=None)[0],401)
        self.assertEqual(self.store.jobs,{})

    def test_unverified_email_issuer_audience_fail_closed(self):
        for token in ("forged","wrong_issuer","wrong_audience","missing"):
            with self.subTest(token=token):
                self.assertEqual(self.create(token=token)[0],401)
        self.assertEqual(self.store.jobs,{})

    def test_caller_cannot_be_worker_or_scheduler(self):
        status,job=self.create()
        self.assertEqual(status,202)
        data=json.dumps({"job_id":job["id"]}).encode()
        self.assertEqual(self.call("POST","/internal/tasks/"+job["id"],"user",data)[0],401)
        self.assertEqual(self.call("POST","/internal/dispatch","user")[0],401)
        self.assertEqual(self.store.effects,{})

    def test_service_roles_cannot_be_user(self):
        self.assertEqual(self.create(token="worker")[0],401)
        self.assertEqual(self.create(token="scheduler")[0],401)
        self.assertEqual(self.store.jobs,{})

    def test_untrusted_tenant_header_cannot_escalate(self):
        status,job=self.create(headers={"X-Caller-Tenant":"tenant-b"})
        self.assertEqual(status,202)
        self.assertEqual(self.store.jobs[job["id"]]["tenant"],"tenant-a")

    def test_worker_executes_once_even_when_retried(self):
        _,job=self.create()
        body=json.dumps({"job_id":job["id"]}).encode()
        for outcome in ("SUCCEEDED","ALREADY_APPLIED"):
            status,result=self.call("POST","/internal/tasks/"+job["id"],"worker",body)
            self.assertEqual(status,200)
            self.assertEqual(result["outcome"],outcome)
        self.assertEqual(self.store.effects,{job["id"]:7})

    def test_worker_cannot_change_job_id(self):
        _,job=self.create()
        body=json.dumps({"job_id":str(uuid.uuid4())}).encode()
        self.assertEqual(self.call("POST","/internal/tasks/"+job["id"],"worker",body)[0],400)
        self.assertEqual(self.store.effects,{})

    def test_absent_task_fails_closed(self):
        new_id=str(uuid.uuid4())
        body=json.dumps({"job_id":new_id}).encode()
        self.assertEqual(self.call("POST","/internal/tasks/"+new_id,"worker",body)[0],400)
        self.assertEqual(self.store.effects,{})

    def test_duplicate_json_keys_rejected(self):
        self.assertEqual(self.create(body=b'{"value":1,"value":2}')[0],400)
        self.assertEqual(self.store.jobs,{})

    def test_boolean_rejected(self):
        self.assertEqual(self.create(body=b'{"value":true}')[0],400)

    def test_idempotency_collision_and_replay(self):
        first=self.create()
        same=self.create()
        self.assertEqual(first[1]["id"],same[1]["id"])
        self.assertEqual(self.create(body=b'{"value":9}')[0],409)
        self.assertEqual(len(self.store.jobs),1)

    def test_failed_store_does_not_claim_acceptance(self):
        self.store.fault=True
        self.assertEqual(self.create()[0],503)
        self.assertEqual(self.store.jobs,{})

    def test_wrong_role_disallowed_dispatch(self):
        self.assertEqual(self.call("POST","/internal/dispatch","worker")[0],401)

    def test_health_scope_is_not_database_reliability(self):
        self.assertEqual(self.call("GET","/health/live")[0],200)
        self.assertEqual(self.call("GET","/health/ready")[0],200)
        self.store.fault=True
        self.assertEqual(self.call("GET","/health/ready")[0],503)


class LeaseAndPolicyTests(unittest.TestCase):
    def test_required_policy_configuration(self):
        with self.assertRaises(ValueError):
            IdentityPolicy("",{},TASK,DISPATCH)
        with self.assertRaises(ValueError):
            IdentityPolicy(AUD,{},TASK,TASK)

    def test_signed_claims_are_not_accepted_without_verification(self):
        policy=IdentityPolicy(AUD,{},TASK,DISPATCH,verifier=lambda _t,_a:{"email":TASK})
        with self.assertRaises(IdentityRejected):
            policy.authorize("Bearer dummy","execute")

    def test_reject_unsupported_uuid(self):
        with self.assertRaises(ValueError):
            task_name("projects/p/locations/r/queues/q","arbitrary")

    def test_deterministic_task_identity(self):
        job=str(uuid.uuid4())
        p="projects/p/locations/r/queues/q"
        self.assertEqual(task_name(p,job),task_name(p,job))
        self.assertTrue(task_name(p,job).endswith("/tasks/job-"+job))

    def test_dispatch_recovers_transient_enqueue_failure(self):
        class Leases:
            def __init__(self):
                self.acked=[]
                self.released=[]
            def claim(self,limit):
                return [{"job_id":"id1","lease_token":"token1"}]
            def mark_enqueued(self,id,token):
                self.acked.append((id,token))
                return True
            def release_claim(self,id,token,error):
                self.released.append((id,token,error))
        store=Leases()
        publisher=FakeDispatcher()
        publisher.fail=True
        self.assertEqual(dispatch_batch(store,publisher)[0]["delivery"],"FAILED")
        self.assertEqual(len(store.released),1)
        publisher.fail=False
        self.assertEqual(dispatch_batch(store,publisher)[0]["delivery"],"CREATED")
        self.assertEqual(store.acked,[("id1","token1")])


if __name__=="__main__":
    unittest.main()
