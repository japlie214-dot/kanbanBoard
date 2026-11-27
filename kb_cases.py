"""kb_cases.py – Ticket-Linked Cases (Main <-> QA Communication, Proof, Discoveries & Attachments) (v3.0).

Replaces disconnected `evidence/*.md` files with structured Case threads stored in `board/_cases/`:
  - Every Case links to 1..100 tickets (may cross projects and epics).
  - Auto-collects `projects[]` and `epics[]` metadata from the linked tickets.
  - Supports threaded replies and safe binary/text attachments (PNG, JSON, HAR, logs) in `board/_cases/attachments/<cid>/`.
  - Marks purged/deleted tickets clearly as `[DELETED: ref — title · purged YYYY-MM-DD]` via `.purge_audit.jsonl` or link-time snapshot.
  - Auto-archives stale Cases into `board/_cases/_archive/YYYY/` once all linked tickets are deleted or done >= 180 days.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import kb_crud

MAX_LINKED_TICKETS = 100
DEFAULT_ARCHIVE_DONE_DAYS = 180
ARCHIVE_THROTTLE_SECONDS = 3600


def cases_root(board: Path) -> Path:
    return board / "_cases"


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "case").lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "case"


def _next_case_id(board: Path) -> str:
    cdir = cases_root(board)
    highest = 0
    if cdir.exists():
        for p in list(cdir.glob("C*.md")) + list((cdir / "_archive").glob("*/C*.md")):
            m = re.match(r"^C(\d+)", p.stem)
            if m:
                highest = max(highest, int(m.group(1)))
    return f"C{highest + 1:03d}"


def _load_purge_audit(board: Path) -> dict[str, dict[str, Any]]:
    audit_file = board / ".purge_audit.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not audit_file.is_file():
        return out
    for line in audit_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("ref"):
                out[str(rec["ref"])] = rec
        except Exception:
            continue
    return out


def _copy_attachments(cid: str, attachments: list[str] | None, board: Path) -> list[str]:
    if not attachments:
        return []
    dest_dir = cases_root(board) / "attachments" / cid
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored: list[str] = []
    for raw in attachments:
        src = Path(raw)
        if not src.is_file():
            raise FileNotFoundError(f"Attachment not found: {raw}")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", src.name)
        dst = dest_dir / safe_name
        shutil.copy2(src, dst)
        stored.append(f"_cases/attachments/{cid}/{safe_name}")
    return stored


def _resolve_linked_tickets(
    ticket_refs: list[str],
    saved_titles: dict[str, str],
    board: Path,
) -> list[dict[str, Any]]:
    purge_map = _load_purge_audit(board)
    resolved: list[dict[str, Any]] = []
    for ref in ticket_refs:
        parts = [p for p in ref.split("/") if p]
        proj = parts[0] if len(parts) == 3 else ""
        epic = parts[1] if len(parts) == 3 else ""
        try:
            tpath = kb_crud.resolve_ticket_path(ref, board)
            meta, _ = kb_crud.split_frontmatter(tpath.read_text(encoding="utf-8"))
            resolved.append({
                "ref": ref,
                "project": proj,
                "epic": epic,
                "title": str(meta.get("title") or saved_titles.get(ref) or ""),
                "status": str(meta.get("status") or "backlog"),
                "retired": bool(meta.get("retired")),
                "deleted": False,
                "tombstone": None,
            })
        except (FileNotFoundError, ValueError):
            pinfo = purge_map.get(ref) or {}
            title = str(pinfo.get("title") or saved_titles.get(ref) or "Unknown title")
            purged_at = str(pinfo.get("ts") or "")[:10]
            suffix = f" · purged {purged_at}" if purged_at else " · deleted"
            resolved.append({
                "ref": ref,
                "project": proj,
                "epic": epic,
                "title": title,
                "status": "deleted",
                "retired": False,
                "deleted": True,
                "tombstone": f"[DELETED: {ref} — {title}{suffix}]",
            })
    return resolved


def api_case_create(
    title: str,
    tickets: list[str],
    body: str,
    board: Path,
    kind: str = "qa",
    author: str = "agent",
    attachments: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a Case thread linked to 1..100 tickets (cross-project/epic supported)."""
    clean_title = (title or "").strip()
    if len(clean_title) < 3:
        raise ValueError("Case title must be at least 3 characters.")

    dedup_refs: list[str] = []
    seen: set[str] = set()
    for r in (tickets or []):
        rc = str(r).strip().replace("\\", "/")
        if rc and rc not in seen:
            seen.add(rc)
            dedup_refs.append(rc)

    if not dedup_refs:
        raise ValueError("A Case must link to at least 1 ticket.")
    if len(dedup_refs) > MAX_LINKED_TICKETS:
        raise ValueError(f"A Case can link to at most {MAX_LINKED_TICKETS} tickets (got {len(dedup_refs)}).")

    kind_norm = (kind or "qa").strip().lower()
    if kind_norm not in {"qa", "discovery", "discussion", "bug", "decision"}:
        raise ValueError(f"Unsupported case kind: {kind}")

    projects: set[str] = set()
    epics: set[str] = set()
    saved_titles: dict[str, str] = {}
    for ref in dedup_refs:
        tpath = kb_crud.resolve_ticket_path(ref, board)
        proj, epic, _ = ref.split("/")
        projects.add(proj)
        epics.add(f"{proj}/{epic}")
        tmeta, _ = kb_crud.split_frontmatter(tpath.read_text(encoding="utf-8"))
        saved_titles[ref] = str(tmeta.get("title") or "")

    cid = _next_case_id(board)
    ts = kb_crud.iso_utc(now)
    stored_att = _copy_attachments(cid, attachments, board)

    cdir = cases_root(board)
    cdir.mkdir(parents=True, exist_ok=True)
    cpath = cdir / f"{cid}-{_slugify(clean_title)}.md"

    meta = {
        "id": cid,
        "title": clean_title,
        "kind": kind_norm,
        "author": author.strip() or "agent",
        "created_at": ts,
        "updated_at": ts,
        "tickets": dedup_refs,
        "projects": sorted(projects),
        "epics": sorted(epics),
        "ticket_titles_json": json.dumps(saved_titles, ensure_ascii=False),
        "attachments": stored_att,
    }
    md_body = f"\n## Initial Post ({author} · {ts})\n{(body or '').strip()}\n"
    if stored_att:
        md_body += "\n### Attachments\n" + "\n".join(f"- `{a}`" for a in stored_att) + "\n"

    cpath.write_text(kb_crud.render_frontmatter(meta, md_body), encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "id": cid,
        "path": str(cpath),
        "title": clean_title,
        "kind": kind_norm,
        "tickets": dedup_refs,
        "projects": sorted(projects),
        "epics": sorted(epics),
        "attachments": stored_att,
    }


def _find_case_file(case_id: str, board: Path) -> Path:
    cid = case_id.strip().upper()
    cdir = cases_root(board)
    matches = sorted(cdir.glob(f"{cid}*.md")) if cdir.exists() else []
    if not matches:
        arch = cdir / "_archive"
        if arch.exists():
            matches = sorted(arch.glob(f"*/{cid}*.md"))
    if not matches:
        raise FileNotFoundError(f"Case not found: {case_id}")
    return matches[0]


def api_case_reply(
    case_id: str,
    author: str,
    body: str,
    board: Path,
    attachments: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Append a reply (and optional attachments) to an existing Case thread."""
    cpath = _find_case_file(case_id, board)
    meta, existing_body = kb_crud.split_frontmatter(cpath.read_text(encoding="utf-8"))
    cid = str(meta.get("id") or case_id.upper())
    ts = kb_crud.iso_utc(now)
    new_att = _copy_attachments(cid, attachments, board)

    all_att = list(meta.get("attachments") or []) + new_att
    meta["attachments"] = all_att
    meta["updated_at"] = ts

    reply_md = f"\n## Reply ({author.strip() or 'agent'} · {ts})\n{(body or '').strip()}\n"
    if new_att:
        reply_md += "\n### Attachments\n" + "\n".join(f"- `{a}`" for a in new_att) + "\n"

    cpath.write_text(kb_crud.render_frontmatter(meta, existing_body.rstrip() + "\n" + reply_md), encoding="utf-8", newline="\n")
    return {"ok": True, "id": cid, "updated_at": ts, "attachments_added": new_att}


def api_case_show(case_id: str, board: Path) -> dict[str, Any]:
    cpath = _find_case_file(case_id, board)
    meta, body = kb_crud.split_frontmatter(cpath.read_text(encoding="utf-8"))
    tickets = list(meta.get("tickets") or [])
    saved_titles: dict[str, str] = {}
    if meta.get("ticket_titles_json"):
        try:
            saved_titles = json.loads(str(meta["ticket_titles_json"]))
        except Exception:
            pass
    linked = _resolve_linked_tickets(tickets, saved_titles, board)
    return {
        "ok": True,
        "id": meta.get("id"),
        "title": meta.get("title"),
        "kind": meta.get("kind"),
        "author": meta.get("author"),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "projects": meta.get("projects") or [],
        "epics": meta.get("epics") or [],
        "linked_tickets": linked,
        "deleted_ticket_count": sum(1 for x in linked if x["deleted"]),
        "attachments": meta.get("attachments") or [],
        "body": body.strip(),
    }


def api_case_list(
    board: Path,
    ticket: str | None = None,
    project: str | None = None,
    epic: str | None = None,
    kind: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    cdir = cases_root(board)
    rows: list[dict[str, Any]] = []
    if cdir.exists():
        for p in sorted(cdir.glob("C*.md"), reverse=True):
            try:
                meta, _ = kb_crud.split_frontmatter(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            trefs = list(meta.get("tickets") or [])
            projs = list(meta.get("projects") or [])
            epics = list(meta.get("epics") or [])
            if ticket and ticket not in trefs:
                continue
            if project and project not in projs:
                continue
            if epic and not any(e == epic or e.endswith(f"/{epic}") for e in epics):
                continue
            if kind and str(meta.get("kind") or "").lower() != kind.lower():
                continue
            rows.append({
                "id": meta.get("id"),
                "title": meta.get("title"),
                "kind": meta.get("kind"),
                "author": meta.get("author"),
                "updated_at": meta.get("updated_at"),
                "ticket_count": len(trefs),
                "tickets": trefs[:5],
                "projects": projs,
            })

    ps = max(1, min(int(page_size or 20), 100))
    total = len(rows)
    total_pages = max(1, math.ceil(total / ps))
    pg = max(1, min(int(page or 1), total_pages))
    start = (pg - 1) * ps
    return {
        "ok": True,
        "items": rows[start : start + ps],
        "pagination": {
            "page": pg,
            "page_size": ps,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": pg < total_pages,
            "next_page": pg + 1 if pg < total_pages else None,
        },
    }


def archive_stale_cases(
    board: Path,
    max_done_days: int = DEFAULT_ARCHIVE_DONE_DAYS,
    dry_run: bool = False,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Auto-archive Cases whose linked tickets are ALL deleted or done >= max_done_days."""
    ref_now = now or kb_crud.utc_now()
    cdir = cases_root(board)
    marker = cdir / ".last_archive"
    if not force and not dry_run and marker.is_file():
        last = kb_crud.parse_iso_utc(marker.read_text(encoding="utf-8").strip())
        if last and (ref_now - last).total_seconds() < ARCHIVE_THROTTLE_SECONDS:
            return {"ok": True, "throttled": True, "archived": []}

    archived: list[str] = []
    if cdir.exists():
        for p in sorted(cdir.glob("C*.md")):
            try:
                meta, _ = kb_crud.split_frontmatter(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            updated_dt = kb_crud.parse_iso_utc(str(meta.get("updated_at") or meta.get("created_at") or ""))
            if not updated_dt or (ref_now - updated_dt) < timedelta(days=max_done_days):
                continue
            trefs = list(meta.get("tickets") or [])
            linked = _resolve_linked_tickets(trefs, {}, board)
            if linked and all(x["deleted"] or x["status"] == "done" for x in linked):
                archived.append(str(meta.get("id") or p.stem))
                if not dry_run:
                    year_dir = cdir / "_archive" / str(ref_now.year)
                    year_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(year_dir / p.name))

    if not dry_run and cdir.exists():
        marker.write_text(kb_crud.iso_utc(ref_now) + "\n", encoding="utf-8")

    return {"ok": True, "dry_run": dry_run, "throttled": False, "archived_count": len(archived), "archived": archived}
