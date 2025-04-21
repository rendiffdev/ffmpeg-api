from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.schemas import TranscodeReq, QualityReq, JobResp, JobStatusResp
from app.engine import transcode, measure_quality
from app.jobs import jobs, Job, JobStatus
from app.auth import get_current_user
from app.utils.s3_utils import fetch, upload
import uuid, time

router = APIRouter(prefix="/api/v1/video", dependencies=[Depends(get_current_user)])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/transcode", response_model=JobResp)
def api_transcode(req: TranscodeReq, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex
    job = Job(job_id); jobs[job_id]=job
    def run_job():
        job.status = JobStatus.RUNNING; job.start_time = time.time()
        try:
            in_path = fetch(req.input)
            out_path = req.output.local_path or f"/tmp/{job_id}_out.{req.output.s3_path.split('.')[-1]}"
            transcode(in_path, out_path, req.codec, req.crf, req.preset)
            upload(out_path, req.output)
            job.log = f"Encoded to {out_path}"; job.status = JobStatus.SUCCESS
        except Exception as e:
            job.error = str(e); job.status = JobStatus.FAILED
        finally:
            job.end_time = time.time()
    background_tasks.add_task(run_job)
    return {"job_id": job_id}

@router.get("/jobs/{job_id}", response_model=JobStatusResp)
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job: raise HTTPException(404, "Job not found")
    return job.to_dict()

@router.post("/quality")
def api_quality(req: QualityReq):
    ref = fetch(req.reference); dist = fetch(req.distorted)
    return measure_quality(ref, dist, req.metrics)