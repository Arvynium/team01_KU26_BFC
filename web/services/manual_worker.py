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

WORK_ROOT = Path(os.getenv("DOCUMENT_LAB_WORK_ROOT", "/work/document-jobs"))
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
ALLOWED_PROFILES = {"screen", "archive", "export", "mode-a", "mode-b"}
ALLOWED_SUFFIXES = {".eps", ".pdf", ".ps"}
INPUT_BASENAMES = {
    "screen": "doc_preview1_screen",
    "archive": "doc_preview2_archive",
    "export": "doc_preview3_export",
    "mode-a": "doc_preview4_mode_a",
    "mode-b": "doc_preview5_mode_b",
}
ARTIFACT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
OBSERVER_ROOTS = (WORK_ROOT.parent, WORK_ROOT.parent / "tmp")
OBSERVER_BASELINES: dict[str, dict[Path, tuple[int, int, int]]] = {}
OBSERVER_RESULTS: dict[str, list[dict[str, str]]] = {}
TRACKED_EXTERNAL_ARTIFACTS: dict[Path, tuple[int, int, int]] = {}


@contextmanager
def _observation_lock():
    with open("/tmp/bfc-manual-observer.lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

SAMPLE_POSTSCRIPT = b"""%!PS-Adobe-3.0
%%Pages: 1
%%BoundingBox: 0 0 612 792
/rect { /h exch def /w exch def /y exch def /x exch def x y w h rectfill } def
0.965 0.976 0.968 setrgbcolor 0 0 612 792 rect
0.106 0.239 0.219 setrgbcolor 0 670 612 122 rect
0.906 0.447 0.341 setrgbcolor 46 721 14 14 rect
1 1 1 setrgbcolor
/Helvetica-Bold findfont 32 scalefont setfont 74 714 moveto (RELAY) show
/Helvetica findfont 11 scalefont setfont 74 690 moveto (GEAR LIBRARY  /  LOAN RECORDS) show
0.14 0.22 0.20 setrgbcolor
/Helvetica-Bold findfont 23 scalefont setfont 46 617 moveto (Equipment handover) show
/Helvetica findfont 11 scalefont setfont 46 592 moveto (Member copy  -  generated for a local equipment loan) show
0.83 0.88 0.85 setrgbcolor 46 574 520 1 rect
0.31 0.39 0.35 setrgbcolor
/Helvetica-Bold findfont 10 scalefont setfont 46 543 moveto (ITEM) show
46 491 moveto (KIT CONTENTS) show
46 439 moveto (PICKUP WINDOW) show
46 387 moveto (RETURN CHECK) show
0.11 0.24 0.22 setrgbcolor
/Helvetica findfont 14 scalefont setfont
192 543 moveto (Mirrorless camera kit) show
192 491 moveto (Camera body, lens, strap, carry case) show
192 439 moveto (Weekday collection at service desk) show
192 387 moveto (Bring all accessories for inspection) show
0.83 0.88 0.85 setrgbcolor 46 516 520 1 rect 46 464 520 1 rect
46 412 520 1 rect 46 360 520 1 rect
0.96 0.91 0.88 setrgbcolor 46 257 520 69 rect
0.62 0.27 0.22 setrgbcolor
/Helvetica-Bold findfont 11 scalefont setfont 64 299 moveto (HANDOVER NOTE) show
0.28 0.33 0.30 setrgbcolor
/Helvetica findfont 11 scalefont setfont 64 279 moveto (Check the kit before leaving and report missing items.) show
0.83 0.88 0.85 setrgbcolor 46 114 520 1 rect
0.34 0.41 0.37 setrgbcolor
/Helvetica findfont 10 scalefont setfont 46 93 moveto (Relay  /  Shared gear, ready for the next member) show
46 76 moveto (Sample document for preview testing) show
showpage
%%EOF
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _job_dir(job_id: str) -> Path:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid document job identifier.")
    return WORK_ROOT / job_id


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "upload.bin").suffix
    return suffix if suffix.lower() in ALLOWED_SUFFIXES else ".bin"


def _input_name(profile: str, suffix: str) -> str:
    return f"{INPUT_BASENAMES[profile]}{suffix}"


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


def _observed_content(path: Path) -> str:
    payload = path.read_bytes()
    if payload.startswith(b"%PDF"):
        return f"PDF output was created ({len(payload)} bytes; signature %PDF)."
    return _trim(payload.decode("utf-8", errors="replace"))


def _safe_worker_output(value: str) -> str:
    sanitized = re.sub(
        r"(?:GPL\s+)?Ghostscript\s+\d+\.\d+\.\d+(?:-\d+)?",
        "the document worker",
        _trim(value),
        flags=re.IGNORECASE,
    )
    return re.sub(r"ghostscript", "the document worker", sanitized, flags=re.IGNORECASE)


def _combined_worker_output(completed: subprocess.CompletedProcess[str]) -> str:
    return _safe_worker_output("\n".join(part for part in (completed.stdout, completed.stderr) if part))


def _worker_failed(completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode != 0:
        return True
    diagnostic = re.compile(
        r"(?im)^\s*(?:(?:GPL|AFPL|ESP) Ghostscript\s+\d+(?:\.\d+){1,2}(?:-\d+)?:\s*)?"
        r"\*{4}\s+(?:Could not open the file|Unable to open the file)\b"
    )
    if diagnostic.search(completed.stdout) or diagnostic.search(completed.stderr):
        return True
    return re.search(r"(?im)^\s*Error: /invalidfileaccess\b", completed.stderr) is not None


def _snapshot_external_files() -> dict[Path, tuple[int, int, int]]:
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
    for path, signature in sorted(_snapshot_external_files().items(), key=lambda item: str(item[0])):
        if before.get(path) == signature:
            continue
        try:
            content = _observed_content(path)
        except (FileNotFoundError, OSError):
            continue
        if path not in before or path in TRACKED_EXTERNAL_ARTIFACTS:
            TRACKED_EXTERNAL_ARTIFACTS[path] = signature
        artifacts.append({"name": path.name, "location": f"sandbox boundary: {path}", "content": content})
    job_dir = _job_dir(job_id)
    dump = job_dir / "printer-output.dat"
    if dump.is_file() and not dump.is_symlink():
        artifacts.append({"name": dump.name, "location": f"job directory: {dump}", "content": _trim(dump.read_text(errors="replace"))})
    OBSERVER_RESULTS[job_id] = artifacts


def _clear_tracked_external_artifacts() -> None:
    for path, signature in list(TRACKED_EXTERNAL_ARTIFACTS.items()):
        try:
            if path.is_symlink() or not path.is_file() or path.parent not in OBSERVER_ROOTS:
                continue
            stat = path.stat()
            if (stat.st_ino, stat.st_size, stat.st_mtime_ns) == signature:
                path.unlink()
        except (FileNotFoundError, OSError):
            pass
    TRACKED_EXTERNAL_ARTIFACTS.clear()
    OBSERVER_BASELINES.clear()
    OBSERVER_RESULTS.clear()


def _artifacts(job_dir: Path, source: Path) -> list[str]:
    return sorted(
        child.name
        for child in job_dir.iterdir()
        if child.is_file() and child != source and not child.is_symlink()
    )


def _observer(job_id: str) -> dict:
    return {"artifacts": OBSERVER_RESULTS.get(job_id, [])}


def _reset_jobs() -> None:
    with _observation_lock():
        _clear_tracked_external_artifacts()
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        (WORK_ROOT.parent / "tmp").mkdir(parents=True, exist_ok=True)
        for child in WORK_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)


def _run_observed_unlocked(job_id: str, profile: str, source: Path, result: Path, job_dir: Path) -> subprocess.CompletedProcess[str]:
    OBSERVER_BASELINES[job_id] = _snapshot_external_files()
    if profile == "mode-b":
        (job_dir / "printer-state.tmp").write_text(
            "Temporary state for the local document worker.\n",
            encoding="utf-8",
        )
    run_dir = WORK_ROOT if profile == "export" else job_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _run(_command(profile, source, result), run_dir)
    finally:
        _record_observer(job_id)


def _run_observed(job_id: str, profile: str, source: Path, result: Path, job_dir: Path) -> subprocess.CompletedProcess[str]:
    with _observation_lock():
        return _run_observed_unlocked(job_id, profile, source, result, job_dir)


def _command(profile: str, source: Path, result: Path) -> list[str]:
    base = [
        "gs",
        "-q",
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-r144",
        "--permit-file-read=./*",
        "--permit-file-write=./*",
        "--permit-file-control=./*",
    ]
    if profile == "archive":
        return [*base, "-sDEVICE=pnggray", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4", f"-sOutputFile={result}", str(source)]
    if profile == "mode-a":
        return [*base, "-dNODISPLAY", str(source)]
    if profile == "export":
        return [
            *base,
            "--permit-file-write=/tmp/*",
            "-sDEVICE=pdfwrite",
            "-sOutputFile=/dev/null",
            str(source),
        ]
    if profile == "mode-b":
        return [*base, "-dNODISPLAY", str(source)]
    return [*base, "-sDEVICE=png16m", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4", f"-sOutputFile={result}", str(source)]


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
async def setup() -> None:
    _reset_jobs()


@app.get("/health")
async def health():
    return {"service": "manual-worker", "status": "ready"}


@app.get("/component")
async def component():
    return {
        "status": "ready",
        "profiles": sorted(ALLOWED_PROFILES),
    }


@app.post("/reset")
async def reset():
    _reset_jobs()
    return {"ok": True}


@app.post("/render")
async def render(
    profile: str = Form("screen"),
    sample: bool = Form(False),
    file: UploadFile | None = File(default=None),
):
    if profile not in ALLOWED_PROFILES:
        return JSONResponse({"error": "Choose a supported preview profile."}, status_code=400)
    if not sample and file is None:
        return JSONResponse({"error": "Choose a PDF or PostScript file or load the sample document."}, status_code=400)

    suffix = ".ps" if sample else _safe_suffix(file.filename if file else None)
    payload = SAMPLE_POSTSCRIPT if sample else await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "Document files must be 8 MB or smaller."}, status_code=413)

    job_id = uuid4().hex
    job_dir = _job_dir(job_id)
    source = job_dir / _input_name(profile, suffix)
    result = job_dir / "preview.png"
    with _observation_lock():
        job_dir.mkdir(parents=True, mode=0o700)
        source.write_bytes(payload)
        try:
            completed = _run_observed_unlocked(job_id, profile, source, result, job_dir)
        except subprocess.TimeoutExpired:
            return JSONResponse({"error": "The document worker reached its eight-second processing limit.", "jobId": job_id}, status_code=422)

        if _worker_failed(completed):
            return JSONResponse(
                {
                    "error": "The document worker could not complete this operation.",
                    "jobId": job_id,
                    "workerOutput": _combined_worker_output(completed),
                    "artifacts": _artifacts(job_dir, source),
                    "observer": _observer(job_id),
                },
                status_code=422,
            )
        if profile == "mode-a":
            return {
                "jobId": job_id,
                "profile": profile,
                "inputName": source.name,
                "createdAt": _now(),
                "summary": "Mode A completed without a preview artifact.",
                "observedOutput": _combined_worker_output(completed),
                "artifacts": _artifacts(job_dir, source),
                "observer": _observer(job_id),
            }
        if profile in {"export", "mode-b"}:
            return {
                "jobId": job_id,
                "profile": profile,
                "inputName": source.name,
                "createdAt": _now(),
                "summary": "Document export completed without a preview artifact." if profile == "export" else "Mode B completed without a preview artifact.",
                "observedOutput": _combined_worker_output(completed),
                "artifacts": _artifacts(job_dir, source),
                "observer": _observer(job_id),
            }
        if not result.exists():
            return JSONResponse({"error": "The document worker did not produce a preview.", "jobId": job_id, "artifacts": _artifacts(job_dir, source), "observer": _observer(job_id)}, status_code=422)

        return {
            "jobId": job_id,
            "profile": profile,
            "inputName": source.name,
            "createdAt": _now(),
            "summary": "Page one rendered to PNG",
            "observedOutput": _combined_worker_output(completed),
            "artifacts": _artifacts(job_dir, source),
            "observer": _observer(job_id),
        }


@app.get("/jobs/{job_id}/result")
async def result(job_id: str):
    try:
        artifact = _job_dir(job_id) / "preview.png"
    except ValueError:
        return JSONResponse({"error": "Document preview was not found."}, status_code=404)
    if not artifact.is_file():
        return JSONResponse({"error": "Document preview was not found."}, status_code=404)
    return FileResponse(artifact, media_type="image/png", filename="bfc-document-preview.png", headers={"Cache-Control": "no-store"})


@app.get("/jobs/{job_id}/artifact")
async def artifact(job_id: str, name: str = ""):
    if not ARTIFACT_NAME_PATTERN.fullmatch(name) or Path(name).name != name or name.startswith("doc_preview"):
        return JSONResponse({"error": "Document artifact was not found."}, status_code=404)
    try:
        job_dir = _job_dir(job_id)
    except ValueError:
        return JSONResponse({"error": "Document artifact was not found."}, status_code=404)
    candidate = job_dir / name
    try:
        if candidate.is_symlink() or candidate.resolve().parent != job_dir.resolve() or not candidate.is_file():
            raise FileNotFoundError
    except (FileNotFoundError, OSError):
        return JSONResponse({"error": "Document artifact was not found."}, status_code=404)
    if candidate.suffix.lower() == ".png":
        media_type = "image/png"
    elif candidate.suffix.lower() in {".txt", ".log", ".pcl", ".dat"}:
        media_type = "text/plain"
    else:
        media_type = "application/octet-stream"
    return FileResponse(candidate, media_type=media_type, filename=candidate.name, headers={"Cache-Control": "no-store"})


@app.get("/jobs/{job_id}/observer")
async def observer(job_id: str):
    if not JOB_ID_PATTERN.fullmatch(job_id) or job_id not in OBSERVER_RESULTS or not _job_dir(job_id).is_dir():
        return JSONResponse({"error": "Document job was not found."}, status_code=404)
    return _observer(job_id)
