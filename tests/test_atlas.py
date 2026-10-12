import os
import tempfile
import threading
import unittest
from src.atlas import Atlas, Unavailable, Conflict, Forbidden

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.a=Atlas(os.path.join(self.temp.name,"lab.sqlite"))
    def tearDown(self): self.temp.cleanup()
    def test_R01_baseline(self):
        j=self.a.admit("A","key",5)
        self.assertEqual(self.a.process(j["id"]),"SUCCEEDED")
        self.assertEqual(self.a.snapshot()["value_total"],5)
    def test_R02_crash_before_commit(self):
        j=self.a.admit("A","key",5)
        with self.assertRaises(Unavailable): self.a.process(j["id"],fault="before_commit")
        self.assertEqual(self.a.snapshot()["effects"],0)
        self.a.process(j["id"])
        self.assertEqual(self.a.snapshot()["effects"],1)
    def test_R03_duplicate_delivery(self):
        j=self.a.admit("A","key",5)
        self.a.process(j["id"]); self.a.process(j["id"])
        self.assertEqual(self.a.snapshot()["effects"],1)
    def test_R04_lost_ack_after_commit(self):
        j=self.a.admit("A","key",5)
        with self.assertRaises(Unavailable):self.a.process(j["id"],fault="after_commit")
        self.assertEqual(self.a.get("A",j["id"])["status"],"SUCCEEDED")
        self.assertEqual(self.a.process(j["id"]),"ALREADY_APPLIED")
        self.assertEqual(self.a.snapshot()["effects"],1)
    def test_R05_storage_unavailable(self):
        with self.assertRaises(Unavailable): self.a.admit("A","key",5,storage_available=False)
        self.assertEqual(self.a.snapshot()["jobs"],0)
    def test_R06_pending_reconciliation(self):
        j=self.a.admit("A","key",5)
        self.assertEqual(self.a.pending(),[j["id"]])
        self.a.process(j["id"])
        self.assertEqual(self.a.pending(),[])
    def test_R07_synthetic_burst(self):
        for n in range(30):
            j=self.a.admit("A",str(n),n)
            self.a.process(j["id"])
        self.assertEqual(self.a.snapshot()["effects"],30)
    def test_R08_failed_revision_simulation(self):
        j=self.a.admit("A","key",5)
        before=self.a.snapshot()
        with self.assertRaises(Unavailable):self.a.process(j["id"],fault="before_commit")
        self.assertEqual(self.a.snapshot(),before)
    def test_tenant_isolation(self):
        j=self.a.admit("A","key",5)
        with self.assertRaises(Forbidden): self.a.get("B",j["id"])
    def test_conflicting_idempotency(self):
        self.a.admit("A","key",5)
        with self.assertRaises(Conflict):self.a.admit("A","key",6)
    def test_same_admission_key(self):
        j=self.a.admit("A","key",5)
        self.assertEqual(j["id"],self.a.admit("A","key",5)["id"])
        self.assertEqual(self.a.snapshot()["jobs"],1)
    def test_concurrent_duplicate_workers(self):
        j=self.a.admit("A","key",5)
        failures=[]
        def go():
            try:self.a.process(j["id"])
            except Exception as exc: failures.append(str(exc))
        workers=[threading.Thread(target=go) for _ in range(8)]
        for w in workers:w.start()
        for w in workers:w.join()
        self.assertEqual(failures,[])
        self.assertEqual(self.a.snapshot()["effects"],1)
    def test_reopen_database(self):
        j=self.a.admit("A","key",5)
        Atlas(self.a.database).process(j["id"])
        self.assertEqual(Atlas(self.a.database).snapshot()["effects"],1)
    def test_reject_boolean_value(self):
        with self.assertRaises(ValueError): self.a.admit("A","key",True)
if __name__=="__main__": unittest.main()
