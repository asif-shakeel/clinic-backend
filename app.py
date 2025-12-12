import os
import shutil
from fastapi import FastAPI, UploadFile, File

from analysis_engine import run_analysis
from b2_storage import upload_file, download_file


app = FastAPI()

DATA_DIR = "/tmp/data"
OUT_DIR = "/tmp/output"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


@app.post("/upload")
def upload_csv(file: UploadFile = File(...)):
    local_path = f"/tmp/{file.filename}"

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    upload_file(local_path, f"raw/{file.filename}")

    return {"status": "uploaded", "filename": file.filename}


@app.post("/analyze")
def analyze(start_date: str = None, end_date: str = None):
    for name in ["patients.csv", "visits.csv", "metrics.csv"]:
        download_file(f"raw/{name}", f"{DATA_DIR}/{name}")

    return run_analysis(
        DATA_DIR,
        OUT_DIR,
        start_date=start_date,
        end_date=end_date
    )
