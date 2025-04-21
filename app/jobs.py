from enum import Enum
import time

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.status = JobStatus.PENDING
        self.log = ""
        self.error = ""
        self.start_time = None
        self.end_time = None

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "log": self.log,
            "error": self.error,
            "time_taken": (self.end_time - self.start_time) if self.end_time and self.start_time else None
        }

jobs = {}