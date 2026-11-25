"""kb_ergonomics.py – Frictionless ticket planning, auto-inference, lease reaping, and QA evidence helpers.

Stdlib-only helper module for KanbanBoard v2.4+:
  - Replaces brittle `scaffold` templates with structured `steps` -> Todo Tree builder (`quick` vs `standard` tiers).
  - Auto-infers project slug from current working directory via `board/repo_map.json`.
  - Auto-captures modified/untracked files from git on `verify`.
  - Fixes Gate 2 ("Zero Work" Git Gate) false rejections for committed work, research, or docs tickets.
  - Auto-reaps expired leases so stale agents stop cluttering the board.
  - Validates both legacy 6-section and compact Ponytail + Positive/Negative QA evidence reports.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_plan_from_steps(steps: list[Any], tier: str = "standard") -> str:
    """Convert a simple list of strings or step dicts into valid Todo Tree markdown.

    Supports:
      - Plain strings: ["Implement X", "Run pytest"]
      - Dicts: {"id": "S1", "text": "...", "after": ["S0"], "optional": False,
                "accept": True, "lane": "core", "when": "if(cond):fork1", "parallel": False}
    """
    if not steps:
        raise ValueError("steps must contain at least 1 item")

    tier_norm = (tier or "standard").strip().lower()
    if tier_norm not in {"quick", "standard"}:
        raise ValueError("tier must be 'quick' or 'standard'")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(steps, start=1):
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            normalized.append({"id": f"S{idx}", "text": text})
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            sid = str(item.get("id") or f"S{idx}").strip()
            entry = dict(item)
            entry["id"] = sid
            entry["text"] = text
            normalized.append(entry)
        else:
            raise ValueError(f"Unsupported step item at index {idx - 1}: {type(item).__name__}")

    if not normalized:
        raise ValueError("steps must contain at least 1 non-empty item")

    # Auto-mark last step as mandatory acceptance if none explicitly marked
    has_accept = any(bool(s.get("accept")) or "[ACCEPTANCE" in s["text"] for s in normalized)
    if not has_accept:
        normalized[-1]["accept"] = True

    lines: list[str] = []
    for idx, s in enumerate(normalized):
        tags: list[str] = []
        if idx == 0 and "[START]" not in s["text"]:
            tags.append("[START]")

        lane = str(s.get("lane") or "").strip()
        if lane:
            tags.append(f"[lane:{lane}]")

        after = s.get("after")
        if after:
            if isinstance(after, (list, tuple)):
                after_expr = ",".join(str(x).strip() for x in after if str(x).strip())
            else:
                after_expr = str(after).strip()
            if after_expr:
                tags.append(f"[after:{after_expr}]")
        elif idx > 0 and not s.get("parallel"):
            prev_id = normalized[idx - 1]["id"]
            tags.append(f"[after:{prev_id}]")

        if s.get("parallel"):
            tags.append("[parallel]")

        when = str(s.get("when") or "").strip()
        if when:
            tags.append(f"[when:{when}]")

        is_opt = bool(s.get("optional"))
        if is_opt:
            tags.append("[optional]")

        if s.get("accept") and "[ACCEPTANCE" not in s["text"]:
            tags.append("[ACCEPTANCE:OPTIONAL]" if is_opt else "[ACCEPTANCE:MANDATORY]")

        tag_str = (" " + " ".join(tags)) if tags else ""
        lines.append(f"- [ ] {s['id']}{tag_str} {s['text']}")

    return "\n".join(lines)


def infer_project_from_cwd(cwd: str | Path, board_root: Path) -> str | None:
    """Resolve project slug from board/repo_map.json by longest matching path prefix."""
    map_file = board_root / "repo_map.json"
    if not map_file.is_file():
        return None
    try:
        mapping = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(mapping, dict):
        return None

    norm_cwd = str(Path(cwd).resolve()).replace("\\", "/").rstrip("/").lower()
    best_match: tuple[int, str] | None = None
    for raw_path, slug in mapping.items():
        if not isinstance(raw_path, str) or not isinstance(slug, str):
            continue
        norm_key = raw_path.replace("\\", "/").rstrip("/").lower()
        if norm_cwd == norm_key or norm_cwd.startswith(norm_key + "/"):
            if best_match is None or len(norm_key) > best_match[0]:
                best_match = (len(norm_key), slug.strip())
    return best_match[1] if best_match else None


def capture_git_changed_files(workspace: str | Path) -> list[str]:
    """Return sorted list of modified/added/untracked file paths from git status --porcelain."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return []
        files: list[str] = []
        for line in proc.stdout.splitlines():
            if len(line) < 4:
                continue
            entry = line[3:].strip()
            if " -> " in entry:
                entry = entry.split(" -> ", 1)[1].strip()
            if entry:
                files.append(entry)
        return sorted(set(files))
    except Exception:
        return []


def has_verifiable_work(workspace: str | Path, meta: dict[str, Any]) -> tuple[bool, str]:
    """Gate 2 replacement: allow verify if dirty git tree, new commits since claim, or research/docs ticket."""
    ticket_type = str(meta.get("type") or meta.get("tier") or "").strip().lower()
    if ticket_type in {"research", "docs", "investigation"}:
        return True, f"allowed: ticket type '{ticket_type}' does not require code diff"

    changed = capture_git_changed_files(workspace)
    if changed:
        return True, f"git working tree has {len(changed)} changed file(s)"

    claimed_commit = str(meta.get("claimed_commit") or "").strip()
    if claimed_commit:
        try:
            proc = subprocess.run(
                ["git", "rev-list", "--count", f"{claimed_commit}..HEAD"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and int(proc.stdout.strip() or "0") > 0:
                return True, f"git has {proc.stdout.strip()} new commit(s) since claim"
        except Exception:
            pass

    return False, (
        "Gate 2 rejected: git working tree has zero changes and no new commits since claim. "
        "For doc/research-only tickets, set type='research' or type='docs'."
    )


def reap_expired_leases(tickets: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    """Mark expired leases as stale and return cleaned ticket copies for UI/overview."""
    ref_now = now or datetime.now(timezone.utc)
    cleaned: list[dict[str, Any]] = []
    for t in tickets:
        item = dict(t)
        expires = item.get("lease_expires") or item.get("lease_until")
        if expires and isinstance(expires, str):
            try:
                exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt < ref_now:
                    item["lease_expired"] = True
                    item["lease_active"] = False
                else:
                    item["lease_expired"] = False
                    item["lease_active"] = True
            except ValueError:
                pass
        cleaned.append(item)
    return cleaned


COMPACT_QA_SECTIONS = [
    ("Ponytail Diff", re.compile(r"Ponytail|Minimal\s+Diff|Diff\s+Review", re.I)),
    ("Positive Tests", re.compile(r"Positive\s+Test", re.I)),
    ("Negative Discriminator", re.compile(r"Negative\s+Discriminator|Negative\s+Test", re.I)),
    ("PASS Verdict", re.compile(r"Verdict\s*:\s*PASS\b", re.I)),
]


def validate_qa_evidence(text: str) -> tuple[bool, list[str]]:
    """Validate compact Ponytail + Positive/Negative QA evidence (backward-compatible with legacy 6-section)."""
    missing = [name for name, pat in COMPACT_QA_SECTIONS if not pat.search(text or "")]
    return len(missing) == 0, missing
