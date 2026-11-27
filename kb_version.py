#!/usr/bin/env python3
"""kb_version.py — Project SemVer (V0.0.0), n-1 ticket accounting, programmatic
disjoint clustering (with v4.1 embedding seam), and cluster-aware bump reminders.

Design invariants:
  - 1 Git Repo = 1 Project = 1 Doc = 1 Main Version Number (V0.0.0).
  - Monotonic SemVer increase only: V1.0.0 -> V1.0.1 and V1.0.0 -> V2.0.0 both valid.
  - n - 1 accounting: tickets certified `done` while project is at V2.0.0 are
    pending (`shipped_in: null`) for V_next; bumping to V2.1.0 stamps them into V2.1.0
    in `board/<project>/.versions.json` without mutating signed `done` ticket files.
  - Programmatic disjoint clustering (Union-Find connected components): every pending
    `done` ticket belongs to exactly 1 cluster.
  - Triggers reminder when largest cluster >= 7 OR total pending done >= 12 (configurable).
  - Cluster-aware snooze: after reminding, stays silent until +2 more done tickets join
    the same largest cluster OR a different cluster becomes the new largest cluster
    (or +2 more scattered done tickets when triggered by the total-volume safety net).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

SEMVER_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)$")

STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "into", "is", "it", "of", "on", "or", "that", "the", "to",
    "with", "add", "fix", "update", "implement", "refactor", "use", "using",
    "support", "make", "handle", "ensure", "clean", "up", "new", "test", "tests",
})

DEFAULT_CLUSTER_THRESHOLD = 7
DEFAULT_TOTAL_THRESHOLD = 12
DEFAULT_SNOOZE_DELTA = 2
DEFAULT_EDGE_THRESHOLD = 0.35


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse V0.0.0 or 0.0.0 into (major, minor, patch). Raises ValueError on bad input."""
    if not isinstance(version, str):
        raise ValueError("Version must be a string like V1.0.0")
    m = SEMVER_RE.match(version.strip())
    if not m:
        raise ValueError(f"Invalid SemVer '{version}'. Expected format V0.0.0 (e.g. V1.0.0).")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def format_semver(version: str) -> str:
    """Normalize any valid SemVer string to uppercase V<major>.<minor>.<patch>."""
    maj, min_, pat = parse_semver(version)
    return f"V{maj}.{min_}.{pat}"


def is_version_increase(old_version: str, new_version: str) -> bool:
    """Return True iff new_version is strictly greater than old_version."""
    return parse_semver(new_version) > parse_semver(old_version)


def _validate_project(project: str) -> str:
    p = (project or "").strip()
    if not p or ".." in p or "/" in p or "\\" in p or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", p):
        raise ValueError(f"Invalid project slug '{project}'.")
    return p


def _versions_path(board: Path, project: str) -> Path:
    return board / _validate_project(project) / ".versions.json"


def _project_md_path(board: Path, project: str) -> Path:
    return board / _validate_project(project) / "project.md"


def load_version_state(board: Path, project: str) -> dict[str, Any]:
    """Load or initialize `board/<project>/.versions.json`."""
    p = _versions_path(board, project)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", "V0.0.0")
                data.setdefault("version_updated_at", None)
                data.setdefault("history", [])
                data.setdefault("last_nudge", None)
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "project": project,
        "version": "V0.0.0",
        "version_updated_at": None,
        "history": [],
        "last_nudge": None,
    }


def save_version_state(board: Path, project: str, state: dict[str, Any]) -> None:
    p = _versions_path(board, project)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(p)


def _sync_project_md_version(board: Path, project: str, version: str, updated_at: str) -> None:
    """Keep `version:` metadata synced inside `board/<project>/project.md` if present."""
    pm = _project_md_path(board, project)
    if not pm.is_file():
        return
    text = pm.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm = text[4:end]
            body = text[end + 5:]
            if re.search(r"^version:\s*.*$", fm, re.M):
                fm = re.sub(r"^version:\s*.*$", f"version: {version}", fm, count=1, flags=re.M)
            else:
                fm = fm.rstrip() + f"\nversion: {version}"
            if re.search(r"^version_updated_at:\s*.*$", fm, re.M):
                fm = re.sub(r"^version_updated_at:\s*.*$", f"version_updated_at: {updated_at}", fm, count=1, flags=re.M)
            else:
                fm = fm.rstrip() + f"\nversion_updated_at: {updated_at}"
            pm.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8", newline="\n")
            return
    # Fallback: prepend clean YAML frontmatter
    pm.write_text(
        f"---\nversion: {version}\nversion_updated_at: {updated_at}\n---\n\n{text}",
        encoding="utf-8",
        newline="\n",
    )


def _parse_frontmatter_and_body(text: str) -> tuple[dict[str, Any], str]:
    """Minimal YAML-subset parser for ticket markdown frontmatter (stdlib-only)."""
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            raw_fm = text[4:end]
            body = text[end + 5:]
            cur_list_key: Optional[str] = None
            for line in raw_fm.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if cur_list_key and re.match(r"^\s*-\s+", line):
                    item = re.sub(r"^\s*-\s+", "", line).strip().strip('"').strip("'")
                    fm[cur_list_key].append(item)
                    continue
                cur_list_key = None
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v == "" or v == "[]":
                        fm[k] = []
                        if v == "":
                            cur_list_key = k
                    elif v.startswith("[") and v.endswith("]"):
                        inner = v[1:-1].strip()
                        fm[k] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()] if inner else []
                    else:
                        fm[k] = v.strip('"').strip("'")
    return fm, body


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9_]{3,}", (text or "").lower())
    return {w for w in words if w not in STOP_WORDS and not w.isdigit()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _file_signals(files: list[str]) -> set[str]:
    sigs: set[str] = set()
    for f in files or []:
        norm = str(f).replace("\\", "/").strip().strip("/")
        if not norm:
            continue
        sigs.add(norm.lower())
        parts = norm.split("/")
        if len(parts) > 1:
            sigs.add("/".join(parts[:-1]).lower())
    return sigs


def _load_case_ticket_map(board: Path) -> dict[str, set[str]]:
    """Map ticket ref -> set of Case IDs referencing that ticket."""
    mapping: dict[str, set[str]] = {}
    cases_dir = board / "_cases"
    if not cases_dir.is_dir():
        return mapping
    for p in cases_dir.glob("*.md"):
        try:
            fm, _ = _parse_frontmatter_and_body(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        cid = str(fm.get("id") or p.stem)
        tickets = fm.get("tickets") or []
        if isinstance(tickets, str):
            tickets = [tickets]
        for ref in tickets:
            mapping.setdefault(str(ref).strip(), set()).add(cid)
    return mapping


def scan_project_done_tickets(board: Path, project: str) -> list[dict[str, Any]]:
    """Scan all `done` tickets belonging to `project` across all epics."""
    proj_dir = board / project
    if not proj_dir.is_dir():
        return []
    case_map = _load_case_ticket_map(board)
    tickets: list[dict[str, Any]] = []
    for epic_dir in sorted(proj_dir.iterdir()):
        if not epic_dir.is_dir() or epic_dir.name.startswith(".") or epic_dir.name.startswith("_") or epic_dir.name in ("doc", "docs", "_archive"):
            continue
        epic = epic_dir.name
        for tf in sorted(epic_dir.glob("T*.md")):
            try:
                raw = tf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm, body = _parse_frontmatter_and_body(raw)
            status = str(fm.get("status", "")).strip().lower()
            if status != "done":
                continue
            tid = str(fm.get("id") or tf.stem.split("-", 1)[0])
            ref = f"{project}/{epic}/{tid}"
            title = str(fm.get("title") or tf.stem)
            files = fm.get("files") if isinstance(fm.get("files"), list) else []
            # Extract compact outcome text (title + first 400 chars of body)
            tokens = _tokenize(title + " " + body[:400])
            tickets.append({
                "ref": ref,
                "id": tid,
                "project": project,
                "epic": epic,
                "title": title,
                "files": [str(x) for x in files],
                "cases": sorted(case_map.get(ref, set())),
                "tokens": tokens,
                "updated_at": str(fm.get("updated_at") or fm.get("completed_at") or ""),
                "path": str(tf),
            })
    return tickets


def get_shipped_ticket_map(state: dict[str, Any]) -> dict[str, str]:
    """Return {ticket_ref: version_str} for all tickets already shipped in past versions."""
    shipped: dict[str, str] = {}
    for entry in state.get("history", []):
        ver = entry.get("version", "")
        for ref in entry.get("tickets", []):
            shipped[ref] = ver
    return shipped


def get_pending_done_tickets(board: Path, project: str, state: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Return all `done` tickets in `project` not yet assigned to any shipped version (n - 1 rule)."""
    if state is None:
        state = load_version_state(board, project)
    shipped = get_shipped_ticket_map(state)
    return [t for t in scan_project_done_tickets(board, project) if t["ref"] not in shipped]


def pair_similarity(
    a: dict[str, Any],
    b: dict[str, Any],
    embedder: Optional[Callable[[dict[str, Any], dict[str, Any]], float]] = None,
) -> float:
    """Deterministic lexical/structural similarity in [0.0, 1.0].

    v4.0 signals:
      - Same epic: +0.35
      - Shared files[] or parent directories (Jaccard): +0.30
      - Shared Case link: +0.25
      - Stop-word-filtered title/outcome token Jaccard: +0.20

    v4.1 seam: if `embedder(a, b) -> float` is supplied (cosine similarity in [0, 1]),
    blends deterministic score (0.6) with embedding score (0.4).
    """
    score = 0.0
    if a.get("epic") and a.get("epic") == b.get("epic"):
        score += 0.35
    file_sim = _jaccard(_file_signals(a.get("files", [])), _file_signals(b.get("files", [])))
    score += 0.30 * file_sim
    cases_a = set(a.get("cases", []))
    cases_b = set(b.get("cases", []))
    if cases_a and cases_b and (cases_a & cases_b):
        score += 0.25
    tok_a = a.get("tokens") if isinstance(a.get("tokens"), set) else _tokenize(a.get("title", ""))
    tok_b = b.get("tokens") if isinstance(b.get("tokens"), set) else _tokenize(b.get("title", ""))
    score += 0.20 * _jaccard(tok_a, tok_b)
    det_score = min(1.0, round(score, 4))

    if embedder is not None:
        emb = max(0.0, min(1.0, float(embedder(a, b))))
        return min(1.0, round(0.6 * det_score + 0.4 * emb, 4))
    return det_score


def cluster_tickets(
    tickets: list[dict[str, Any]],
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    embedder: Optional[Callable[[dict[str, Any], dict[str, Any]], float]] = None,
) -> list[dict[str, Any]]:
    """Group tickets into disjoint connected components (each ticket joins exactly 1 cluster).

    Returns clusters sorted descending by (size, avg_weight, signature).
    """
    n = len(tickets)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    edges: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            w = pair_similarity(tickets[i], tickets[j], embedder=embedder)
            if w >= edge_threshold:
                union(i, j)
                edges.append((i, j, w))

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters: list[dict[str, Any]] = []
    for root, idxs in groups.items():
        idx_set = set(idxs)
        internal_weights = [w for i, j, w in edges if i in idx_set and j in idx_set]
        avg_w = round(sum(internal_weights) / len(internal_weights), 3) if internal_weights else 0.0
        refs = sorted(tickets[i]["ref"] for i in idxs)
        # Build human-friendly cluster label from dominant epic + top keywords
        epic_counts: dict[str, int] = {}
        tok_counts: dict[str, int] = {}
        for i in idxs:
            ep = tickets[i].get("epic", "")
            if ep:
                epic_counts[ep] = epic_counts.get(ep, 0) + 1
            for tok in (tickets[i].get("tokens") or []):
                tok_counts[tok] = tok_counts.get(tok, 0) + 1
        top_epic = max(epic_counts.items(), key=lambda kv: (kv[1], kv[0]))[0] if epic_counts else "misc"
        top_words = [w for w, _ in sorted(tok_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        label = f"{top_epic} ({', '.join(top_words)})" if top_words else top_epic
        clusters.append({
            "signature": "|".join(refs[:3]),
            "label": label,
            "size": len(idxs),
            "avg_weight": avg_w,
            "tickets": refs,
        })

    clusters.sort(key=lambda c: (-c["size"], -c["avg_weight"], c["signature"]))
    return clusters


def _is_same_cluster(prev_tickets: list[str], cur_tickets: list[str]) -> bool:
    """Two clusters represent the same ongoing cluster if they share >= 50% of previous tickets."""
    ps, cs = set(prev_tickets or []), set(cur_tickets or [])
    if not ps or not cs:
        return False
    return (len(ps & cs) / len(ps)) >= 0.5


def evaluate_version_nudge(
    board: Path,
    project: str,
    config: Optional[dict[str, Any]] = None,
    record_nudge: bool = True,
    embedder: Optional[Callable[[dict[str, Any], dict[str, Any]], float]] = None,
) -> Optional[dict[str, Any]]:
    """Check if `project` should surface a `version_nudge` on `kanban_board` / `kanban_project`.

    Returns None if below thresholds or snoozed; otherwise returns a compact nudge dict
    and (when `record_nudge=True`) updates `last_nudge` in `.versions.json`.
    """
    cfg = config or {}
    cluster_threshold = int(cfg.get("cluster_threshold", DEFAULT_CLUSTER_THRESHOLD))
    total_threshold = int(cfg.get("total_threshold", DEFAULT_TOTAL_THRESHOLD))
    snooze_delta = int(cfg.get("snooze_delta", DEFAULT_SNOOZE_DELTA))
    edge_threshold = float(cfg.get("edge_threshold", DEFAULT_EDGE_THRESHOLD))

    state = load_version_state(board, project)
    pending = get_pending_done_tickets(board, project, state=state)
    total_pending = len(pending)
    if total_pending == 0:
        return None

    clusters = cluster_tickets(pending, edge_threshold=edge_threshold, embedder=embedder)
    largest = clusters[0]
    hit_cluster = largest["size"] >= cluster_threshold
    hit_total = total_threshold > 0 and total_pending >= total_threshold
    if not (hit_cluster or hit_total):
        return None

    last = state.get("last_nudge")
    if isinstance(last, dict):
        prev_tickets = last.get("cluster_tickets") or []
        prev_size = int(last.get("cluster_size", 0))
        prev_total = int(last.get("total_pending", 0))
        same_largest = _is_same_cluster(prev_tickets, largest["tickets"])

        if hit_cluster:
            if same_largest:
                # Snooze until +snooze_delta more done tickets join this largest cluster
                if largest["size"] < prev_size + snooze_delta:
                    return None
            # Else: a DIFFERENT cluster became the new largest cluster at >= cluster_threshold -> fire!
        else:
            # Scattered safety net only: snooze until +snooze_delta more total pending done tickets
            if total_pending < prev_total + snooze_delta:
                return None

    reason = (
        f"Cluster '{largest['label']}' has {largest['size']} closely-linked done tickets "
        f"(threshold {cluster_threshold})"
        if hit_cluster
        else f"{total_pending} pending done tickets accumulated since {state['version']} "
        f"(scattered safety net {total_threshold})"
    )
    nudge = {
        "project": project,
        "current_version": state["version"],
        "trigger": "cluster" if hit_cluster else "scattered_total",
        "largest_cluster": largest,
        "total_pending_done": total_pending,
        "message": (
            f"{reason} since {state['version']}. "
            f"Consider bumping the version via kanban_project(action='bump_version', project='{project}', version='V...')."
        ),
    }
    if record_nudge:
        state["last_nudge"] = {
            "cluster_tickets": largest["tickets"],
            "cluster_size": largest["size"],
            "total_pending": total_pending,
            "trigger": nudge["trigger"],
            "nudged_at": _now_iso(),
        }
        save_version_state(board, project, state)
    return nudge


def bump_project_version(
    board: Path,
    project: str,
    new_version: str,
    bumped_by: str = "agent",
    note: str = "",
) -> dict[str, Any]:
    """Validate monotonic SemVer increase, stamp pending done tickets (n - 1), and persist."""
    project = _validate_project(project)
    proj_dir = board / project
    if not proj_dir.is_dir():
        raise FileNotFoundError(f"Project '{project}' does not exist on board.")

    norm_new = format_semver(new_version)
    state = load_version_state(board, project)
    old_ver = state.get("version", "V0.0.0")
    if not is_version_increase(old_ver, norm_new):
        raise ValueError(
            f"Version must strictly increase: requested '{norm_new}' is not greater than current '{old_ver}'."
        )

    pending = get_pending_done_tickets(board, project, state=state)
    shipped_refs = [t["ref"] for t in pending]
    now = _now_iso()

    entry = {
        "version": norm_new,
        "previous_version": old_ver,
        "bumped_at": now,
        "bumped_by": (bumped_by or "agent").strip(),
        "note": (note or "").strip(),
        "tickets": shipped_refs,
        "ticket_count": len(shipped_refs),
    }
    state["project"] = project
    state["version"] = norm_new
    state["version_updated_at"] = now
    state["history"].append(entry)
    state["last_nudge"] = None  # Reset snooze immediately on version bump
    save_version_state(board, project, state)
    _sync_project_md_version(board, project, norm_new, now)

    return {
        "ok": True,
        "project": project,
        "old_version": old_ver,
        "new_version": norm_new,
        "bumped_at": now,
        "bumped_by": entry["bumped_by"],
        "note": entry["note"],
        "shipped_tickets": shipped_refs,
        "ticket_count": len(shipped_refs),
    }


def get_version_history(
    board: Path,
    project: str,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return current version, full version history with attached tickets, and Pending (V_next) cluster progress."""
    cfg = config or {}
    edge_threshold = float(cfg.get("edge_threshold", DEFAULT_EDGE_THRESHOLD))
    cluster_threshold = int(cfg.get("cluster_threshold", DEFAULT_CLUSTER_THRESHOLD))
    total_threshold = int(cfg.get("total_threshold", DEFAULT_TOTAL_THRESHOLD))

    state = load_version_state(board, project)
    pending = get_pending_done_tickets(board, project, state=state)
    clusters = cluster_tickets(pending, edge_threshold=edge_threshold)
    largest = clusters[0] if clusters else None

    return {
        "ok": True,
        "project": project,
        "version": state["version"],
        "version_updated_at": state["version_updated_at"],
        "history": list(reversed(state["history"])),
        "pending_next": {
            "ticket_count": len(pending),
            "tickets": [
                {"ref": t["ref"], "id": t["id"], "epic": t["epic"], "title": t["title"]}
                for t in pending
            ],
            "clusters": clusters,
            "largest_cluster_size": largest["size"] if largest else 0,
            "cluster_threshold": cluster_threshold,
            "total_threshold": total_threshold,
        },
    }
