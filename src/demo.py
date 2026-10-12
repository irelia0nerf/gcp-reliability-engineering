"""Reproducible local simulation, not proof of GCP resilience."""
import argparse
import datetime
import json
import os
import tempfile
import uuid
from src.atlas import Atlas, Unavailable
def run(scenario):
    with tempfile.TemporaryDirectory() as d:
        a=Atlas(os.path.join(d,"lab.sqlite"))
        before=a.snapshot(); started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        job=None
        try:
            if scenario=="R05": a.admit("demo","key",5,storage_available=False)
            else:
                job=a.admit("demo","key",5)
                if scenario=="R02":
                    try:a.process(job["id"],fault="before_commit")
                    except Unavailable:pass
                    a.process(job["id"])
                elif scenario=="R04":
                    try:a.process(job["id"],fault="after_commit")
                    except Unavailable:pass
                    a.process(job["id"])
                elif scenario=="R03":a.process(job["id"]);a.process(job["id"])
                else:a.process(job["id"])
        except Unavailable:pass
        after=a.snapshot()
        return {"run_id":str(uuid.uuid4()),"scenario_id":scenario,"started_at":started,
            "finished_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "environment":"LOCAL_SQLITE","evidence_level":"SIMULATED",
            "before":before,"after":after,"job_id":job["id"] if job else None,
            "pass":after["effects"]==(0 if scenario=="R05" else 1),
            "limitations":["No Google Cloud deployment or regional-failure validation"]}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--scenario",choices=["R01","R02","R03","R04","R05"],required=True)
    print(json.dumps(run(parser.parse_args().scenario),indent=2))
