from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

DOCUMENT_ROOT = Path("/tmp/relay-documents")
PUBLIC_DOCUMENTS = DOCUMENT_ROOT / "public"
STAFF_DOCUMENTS = DOCUMENT_ROOT / "staff"
SAVED_VIEWS: dict[str, dict[str, int | str]] = {}


def _setup_documents() -> None:
    PUBLIC_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    STAFF_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DOCUMENTS / "pickup-guide.txt").write_text(
        "RELAY / PICKUP GUIDE\nCheck the kit number, accessories, and due date before handover.\n",
        encoding="utf-8",
    )
    (PUBLIC_DOCUMENTS / "care-sheet.txt").write_text(
        "RELAY / CARE SHEET\nReturn batteries charged and report any damage in a condition note.\n",
        encoding="utf-8",
    )
    manifest = {
        "service": "Relay gear library",
        "documents": ["pickup-guide.txt", "care-sheet.txt"],
        "internalMedia": {"service": "internal-media", "port": 8082, "path": "/internal/asset", "mediaType": "image/png", "access": "services-network-only"},
    }
    (PUBLIC_DOCUMENTS / "kit-index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (STAFF_DOCUMENTS / "handover-ledger-2026.txt").write_text(
        "RELAY / STAFF HANDOVER LEDGER\nSettlement reference: " + os.environ["LAB_PATH_FLAG"] + "\n",
        encoding="utf-8",
    )


def _setup_database() -> sqlite3.Connection:
    database = sqlite3.connect("/tmp/relay-inventory.sqlite")
    database.execute(
        "CREATE TABLE inventory (id INTEGER PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, owner TEXT NOT NULL, visibility TEXT NOT NULL)"
    )
    database.executemany(
        "INSERT INTO inventory (title, summary, owner, visibility) VALUES (?, ?, ?, ?)",
        [
            ("Mirrorless camera kit", "Camera body, lens, charger, and two batteries.", "Media desk", "public"),
            ("Portable projector", "Projector, remote, HDMI cable, and carry case.", "Events desk", "public"),
            ("Field audio kit", "Recorder, headphones, windscreen, and spare cells.", "Media desk", "public"),
            ("Tripod and LED kit", "Travel tripod, panel light, and power adapter.", "Media desk", "public"),
            ("Wireless microphone set", "Two handheld microphones, receiver, and charging case.", "Events desk", "public"),
            ("Portable PA speaker", "Battery speaker, power lead, and protective cover.", "Events desk", "public"),
            ("Live production switcher", "Four-input video switcher, adapters, and carry case.", "Media desk", "public"),
            ("Instant photo printer", "Compact printer, power adapter, and starter paper pack.", "Creative desk", "public"),
            ("Internal settlement / Q3", os.environ["LAB_SQL_FLAG"], "Operations", "staff"),
        ],
    )
    database.row_factory = sqlite3.Row
    return database


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_documents()
    app.state.database = _setup_database()
    yield
    app.state.database.close()


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


@app.get("/health")
async def health():
    return {"service": "relay-catalog", "status": "ready"}


@app.post("/reset")
async def reset():
    SAVED_VIEWS.clear()
    return {"ok": True}


@app.get("/search")
async def search(request: Request, q: str = ""):
    pattern = f"%{q.replace('*', '%')}%"
    rows = _rows(request.app.state.database.execute(
        "SELECT id, title, summary, owner, visibility FROM inventory WHERE visibility = ? AND (title LIKE ? OR summary LIKE ?) ORDER BY id",
        ("public", pattern, pattern),
    ))
    return {"rows": rows}


@app.post("/saved-view")
async def save_view(request: Request):
    body = await request.json()
    query = body.get("query")
    if not isinstance(query, str) or len(query) > 160:
        return JSONResponse({"error": "The inventory filter is invalid."}, status_code=400)
    view_id = uuid4().hex
    SAVED_VIEWS[view_id] = {"query": query, "createdAt": int(time.time() * 1000)}
    return {"viewId": view_id, "label": query or "All available gear"}


def _export_statement(query: str) -> str:
    pattern = query.replace("*", "%")
    return " ".join([
        "SELECT id, title, summary, owner, visibility FROM inventory",
        "WHERE visibility = 'public'",
        f"AND (title LIKE '%{pattern}%' OR summary LIKE '%{pattern}%')",
        "ORDER BY id",
    ])


@app.get("/review-export")
async def review_export(request: Request, snapshotId: str = ""):
    view = SAVED_VIEWS.get(snapshotId)
    if not view:
        return JSONResponse({"error": "The saved view was not found."}, status_code=404)
    try:
        rows = _rows(request.app.state.database.execute(_export_statement(str(view["query"]))))
    except sqlite3.Error:
        return JSONResponse({"error": "The inventory export could not be generated."}, status_code=400)
    return {"rows": rows, "createdAt": view["createdAt"]}


@app.get("/artifact")
async def artifact(path: str = ""):
    if ".." in path or path.startswith("/"):
        return JSONResponse({"error": "Only document references are accepted."}, status_code=403)
    resolved_path = (PUBLIC_DOCUMENTS / unquote(path)).resolve()
    if not resolved_path.is_relative_to(DOCUMENT_ROOT):
        return JSONResponse({"error": "Document is outside the library."}, status_code=403)
    try:
        return PlainTextResponse(resolved_path.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})
    except OSError:
        return JSONResponse({"error": "Document was not found."}, status_code=404)


