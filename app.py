import os
import shutil
from fastapi import FastAPI, UploadFile, File

from analysis_engine import run_analysis
from b2_storage import upload_file, download_file, generate_signed_url
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
from auth import get_user_id
from supabase_client import supabase
from datetime import datetime
from fastapi import HTTPException

app = FastAPI()

ALLOWED_ORIGINS = [
    "https://incidentreportshub.com",
    "https://www.incidentreportshub.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

DATA_DIR = "/tmp/data"
OUT_DIR = "/tmp/output"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


@app.post("/upload")
def upload_csv(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id)
):
    local_path = f"/tmp/{file.filename}"

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    upload_file(local_path, f"raw/{file.filename}")

    return {"status": "uploaded", "filename": file.filename}


@app.post("/analyze")
def analyze(
    start_date: str = None,
    end_date: str = None,
    user_id: str = Depends(get_user_id),
):
    # 1. create job
    job = supabase.table("analysis_jobs").insert({
        "user_id": user_id,
        "status": "running",
        "start_date": start_date,
        "end_date": end_date,
    }).execute()

    job_id = job.data[0]["id"]

    try:
        # clean output dir per job
        for f in os.listdir(OUT_DIR):
            os.remove(os.path.join(OUT_DIR, f))

        # ensure inputs exist locally
        os.makedirs(DATA_DIR, exist_ok=True)
        for fname in ["patients.csv", "visits.csv", "metrics.csv"]:
            download_file(f"raw/{fname}", os.path.join(DATA_DIR, fname))

        # run analysis ONCE
        run_analysis(
            DATA_DIR,
            OUT_DIR,
            start_date=start_date,
            end_date=end_date,
        )

        # upload results
        job_prefix = f"results/{job_id}"
        uploaded_files = []

        for fname in os.listdir(OUT_DIR):
            upload_file(
                os.path.join(OUT_DIR, fname),
                f"{job_prefix}/{fname}",
            )
            uploaded_files.append(fname)

        # mark complete
        supabase.table("analysis_jobs").update({
            "status": "completed",
            "finished_at": datetime.utcnow().isoformat(),
            "result_files": uploaded_files,
        }).eq("id", job_id).execute()

        return {"job_id": job_id}

    except Exception as e:
        # 4. mark failed
        supabase.table("analysis_jobs").update({
            "status": "failed",
            "error": str(e),
            "finished_at": datetime.utcnow().isoformat(),
        }).eq("id", job_id).execute()

        raise



@app.get("/jobs")
def list_jobs(user_id: str = Depends(get_user_id)):
    res = (
        supabase
        .table("analysis_jobs")
        .select(
            "id,status,start_date,end_date,created_at,finished_at,error,result_files"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return res.data

@app.get("/jobs/{job_id}/download/{filename}")
def download_result(
    job_id: str,
    filename: str,
    user_id: str = Depends(get_user_id),
):
    # ownership check
    job = (
        supabase.table("analysis_jobs")
        .select("id")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not job.data:
        raise HTTPException(status_code=404)

    path = f"results/{job_id}/{filename}"
    return {"url": generate_signed_url(path)}

