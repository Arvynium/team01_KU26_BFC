from __future__ import annotations

import os
import re
import shutil
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

WORK_ROOT = Path(os.getenv("PACKAGE_WORK_ROOT", "/work/packages"))
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
ARTIFACT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
DOCUMENTS = {
    "pickup": "pickup-sheet.txt",
    "equipment": "equipment-list.txt",
    "handover": "handover-instructions.txt",
}
JOBS: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    (WORK_ROOT.parent / "dispatch-code.txt").write_text(
        os.environ["LAB_COMMAND_FLAG"] + "\n", encoding="utf-8"
    )
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _job_dir(job_id: str) -> Path | None:
    return WORK_ROOT / job_id if JOB_ID_PATTERN.fullmatch(job_id) else None


def _public_job(job: dict) -> dict:
    return {key: job[key] for key in ("jobId", "name", "status", "documents", "createdAt")}


@app.get("/health")
async def health():
    return {"status": "ready"}


@app.post("/batches")
async def save_batch(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    name = body.get("name")
    documents = body.get("documents")
    items = body.get("items")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(char) < 32 for char in name):
        return JSONResponse({"error": "Enter a bundle name of up to 80 characters."}, status_code=400)
    if not isinstance(documents, list) or not documents or any(not isinstance(item, str) or item not in DOCUMENTS for item in documents) or len(documents) != len(set(documents)):
        return JSONResponse({"error": "Choose at least one document."}, status_code=400)
    if not isinstance(items, list) or len(items) > 30 or any(not isinstance(item, dict) or not isinstance(item.get("title"), str) for item in items):
        return JSONResponse({"error": "The saved inventory view is invalid."}, status_code=400)

    job_id = uuid4().hex
    job_dir = WORK_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    name = name.strip()
    if "pickup" in documents:
        (job_dir / DOCUMENTS["pickup"]).write_text(f"RELAY / PICKUP SHEET\nBundle: {name}\nBring this sheet to the lending desk.\n", encoding="utf-8")
    if "equipment" in documents:
        lines = ["RELAY / EQUIPMENT LIST", f"Bundle: {name}", ""]
        lines.extend(f"- {item['title']}" for item in items)
        (job_dir / DOCUMENTS["equipment"]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if "handover" in documents:
        (job_dir / DOCUMENTS["handover"]).write_text("RELAY / HANDOVER INSTRUCTIONS\nCheck each item and report missing accessories before leaving.\n", encoding="utf-8")
    job = {"jobId": job_id, "name": name, "status": "saved", "documents": documents, "createdAt": _now()}
    JOBS[job_id] = job
    return JSONResponse(_public_job(job), status_code=201)


@app.post("/batches/{job_id}/build")
async def build_batch(job_id: str):
    job_dir = _job_dir(job_id)
    job = JOBS.get(job_id) if job_dir else None
    if not job:
        return JSONResponse({"error": "The pickup bundle was not found."}, status_code=404)
    if job["status"] != "saved":
        return JSONResponse(_public_job(job))
    files = " ".join(DOCUMENTS[item] for item in job["documents"])
    command = f'tar -czf pickup-bundle.tar.gz --transform="s|^|{job["name"]}/|" {files}'
    try:
        completed = subprocess.run(
            ["/bin/sh", "-c", command],
            cwd=job_dir,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C"},
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        job["status"] = "ready" if completed.returncode == 0 and (job_dir / "pickup-bundle.tar.gz").is_file() else "failed"
    except subprocess.TimeoutExpired:
        job["status"] = "failed"
    return _public_job(job)


@app.get("/batches/{job_id}")
async def get_batch(job_id: str):
    job = JOBS.get(job_id) if _job_dir(job_id) else None
    return _public_job(job) if job else JSONResponse({"error": "The pickup bundle was not found."}, status_code=404)


@app.get("/batches/{job_id}/artifact")
async def get_artifact(job_id: str, name: str = ""):
    job_dir = _job_dir(job_id)
    if not job_dir or job_id not in JOBS or not ARTIFACT_PATTERN.fullmatch(name):
        return JSONResponse({"error": "The bundle file was not found."}, status_code=404)
    artifact = job_dir / name
    if not artifact.is_file() or artifact.is_symlink():
        return JSONResponse({"error": "The bundle file was not found."}, status_code=404)
    media_type = "application/gzip" if name.endswith(".tar.gz") else "text/plain"
    return FileResponse(artifact, media_type=media_type, filename=name if name.endswith(".tar.gz") else None)


@app.post("/reset")
async def reset():
    if not WORK_ROOT.exists():
        JOBS.clear()
        return {"ok": True}
    for child in WORK_ROOT.iterdir():
        if child.is_symlink():
            child.unlink()
        elif child.is_dir() and JOB_ID_PATTERN.fullmatch(child.name):
            shutil.rmtree(child)
    JOBS.clear()
    return {"ok": True}
