#!/usr/bin/env python3
"""kb_doc_v401.py — v4.0.1 extensions for kb_doc_store & kb_doc_runner:
  - Per-section rollback snapshots (last 5 versions under doc/.snapshots/<slug>/)
  - Smart SHOW drift context builder (<= 2 versions: bounded delta; > 2 versions: fresh from tell.html)
  - Internal `doc_prompts/` loader (keeps kb-doc completely invisible to main agents)
  - Declarative `stack_diagram` rendering outside the sterilized LLM sandbox
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import kb_doc_store
import kb_stack_diagram
import kb_version

MAX_SNAPSHOTS_PER_SECTION = 5


def _ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def snapshot_section(board: Path, project: str, slug: str) -> Optional[str]:
    """Copy current section files into `doc/.snapshots/<slug>/<ts>/` before overwrite. Keeps last 5."""
    clean_slug = kb_doc_store.validate_slug(slug)
    sec_dir = kb_doc_store.doc_root(board, project) / "sections" / clean_slug
    if not sec_dir.is_dir():
        return None
    snap_root = kb_doc_store.doc_root(board, project) / ".snapshots" / clean_slug
    snap_id = _ts_slug()
    dest = snap_root / snap_id
    # Avoid collision within the same second
    suffix = 1
    while dest.exists():
        snap_id = f"{_ts_slug()}_{suffix}"
        dest = snap_root / snap_id
        suffix += 1
    shutil.copytree(sec_dir, dest)

    # Prune older snapshots beyond MAX_SNAPSHOTS_PER_SECTION
    snaps = sorted([p for p in snap_root.iterdir() if p.is_dir()])
    for old in snaps[:-MAX_SNAPSHOTS_PER_SECTION]:
        shutil.rmtree(old, ignore_errors=True)
    return snap_id


def list_snapshots(board: Path, project: str, slug: str) -> list[str]:
    clean_slug = kb_doc_store.validate_slug(slug)
    snap_root = kb_doc_store.doc_root(board, project) / ".snapshots" / clean_slug
    if not snap_root.is_dir():
        return []
    return sorted([p.name for p in snap_root.iterdir() if p.is_dir()], reverse=True)


def revert_section(board: Path, project: str, slug: str, snapshot_id: Optional[str] = None) -> dict[str, Any]:
    """Restore a section from its latest (or specified) rollback snapshot."""
    clean_slug = kb_doc_store.validate_slug(slug)
    snaps = list_snapshots(board, project, clean_slug)
    if not snaps:
        raise FileNotFoundError(f"No rollback snapshots available for section '{clean_slug}'.")
    chosen = snapshot_id or snaps[0]
    if chosen not in snaps:
        raise FileNotFoundError(f"Snapshot '{chosen}' not found for section '{clean_slug}'.")

    snap_dir = kb_doc_store.doc_root(board, project) / ".snapshots" / clean_slug / chosen
    sec_dir = kb_doc_store.doc_root(board, project) / "sections" / clean_slug
    if sec_dir.is_dir():
        shutil.rmtree(sec_dir)
    shutil.copytree(snap_dir, sec_dir)

    meta = json.loads((sec_dir / "meta.json").read_text(encoding="utf-8"))
    manifest = kb_doc_store.load_manifest(board, project)
    for entry in manifest.get("sections") or []:
        if entry.get("slug") == clean_slug:
            entry["title"] = meta.get("title", entry.get("title"))
            entry["summary"] = meta.get("summary", entry.get("summary", ""))
            if meta.get("parent_section"):
                entry["parent_section"] = meta["parent_section"]
            entry["tell_version"] = meta.get("tell_version")
            entry["tell_updated_at"] = meta.get("tell_updated_at")
            entry["show_version"] = meta.get("show_version")
            entry["show_updated_at"] = meta.get("show_updated_at")
            entry["has_show"] = (sec_dir / "show.js").is_file()
            break
    kb_doc_store.save_manifest(board, project, manifest)
    return {"ok": True, "slug": clean_slug, "reverted_to": chosen, "meta": meta}


def compute_version_gap(board: Path, project: str, show_version: Optional[str], tell_version: Optional[str]) -> int:
    """Count how many released versions sit between show_version and tell_version."""
    if not show_version or not tell_version or show_version == tell_version:
        return 0
    state = kb_version.load_version_state(board, project)
    hist_vers = [h.get("version") for h in (state.get("history") or [])]
    if show_version in hist_vers and tell_version in hist_vers:
        return max(0, hist_vers.index(tell_version) - hist_vers.index(show_version))
    # Fallback when show_version predates recorded history
    return len(hist_vers)


def build_show_context_v401(board: Path, project: str, slug: str) -> dict[str, Any]:
    """Current-truth-first + bounded delta context builder for on-demand SHOW generation.

    - Gap <= 2 versions: includes tell.html + existing show.js + up to 12 delta tickets.
    - Gap > 2 versions (or first-time SHOW): fresh synthesis from tell.html + meta.json
      + latest 8 source_tickets + 1-line version-range summary (omits stale show.js).
    """
    sec = kb_doc_store.read_section(board, project, slug)
    meta = sec["meta"]
    show_ver = meta.get("show_version")
    tell_ver = meta.get("tell_version") or kb_version.load_version_state(board, project).get("version", "V0.0.0")
    gap = compute_version_gap(board, project, show_ver, tell_ver)
    fresh_synthesis = (not sec.get("has_show")) or (gap > 2)

    all_done = {t["ref"]: t for t in kb_version.scan_project_done_tickets(board, project)}
    state = kb_version.load_version_state(board, project)
    hist = state.get("history") or []

    if fresh_synthesis:
        refs = (meta.get("source_tickets") or [])[-8:]
        ticket_ctx = [
            {"ref": r, "title": all_done[r]["title"], "files": all_done[r]["files"]}
            for r in refs if r in all_done
        ]
        existing_show_js = None
        strategy = "fresh_current_state"
    else:
        # Collect tickets shipped in versions strictly after show_ver up to tell_ver
        collecting = False
        delta_refs: list[str] = []
        for h in hist:
            v = h.get("version")
            if v == show_ver:
                collecting = True
                continue
            if collecting:
                delta_refs.extend(h.get("tickets") or [])
            if v == tell_ver:
                break
        # Prefer tickets linked to this section or fallback to recent delta tickets (cap 12)
        sec_refs = set(meta.get("source_tickets") or [])
        prioritized = [r for r in delta_refs if r in sec_refs] or delta_refs
        prioritized = list(dict.fromkeys(prioritized))[-12:]
        ticket_ctx = [
            {"ref": r, "title": all_done[r]["title"], "files": all_done[r]["files"], "cases": all_done[r]["cases"]}
            for r in prioritized if r in all_done
        ]
        existing_show_js = sec.get("show_js") or None
        strategy = "bounded_delta"

    open_fb = [
        fb for fb in kb_doc_store.list_feedback(board, project, status="open")
        if fb.get("section") in (slug, "global")
    ]
    return {
        "mode": "SHOW",
        "strategy": strategy,
        "version_gap": gap,
        "project": project,
        "slug": slug,
        "tell_version": tell_ver,
        "previous_show_version": show_ver,
        "meta": meta,
        "tell_html": sec.get("tell_html") or "",
        "existing_show_js": existing_show_js,
        "tickets": ticket_ctx,
        "open_boss_feedback": open_fb,
    }


def load_internal_prompt(repo_root: Path, mode: str) -> str:
    """Load internal `doc_prompts/RUNNER.md` + mode-specific guide (invisible to main agents)."""
    prompts_dir = repo_root / "doc_prompts"
    runner_p = prompts_dir / "RUNNER.md"
    guide_p = prompts_dir / ("TELL-GUIDE.md" if mode.lower() == "tell" else "SHOW-GUIDE.md")
    parts: list[str] = []
    if runner_p.is_file():
        parts.append(runner_p.read_text(encoding="utf-8").strip())
    if guide_p.is_file():
        parts.append(guide_p.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)


def apply_stack_diagram_if_present(board: Path, project: str, slug: str, diagram_spec: Optional[dict[str, Any]]) -> bool:
    """Render declarative stack_diagram JSON into `sections/<slug>/diagram.html` outside LLM sandbox."""
    if not isinstance(diagram_spec, dict) or not diagram_spec.get("groups"):
        return False
    clean_slug = kb_doc_store.validate_slug(slug)
    frag = kb_stack_diagram.render_stack_diagram_fragment(diagram_spec, board=board)
    sec_dir = kb_doc_store.doc_root(board, project) / "sections" / clean_slug
    sec_dir.mkdir(parents=True, exist_ok=True)
    (sec_dir / "diagram.html").write_text(frag, encoding="utf-8", newline="\n")
    return True
