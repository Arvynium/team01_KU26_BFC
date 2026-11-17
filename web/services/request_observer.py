from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, Request

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_TRACE: list[dict[str, str]] = []
_TRACE_LOCK = Lock()


def _record(request: Request) -> None:
    entry = {
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "observedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    with _TRACE_LOCK:
        _TRACE.append(entry)
        del _TRACE[:-40]


@app.get("/health")
async def health(request: Request):
    _record(request)
    return {"service": "request-observer", "status": "ready"}


@app.get("/trace")
async def trace():
    with _TRACE_LOCK:
        return {"requests": list(_TRACE)}


@app.post("/reset")
async def reset():
    with _TRACE_LOCK:
        _TRACE.clear()
    return {"ok": True}
