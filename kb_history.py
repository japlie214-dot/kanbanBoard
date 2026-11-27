"""kb_history.py – Expandable Ticket Journey & State Snapshot Recorder (v3.0 + v4 Auto-Doc Foundation).

Stores compact JSONL transition logs in `board/.history/<project>__<epic>__<tid>.jsonl`.
Deduplicates `body_snapshot` by SHA-256 hash so unchanged ticket bodies take near-zero disk space.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import kb_crud


def history_file(ref: str, board: Path) -> Path:
    safe_key = ref.strip().replace("\\", "/").replace("/", "__")
    return board / ".history" / f"{safe_key}.jsonl"


def _last_body_hash(hfile: Path) -> str | None:
    if not hfile.is_file():
        return None
    last_hash = None
    for line in hfile.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("body_hash"):
                last_hash = obj["body_hash"]
        except Exception:
            continue
    return last_hash


def record_transition(
    ref: str,
    from_status: str,
    to_status: str,
    actor: str,
    board: Path,
    note: str = "",
    todo_progress: str = "",
    files: list[str] | None = None,
    body: str = "",
    case_id: str | None = None,
    commit_sha: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Append a state transition entry with deduplicated content snapshot."""
    hfile = history_file(ref, board)
    hfile.parent.mkdir(parents=True, exist_ok=True)

    clean_body = (body or "").strip()
    bhash = hashlib.sha256(clean_body.encode("utf-8")).hexdigest()[:16] if clean_body else None
    prev_hash = _last_body_hash(hfile)

    entry: dict[str, Any] = {
        "ts": kb_crud.iso_utc(now),
        "ref": ref,
        "from": from_status,
        "to": to_status,
        "actor": actor or "agent",
        "note": (note or "").strip(),
        "todo_progress": todo_progress or "",
        "files": list(files or []),
    }
    if case_id:
        entry["case_id"] = case_id
    if commit_sha:
        entry["commit_sha"] = commit_sha
    if bhash:
        entry["body_hash"] = bhash
        if bhash != prev_hash:
            entry["body_snapshot"] = clean_body

    with open(hfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_history(ref: str, board: Path) -> list[dict[str, Any]]:
    """Return chronological journey entries, hydrating deduplicated snapshots for UI expansion."""
    hfile = history_file(ref, board)
    if not hfile.is_file():
        return []
    entries: list[dict[str, Any]] = []
    snapshots: dict[str, str] = {}
    for line in hfile.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        bhash = obj.get("body_hash")
        if bhash and "body_snapshot" in obj:
            snapshots[bhash] = obj["body_snapshot"]
        elif bhash and bhash in snapshots:
            obj["body_snapshot"] = snapshots[bhash]
        entries.append(obj)
    return entries
