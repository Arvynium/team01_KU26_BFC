from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

_store_lock = Lock()

_EMPTY_DRAFT = {"title": "", "content": "", "updatedAt": None}


def _data_file() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/data")) / "bfc.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_store() -> dict:
    data_file = _data_file()
    with _store_lock:
        if not data_file.exists():
            data_file.parent.mkdir(parents=True, exist_ok=True)
            store = {"conditionReports": [], "returnApprovals": [], "projectUpdate": _EMPTY_DRAFT.copy()}
            data_file.write_text(json.dumps(store, indent=2), encoding="utf-8")
            return store
        stored = json.loads(data_file.read_text(encoding="utf-8"))
        draft = stored.get("projectUpdate", {})
        return {
            "conditionReports": stored.get("conditionReports", stored.get("labNotes", [])),
            "returnApprovals": stored.get("returnApprovals", []),
            "projectUpdate": {
                "title": draft.get("title", "") if isinstance(draft, dict) else "",
                "content": draft.get("content", "") if isinstance(draft, dict) else "",
                "updatedAt": draft.get("updatedAt") if isinstance(draft, dict) else None,
            },
        }


def _save_store(store: dict) -> None:
    data_file = _data_file()
    with _store_lock:
        data_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = data_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(store, indent=2), encoding="utf-8")
        temporary.replace(data_file)


def notes() -> list[dict]:
    return _read_store()["conditionReports"][:100]


def add_condition_report(body: str) -> dict:
    store = _read_store()
    note = {"id": str(uuid4()), "body": body, "createdAt": _now()}
    store["conditionReports"].insert(0, note)
    _save_store(store)
    return note


def delete_condition_report(note_id: str) -> bool:
    store = _read_store()
    before = len(store["conditionReports"])
    store["conditionReports"] = [note for note in store["conditionReports"] if note["id"] != note_id]
    if len(store["conditionReports"]) == before:
        return False
    _save_store(store)
    return True


def return_approvals() -> list[dict]:
    return _read_store()["returnApprovals"][:100]


def approve_return(note_id: str) -> dict | None:
    store = _read_store()
    if not any(note["id"] == note_id for note in store["conditionReports"]):
        return None
    for approval in store["returnApprovals"]:
        if approval["noteId"] == note_id:
            return approval
    approval = {
        "id": str(uuid4()),
        "noteId": note_id,
        "approvedAt": _now(),
        "verificationCode": os.environ["LAB_XSS_FLAG"],
    }
    store["returnApprovals"].insert(0, approval)
    _save_store(store)
    return approval


def project_update() -> dict:
    return _read_store()["projectUpdate"]


def save_project_update(title: str, content: str) -> dict:
    store = _read_store()
    draft = {"title": title, "content": content, "updatedAt": _now()}
    store["projectUpdate"] = draft
    _save_store(store)
    return draft


def reset_practice_environment() -> None:
    _save_store({"conditionReports": [], "returnApprovals": [], "projectUpdate": _EMPTY_DRAFT.copy()})
