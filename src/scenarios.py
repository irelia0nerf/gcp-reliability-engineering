"""R01-R08 local-only failure simulations; no cloud availability claims."""
import argparse
import datetime as dt
import json
import os
import sqlite3
import tempfile
import time
import uuid

from src.atlas import Atlas, Unavailable


class BoundedPoison:
    def __init__(self, database, limit=3):
        self.database, self.limit = database, limit
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS poison (id TEXT PRIMARY KEY, attempts INTEGER NOT NULL, status TEXT NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO poison VALUES ('p1', 0, 'PENDING')")

    def attempt(self):
        with sqlite3.connect(self.database) as connection:
            attempts, state = connection.execute("SELECT attempts, status FROM poison WHERE id='p1'").fetchone()
            if state == "FAILED":
                return {"attempts": attempts, "status": state}
            attempts += 1
            state = "FAILED" if attempts >= self.limit else "RETRY"
            connection.execute("UPDATE poison SET attempts=?, status=? WHERE id='p1'", (attempts, state))
            return {"attempts": attempts, "status": state}


def run(scenario):
    if scenario not in {f"R{i:02d}" for i in range(1, 9)}:
        raise ValueError("unknown scenario")
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with tempfile.TemporaryDirectory() as directory:
        store = Atlas(os.path.join(directory, "state.sqlite"))
        before = store.snapshot()
        events, latencies = [], []
        job_id = None
        if scenario == "R05":
            try:
                store.admit("A", "k", 7, storage_available=False)
            except Unavailable:
                events.append("admission_refused")
        elif scenario == "R06":
            poison = BoundedPoison(os.path.join(directory, "poison.sqlite"))
            events = [poison.attempt() for _ in range(5)]
        elif scenario == "R07":
            for index in range(50):
                start = time.perf_counter()
                item = store.admit("A", f"burst-{index}", index)
                store.process(item["id"])
                latencies.append((time.perf_counter() - start) * 1000)
            events.append("sequential_synthetic_burst_not_autoscaling")
        else:
            item = store.admit("A", "k", 7)
            job_id = item["id"]
            if scenario in ("R02", "R08"):
                try:
                    store.process(job_id, fault="before_commit")
                except Unavailable:
                    events.append("precommit_failure")
                if scenario == "R08":
                    events.append("local_rollback_simulation_not_a_CI_deployment")
            elif scenario == "R04":
                try:
                    store.process(job_id, fault="after_commit")
                except Unavailable:
                    events.append("lost_ACK_after_commit")
            store.process(job_id)
            if scenario == "R03":
                store.process(job_id)
                events.append("duplicate_delivery")
        after = store.snapshot()
        expected = 0 if scenario in ("R05", "R06") else 50 if scenario == "R07" else 1
        passed = after["effects"] == expected
        if scenario == "R06":
            passed = passed and events[-1] == {"attempts": 3, "status": "FAILED"}
        return {"schema_version": "1.0", "run_id": str(uuid.uuid4()), "scenario_id": scenario,
                "started_at": started, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "environment": "LOCAL_SQLITE", "evidence_level": "SIMULATED", "before": before,
                "after": after, "job_id": job_id, "events": events,
                "business_mutations": after["effects"] - before["effects"],
                "p95_ms": sorted(latencies)[int(.95 * (len(latencies)-1))] if latencies else None,
                "passed": bool(passed),
                "limitations": ["No real GCP failure, throughput validation, or deployment rollback"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=[f"R{i:02d}" for i in range(1,9)] + ["all"], required=True)
    scenario = parser.parse_args().scenario
    result = [run(f"R{i:02d}") for i in range(1,9)] if scenario == "all" else run(scenario)
    print(json.dumps(result, indent=2))
    if not all(x["passed"] for x in result) if isinstance(result, list) else not result["passed"]:
        raise SystemExit(1)
