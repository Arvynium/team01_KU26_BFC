from __future__ import annotations

import os
import fcntl
import re
import shutil
import subprocess
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

WORK_ROOT = Path(os.getenv("IMAGE_LAB_WORK_ROOT", "/work/image-jobs"))
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
ALLOWED_OPERATIONS = {"thumbnail", "grayscale", "metadata"}
ALLOWED_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".msl", ".mvg", ".png", ".ppm", ".svg", ".tif", ".tiff", ".webp"}
INPUT_BASENAMES = {
    "thumbnail": "img_trans1_thumpreview",
    "grayscale": "img_trans2_grayscale",
    "metadata": "img_trans3_metadata",
}
ARTIFACT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
OBSERVER_ROOTS = (WORK_ROOT, WORK_ROOT.parent)
OBSERVER_BASELINES: dict[str, dict[Path, tuple[int, int, int]]] = {}
OBSERVER_RESULTS: dict[str, list[dict[str, str]]] = {}
TRACKED_OBSERVER_ARTIFACTS: dict[Path, tuple[int, int, int]] = {}


@contextmanager
def _observation_lock():
    with open("/tmp/bfc-photo-observer.lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _job_dir(job_id: str) -> Path:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid image job identifier.")
    return WORK_ROOT / job_id


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "upload.bin").suffix
    return suffix if suffix.lower() in ALLOWED_SUFFIXES else ".bin"


def _input_name(operation: str, suffix: str) -> str:
    return f"{INPUT_BASENAMES[operation]}{suffix}"


SAMPLE_IMAGE = Path("/app/assets/relay-gear.png")


def _run(arguments: list[str], job_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
        cwd=job_dir,
        env={"HOME": "/tmp", "LANG": "C", "LC_ALL": "C", "PATH": os.getenv("PATH", "")},
    )


def _trim(value: str, limit: int = 1200) -> str:
    compact = value.strip()
    return compact[-limit:] if len(compact) > limit else compact


def _safe_worker_output(value: str) -> str:
    sanitized = re.sub(
        r"ImageMagick(?:\s+version)?\s+\d+\.\d+\.\d+(?:-\d+)?",
        "the image worker",
        _trim(value),
        flags=re.IGNORECASE,
    )
    return re.sub(r"imagemagick", "the image worker", sanitized, flags=re.IGNORECASE)


def _artifacts(job_dir: Path, source: Path) -> list[str]:
    return sorted(
        child.name
        for child in job_dir.iterdir()
        if child.is_file() and child != source and not child.is_symlink()
    )


def _observed_content(path: Path) -> str:
    payload = path.read_bytes()
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return f"PNG output was written outside the job directory ({len(payload)} bytes; PNG signature)."
    return _trim(payload.decode("utf-8", errors="replace"))


def _snapshot_observer_files() -> dict[Path, tuple[int, int, int]]:
    snapshot: dict[Path, tuple[int, int, int]] = {}
    for root in OBSERVER_ROOTS:
        try:
            children = root.iterdir()
        except FileNotFoundError:
            continue
        for path in children:
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                stat = path.stat()
            except (FileNotFoundError, OSError):
                continue
            snapshot[path] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    return snapshot


def _record_observer(job_id: str) -> None:
    before = OBSERVER_BASELINES.pop(job_id)
    artifacts: list[dict[str, str]] = []
    for path, signature in sorted(_snapshot_observer_files().items(), key=lambda item: str(item[0])):
        if before.get(path) == signature:
            continue
        try:
            content = _observed_content(path)
        except (FileNotFoundError, OSError):
            continue
        if path not in before or path in TRACKED_OBSERVER_ARTIFACTS:
            TRACKED_OBSERVER_ARTIFACTS[path] = signature
        artifacts.append({"name": path.name, "location": f"outside current job directory: {path}", "content": content})
    OBSERVER_RESULTS[job_id] = artifacts


def _observer(job_id: str) -> dict:
    return {"artifacts": OBSERVER_RESULTS.get(job_id, [])}


def _clear_tracked_observer_artifacts() -> None:
    for path, signature in list(TRACKED_OBSERVER_ARTIFACTS.items()):
        try:
            if path.is_symlink() or not path.is_file() or path.parent not in OBSERVER_ROOTS:
                continue
            stat = path.stat()
            if (stat.st_ino, stat.st_size, stat.st_mtime_ns) == signature:
                path.unlink()
        except (FileNotFoundError, OSError):
            pass
    TRACKED_OBSERVER_ARTIFACTS.clear()
    OBSERVER_BASELINES.clear()
    OBSERVER_RESULTS.clear()


def _reset_jobs() -> None:
    with _observation_lock():
        _clear_tracked_observer_artifacts()
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        for child in WORK_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)


def _run_observed_unlocked(job_id: str, command: list[str], job_dir: Path) -> subprocess.CompletedProcess[str]:
    OBSERVER_BASELINES[job_id] = _snapshot_observer_files()
    try:
        return _run(command, job_dir)
    finally:
        _record_observer(job_id)


def _run_observed(job_id: str, command: list[str], job_dir: Path) -> subprocess.CompletedProcess[str]:
    with _observation_lock():
        return _run_observed_unlocked(job_id, command, job_dir)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
async def setup() -> None:
    _reset_jobs()


@app.get("/health")
async def health():
    return {"service": "photo-worker", "status": "ready"}


@app.get("/component")
async def component():
    return {
        "status": "ready",
        "operations": sorted(ALLOWED_OPERATIONS),
    }


@app.post("/reset")
async def reset():
    _reset_jobs()
    return {"ok": True}


@app.post("/transform")
async def transform(
    operation: str = Form("thumbnail"),
    sample: bool = Form(False),
    file: UploadFile | None = File(default=None),
    reference: UploadFile | None = File(default=None),
):
    if operation not in ALLOWED_OPERATIONS:
        return JSONResponse({"error": "Choose a supported image operation."}, status_code=400)
    if not sample and file is None:
        return JSONResponse({"error": "Choose an image file or load the sample image."}, status_code=400)
    if not sample and file is not None and Path(file.filename or "").suffix.lower() == ".msl":
        return JSONResponse({"error": "Choose an image as the main file."}, status_code=400)

    suffix = ".png" if sample else _safe_suffix(file.filename if file else None)
    payload = None if sample else await file.read(MAX_UPLOAD_BYTES + 1)
    if payload is not None and len(payload) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "Image files must be 6 MB or smaller."}, status_code=413)
    reference_payload = None
    if reference is not None and not sample:
        reference_payload = await reference.read(MAX_UPLOAD_BYTES + 1)
        if len(reference_payload) > MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "Related files must be 6 MB or smaller."}, status_code=413)

    job_id = uuid4().hex
    job_dir = _job_dir(job_id)
    source = job_dir / _input_name(operation, suffix)
    result = job_dir / "result.png"
    command = ["convert", str(source), "-thumbnail", "960x640", str(result)]
    if operation == "grayscale":
        command = ["convert", str(source), "-colorspace", "Gray", "-thumbnail", "960x640", str(result)]
    if operation == "metadata":
        command = ["convert", str(source), "-strip", "-thumbnail", "960x640", str(result)]

    with _observation_lock():
        job_dir.mkdir(parents=True, mode=0o700)
        if sample:
            shutil.copyfile(SAMPLE_IMAGE, source)
        else:
            assert payload is not None
            source.write_bytes(payload)
        if reference_payload is not None and reference is not None:
            (job_dir / f"reference{_safe_suffix(reference.filename)}").write_bytes(reference_payload)

        try:
            completed = _run_observed_unlocked(job_id, command, job_dir)
        except subprocess.TimeoutExpired:
            return JSONResponse({"error": "The image worker reached its eight-second processing limit.", "jobId": job_id}, status_code=422)

        if completed.returncode != 0 or not result.exists():
            return JSONResponse(
                {
                    "error": "The image worker could not complete this operation.",
                    "jobId": job_id,
                    "workerOutput": _safe_worker_output(completed.stderr or completed.stdout),
                    "artifacts": _artifacts(job_dir, source),
                    "observer": _observer(job_id),
                },
                status_code=422,
            )

        identify = _run(["identify", "-format", "%m %wx%h %b", str(result)], job_dir)
        return {
            "jobId": job_id,
            "operation": operation,
            "inputName": source.name,
            "createdAt": _now(),
            "summary": identify.stdout.strip() if identify.returncode == 0 else "Preview generated",
            "artifacts": _artifacts(job_dir, source),
            "observer": _observer(job_id),
        }


@app.get("/jobs/{job_id}/result")
async def result(job_id: str):
    try:
        artifact = _job_dir(job_id) / "result.png"
    except ValueError:
        return JSONResponse({"error": "Image result was not found."}, status_code=404)
    if not artifact.is_file():
        return JSONResponse({"error": "Image result was not found."}, status_code=404)
    return FileResponse(artifact, media_type="image/png", filename="bfc-image-preview.png", headers={"Cache-Control": "no-store"})


@app.get("/jobs/{job_id}/artifact")
async def artifact(job_id: str, name: str = ""):
    if not ARTIFACT_NAME_PATTERN.fullmatch(name) or Path(name).name != name or name.startswith("input"):
        return JSONResponse({"error": "Image artifact was not found."}, status_code=404)
    try:
        job_dir = _job_dir(job_id)
    except ValueError:
        return JSONResponse({"error": "Image artifact was not found."}, status_code=404)
    candidate = job_dir / name
    try:
        if candidate.is_symlink() or candidate.resolve().parent != job_dir.resolve() or not candidate.is_file():
            raise FileNotFoundError
    except (FileNotFoundError, OSError):
        return JSONResponse({"error": "Image artifact was not found."}, status_code=404)
    media_type = "image/png" if candidate.suffix.lower() == ".png" else "application/octet-stream"
    return FileResponse(candidate, media_type=media_type, filename=candidate.name, headers={"Cache-Control": "no-store"})


@app.get("/jobs/{job_id}/observer")
async def observer(job_id: str):
    if not JOB_ID_PATTERN.fullmatch(job_id) or job_id not in OBSERVER_RESULTS or not _job_dir(job_id).is_dir():
        return JSONResponse({"error": "Image job was not found."}, status_code=404)
    return _observer(job_id)
