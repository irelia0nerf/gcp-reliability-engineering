"""Cloud Tasks publisher: stable task name for deduplication of enqueue retries."""
import json
import re


class PublishFailed(Exception):
    pass


def task_name(queue_path, job_id):
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",job_id):
        raise ValueError("invalid job UUID")
    return queue_path + "/tasks/job-" + job_id


class CloudTasksPublisher:
    def __init__(self, project, region, queue, service_url, service_account, client=None):
        if not all((project,region,queue,service_url,service_account)):
            raise ValueError("publisher configuration required")
        if not service_url.startswith("https://"):
            raise ValueError("HTTPS service URL required")
        if not service_account.endswith(".gserviceaccount.com"):
            raise ValueError("service account email required")
        if client is None:
            from google.cloud import tasks_v2
            client = tasks_v2.CloudTasksClient()
        self.client=client
        self.parent=self.client.queue_path(project,region,queue)
        self.service_url=service_url.rstrip("/")
        self.service_account=service_account

    def publish(self, job_id):
        from google.api_core.exceptions import AlreadyExists
        name=task_name(self.parent,job_id)
        task={"name":name,"http_request":{
            "http_method":"POST",
            "url":self.service_url+"/internal/tasks/"+job_id,
            "headers":{"Content-Type":"application/json"},
            "body":json.dumps({"job_id":job_id},separators=(",",":")).encode(),
            "oidc_token":{
                "service_account_email":self.service_account,
                "audience":self.service_url,
            },
        }}
        try:
            self.client.create_task(request={"parent":self.parent,"task":task})
            return "CREATED"
        except AlreadyExists:
            # Stable name: enqueue-retry ACK ambiguity; does not imply delivery.
            return "ALREADY_EXISTS"


def dispatch_batch(store,publisher,limit=10):
    """Persisted leases; expired leases permit recovery after dispatcher crash."""
    outcomes=[]
    for lease in store.claim(limit):
        try:
            result=publisher.publish(lease["job_id"])
            done=store.mark_enqueued(lease["job_id"],lease["lease_token"])
            outcomes.append({"job_id":lease["job_id"],"delivery":result,
                             "lease_ack":done})
        except Exception as exc:
            store.release_claim(lease["job_id"],lease["lease_token"],type(exc).__name__)
            outcomes.append({"job_id":lease["job_id"],"delivery":"FAILED"})
    return outcomes
