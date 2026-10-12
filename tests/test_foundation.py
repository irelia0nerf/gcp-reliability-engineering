"""Security and adversarial HTTP tests for the local-only simulator."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from src.atlas import Atlas
from src.auth import AuthenticationError, LabAuthority
from src.http_api import make_server
from src.scenarios import BoundedPoison, run

class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Atlas(os.path.join(self.temp.name, "db.sqlite"))
        self.authority = LabAuthority()
        self.server = make_server(self.store, self.authority)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.token_a = self.authority.issue_for_test("alice", "A", ["jobs:create","jobs:read"])
        self.token_b = self.authority.issue_for_test("bob", "B", ["jobs:create","jobs:read"])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, token=None, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        hs = dict(headers or {})
        if token is not None:
            hs["Authorization"] = "Bearer " + token
        if body is not None:
            hs.setdefault("Content-Type", "application/json")
            hs.setdefault("Idempotency-Key", "k")
        conn.request(method, path, body=body, headers=hs)
        response = conn.getresponse()
        code, data = response.status, json.loads(response.read())
        conn.close()
        return code, data

    def test_anonymous_write_denied_no_effect(self):
        before = self.store.snapshot()
        self.assertEqual(self.request("POST", "/v1/jobs", body=b'{"value":1}')[0], 401)
        self.assertEqual(self.store.snapshot(), before)

    def test_spoofed_tenant_header_ignored(self):
        code, job = self.request("POST", "/v1/jobs", token=self.token_a, body=b'{"value":1}', headers={"X-Demo-Tenant":"B"})
        self.assertEqual(code, 202)
        self.assertEqual(self.store.get("A",job["id"])["status"], "ACCEPTED")
        self.assertEqual(self.request("GET",f"/v1/jobs/{job['id']}",token=self.token_b)[0],404)

    def test_mutated_token_denied(self):
        forged = self.token_a[:-2] + ("xx" if self.token_a[-2:] != "xx" else "yy")
        before = self.store.snapshot()
        self.assertEqual(self.request("POST", "/v1/jobs", token=forged, body=b'{"value":1}')[0],401)
        self.assertEqual(self.store.snapshot(), before)

    def test_expired_token(self):
        token = self.authority.issue_for_test("a","A",["jobs:create"],expires_in=0,now=int(time.time())-2)
        with self.assertRaises(AuthenticationError):
            self.authority.verify("Bearer "+token,"jobs:create")

    def test_read_scope_cannot_write(self):
        token = self.authority.issue_for_test("a","A",["jobs:read"])
        self.assertEqual(self.request("POST","/v1/jobs",token=token,body=b'{"value":1}')[0],401)
        self.assertEqual(self.store.snapshot()["jobs"],0)

    def test_reject_duplicate_json_keys(self):
        self.assertEqual(self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":1,"value":2}')[0],400)
        self.assertEqual(self.store.snapshot()["jobs"],0)

    def test_reject_boolean(self):
        self.assertEqual(self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":true}')[0],400)

    def test_reject_empty_idempotency_key(self):
        self.assertEqual(self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":1}',headers={"Idempotency-Key":""})[0],400)

    def test_http_replay_collision(self):
        _, job = self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":1}')
        self.assertEqual(self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":1}')[1]["id"],job["id"])
        self.assertEqual(self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":2}')[0],409)
        self.assertEqual(self.store.snapshot()["jobs"],1)

    def test_health_and_private_reads(self):
        self.assertEqual(self.request("GET","/health/live")[0],200)
        self.assertEqual(self.request("GET","/health/ready")[0],200)
        self.assertEqual(self.request("GET","/v1/jobs/arbitrary")[0],401)

    def test_external_bind_rejected(self):
        with self.assertRaises(ValueError):
            make_server(self.store,self.authority,host="0.0.0.0")

    def test_eight_scenarios(self):
        for number in range(1,9):
            with self.subTest(number=number):
                proof=run(f"R{number:02d}")
                self.assertTrue(proof["passed"],proof)
                self.assertEqual(proof["evidence_level"],"SIMULATED")

    def test_bounded_poison(self):
        poison=BoundedPoison(os.path.join(self.temp.name,"poison.sqlite"))
        outcome=None
        for _ in range(10):
            outcome=poison.attempt()
        self.assertEqual(outcome,{"attempts":3,"status":"FAILED"})

    def test_isolate_same_key_across_tenants(self):
        a=self.request("POST","/v1/jobs",token=self.token_a,body=b'{"value":1}')[1]
        b=self.request("POST","/v1/jobs",token=self.token_b,body=b'{"value":2}')[1]
        self.assertNotEqual(a["id"],b["id"])
        self.assertEqual(self.request("GET",f"/v1/jobs/{a['id']}",token=self.token_b)[0],404)
