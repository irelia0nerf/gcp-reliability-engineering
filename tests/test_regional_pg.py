"""PostgreSQL contract tests; require disposable database ATLAS_TEST_PG_DSN."""
import os
import unittest
import uuid

from regional.store import Collision, Missing, PgStore

DSN=os.getenv("ATLAS_TEST_PG_DSN")


@unittest.skipUnless(DSN,"Requires isolated Postgres service and ATLAS_TEST_PG_DSN")
class PgContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=PgStore(DSN)
        cls.store.bootstrap()

    def setUp(self):
        with self.store.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE atlas_outbox,atlas_effects,atlas_jobs CASCADE")

    def test_admission_outbox_and_effect_single_transaction(self):
        a=self.store.admit("A","alice","key1",7)
        self.assertTrue(a["created"])
        self.assertEqual(self.store.stats(),{"jobs":1,"effects":0,"value_total":0,"pending_outbox":1})
        b=self.store.admit("A","alice","key1",7)
        self.assertEqual(b["id"],a["id"])
        self.assertFalse(b["created"])
        with self.assertRaises(Collision):
            self.store.admit("A","alice","key1",8)
        self.assertEqual(self.store.apply_effect(a["id"]),"SUCCEEDED")
        self.assertEqual(self.store.apply_effect(a["id"]),"ALREADY_APPLIED")
        self.assertEqual(self.store.stats()["effects"],1)
        self.assertEqual(self.store.stats()["value_total"],7)

    def test_identity_and_tenant_scope(self):
        a=self.store.admit("A","alice","same",1)
        b=self.store.admit("B","bob","same",2)
        self.assertNotEqual(a["id"],b["id"])
        with self.assertRaises(Missing):
            self.store.get("B","alice",a["id"])
        with self.assertRaises(Missing):
            self.store.get("A","bob",a["id"])
        self.assertEqual(self.store.get("A","alice",a["id"])["status"],"ACCEPTED")

    def test_lease_expiry_fencing_and_success(self):
        j=self.store.admit("A","alice","k",1)["id"]
        lease=self.store.claim(limit=1)[0]
        self.assertEqual(lease["job_id"],j)
        self.assertEqual(self.store.claim(limit=1),[])
        self.assertFalse(self.store.mark_enqueued(j,str(uuid.uuid4())))
        self.assertTrue(self.store.mark_enqueued(j,lease["lease_token"]))
        self.assertEqual(self.store.stats()["pending_outbox"],0)
        self.assertFalse(self.store.release_claim(j,lease["lease_token"],"late"))

    def test_release_failed_lease_for_retry(self):
        j=self.store.admit("A","alice","k",1)["id"]
        lease=self.store.claim(limit=1)[0]
        self.assertTrue(self.store.release_claim(j,lease["lease_token"],"transport"))
        nxt=self.store.claim(limit=1)[0]
        self.assertEqual(nxt["job_id"],j)
        self.assertNotEqual(nxt["lease_token"],lease["lease_token"])

    def test_reject_invalid_values(self):
        with self.assertRaises(ValueError):
            self.store.admit("A","alice","key",True)
        with self.assertRaises(ValueError):
            self.store.admit("A","alice","key",1000001)
        self.assertEqual(self.store.stats()["jobs"],0)

    def test_ping(self):
        self.assertTrue(self.store.ping())


if __name__=="__main__":
    unittest.main()
