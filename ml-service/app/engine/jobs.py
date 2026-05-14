import uuid
import time
from typing import Dict, Any, Optional

class JobManager:
    def __init__(self):
        # job_id -> { "status": "running/done/error/cancelled", "progress": 0.0, "stage": "", "result": None, "error": None }
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "status": "running",
            "progress": 0.0,
            "stage": "starting",
            "start_time": time.time(),
            "result": None,
            "error": None
        }
        return job_id

    def update_job(self, job_id: str, progress: float, stage: str):
        if job_id in self.jobs and self.jobs[job_id]["status"] == "running":
            self.jobs[job_id]["progress"] = progress
            self.jobs[job_id]["stage"] = stage

    def finish_job(self, job_id: str, result: Any):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "done"
            self.jobs[job_id]["progress"] = 1.0
            self.jobs[job_id]["stage"] = "completed"
            self.jobs[job_id]["result"] = result
            self.jobs[job_id]["end_time"] = time.time()
            self.jobs[job_id]["duration"] = self.jobs[job_id]["end_time"] - self.jobs[job_id]["start_time"]

    def fail_job(self, job_id: str, error: str):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "error"
            self.jobs[job_id]["error"] = error
            self.jobs[job_id]["stage"] = "failed"

    def cancel_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "cancelled"
            self.jobs[job_id]["stage"] = "aborted"

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        return job is not None and job["status"] == "cancelled"

# Global instance
job_manager = JobManager()
