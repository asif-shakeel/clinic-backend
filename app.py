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
import pandas as pd
from analysis_registry import ANALYSES



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
    allow_methods=["*"],
    allow_headers=["*"],
)


DATA_DIR = "/tmp/data"
OUT_DIR = "/tmp/output"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


@app.post("/upload")
def upload_csv(
    analysis_key: str,
    file_role: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
):
    # 1. validate analysis
    if analysis_key not in ANALYSES:
        raise HTTPException(status_code=400, detail="Unknown analysis")

    analysis = ANALYSES[analysis_key]

    # 2. validate file role
    if file_role not in analysis["files"]:
        raise HTTPException(status_code=400, detail="Invalid file role")

    # 3. read csv + normalize columns
    df = pd.read_csv(file.file)
    df.columns = [c.lower() for c in df.columns]

    # 4. validate required columns
    required = [
        c.lower()
        for c in analysis["files"][file_role]["required_columns"]
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing}",
        )

    # 5. save normalized csv
    os.makedirs("/tmp", exist_ok=True)
    tmp_path = f"/tmp/{file_role}.csv"
    df.to_csv(tmp_path, index=False)

    # 6. upload to storage
    remote_path = f"raw/{user_id}/{analysis_key}/{file_role}.csv"
    upload_file(tmp_path, remote_path)

    return {
        "status": "uploaded",
        "analysis": analysis_key,
        "file_role": file_role,
    }



@app.post("/analyze")
def analyze(
    analysis_key: str,
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

    if analysis_key not in ANALYSES:
        raise HTTPException(status_code=400, detail="Unknown analysis")

    analysis = ANALYSES[analysis_key]

    try:
        # clean output dir per job
        for f in os.listdir(OUT_DIR):
            os.remove(os.path.join(OUT_DIR, f))

        # ensure inputs exist locally
        os.makedirs(DATA_DIR, exist_ok=True)

        required_files = [
            f"{role}.csv"
            for role in ANALYSES[analysis_key]["files"].keys()
        ]


        if not required_files:
            raise HTTPException(status_code=400, detail="Unknown analysis type")

        missing = []

        for fname in required_files:
            try:
                download_file(
                    f"raw/{user_id}/{analysis_key}/{fname}",
                    os.path.join(DATA_DIR, fname),
                )
            except Exception:
                missing.append(fname)

        if missing:
            supabase.table("analysis_jobs").update({
                "status": "failed",
                "error": f"Missing required files: {', '.join(missing)}",
                "finished_at": datetime.utcnow().isoformat(),
            }).eq("id", job_id).execute()

            return {
                "job_id": job_id,
                "error": f"Missing required files: {', '.join(missing)}",
            }



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

from analysis_registry import ANALYSES

@app.get("/analyses")
def list_analyses():
    """
    Public, read-only endpoint that exposes
    available analyses and their file requirements.
    """

    def normalize(col: str) -> str:
        return (
            col.strip()
               .lower()
               .replace(" ", "_")
               .replace("-", "_")
        )

    out = {}

    for analysis_key, analysis in ANALYSES.items():
        out[analysis_key] = {
            "label": analysis["label"],
            "files": {}
        }

        for role, cfg in analysis["files"].items():
            out[analysis_key]["files"][role] = {
                "required_columns": [
                    normalize(c) for c in cfg["required_columns"]
                ]
            }

    return out
