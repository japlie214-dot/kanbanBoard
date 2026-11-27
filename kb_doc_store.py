#!/usr/bin/env python3
"""kb_doc_store.py — Containerized per-project doc storage, global/per-project
Boss config, section CRUD, and 120-day resolved feedback lifecycle.

Layout:
  board/_doc_config.json                  # Global Boss defaults (runner, thresholds)
  board/<project>/doc/
    ├── doc.config.json                   # Optional per-project overrides
    ├── manifest.json                     # Version, ordered section index, TELL/SHOW versions
    ├── overrides.css                     # Optional — kb-doc has full creative freedom
    ├── feedback.jsonl                    # Open (never expires) + resolved (120d auto-purge)
    ├── runs.jsonl                        # Audit log of kb-doc runs
    └── sections/<slug>/
        ├── meta.json                     # title, summary, source_tickets, tell_version, show_version
        ├── tell.html                     # Auto-updated on version bump
        └── show.js                       # On-demand by Boss in Web App
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

DEFAULT_DOC_CONFIG: dict[str, Any] = {
    "primary_backend": "agy",
    "primary_model": "gemini-4-hydrogen-medium",
    "fallback_backend": "codex",
    "fallback_model": "gpt-6-luna",
    "fallback_reasoning_effort": "medium",
    "timeout_seconds": 150,
    "auto_tell_on_bump": True,
    "cluster_threshold": 7,
    "total_threshold": 12,
    "snooze_delta": 2,
    "edge_threshold": 0.35,
    "feedback_retention_days": 120,
}

ALLOWED_BACKENDS = {"agy", "codex"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not SLUG_RE.match(s):
        raise ValueError(f"Invalid section slug '{slug}'. Must match {SLUG_RE.pattern}")
    return s


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def _atomic_write_json(path: Path, data: Any) -> None:
    _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _validate_project(project: str) -> str:
    p = (project or "").strip()
    if not p or ".." in p or "/" in p or "\\" in p or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", p):
        raise ValueError(f"Invalid project slug '{project}'.")
    return p


def doc_root(board: Path, project: str) -> Path:
    return board / _validate_project(project) / "doc"


def global_config_path(board: Path) -> Path:
    return board / "_doc_config.json"


def project_config_path(board: Path, project: str) -> Path:
    return doc_root(board, project) / "doc.config.json"


def validate_config_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize Boss config fields."""
    clean: dict[str, Any] = {}
    if not isinstance(patch, dict):
        raise ValueError("Config payload must be a JSON object.")

    for key in ("primary_backend", "fallback_backend"):
        if key in patch and patch[key] is not None:
            val = str(patch[key]).strip().lower()
            if val not in ALLOWED_BACKENDS:
                raise ValueError(f"{key} must be one of {sorted(ALLOWED_BACKENDS)}")
            clean[key] = val

    for key in ("primary_model", "fallback_model", "fallback_reasoning_effort"):
        if key in patch and patch[key] is not None:
            val = str(patch[key]).strip()
            if not val or len(val) > 100:
                raise ValueError(f"Invalid {key}")
            clean[key] = val

    if "auto_tell_on_bump" in patch and patch["auto_tell_on_bump"] is not None:
        clean["auto_tell_on_bump"] = bool(patch["auto_tell_on_bump"])

    int_bounds = {
        "timeout_seconds": (30, 900),
        "cluster_threshold": (2, 100),
        "total_threshold": (0, 200),
        "snooze_delta": (1, 50),
        "feedback_retention_days": (7, 3650),
    }
    for key, (lo, hi) in int_bounds.items():
        if key in patch and patch[key] is not None:
            val = int(patch[key])
            if not (lo <= val <= hi):
                raise ValueError(f"{key} must be between {lo} and {hi}")
            clean[key] = val

    if "edge_threshold" in patch and patch["edge_threshold"] is not None:
        val = float(patch["edge_threshold"])
        if not (0.05 <= val <= 0.95):
            raise ValueError("edge_threshold must be between 0.05 and 0.95")
        clean["edge_threshold"] = round(val, 3)

    return clean


def load_global_config(board: Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_DOC_CONFIG)
    p = global_config_path(board)
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_global_config(board: Path, patch: dict[str, Any]) -> dict[str, Any]:
    cfg = load_global_config(board)
    cfg.update(validate_config_patch(patch))
    _atomic_write_json(global_config_path(board), cfg)
    return cfg


def load_effective_config(board: Path, project: Optional[str] = None) -> dict[str, Any]:
    cfg = load_global_config(board)
    if project:
        p = project_config_path(board, project)
        if p.is_file():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    cfg.update(raw)
            except (OSError, json.JSONDecodeError):
                pass
    return cfg


def save_project_config(board: Path, project: str, patch: dict[str, Any]) -> dict[str, Any]:
    p = project_config_path(board, project)
    existing: dict[str, Any] = {}
    if p.is_file():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(validate_config_patch(patch))
    _atomic_write_json(p, existing)
    return load_effective_config(board, project)


def load_manifest(board: Path, project: str) -> dict[str, Any]:
    p = doc_root(board, project) / "manifest.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("project", project)
                data.setdefault("version", "V0.0.0")
                data.setdefault("sections", [])
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "project": project,
        "version": "V0.0.0",
        "updated_at": None,
        "sections": [],
    }


def save_manifest(board: Path, project: str, manifest: dict[str, Any]) -> None:
    manifest["project"] = project
    manifest["updated_at"] = _now_iso()
    _atomic_write_json(doc_root(board, project) / "manifest.json", manifest)


def sanitize_tell_html(html: str) -> str:
    """Strip <script> tags, inline on* event handlers (quoted or unquoted), and dangerous URIs."""
    cleaned = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", html or "", flags=re.I | re.S)
    cleaned = re.sub(r"\son[a-z]+\s*=\s*(['\"]).*?\1", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"\son[a-z]+\s*=\s*[^\s>]+", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"(\b(?:href|src)\s*=\s*)(?:(['\"])\s*(?:javascript|vbscript|data:text/html):[^'\"]*\2|(?:javascript|vbscript|data:text/html):[^\s>]+)",
        r'\1"#"',
        cleaned,
        flags=re.I,
    )
    return cleaned.strip()


def upsert_section(
    board: Path,
    project: str,
    slug: str,
    *,
    title: str,
    summary: str = "",
    tell_html: Optional[str] = None,
    show_js: Optional[str] = None,
    version: str = "V0.0.0",
    source_tickets: Optional[list[str]] = None,
    order: Optional[int] = None,
) -> dict[str, Any]:
    """Create or update a single containerized doc section cleanly."""
    clean_slug = validate_slug(slug)
    sec_dir = doc_root(board, project) / "sections" / clean_slug
    sec_dir.mkdir(parents=True, exist_ok=True)
    meta_path = sec_dir / "meta.json"

    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}

    now = _now_iso()
    meta["slug"] = clean_slug
    meta["title"] = (title or meta.get("title") or clean_slug).strip()
    meta["summary"] = (summary if summary is not None else meta.get("summary", "")).strip()
    if source_tickets is not None:
        meta["source_tickets"] = list(dict.fromkeys(str(t) for t in source_tickets))
    else:
        meta.setdefault("source_tickets", [])

    if tell_html is not None:
        _atomic_write_text(sec_dir / "tell.html", sanitize_tell_html(tell_html) + "\n")
        meta["tell_version"] = version
        meta["tell_updated_at"] = now
    else:
        meta.setdefault("tell_version", None)
        meta.setdefault("tell_updated_at", None)

    if show_js is not None:
        _atomic_write_text(sec_dir / "show.js", (show_js or "").strip() + "\n")
        meta["show_version"] = version
        meta["show_updated_at"] = now
    else:
        meta.setdefault("show_version", None)
        meta.setdefault("show_updated_at", None)

    _atomic_write_json(meta_path, meta)

    manifest = load_manifest(board, project)
    manifest["version"] = version
    sections = [s for s in manifest.get("sections", []) if s.get("slug") != clean_slug]
    entry = {
        "slug": clean_slug,
        "title": meta["title"],
        "summary": meta["summary"],
        "order": order if order is not None else len(sections),
        "tell_version": meta.get("tell_version"),
        "tell_updated_at": meta.get("tell_updated_at"),
        "show_version": meta.get("show_version"),
        "show_updated_at": meta.get("show_updated_at"),
        "has_show": (sec_dir / "show.js").is_file(),
    }
    sections.append(entry)
    sections.sort(key=lambda s: (int(s.get("order", 999)), s["slug"]))
    manifest["sections"] = sections
    save_manifest(board, project, manifest)
    return meta


def delete_section(board: Path, project: str, slug: str) -> bool:
    clean_slug = validate_slug(slug)
    sec_dir = doc_root(board, project) / "sections" / clean_slug
    existed = sec_dir.is_dir()
    if existed:
        shutil.rmtree(sec_dir)
    manifest = load_manifest(board, project)
    manifest["sections"] = [s for s in manifest.get("sections", []) if s.get("slug") != clean_slug]
    save_manifest(board, project, manifest)
    return existed


def read_section(board: Path, project: str, slug: str) -> dict[str, Any]:
    clean_slug = validate_slug(slug)
    sec_dir = doc_root(board, project) / "sections" / clean_slug
    meta_path = sec_dir / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Doc section '{clean_slug}' not found for project '{project}'.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    tell_path = sec_dir / "tell.html"
    show_path = sec_dir / "show.js"
    return {
        "meta": meta,
        "tell_html": tell_path.read_text(encoding="utf-8") if tell_path.is_file() else "",
        "has_show": show_path.is_file(),
        "show_js": show_path.read_text(encoding="utf-8") if show_path.is_file() else "",
    }


def write_overrides_css(board: Path, project: str, css: str) -> None:
    _atomic_write_text(doc_root(board, project) / "overrides.css", (css or "").strip() + "\n")


def read_overrides_css(board: Path, project: str) -> str:
    p = doc_root(board, project) / "overrides.css"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


# ── Boss Feedback Lifecycle (Open never expires; Resolved auto-purged at 120d) ─

def _feedback_path(board: Path, project: str) -> Path:
    return doc_root(board, project) / "feedback.jsonl"


def list_feedback(board: Path, project: str, status: Optional[str] = None) -> list[dict[str, Any]]:
    p = _feedback_path(board, project)
    if not p.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if status and obj.get("status") != status:
                continue
            items.append(obj)
        except json.JSONDecodeError:
            continue
    return items


def _write_feedback_list(board: Path, project: str, items: list[dict[str, Any]]) -> None:
    lines = [json.dumps(x, ensure_ascii=False) for x in items]
    _atomic_write_text(_feedback_path(board, project), ("\n".join(lines) + "\n") if lines else "")


def add_feedback(
    board: Path,
    project: str,
    text: str,
    section: str = "global",
    author: str = "Boss",
) -> dict[str, Any]:
    msg = (text or "").strip()
    if len(msg) < 3:
        raise ValueError("Feedback text must be at least 3 characters.")
    sec = "global" if (section or "global").strip().lower() == "global" else validate_slug(section)
    items = list_feedback(board, project)
    entry = {
        "id": "fb-" + uuid.uuid4().hex[:8],
        "section": sec,
        "author": (author or "Boss").strip(),
        "text": msg,
        "created_at": _now_iso(),
        "status": "open",
        "resolved_at": None,
        "resolved_in_version": None,
        "resolution_note": "",
    }
    items.append(entry)
    _write_feedback_list(board, project, items)
    return entry


def resolve_feedback(
    board: Path,
    project: str,
    feedback_id: str,
    version: str,
    resolution_note: str = "",
) -> Optional[dict[str, Any]]:
    items = list_feedback(board, project)
    updated = None
    for item in items:
        if item.get("id") == feedback_id and item.get("status") == "open":
            item["status"] = "resolved"
            item["resolved_at"] = _now_iso()
            item["resolved_in_version"] = version
            item["resolution_note"] = (resolution_note or "").strip()
            updated = item
            break
    if updated is not None:
        _write_feedback_list(board, project, items)
    return updated


def purge_expired_feedback(
    board: Path,
    project: str,
    retention_days: int = 120,
    now: Optional[datetime] = None,
) -> int:
    """Auto-delete RESOLVED feedback older than `retention_days`. OPEN feedback is never deleted."""
    items = list_feedback(board, project)
    if not items:
        return 0
    ref_now = now or datetime.now(timezone.utc)
    cutoff = ref_now - timedelta(days=retention_days)
    kept: list[dict[str, Any]] = []
    purged = 0
    for item in items:
        if item.get("status") != "resolved":
            kept.append(item)
            continue
        res_dt = _parse_iso(str(item.get("resolved_at") or ""))
        if res_dt is not None and res_dt < cutoff:
            purged += 1
        else:
            kept.append(item)
    if purged:
        _write_feedback_list(board, project, kept)
    return purged


def append_run_log(board: Path, project: str, record: dict[str, Any]) -> None:
    p = doc_root(board, project) / "runs.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    record.setdefault("created_at", _now_iso())
    with p.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_runs(board: Path, project: str, limit: int = 25) -> list[dict[str, Any]]:
    p = doc_root(board, project) / "runs.jsonl"
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out[-limit:]))
