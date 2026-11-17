from __future__ import annotations

import os
import hashlib
import hmac

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from .constants import APP_NAME
from .store import add_condition_report, approve_return, delete_condition_report, notes, project_update, reset_practice_environment, return_approvals, save_project_update

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _catalog_url() -> str:
    return os.getenv("GEAR_CATALOG_URL", "http://gear-catalog:8081").rstrip("/")


def _photo_worker_url() -> str:
    return os.getenv("PHOTO_WORKER_URL", "http://photo-worker:8084").rstrip("/")


def _manual_worker_url() -> str:
    return os.getenv("MANUAL_WORKER_URL", "http://manual-worker:8085").rstrip("/")


def _request_observer_url() -> str:
    return os.getenv("REQUEST_OBSERVER_URL", "http://request-observer:8083").rstrip("/")


def _reviewer_url() -> str:
    return os.getenv("REVIEWER_URL", "").rstrip("/")


def _package_worker_url() -> str:
    return os.getenv("PACKAGE_WORKER_URL", "http://package-worker:8087").rstrip("/")


def _staff_review_authorized(request: Request) -> bool:
    secret = os.environ["LAB_REVIEW_SECRET"]
    expected = hmac.new(secret.encode(), b"relay-staff-review", hashlib.sha256).hexdigest()
    return hmac.compare_digest(request.cookies.get("relay_staff_review", ""), expected)


async def _catalog_json(method: str, path: str, *, params: dict[str, str] | None = None, payload: dict | None = None) -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.request(method, f"{_catalog_url()}{path}", params=params, json=payload)
        try:
            body = upstream.json()
        except ValueError:
            body = {"error": "The gear catalog returned an invalid response."}
        return JSONResponse(body, status_code=upstream.status_code)
    except httpx.HTTPError:
        return _error_response(502, "The gear catalog is temporarily unavailable.")


async def _component_json(base_url: str, path: str) -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(f"{base_url}{path}")
        payload = upstream.json()
        if path == "/component" and isinstance(payload, dict):
            allowed = ("status", "operations") if "operations" in payload else ("status", "profiles")
            payload = {key: payload[key] for key in allowed if key in payload}
        return JSONResponse(payload, status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "The component worker is temporarily unavailable.")


async def _forward_component_upload(base_url: str, path: str, *, field: str, operation: str, sample: bool, upload: UploadFile | None, reference: UploadFile | None = None) -> JSONResponse:
    files = None
    if upload is not None:
        payload = await upload.read()
        files = {"file": (upload.filename or "upload.bin", payload, upload.content_type or "application/octet-stream")}
    if reference is not None and not sample:
        files = files or {}
        payload = await reference.read()
        files["reference"] = (reference.filename or "related.bin", payload, reference.content_type or "application/octet-stream")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            upstream = await client.post(f"{base_url}{path}", data={field: operation, "sample": str(sample).lower()}, files=files)
        return JSONResponse(upstream.json(), status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "The component worker is temporarily unavailable.")


async def _component_result(base_url: str, path: str, *, params: dict[str, str] | None = None) -> Response:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            upstream = await client.get(f"{base_url}{path}", params=params)
        if upstream.is_success:
            return Response(upstream.content, media_type=upstream.headers.get("content-type", "application/octet-stream"), headers={"Cache-Control": "no-store"})
        return JSONResponse(upstream.json(), status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "The component worker is temporarily unavailable.")


async def _package_json(method: str, path: str, *, payload: dict | None = None) -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=9.0) as client:
            upstream = await client.request(method, f"{_package_worker_url()}{path}", json=payload)
        return JSONResponse(upstream.json(), status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "Pickup bundle service is temporarily unavailable.")


async def _reset_request_trace() -> None:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{_request_observer_url()}/reset")
    except httpx.HTTPError:
        pass


@app.get("/api/gear/search")
async def gear_search(request: Request, q: str = ""):
    return await _catalog_json("GET", "/search", params={"q": q})


@app.post("/api/gear/saved-view")
async def gear_saved_view(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    query = body.get("query")
    if not isinstance(query, str):
        return _error_response(400, "An inventory filter is required.")
    return await _catalog_json("POST", "/saved-view", payload={"query": query})


@app.get("/api/gear/export")
async def gear_export(request: Request, snapshotId: str = ""):
    if not snapshotId:
        return _error_response(400, "A review snapshot is required.")
    return await _catalog_json("GET", "/review-export", params={"snapshotId": snapshotId})


@app.post("/api/dispatch/batches")
async def save_pickup_bundle(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    snapshot_id = body.get("snapshotId")
    name = body.get("name")
    documents = body.get("documents")
    if not isinstance(snapshot_id, str) or not snapshot_id or not isinstance(name, str) or not isinstance(documents, list):
        return _error_response(400, "Choose a saved inventory view, bundle name, and documents.")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(f"{_catalog_url()}/review-export", params={"snapshotId": snapshot_id})
        if not upstream.is_success:
            return _error_response(404, "The saved inventory view was not found.")
        items = [{"title": row["title"]} for row in upstream.json()["rows"]]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return _error_response(502, "The saved inventory view is unavailable.")
    return await _package_json("POST", "/batches", payload={"name": name, "documents": documents, "items": items})


@app.post("/api/dispatch/batches/{job_id}/build")
async def build_pickup_bundle(job_id: str):
    return await _package_json("POST", f"/batches/{job_id}/build")


@app.get("/api/dispatch/batches/{job_id}")
async def pickup_bundle_status(job_id: str):
    return await _package_json("GET", f"/batches/{job_id}")


@app.get("/api/dispatch/batches/{job_id}/artifact")
async def pickup_bundle_artifact(job_id: str, name: str = ""):
    response = await _component_result(_package_worker_url(), f"/batches/{job_id}/artifact", params={"name": name})
    if response.status_code == 200 and name.endswith(".tar.gz"):
        response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@app.get("/api/borrowing/document")
async def borrowing_document(request: Request, path: str = ""):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(f"{_catalog_url()}/artifact", params={"path": path})
        if upstream.is_success:
            return Response(upstream.text, media_type=upstream.headers.get("content-type", "text/plain"), headers={"Cache-Control": "no-store"})
        return JSONResponse(upstream.json(), status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "The artifact archive is temporarily unavailable.")


@app.get("/api/photos")
async def image_component():
    return await _component_json(_photo_worker_url(), "/component")


@app.post("/api/photos/transform")
async def image_transform(
    operation: str = Form("thumbnail"),
    sample: bool = Form(False),
    file: UploadFile | None = File(default=None),
    reference: UploadFile | None = File(default=None),
):
    await _reset_request_trace()
    return await _forward_component_upload(_photo_worker_url(), "/transform", field="operation", operation=operation, sample=sample, upload=file, reference=reference)


@app.get("/api/photos/jobs/{job_id}/result")
async def image_result(job_id: str):
    return await _component_result(_photo_worker_url(), f"/jobs/{job_id}/result")


@app.get("/api/photos/jobs/{job_id}/artifact")
async def image_artifact(job_id: str, name: str = ""):
    return await _component_result(_photo_worker_url(), f"/jobs/{job_id}/artifact", params={"name": name})


@app.get("/api/photos/jobs/{job_id}/observer")
async def image_observer(job_id: str):
    return await _component_json(_photo_worker_url(), f"/jobs/{job_id}/observer")


@app.get("/api/photos/trace")
async def image_trace():
    return await _component_json(_request_observer_url(), "/trace")


@app.get("/api/manuals")
async def document_component():
    return await _component_json(_manual_worker_url(), "/component")


@app.post("/api/manuals/render")
async def document_render(
    profile: str = Form("screen"),
    sample: bool = Form(False),
    file: UploadFile | None = File(default=None),
):
    return await _forward_component_upload(_manual_worker_url(), "/render", field="profile", operation=profile, sample=sample, upload=file)


@app.get("/api/manuals/jobs/{job_id}/result")
async def document_result(job_id: str):
    return await _component_result(_manual_worker_url(), f"/jobs/{job_id}/result")


@app.get("/api/manuals/jobs/{job_id}/artifact")
async def document_artifact(job_id: str, name: str = ""):
    return await _component_result(_manual_worker_url(), f"/jobs/{job_id}/artifact", params={"name": name})


@app.get("/api/manuals/jobs/{job_id}/observer")
async def document_observer(job_id: str):
    return await _component_json(_manual_worker_url(), f"/jobs/{job_id}/observer")


@app.get("/api/returns/reports")
async def get_notes():
    return {"notes": notes()}


@app.get("/api/returns/review/status")
async def review_status():
    return {"available": bool(_reviewer_url())}


@app.get("/api/returns/review/context")
async def review_context(request: Request):
    return {"staff": _staff_review_authorized(request)}


@app.get("/api/returns/approvals")
async def get_return_approvals(request: Request):
    approvals = return_approvals()
    if not _staff_review_authorized(request):
        approvals = [
            {key: approval[key] for key in ("id", "noteId", "approvedAt")}
            for approval in approvals
        ]
    return JSONResponse({"approvals": approvals}, headers={"Cache-Control": "private, no-store", "Vary": "Cookie"})


@app.post("/api/returns/approve")
async def post_return_approval(request: Request):
    if not _staff_review_authorized(request):
        return _error_response(403, "Staff review authorization is required.")
    try:
        body = await request.json()
    except ValueError:
        body = {}
    note_id = body.get("noteId")
    if not isinstance(note_id, str):
        return _error_response(400, "A return report is required.")
    approval = approve_return(note_id)
    if approval is None:
        return _error_response(404, "Return report was not found.")
    return JSONResponse({"approval": approval}, headers={"Cache-Control": "private, no-store"})


@app.post("/api/returns/review")
async def request_review():
    if not _reviewer_url():
        return _error_response(503, "Review is unavailable in this environment.")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            upstream = await client.post(f"{_reviewer_url()}/review")
        return JSONResponse(upstream.json(), status_code=upstream.status_code)
    except (httpx.HTTPError, ValueError):
        return _error_response(502, "The reviewer could not open the notes.")


@app.post("/api/returns/reports")
async def post_note(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    note_body = body.get("body")
    if not isinstance(note_body, str) or not note_body.strip():
        return _error_response(400, "A condition note is required.")
    if len(note_body) > 2500:
        return _error_response(400, "A condition note must be 2,500 characters or fewer.")
    return JSONResponse({"note": add_condition_report(note_body)}, status_code=201)


@app.delete("/api/returns/reports/{note_id}")
async def remove_note(note_id: str):
    if not delete_condition_report(note_id):
        return _error_response(404, "Condition note not found.")
    return Response(status_code=204)


@app.get("/api/project-updates/draft")
async def get_project_update():
    return {"draft": project_update()}


@app.put("/api/project-updates/draft")
async def put_project_update(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    title = body.get("title")
    content = body.get("content")
    if not isinstance(title, str) or not isinstance(content, str):
        return _error_response(400, "A title and update content are required.")
    if len(title) > 160:
        return _error_response(400, "A project update title must be 160 characters or fewer.")
    if len(content) > 60_000:
        return _error_response(400, "A project update must be 60,000 characters or fewer.")
    return {"draft": save_project_update(title, content)}


@app.post("/api/workspace/reset")
async def reset_practice():
    reset_practice_environment()
    component_resets: dict[str, bool] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, base_url in (("image", _photo_worker_url()), ("document", _manual_worker_url()), ("briefing", _request_observer_url()), ("catalog", _catalog_url()), ("packages", _package_worker_url())):
            try:
                component_resets[name] = (await client.post(f"{base_url}/reset")).is_success
            except httpx.HTTPError:
                component_resets[name] = False
    return {"ok": True, "componentResets": component_resets}
