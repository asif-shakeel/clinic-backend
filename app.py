import os
import shutil
from fastapi import FastAPI, UploadFile, File

from analysis_engine import run_analysis
from b2_storage import upload_file, download_file, generate_signed_url, delete_file
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
from auth import get_user_id
from supabase_client import supabase
from datetime import datetime
from fastapi import HTTPException
import pandas as pd
from analysis_registry import ANALYSES
from fastapi import Body
from column_normalization import normalize_list, normalize_columns





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
    print("UPLOAD HIT", file.filename, user_id)

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


    result = supabase.table("user_files").insert({
        "user_id": user_id,
        "filename": file.filename or "uploaded.csv",
        "storage_path": remote_path,
        "detected_columns": list(df.columns),
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to record uploaded file"
        )

    return {
        "status": "uploaded",
        "file_id": result.data[0]["id"],
        "filename": file.filename,
    }



@app.post("/analyze")
def analyze(
    analysis_key: str = None,
    start_date: str = None,
    end_date: str = None,
    body: dict = Body(default=None),
    user_id: str = Depends(get_user_id),
):
    # Support both query params (old) and JSON body (new)
    if body:
        analysis_key = body.get("analysis_key", analysis_key)
        start_date = body.get("start_date", start_date)
        end_date = body.get("end_date", end_date)
        selected_files = body.get("files")
    else:
        selected_files = None

    if not analysis_key or analysis_key not in ANALYSES:
        raise HTTPException(status_code=400, detail="Unknown analysis")
    
    # 1. create job
    job = supabase.table("analysis_jobs").insert({
        "user_id": user_id,
        "status": "running",
        "start_date": start_date,
        "end_date": end_date,
    }).execute()

    job_id = job.data[0]["id"]



    analysis = ANALYSES[analysis_key]

    try:
        # clean output dir per job
        for f in os.listdir(OUT_DIR):
            os.remove(os.path.join(OUT_DIR, f))

        # ensure inputs exist locally
        os.makedirs(DATA_DIR, exist_ok=True)

        required_roles = set(ANALYSES[analysis_key]["files"].keys())

        if not selected_files:
            raise HTTPException(400, "No files selected")

        missing_roles = [
            r for r in required_roles
            if r not in selected_files or not selected_files[r]
        ]

        if missing_roles:
            raise HTTPException(
                400,
                f"Missing files for roles: {missing_roles}"
            )

        # now download files (guaranteed to exist)
        for role, file_id in selected_files.items():
            row = (
                supabase
                .table("user_files")
                .select("storage_path")
                .eq("id", file_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            download_file(
                row.data["storage_path"],
                os.path.join(DATA_DIR, f"{role}.csv"),
            )

        analysis = ANALYSES[analysis_key]

        for role, cfg in analysis["files"].items():
            path = os.path.join(DATA_DIR, f"{role}.csv")

            if not os.path.exists(path):
                raise HTTPException(400, f"Missing file for role: {role}")

            df = pd.read_csv(path)
            df = normalize_columns(df)

            required = normalize_list(cfg["required_columns"])
            missing = [c for c in required if c not in df.columns]

            if missing:
                supabase.table("analysis_jobs").update({
                    "status": "failed",
                    "error": f"{role} missing columns: {missing}",
                    "finished_at": datetime.utcnow().isoformat(),
                }).eq("id", job_id).execute()

                return {
                    "job_id": job_id,
                    "error": f"{role} missing columns: {missing}",
                }

        # run analysis ONCE
        try:
            run_analysis(
                analysis_key,
                DATA_DIR,
                OUT_DIR,
                start_date=start_date,
                end_date=end_date,
            )

        except Exception as e:
            supabase.table("analysis_jobs").update({
                "status": "failed",
                "error": str(e),
                "finished_at": datetime.utcnow().isoformat(),
            }).eq("id", job_id).execute()

            raise HTTPException(status_code=400, detail=str(e))



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
@app.get("/files")
def list_files(user_id: str = Depends(get_user_id)):
    res = (
        supabase
        .table("user_files")
        .select("id, filename, detected_columns, uploaded_at")
        .eq("user_id", user_id)
        .order("uploaded_at", desc=True)
        .limit(10)
        .execute()
    )
    return res.data



@app.post("/upload_file")
def upload_file_generic(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
):
    df = pd.read_csv(file.file)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    tmp_path = f"/tmp/{file.filename}"
    df.to_csv(tmp_path, index=False)

    storage_path = f"raw/{user_id}/files/{file.filename}"
    upload_file(tmp_path, storage_path)

    supabase.table("user_files").insert({
        "user_id": user_id,
        "filename": file.filename,
        "storage_path": storage_path,
        "detected_columns": list(df.columns),
    }).execute()

    return {"status": "uploaded"}

@app.delete("/files/{file_id}")
def delete_file_endpoint(
    file_id: str,
    user_id: str = Depends(get_user_id),
):
    row = (
        supabase
        .table("user_files")
        .select("storage_path")
        .eq("id", file_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not row.data:
        raise HTTPException(status_code=404)

    delete_file(row.data["storage_path"])

    supabase.table("user_files").delete().eq("id", file_id).execute()

    return {"status": "deleted"}
