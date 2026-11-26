"""kb_crud.py – Complete Ticket CRUD, 120-Day Retirement/Purge Lifecycle, and LLM Pagination (v2.6).

Stdlib-only module designed for KanbanBoard:
  - api_retire(): Soft-delete any non-done ticket back to backlog with `retired: true` + 120-day timer.
  - api_restore(): Un-retire a backlog ticket and cancel its 120-day hard-delete timer.
  - api_rehome(): Move a non-done ticket cleanly to another epic/project without manual file edits.
  - purge_expired_retired(): Throttled hourly sweep that hard-deletes backlog tickets retired >= 120 days,
    recording a 1-line JSONL tombstone in `board/.purge_audit.jsonl`.
  - paginate_items() + compact_ticket_row(): Bounded, LLM-context-friendly pagination & filtering.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_PURGE_DAYS = 120
PURGE_THROTTLE_SECONDS = 3600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime | None = None) -> str:
    return (dt or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(raw: str | None) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Minimal YAML-subset frontmatter parser for Kanban ticket files (preserves scalar & simple list fields)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw_meta, body = parts[1], parts[2]
    meta: dict[str, Any] = {}
    current_key: str | None = None
    in_indented_dict = False
    for line in raw_meta.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent > 0 and current_key is not None:
            if stripped.startswith("- "):
                val = stripped[2:].strip().strip('"').strip("'")
                if not isinstance(meta.get(current_key), list):
                    meta[current_key] = []
                meta[current_key].append(val)
                in_indented_dict = False
                continue
            if ":" in stripped and (in_indented_dict or meta.get(current_key) == ""):
                sub_k, sub_v = stripped.split(":", 1)
                sub_k, sub_v = sub_k.strip(), sub_v.strip().strip('"').strip("'")
                if not isinstance(meta.get(current_key), dict):
                    meta[current_key] = {}
                in_indented_dict = True
                if sub_v == "" or sub_v.lower() in {"null", "none", "~"}:
                    meta[current_key][sub_k] = None
                elif sub_v.lower() == "true":
                    meta[current_key][sub_k] = True
                elif sub_v.lower() == "false":
                    meta[current_key][sub_k] = False
                else:
                    meta[current_key][sub_k] = sub_v
                continue
        in_indented_dict = False
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        current_key = k
        if v == "":
            meta[k] = ""
        elif v.lower() == "true":
            meta[k] = True
        elif v.lower() == "false":
            meta[k] = False
        elif v.lower() in {"null", "none", "~"}:
            meta[k] = None
        elif re.fullmatch(r"-?\d+", v):
            meta[k] = int(v)
        elif v.startswith("{") and v.endswith("}"):
            try:
                parsed_obj = json.loads(v)
                meta[k] = parsed_obj if isinstance(parsed_obj, dict) else v
            except Exception:
                meta[k] = v
        elif v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[k] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()] if inner else []
        else:
            meta[k] = v.strip('"').strip("'")
    for k, v in list(meta.items()):
        if v == "":
            meta[k] = None
    return meta, body


def render_frontmatter(meta: dict[str, Any], body: str) -> str:
    """Serialize frontmatter dict back to clean YAML + body (compatible with kb.parse_frontmatter)."""
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {json.dumps(str(item))}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for sub_k, sub_v in v.items():
                if sub_v is None:
                    lines.append(f"  {sub_k}:")
                elif isinstance(sub_v, str) and any(ch in sub_v for ch in ':#{}[]|>&!'):
                    lines.append(f'  {sub_k}: "{sub_v}"')
                else:
                    lines.append(f"  {sub_k}: {sub_v}")
        else:
            s = str(v)
            if any(ch in s for ch in (":", "#", "\n", '"', "'")) or s.lower() in {"true", "false", "null"}:
                lines.append(f"{k}: {json.dumps(s)}")
            else:
                lines.append(f"{k}: {s}")
    lines.append("---")
    clean_body = body if body.startswith("\n") else "\n" + body
    return "\n".join(lines) + clean_body


def append_execution_log(body: str, entry: str) -> str:
    """Append a timestamped entry under `## Execution Log` (creating the section if absent)."""
    if re.search(r"^##\s+Execution Log\s*$", body, re.M):
        return body.rstrip() + f"\n{entry}\n"
    return body.rstrip() + f"\n\n## Execution Log\n{entry}\n"


def resolve_ticket_path(ref: str, board: Path) -> Path:
    parts = [p for p in ref.strip().replace("\\", "/").split("/") if p]
    if len(parts) != 3:
        raise ValueError(f"Invalid ticket ref '{ref}'; expected '<project>/<epic>/<tid>'")
    proj, epic, tid = parts
    fname = tid if tid.endswith(".md") else f"{tid}.md"
    p = board / proj / epic / fname
    if not p.is_file():
        raise FileNotFoundError(f"Ticket not found: {ref}")
    return p


def days_until_purge(meta: dict[str, Any], now: datetime | None = None) -> int | None:
    if not meta.get("retired"):
        return None
    retired_dt = parse_iso_utc(meta.get("retired_at"))
    if retired_dt is None:
        return None
    max_days = int(meta.get("purge_after_days") or DEFAULT_PURGE_DAYS)
    elapsed = ((now or utc_now()) - retired_dt).total_seconds() / 86400.0
    return max(0, math.ceil(max_days - elapsed))


def api_retire(
    ref: str,
    reason: str,
    board: Path,
    purge_after_days: int = DEFAULT_PURGE_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Retire a non-done ticket: moves it back to backlog with retired metadata and a 120-day auto-purge timer."""
    reason_clean = (reason or "").strip()
    if len(reason_clean) < 5:
        raise ValueError("Retire reason is required (min 5 characters).")
    if purge_after_days < 1:
        raise ValueError("purge_after_days must be >= 1.")

    path = resolve_ticket_path(ref, board)
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    status = str(meta.get("status") or "backlog").strip().lower()
    if status == "done":
        raise PermissionError("Cannot retire a 'done' ticket; certified done tickets are immutable history.")

    ts = iso_utc(now)
    meta["status"] = "backlog"
    meta["retired"] = True
    meta["retired_at"] = ts
    meta["retire_reason"] = reason_clean
    meta["purge_after_days"] = int(purge_after_days)
    meta.pop("owner", None)
    meta.pop("agent", None)
    meta.pop("lease_until", None)
    meta.pop("lease_expires", None)
    meta["note"] = f"[RETIRED] {reason_clean}"

    log_line = f"- [{ts}] [RETIRED] {reason_clean} | auto-purge in {purge_after_days}d if still in backlog"
    new_body = append_execution_log(body, log_line)
    path.write_text(render_frontmatter(meta, new_body), encoding="utf-8", newline="\n")

    return {
        "ok": True,
        "ref": ref,
        "status": "backlog",
        "retired": True,
        "retired_at": ts,
        "purge_after_days": int(purge_after_days),
        "retire_reason": reason_clean,
    }


def api_restore(ref: str, board: Path, note: str = "Restored to active backlog", now: datetime | None = None) -> dict[str, Any]:
    """Un-retire a ticket and cancel its 120-day auto hard-delete timer."""
    path = resolve_ticket_path(ref, board)
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not meta.get("retired"):
        return {"ok": True, "ref": ref, "retired": False, "message": "Ticket was not retired."}

    ts = iso_utc(now)
    for key in ("retired", "retired_at", "retire_reason", "purge_after_days"):
        meta.pop(key, None)
    meta["note"] = note.strip() or "Restored to active backlog"

    log_line = f"- [{ts}] [RESTORED] {meta['note']}"
    new_body = append_execution_log(body, log_line)
    path.write_text(render_frontmatter(meta, new_body), encoding="utf-8", newline="\n")
    return {"ok": True, "ref": ref, "status": meta.get("status", "backlog"), "retired": False}


def api_rehome(
    ref: str,
    new_epic: str,
    board: Path,
    new_project: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Move a non-done ticket cleanly to another epic (or project/epic) without manual file manipulation."""
    src = resolve_ticket_path(ref, board)
    old_proj, old_epic, tid = ref.strip().replace("\\", "/").split("/")
    target_proj = (new_project or old_proj).strip()
    target_epic = new_epic.strip()
    if not target_proj or not target_epic:
        raise ValueError("new_epic (and optional new_project) must be non-empty slugs.")
    if any(x in target_proj + target_epic for x in ("..", "/", "\\")):
        raise ValueError("Invalid project or epic slug.")

    meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
    if str(meta.get("status") or "").lower() == "done":
        raise PermissionError("Cannot rehome a certified 'done' ticket (would invalidate its HMAC signature).")

    dst_dir = board / target_proj / target_epic
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        raise FileExistsError(f"Target ticket already exists: {target_proj}/{target_epic}/{tid}")

    ts = iso_utc(now)
    new_ref = f"{target_proj}/{target_epic}/{tid}"
    new_body = append_execution_log(body, f"- [{ts}] [REHOMED] {ref} -> {new_ref}")
    dst.write_text(render_frontmatter(meta, new_body), encoding="utf-8", newline="\n")
    src.unlink()
    return {"ok": True, "old_ref": ref, "new_ref": new_ref}


def purge_expired_retired(
    board: Path,
    default_days: int = DEFAULT_PURGE_DAYS,
    dry_run: bool = False,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Hard-delete backlog tickets retired >= 120 days ago. Throttled to once/hour unless force=True."""
    ref_now = now or utc_now()
    marker = board / ".last_purge"
    if not force and not dry_run and marker.is_file():
        try:
            last = parse_iso_utc(marker.read_text(encoding="utf-8").strip())
            if last and (ref_now - last).total_seconds() < PURGE_THROTTLE_SECONDS:
                return {"ok": True, "throttled": True, "purged": [], "skipped": 0}
        except Exception:
            pass

    purged: list[dict[str, Any]] = []
    skipped = 0
    audit_log = board / ".purge_audit.jsonl"

    if board.exists():
        for md in sorted(board.glob("*/*/*.md")):
            if md.name.lower() in {"project.md", "epic.md", "readme.md"}:
                continue
            try:
                meta, _ = split_frontmatter(md.read_text(encoding="utf-8"))
            except Exception:
                skipped += 1
                continue

            # Strict 4-guard safety check before hard deletion
            if str(meta.get("status") or "").strip().lower() != "backlog":
                continue
            if meta.get("retired") is not True:
                continue
            retired_dt = parse_iso_utc(meta.get("retired_at"))
            if retired_dt is None:
                skipped += 1
                continue
            max_days = int(meta.get("purge_after_days") or default_days)
            if (ref_now - retired_dt) < timedelta(days=max_days):
                continue

            rel = md.relative_to(board)
            tref = f"{rel.parts[0]}/{rel.parts[1]}/{md.stem}"
            record = {
                "ts": iso_utc(ref_now),
                "ref": tref,
                "title": str(meta.get("title") or ""),
                "retired_at": str(meta.get("retired_at")),
                "retire_reason": str(meta.get("retire_reason") or ""),
                "purge_after_days": max_days,
            }
            purged.append(record)
            if not dry_run:
                md.unlink(missing_ok=True)
                # Clean orphaned nonce if any
                nonce_key = tref.replace("/", "__")
                nonce_file = board / ".qa_nonces" / f"{nonce_key}.nonce"
                if nonce_file.is_file():
                    nonce_file.unlink(missing_ok=True)
                with open(audit_log, "a", encoding="utf-8") as af:
                    af.write(json.dumps(record, ensure_ascii=False) + "\n")

    if not dry_run:
        board.mkdir(parents=True, exist_ok=True)
        marker.write_text(iso_utc(ref_now) + "\n", encoding="utf-8")

    return {"ok": True, "dry_run": dry_run, "throttled": False, "purged_count": len(purged), "purged": purged, "skipped": skipped}


def compact_ticket_row(t: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Return a compact LLM-friendly summary row (omits heavy markdown bodies & logs)."""
    row = {
        "ref": t.get("ref") or t.get("reference") or "",
        "status": t.get("status") or "backlog",
        "title": t.get("title") or "",
        "owner": t.get("agent") or (t.get("owner") if isinstance(t.get("owner"), str) else ""),
        "progress": f"{t.get('todo_done', 0)}/{t.get('todo_total', 0)}" if t.get("todo_total") else None,
    }
    if t.get("retired"):
        row["retired"] = True
        row["days_until_purge"] = t.get("days_until_purge") if t.get("days_until_purge") is not None else days_until_purge(t, now=now)
    if t.get("is_rejected"):
        row["qa_rejected"] = True
    return {k: v for k, v in row.items() if v is not None and v != ""}


def paginate_items(
    items: list[dict[str, Any]],
    page: int = 1,
    page_size: int = 25,
    max_page_size: int = 100,
    status: str | None = None,
    project: str | None = None,
    epic: str | None = None,
    q: str | None = None,
    include_retired: bool = False,
) -> dict[str, Any]:
    """Filter and paginate ticket lists cleanly so MCP responses stay compact for LLMs."""
    ps = max(1, min(int(page_size or 25), max_page_size))
    pg = max(1, int(page or 1))
    ql = (q or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    for item in items:
        if not include_retired and item.get("retired"):
            continue
        if status and str(item.get("status") or "").lower() != status.lower():
            continue
        if project and str(item.get("project") or "").lower() != project.lower():
            continue
        if epic and str(item.get("epic") or "").lower() != epic.lower():
            continue
        if ql:
            hay = f"{item.get('ref', '')} {item.get('title', '')} {item.get('agent', '')} {item.get('project', '')} {item.get('epic', '')}".lower()
            if ql not in hay:
                continue
        filtered.append(item)

    total = len(filtered)
    total_pages = max(1, math.ceil(total / ps))
    pg = min(pg, total_pages)
    start = (pg - 1) * ps
    page_slice = [compact_ticket_row(x) for x in filtered[start : start + ps]]

    return {
        "items": page_slice,
        "pagination": {
            "page": pg,
            "page_size": ps,
            "total_items": total,
            "total_pages": total_pages,
            "has_prev": pg > 1,
            "has_next": pg < total_pages,
            "next_page": pg + 1 if pg < total_pages else None,
        },
    }
