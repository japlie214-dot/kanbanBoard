#!/usr/bin/env python3
"""kb.py — Core Kanban Board Engine with Anti-Laziness Gates, DAG Todo Tree, and Multi-Agent Leases.

Tracks tickets across projects and epics backed by pure Markdown files with YAML frontmatter.
Lifecycle:
  backlog ⇄ in-progress ⇄ verify → done
     ⇅          ⇅          ⇅
  blocked    blocked    blocked

Key Architectural Features:
- 5 Mechanical Anti-Laziness Gates (Todo Tree validation, physical git change detection, unbroken DAG path, non-trivial prove, substantive evidence audit).
- Atomic Move + Claim with configurable lease (default 60m) & force takeover.
- Unified Discovery (kanban_overview).
- Secure File Attachments & Documentation (docs: []).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

BOARD_DIR = "board"
EVIDENCE_DIR = "evidence"
ATTACHMENTS_DIR_NAME = "attachments"
LOCK_TIMEOUT = 10.0
DEFAULT_LEASE_MINUTES = 60

VALID_STATUSES = {"backlog", "in-progress", "verify", "done", "blocked"}

ALLOWED_TRANSITIONS = {
    "backlog": {"in-progress", "blocked"},
    "in-progress": {"verify", "blocked", "backlog"},
    "verify": {"done", "in-progress", "blocked", "backlog"},
    "blocked": {"backlog", "in-progress", "verify"},
    "done": set(),
}

REQUIRED_SECTIONS = {"Outcome", "Scope", "Prove"}
GATE_STATUSES = {"in-progress", "verify"}

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TICKET_ID_RE = re.compile(r"^T[0-9]{3,}$")
NONCE_RE = re.compile(r"^[a-f0-9]{32}$")

# Security boundaries for attachments
PRIVATE_PARTS = frozenset({
    ".git", ".claude", ".gemini", ".agents", ".vscode", ".idea",
    "node_modules", "__pycache__", ".venv", "venv", ".env",
    "secrets", "auth", "tokens", "keyring", ".ssh", "credentials"
})
PRIVATE_SUFFIXES = (
    ".pem", ".key", ".p12", ".pfx", ".kdbx", ".keychain", ".crt", ".cer", ".env"
)


# ---------------------------------------------------------------------------
# Path Resolution & Locking
# ---------------------------------------------------------------------------

def is_plugin_internal_path(path: Path) -> bool:
    """Check if a path is inside a plugin installation/cache directory."""
    s = str(path).replace("\\", "/").lower()
    return any(marker in s for marker in (
        "/plugins/kanban-board",
        "/.gemini/config/plugins",
        "/claude/rpm",
        "/appdata/roaming/claude/plugins",
        "/.claude/plugins",
        "/node_modules",
    ))


def board_root() -> Path:
    """Resolve the canonical board directory with clean precedence:
    1. Explicit environment variable: KANBAN_BOARD_ROOT
    2. Explicit workspace env var: KANBAN_WORKSPACE_ROOT / 'board'
    3. Active project workspace: If current working directory or any parent has a 'board/' directory
    4. Active git repository: If current working directory or any parent has a '.git' directory
    5. Universal user data directory: ~/.kanban/board (works on every machine, standalone plugin, zero clone required)
    """
    env_board = os.environ.get("KANBAN_BOARD_ROOT")
    if env_board:
        return Path(env_board).resolve()

    env_ws = os.environ.get("KANBAN_WORKSPACE_ROOT")
    if env_ws:
        return Path(env_ws).resolve() / BOARD_DIR

    cwd = Path.cwd()
    # 3. Check for existing project board/ directory (excluding plugin caches)
    for p in [cwd] + list(cwd.parents):
        b = p / BOARD_DIR
        if b.is_dir() and not is_plugin_internal_path(p):
            return b

    # 4. Check for active git repository root
    for p in [cwd] + list(cwd.parents):
        if (p / ".git").is_dir() and not is_plugin_internal_path(p):
            return p / BOARD_DIR

    # 5. Universal user data directory: ~/.kanban/board
    # Completely independent of any repository clone; works for standalone .plugin installs.
    user_board = Path.home() / ".kanban" / BOARD_DIR
    try:
        user_board.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return user_board


def workspace_root() -> Path:
    env_ws = os.environ.get("KANBAN_WORKSPACE_ROOT")
    if env_ws:
        return Path(env_ws).resolve()

    b_root = board_root()
    # If board_root is inside user home ~/.kanban/board, workspace root is cwd if cwd has git, else ~/.kanban
    if b_root == Path.home() / ".kanban" / BOARD_DIR:
        cwd = Path.cwd()
        for p in [cwd] + list(cwd.parents):
            if (p / ".git").is_dir() and not is_plugin_internal_path(p):
                return p
        return b_root.parent

    return b_root.parent if b_root.name == BOARD_DIR else b_root


@contextlib.contextmanager
def board_lock(root: Path, timeout: float = LOCK_TIMEOUT):
    lock_file = root / ".lock"
    root.mkdir(parents=True, exist_ok=True)
    start = time.time()
    fd = None
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Could not acquire lock on {root} within {timeout}s")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock_file.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Nonce & Ephemeral QA Management
# ---------------------------------------------------------------------------

def _safe_ref_key(path: Path, board: Path) -> str:
    rel = path.relative_to(board)
    return str(rel).replace("/", "_").replace("\\", "_").replace(".md", "")


def get_qa_nonce_path(path: Path, board: Path) -> Path:
    key = _safe_ref_key(path, board)
    nonce_dir = board / ".qa_nonces"
    nonce_dir.mkdir(parents=True, exist_ok=True)
    return nonce_dir / f"{key}.nonce"


def generate_qa_nonce(path: Path, board: Path) -> str:
    nonce = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    nonce_file = get_qa_nonce_path(path, board)
    nonce_file.write_text(nonce, encoding="utf-8")
    return nonce


def read_qa_nonce(path: Path, board: Path) -> Optional[str]:
    nonce_file = get_qa_nonce_path(path, board)
    if nonce_file.exists():
        return nonce_file.read_text(encoding="utf-8").strip()
    return None


def burn_qa_nonce(path: Path, board: Path):
    nonce_file = get_qa_nonce_path(path, board)
    if nonce_file.exists():
        try:
            nonce_file.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# YAML Frontmatter Serialization
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw_yaml, body = parts[1], parts[2]
    meta: dict[str, Any] = {}
    current_key = None
    current_list: list = []
    in_subdict = False
    subdict_key = None
    subdict_obj: dict = {}

    for line in raw_yaml.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue

        # Sub-dictionary handling (e.g. owner:)
        indent = len(line) - len(line.lstrip())
        if indent > 0 and in_subdict and subdict_key:
            if ":" in trimmed:
                sub_k, sub_v = trimmed.split(":", 1)
                sub_k = sub_k.strip()
                sub_v = sub_v.strip().strip('"').strip("'")
                subdict_obj[sub_k] = None if sub_v == "" else sub_v
            continue
        elif in_subdict and subdict_key:
            meta[subdict_key] = subdict_obj
            in_subdict = False
            subdict_key = None
            subdict_obj = {}

        if trimmed.startswith("- ") and current_key:
            item = trimmed[2:].strip().strip('"').strip("'")
            current_list.append(item)
            continue
        else:
            if current_key and current_list:
                meta[current_key] = current_list
                current_list = []
                current_key = None

        if ":" in trimmed:
            k, v = trimmed.split(":", 1)
            k, v = k.strip(), v.strip()
            if not v:
                # Could be start of list or subdict
                if k == "owner":
                    in_subdict = True
                    subdict_key = k
                    subdict_obj = {}
                else:
                    current_key = k
                    current_list = []
                    meta[k] = None
            elif v.startswith("[") and v.endswith("]"):
                items_str = v[1:-1].strip()
                if not items_str:
                    meta[k] = []
                else:
                    meta[k] = [x.strip().strip('"').strip("'") for x in items_str.split(",") if x.strip()]
            else:
                meta[k] = v.strip('"').strip("'")

    if in_subdict and subdict_key:
        meta[subdict_key] = subdict_obj
    if current_key and current_list:
        meta[current_key] = current_list

    return meta, body


def render_frontmatter(meta: dict, body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            lines.append(f"{k}:")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for sub_k, sub_v in v.items():
                if sub_v is None:
                    lines.append(f"  {sub_k}:")
                elif isinstance(sub_v, str) and any(c in sub_v for c in ':#{}[]|>&!'):
                    lines.append(f'  {sub_k}: "{sub_v}"')
                else:
                    lines.append(f"  {sub_k}: {sub_v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            elif all(isinstance(x, str) for x in v):
                items = ', '.join(f'"{x}"' for x in v)
                lines.append(f"{k}: [{items}]")
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        lines.append("  - " + json.dumps(item))
                    else:
                        lines.append(f"  - {item}")
        elif isinstance(v, str) and any(c in v for c in ':#{}[]|>&!'):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    body_clean = body.lstrip("\r\n")
    return "\n".join(lines) + "\n\n" + body_clean


# ---------------------------------------------------------------------------
# Todo Tree Parsing & DAG Validation (Anti-Laziness Gates 1 & 3)
# ---------------------------------------------------------------------------

PLAN_SECTION_RE = re.compile(
    r'(##\s+(?:Plan(?:\s*\(Todo\s+Tree\))?|Todo\s+Tree|Acceptance)\s*\n)(.*?)(?=\n##\s+|\Z)',
    re.S | re.I,
)
EXEC_LOG_SECTION_RE = re.compile(
    r'##\s+Execution\s+Log\s*\n(.*?)(?=\n##\s+|\Z)',
    re.S | re.I,
)
NODE_ID_RE = re.compile(r'^([A-Za-z][A-Za-z0-9._-]*|\d+(?:[A-Za-z]+|\.\d+)*)\b\.?\s*')
AFTER_TAG_RE = re.compile(r'\[after:([^\]]+)\]', re.I)
LANE_TAG_RE = re.compile(r'\[lane:([^\]]+)\]', re.I)
WHEN_TAG_RE = re.compile(r'\[when:(if|else)\(([^)]*)\)(?::([A-Za-z0-9_-]+))?\]', re.I)
ACC_TAG_RE = re.compile(r'\[ACCEPTANCE(?::(MANDATORY|OPTIONAL))?\]', re.I)


def _parse_after_expr(expr: str) -> list[dict]:
    """Parse [after:A2,B3?,B5|C5] into structured dependency clauses.

    Comma-separated terms are AND clauses.
    Pipe-separated IDs within a term are OR/XOR alternatives (at least one done).
    Trailing '?' marks a conditional/optional dependency (if skipped, does not block).
    """
    clauses: list[dict] = []
    for raw_term in expr.split(","):
        term = raw_term.strip()
        if not term:
            continue
        optional = term.endswith("?")
        if optional:
            term = term[:-1].strip()
        alts = [a.strip() for a in term.split("|") if a.strip()]
        if alts:
            clauses.append({"alts": alts, "optional": optional})
    return clauses


def parse_execution_log(text: str) -> dict[str, list[dict]]:
    """Parse append-only ## Execution Log entries keyed by node_id.

    Supports canonical timestamped format:
      - [2026-11-23 07:00 UTC] [DONE] A1 | proof: <evidence>
      - [2026-11-23 07:01 UTC] [SKIP] C1 | reason: <branch decision>

    And lenient human/agent formats:
      - Node A1: <evidence>
      - [A1]: <evidence> or - [x] A1: <evidence>
      - - A1 | proof: <evidence>
      - - Node A1 (DONE): <evidence>
    """
    m = EXEC_LOG_SECTION_RE.search(text)
    if not m:
        return {}
    entries: dict[str, list[dict]] = {}
    
    # 1. Primary canonical line format
    canonical_re = re.compile(
        r'^-\s*\[(?P<ts>[^\]]+)\]\s*\[(?P<kind>DONE|SKIP|UNCHECK)\]\s*(?P<nid>[A-Za-z0-9._-]+)\s*\|\s*(?P<detail>.*)$',
        re.I,
    )
    # 2. Lenient human / agent formats
    lenient_re = re.compile(
        r'^-\s*(?:\[(?P<box>[xX -])\]\s*)?(?:Node\s+)?\[?(?P<nid>[A-Za-z0-9._-]+)\]?(?:\s*\((?P<kind>DONE|SKIP|UNCHECK)\))?\s*(?::|\|)\s*(?P<detail>.*)$',
        re.I,
    )

    for line in m.group(1).splitlines():
        line_str = line.strip()
        if not line_str or not line_str.startswith("-"):
            continue
        
        lm = canonical_re.match(line_str)
        if lm:
            nid = lm.group("nid").strip()
            entries.setdefault(nid, []).append({
                "timestamp": lm.group("ts").strip(),
                "kind": lm.group("kind").upper(),
                "detail": lm.group("detail").strip(),
            })
            continue

        lm_lenient = lenient_re.match(line_str)
        if lm_lenient:
            nid = lm_lenient.group("nid").strip()
            box = lm_lenient.group("box")
            kind_explicit = lm_lenient.group("kind")
            kind = kind_explicit.upper() if kind_explicit else ("SKIP" if box == "-" else "DONE")
            detail = lm_lenient.group("detail").strip()
            # Strip redundant 'proof:' or 'reason:' prefix if present
            detail = re.sub(r'^(?:proof|reason)\s*:\s*', '', detail, flags=re.I).strip()
            entries.setdefault(nid, []).append({
                "timestamp": "recorded",
                "kind": kind,
                "detail": detail,
            })
    return entries


def parse_todo_tree(text: str) -> tuple[Optional[list[dict]], str]:
    """Parse DAG Todo Tree checklist items from markdown.

    Supports explicit DAG syntax ([START], [lane:A], [after:A1,B3?], [after:A4,B5|C5],
    [parallel], [optional], [when:if(cond):fork], [ACCEPTANCE:MANDATORY|OPTIONAL],
    and - [-] skipped status) with backward-compatible fallback for legacy indented lists.
    """
    m = PLAN_SECTION_RE.search(text)
    if not m:
        return None, "Missing '## Plan (Todo Tree)' or '## Acceptance' section"

    content = m.group(2).strip()
    lines = content.splitlines()
    nodes: list[dict] = []
    line_re = re.compile(r'^(\s*)-\s*\[([ xX-])\]\s*(.*)$')

    has_explicit_after = False
    seen_ids: set[str] = set()

    for idx, line in enumerate(lines):
        lm = line_re.match(line)
        if not lm:
            continue
        indent = len(lm.group(1).expandtabs(4))
        mark = lm.group(2).lower()
        status = "done" if mark == "x" else ("skipped" if mark == "-" else "pending")
        item_text = lm.group(3).strip()

        id_match = NODE_ID_RE.match(item_text)
        node_id = id_match.group(1).rstrip(".") if id_match else f"N{idx + 1}"
        if node_id in seen_ids:
            return None, f"Duplicate Todo Tree node ID '{node_id}'."
        seen_ids.add(node_id)

        acc_m = ACC_TAG_RE.search(item_text)
        is_acceptance = bool(acc_m)
        acceptance_kind: Optional[str] = None
        if acc_m:
            acceptance_kind = (acc_m.group(1) or "MANDATORY").upper()

        is_start = "[start]" in item_text.lower()
        is_parallel = "[parallel]" in item_text.lower()
        is_optional = "[optional]" in item_text.lower() or acceptance_kind == "OPTIONAL"

        lane_m = LANE_TAG_RE.search(item_text)
        lane = lane_m.group(1).strip() if lane_m else (node_id[0] if node_id[0].isalpha() else "main")

        after_m = AFTER_TAG_RE.search(item_text)
        after_clauses: list[dict] = []
        if after_m:
            has_explicit_after = True
            after_clauses = _parse_after_expr(after_m.group(1))

        when_m = WHEN_TAG_RE.search(item_text)
        when_info = None
        if when_m:
            when_info = {
                "branch": when_m.group(1).lower(),
                "condition": when_m.group(2).strip(),
                "group": (when_m.group(3) or when_m.group(2).strip() or "default").strip(),
            }

        nodes.append({
            "id": node_id,
            "indent": indent,
            "status": status,
            "checked": status == "done",
            "skipped": status == "skipped",
            "text": item_text,
            "lane": lane,
            "is_start": is_start,
            "is_parallel": is_parallel,
            "is_optional": is_optional,
            "is_acceptance": is_acceptance,
            "acceptance_kind": acceptance_kind,  # "MANDATORY" | "OPTIONAL" | None
            "after_clauses": after_clauses,
            "when": when_info,
        })

    if not nodes:
        return None, "No checkbox items (- [ ] / - [x] / - [-]) found in Plan (Todo Tree)"

    # Backward-compatible fallback: if no explicit [after:...] tags exist, derive edges from indentation
    if not has_explicit_after:
        stack: list[tuple[str, int]] = []
        for n in nodes:
            while stack and stack[-1][1] >= n["indent"]:
                stack.pop()
            if stack:
                n["after_clauses"] = [{"alts": [stack[-1][0]], "optional": False}]
            elif not any(x["is_start"] for x in nodes):
                n["is_start"] = True
            stack.append((n["id"], n["indent"]))

    return nodes, ""


def _clause_satisfied(clause: dict, by_id: dict[str, dict]) -> bool:
    """Return True if a single AND/OR/optional dependency clause is satisfied."""
    alts = clause["alts"]
    if any(by_id[a]["status"] == "done" for a in alts if a in by_id):
        return True
    if clause.get("optional") and all(by_id[a]["status"] == "skipped" for a in alts if a in by_id):
        return True
    return False


def compute_ready_nodes(nodes: list[dict]) -> list[str]:
    """Return pending node IDs whose prerequisites are satisfied and can run now (including in parallel)."""
    by_id = {n["id"]: n for n in nodes}
    ready: list[str] = []
    for n in nodes:
        if n["status"] != "pending":
            continue
        if all(_clause_satisfied(c, by_id) for c in n["after_clauses"]):
            ready.append(n["id"])
    return ready


def validate_todo_tree(
    nodes: list[dict],
    for_verify: bool = False,
    for_inprogress: bool = False,
    body: str = "",
    require_process_proof: bool = True,
) -> tuple[bool, str]:
    """Validate Todo Tree DAG structure, mandatory/optional acceptances, if/else, and execution proof."""
    if not nodes:
        return False, "Todo Tree has zero tasks."

    by_id = {n["id"]: n for n in nodes}

    # 1. Verify all referenced predecessor IDs exist
    children: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    indegree: dict[str, int] = {n["id"]: 0 for n in nodes}
    for n in nodes:
        for clause in n["after_clauses"]:
            for pred in clause["alts"]:
                if pred not in by_id:
                    return False, f"Node '{n['id']}' references unknown predecessor '{pred}' in [after:...]."
                children[pred].append(n["id"])
                indegree[n["id"]] += 1

    # 2. Cycle detection (Kahn's topological sort)
    q = [nid for nid, deg in indegree.items() if deg == 0]
    visited_count = 0
    indeg_copy = dict(indegree)
    while q:
        cur = q.pop(0)
        visited_count += 1
        for nxt in children[cur]:
            indeg_copy[nxt] -= 1
            if indeg_copy[nxt] == 0:
                q.append(nxt)
    if visited_count != len(nodes):
        return False, "Todo Tree contains a cycle; workflow must be a Directed Acyclic Graph (DAG)."

    # 3. START invariant: every root must be [START], and all nodes reachable from [START]
    starts = [n["id"] for n in nodes if n["is_start"]]
    if not starts:
        return False, "Todo Tree must define a [START] checkpoint."
    non_start_roots = [nid for nid, deg in indegree.items() if deg == 0 and not by_id[nid]["is_start"]]
    if non_start_roots:
        return False, f"Root node(s) {non_start_roots} have no [after:...] predecessor and are not marked [START]."

    reachable: set[str] = set()
    stack = list(starts)
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for nxt in children[cur]:
            if nxt not in reachable:
                stack.append(nxt)
    unreachable = [n["id"] for n in nodes if n["id"] not in reachable]
    if unreachable:
        return False, f"Unreachable node(s) from [START]: {', '.join(unreachable)}."

    # 4. END invariant: every terminal leaf (out-degree == 0) MUST be an acceptance checkpoint
    dangling_leaves = [n["id"] for n in nodes if not children[n["id"]] and not n["is_acceptance"]]
    if dangling_leaves:
        return False, (
            f"Every path must end at an acceptance checkpoint. Terminal node(s) without [ACCEPTANCE]: "
            f"{', '.join(dangling_leaves)}."
        )

    mandatory_accs = [n for n in nodes if n["is_acceptance"] and n["acceptance_kind"] == "MANDATORY"]
    optional_accs = [n for n in nodes if n["is_acceptance"] and n["acceptance_kind"] == "OPTIONAL"]
    if not mandatory_accs:
        return False, "Todo Tree must define at least one [ACCEPTANCE:MANDATORY] (or [ACCEPTANCE]) checkpoint."

    if for_inprogress:
        if len(nodes) < 2:
            return False, "Todo Tree must define at least 2 distinct checkpoints."
        for n in nodes:
            if n["is_acceptance"] and n["checked"]:
                return False, "Cannot enter 'in-progress' with [ACCEPTANCE] criteria already checked (- [x])."
        return True, "Valid DAG plan for in-progress."

    if for_verify:
        # 5. Enforce mutually exclusive if/else groups (cannot execute both if and else of the same fork)
        groups: dict[str, list[dict]] = {}
        for n in nodes:
            if n.get("when"):
                groups.setdefault(n["when"]["group"], []).append(n)
        for grp, members in groups.items():
            done_branches = {m["when"]["branch"] for m in members if m["status"] == "done"}
            if "if" in done_branches and "else" in done_branches:
                return False, f"Invalid if/else execution in fork '{grp}': both 'if' and 'else' branches are checked."

        # 6. Every non-skipped MANDATORY acceptance must be checked (- [x])
        #    (A mandatory acceptance is only skippable if its conditional branch was legitimately skipped)
        active_mandatory = [n for n in mandatory_accs if n["status"] != "skipped"]
        if not active_mandatory:
            return False, "Cannot move to 'verify': All mandatory acceptance checkpoints were skipped."
        unfinished_mandatory = [n["id"] for n in active_mandatory if n["status"] != "done"]
        if unfinished_mandatory:
            return False, (
                f"Cannot move to 'verify': Mandatory acceptance checkpoint(s) not completed: "
                f"{', '.join(unfinished_mandatory)}."
            )

        # 7. Optional acceptance branches must be either fully done OR cleanly skipped (no half-finished optional paths)
        for opt in optional_accs:
            if opt["status"] == "pending":
                # Check if any ancestor exclusive to this optional lane was started
                lane_started = any(
                    n["status"] == "done" and n["is_optional"] and n["lane"] == opt["lane"]
                    for n in nodes
                )
                if lane_started:
                    return False, (
                        f"Optional branch '{opt['lane']}' was started but optional acceptance '{opt['id']}' "
                        f"is still pending. Finish '{opt['id']}' or skip the branch (- [-])."
                    )

        # 8. Trace backward from ALL satisfied acceptances to [START] and verify every active checkpoint
        #    is checked (- [x]) AND has recorded execution proof in ## Execution Log
        exec_log = parse_execution_log(body) if body else {}
        required_done_ids: set[str] = set()
        to_trace = [n["id"] for n in active_mandatory] + [n["id"] for n in optional_accs if n["status"] == "done"]
        seen_trace: set[str] = set()

        while to_trace:
            nid = to_trace.pop()
            if nid in seen_trace:
                continue
            seen_trace.add(nid)
            node = by_id[nid]
            if node["status"] != "done":
                return False, f"Cannot move to 'verify': Checkpoint '{nid}' on active acceptance path is '{node['status']}'."
            required_done_ids.add(nid)
            for clause in node["after_clauses"]:
                if not _clause_satisfied(clause, by_id):
                    return False, (
                        f"Cannot move to 'verify': Checkpoint '{nid}' dependency '{clause['alts']}' is not satisfied."
                    )
                for alt in clause["alts"]:
                    if by_id[alt]["status"] == "done":
                        to_trace.append(alt)

        # Ensure at least one [START] node is on the verified path
        if not any(s in required_done_ids for s in starts):
            return False, "Cannot move to 'verify': Verified acceptance path does not connect back to [START]."

        # 9. Process execution proof check
        if require_process_proof:
            missing_proofs = [
                nid for nid in sorted(required_done_ids)
                if not any(e["kind"] == "DONE" and len(e["detail"]) >= 5 for e in exec_log.get(nid, []))
            ]
            if missing_proofs:
                return False, (
                    f"Cannot move to 'verify': Missing execution proof in '## Execution Log' for checkpoint(s): "
                    f"{', '.join(missing_proofs)}. Check off nodes via kanban_update with node_proofs."
                )

        verified_list = ", ".join(n["id"] for n in active_mandatory)
        return True, f"Verified complete START -> mandatory acceptance DAG paths ({verified_list}) with execution proofs."

    return True, "OK"


# ---------------------------------------------------------------------------
# Section Content Verification (Anti-Laziness Gates 1 & 4)
# ---------------------------------------------------------------------------

def check_required_sections(body: str, sections: set[str]) -> list[str]:
    """Return list of missing or placeholder sections with descriptive details."""
    missing = []
    placeholder_exact_starts = (
        'describe the observable result',
        'exact commands and expected output',
        'pytest tests/test_feature.py'
    )
    for s in sections:
        pattern = re.compile(r'##\s+' + re.escape(s) + r'\s*\n(.*?)(?=\n##|\Z)', re.S)
        m = pattern.search(body)
        if not m:
            missing.append(f"{s} (section missing)")
            continue
        content = m.group(1).strip()
        if not content:
            missing.append(f"{s} (section is empty)")
            continue
        first_line = content.splitlines()[0].strip().lower()
        if any(first_line.startswith(prefix) for prefix in placeholder_exact_starts):
            missing.append(f"{s} (contains unedited placeholder text)")
            continue
        if s == "Scope" and ("src/..." in content or "`...`" in content):
            missing.append("Scope (contains unedited placeholder 'src/...')")
            continue
        if len(content) < 10:
            missing.append(f"{s} (content too brief, < 10 chars)")
            continue
    return missing


def check_prove_command(body: str) -> tuple[bool, str]:
    """Gate 4: Reject trivial or fake test prove commands."""
    pattern = re.compile(r'##\s+Prove\s*\n(.*?)(?=\n##|\Z)', re.S | re.I)
    m = pattern.search(body)
    if not m:
        return False, "Missing '## Prove' section"
    text = m.group(1).strip()
    if len(text) < 10:
        return False, "Prove section is too short or empty."

    # Reject mock or bypass commands
    lines = [l.strip().lower() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    trivial = {"echo", "true", "exit 0", "pass", "pytest ...", "npm test ..."}
    for l in lines:
        if any(l == t or l.startswith(f"{t} ") for t in trivial):
            return False, f"Trivial or placeholder test command '{l}' is forbidden in ## Prove."

    return True, "Prove command acceptable."


# ---------------------------------------------------------------------------
# Physical Git Verification (Anti-Laziness Gate 2)
# ---------------------------------------------------------------------------

def inspect_git_status(ws_root: Path) -> dict:
    """Inspect physical git working tree status."""
    git_dir = ws_root / ".git"
    if not git_dir.exists():
        return {"has_git": False, "uncommitted": [], "all_changed": []}

    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ws_root),
            capture_output=True,
            text=True,
            timeout=5
        )
        uncommitted = []
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if len(line) >= 4:
                    filepath = line[3:].strip()
                    # Strip quotes if git quoted spaces
                    if filepath.startswith('"') and filepath.endswith('"'):
                        filepath = filepath[1:-1]
                    uncommitted.append(filepath.replace("\\", "/"))
        return {"has_git": True, "uncommitted": uncommitted}
    except Exception:
        return {"has_git": True, "uncommitted": []}


# ---------------------------------------------------------------------------
# Ownership & Leases
# ---------------------------------------------------------------------------

def parse_iso_time(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(ts_str)
    except Exception:
        return None


def inspect_ticket_lease(owner_meta: Optional[dict]) -> tuple[bool, str]:
    """Check if a ticket is actively leased and returns (is_active, description)."""
    if not owner_meta or not isinstance(owner_meta, dict):
        return False, "unclaimed"

    agent = owner_meta.get("agent", "unknown")
    expires_str = owner_meta.get("lease_expires")
    if not expires_str:
        return True, f"held by {agent} (no expiry)"

    exp_dt = parse_iso_time(expires_str)
    if not exp_dt:
        return True, f"held by {agent}"

    now = datetime.datetime.now(datetime.timezone.utc)
    if now < exp_dt:
        diff_mins = int((exp_dt - now).total_seconds() / 60)
        return True, f"held by {agent} ({diff_mins}m remaining)"
    else:
        return False, f"lease expired for {agent}"


# ---------------------------------------------------------------------------
# Attachments & Bounded Security
# ---------------------------------------------------------------------------

def check_attachment_safety(file_path: str, ws_root: Path) -> Path:
    """Validate that target file does not cross security boundaries."""
    p = Path(file_path)
    if not p.is_absolute():
        p = (ws_root / p).resolve()
    else:
        p = p.resolve()

    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Attachment file not found: {file_path}")

    # Ensure path stays within workspace root
    try:
        rel = p.relative_to(ws_root.resolve())
    except ValueError:
        raise PermissionError(f"Attachment '{file_path}' is outside workspace root.")

    # Check forbidden paths
    for part in rel.parts:
        part_cf = part.casefold()
        if part_cf in PRIVATE_PARTS or any(part_cf.startswith(prefix) for prefix in (".env", ".git", ".secret")):
            raise PermissionError(f"Access to '{part}' is restricted for attachments.")

    if any(p.name.casefold().endswith(sfx) for sfx in PRIVATE_SUFFIXES):
        raise PermissionError(f"Files of type '{p.suffix}' cannot be attached for security reasons.")

    return p


# ---------------------------------------------------------------------------
# Ticket resolution
# ---------------------------------------------------------------------------

def resolve_ref(ref: str, board: Path) -> Path:
    """Resolve a ticket ref to a file path. Accepts full, 2-part, or 1-part refs."""
    parts = ref.strip().split('/')
    if len(parts) == 3:
        project, epic, tid = parts
    elif len(parts) == 2:
        projects = [d for d in board.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if len(projects) == 1:
            project = projects[0].name
        else:
            raise ValueError(f"Ambiguous ref '{ref}': specify project/epic/Tnnn")
        epic, tid = parts
    elif len(parts) == 1:
        projects = [d for d in board.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if len(projects) == 1:
            project = projects[0].name
            epics = [d for d in (board / project).iterdir() if d.is_dir() and not d.name.startswith('.')]
            if len(epics) == 1:
                epic = epics[0].name
            else:
                raise ValueError(f"Ambiguous ref '{ref}': specify project/epic/Tnnn")
        else:
            raise ValueError(f"Ambiguous ref '{ref}': specify project/epic/Tnnn")
        tid = parts[0]
    else:
        raise ValueError(f"Invalid ref: {ref}")

    tid = tid.upper().replace('T', 'T', 1)
    if not TICKET_ID_RE.match(tid):
        raise ValueError(f"Invalid ticket ID '{tid}': must be T001-T999")

    return board / project / epic / f"{tid}.md"


def full_ref(path: Path, board: Path) -> str:
    rel = path.relative_to(board)
    parts = rel.parts
    return f"{parts[0]}/{parts[1]}/{parts[2].replace('.md', '')}"


# ---------------------------------------------------------------------------
# Core Engine Operations
# ---------------------------------------------------------------------------

def next_ticket_id(project: str, epic: str, board: Path) -> str:
    """Find highest Tnnn in epic directory and return the next formatted ID."""
    epic_dir = board / project / epic
    if not epic_dir.exists():
        return "T001"
    highest = 0
    for f in epic_dir.glob("T*.md"):
        m = re.match(r"^T(\d{3,})$", f.stem)
        if m:
            num = int(m.group(1))
            if num > highest:
                highest = num
    return f"T{highest + 1:03d}"


SCAFFOLD_PATTERNS = {
    "agile": (
        "## Plan (Todo Tree)\n"
        "- [ ] A1 [START] [lane:main] Probe environment, dependencies & verify baseline assumptions\n"
        "- [ ] B1 [lane:fast] [after:A1] [when:if(fast_path_viable):fork1] Fast-path primary implementation\n"
        "- [ ] B2 [lane:fallback] [after:A1] [when:else(fast_path_viable):fork1] Fallback/contingency polyfill implementation\n"
        "- [ ] A2 [lane:main] [after:B1|B2] Integrate core solution with chosen branch\n"
        "- [ ] P1 [lane:test] [after:A1] [parallel] Draft test suite, boundary cases & negative discriminator probes\n"
        "- [ ] T1 [lane:test] [after:A2,P1] [ACCEPTANCE:MANDATORY] Positive functional requirements verified and regression tests pass\n"
        "- [ ] T2 [lane:test] [after:A2,P1] [parallel] [ACCEPTANCE:MANDATORY] Negative Discriminator: Malformed inputs and edge-case faults rejected cleanly\n"
        "- [ ] O1 [lane:polish] [after:A2] [optional] Performance optimization, caching, or visual polish enhancement\n"
        "- [ ] O2 [lane:polish] [after:O1] [ACCEPTANCE:OPTIONAL] Optional polish enhancement verified\n"
        "- [ ] T3 [lane:docs] [after:T1,T2,O2?] [ACCEPTANCE:MANDATORY] Synchronize living architecture documentation in epic.md"
    ),
    "feature": (
        "## Plan (Todo Tree)\n"
        "- [ ] A1 [START] [lane:core] Implement core feature logic and public interfaces\n"
        "- [ ] A2 [lane:core] [after:A1] Integrate validation guardrails and state handling\n"
        "- [ ] B1 [lane:test] [after:A1] [parallel] Author unit and integration regression test suite\n"
        "- [ ] T1 [lane:test] [after:A2,B1] [ACCEPTANCE:MANDATORY] Positive functional verification and automated test pass\n"
        "- [ ] T2 [lane:test] [after:A2,B1] [parallel] [ACCEPTANCE:MANDATORY] Negative Discriminator: Invalid inputs and unauthorized actions rejected\n"
        "- [ ] T3 [lane:docs] [after:T1,T2] [ACCEPTANCE:MANDATORY] Update epic.md living architecture documentation"
    ),
    "spike": (
        "## Plan (Todo Tree)\n"
        "- [ ] S1 [START] [lane:spike] Feasibility spike: probe target API, performance limits and constraints\n"
        "- [ ] S2 [lane:spike] [after:S1] Benchmark alternative solutions and identify trade-offs\n"
        "- [ ] B1 [lane:arch] [after:S2] [when:if(viable):eval] Author architectural decision record (ADR) adopting approach\n"
        "- [ ] B2 [lane:arch] [after:S2] [when:else(viable):eval] Author spike findings recommending alternative or deferral\n"
        "- [ ] A1 [lane:arch] [after:B1|B2] [ACCEPTANCE:MANDATORY] Architecture decision documented with concrete recommendations"
    ),
    "refactor": (
        "## Plan (Todo Tree)\n"
        "- [ ] 1. [START] [lane:guard] Establish baseline regression snapshot tests before refactoring\n"
        "- [ ] 2. [lane:refactor] [after:1] Perform modular refactoring isolating components\n"
        "- [ ] 3. [lane:refactor] [after:2] Modernize internal data structures and eliminate dead code\n"
        "- [ ] 4. [lane:test] [after:3] [ACCEPTANCE:MANDATORY] Ponytail Zero-Diff: All baseline snapshot tests pass with identical external behavior\n"
        "- [ ] 5. [lane:docs] [after:4] [ACCEPTANCE:MANDATORY] Update architectural documentation and code comments"
    )
}


def api_scaffold_dag(pattern: str = "agile", goal: str = "", lanes: Optional[list[str]] = None) -> str:
    """Generate a pre-validated, mathematically compliant Agile DAG Todo Tree template."""
    pat = pattern.lower().strip() if pattern else "agile"
    if pat not in SCAFFOLD_PATTERNS:
        valid_pats = ", ".join(SCAFFOLD_PATTERNS.keys())
        raise ValueError(f"Unknown scaffold pattern '{pattern}'. Available: {valid_pats}")
    return SCAFFOLD_PATTERNS[pat]


def api_create(ref: str, title: str, board: Path, pattern: str = "agile", plan: Optional[str] = None) -> dict:
    parts = ref.strip().split('/')
    if len(parts) == 2:
        project, epic = parts
        tid = next_ticket_id(project, epic, board)
    elif len(parts) == 3:
        project, epic, tid = parts
    else:
        raise ValueError(f"Ticket ref must be project/epic or project/epic/Tnnn: '{ref}'")
    if not SLUG_RE.match(project):
        raise ValueError(f"Invalid project slug '{project}'")
    if not SLUG_RE.match(epic):
        raise ValueError(f"Invalid epic slug '{epic}'")
    tid = tid.upper().replace('T', 'T', 1)
    if not TICKET_ID_RE.match(tid):
        raise ValueError(f"Invalid ticket ID '{tid}': must be T001-T999")

    path = board / project / epic / f"{tid}.md"
    if path.exists():
        raise FileExistsError(f"Ticket already exists: {path}")

    proj_md = board / project / "project.md"
    epic_md = board / project / epic / "epic.md"
    if not proj_md.exists() or not epic_md.exists():
        api_init(project, epic, board)

    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    plan_str = plan.strip() if plan and plan.strip() else api_scaffold_dag(pattern)
    if not plan_str.startswith("## Plan (Todo Tree)"):
        plan_str = f"## Plan (Todo Tree)\n{plan_str}"

    template_body = (
        "\n## Outcome\n"
        "Describe the observable result from a user or system perspective after this ticket is complete.\n\n"
        "## Scope\n"
        "- Allowed files/surfaces:\n"
        "  - `src/...`\n"
        "- Explicitly out of scope:\n"
        "  - `...`\n\n"
        f"{plan_str}\n\n"
        "## Prove\n"
        "Exact commands and expected output:\n"
        "```bash\n"
        "pytest tests/test_feature.py -v\n"
        "```\n"
        "Expected: All tests pass with zero regressions.\n"
    )

    content = render_frontmatter(
        {
            "title": title,
            "status": "backlog",
            "since": today,
            "note": None,
            "depends": [],
            "files": [],
            "owner": None,
            "attachments": []
        },
        template_body
    )
    with board_lock(board):
        path.write_text(content, encoding="utf-8")

    fref = full_ref(path, board)
    return {"ref": fref, "path": str(path), "status": "backlog", "title": title}


def api_init(project: str, epic: Optional[str], board: Path):
    if not SLUG_RE.match(project):
        raise ValueError(f"Invalid project slug '{project}'")
    proj_dir = board / project
    proj_dir.mkdir(parents=True, exist_ok=True)
    proj_md = proj_dir / "project.md"
    if not proj_md.exists():
        proj_md.write_text(
            f"---\nname: {project}\nstate: active\nsummary: Core {project} charter\nrepo: .\n---\n",
            encoding="utf-8"
        )
    if epic:
        if not SLUG_RE.match(epic):
            raise ValueError(f"Invalid epic slug '{epic}'")
        epic_dir = proj_dir / epic
        epic_dir.mkdir(exist_ok=True)
        epic_md = epic_dir / "epic.md"
        if not epic_md.exists():
            epic_md.write_text(
                f"---\nname: {epic}\nstate: active\nsummary: Milestone for {epic}\nrepo: .\n---\n",
                encoding="utf-8"
            )


def api_move(
    ref: str,
    new_status: str,
    note: str,
    board: Path,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    force: bool = False,
    caller_is_qa: bool = False,
    reason: str = "",
) -> dict:
    new_status = new_status.lower()
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Unknown status '{new_status}'. Valid: {', '.join(sorted(VALID_STATUSES))}")

    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    # Anti-cheat check: strictly no self-approval to done
    if new_status == "done" and not caller_is_qa:
        raise PermissionError(
            "Direct transition to 'done' is forbidden via kanban_move. "
            "Must be approved by kb-qa using kanban_qa(action='approve')."
        )

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        cur = meta.get("status", "backlog")

        if cur == new_status:
            raise ValueError(f"Ticket is already '{new_status}'. Same-status move is not allowed.")

        allowed = ALLOWED_TRANSITIONS.get(cur, set())
        if new_status not in allowed:
            raise ValueError(
                f"Transition '{cur}' -> '{new_status}' is not allowed.\n"
                f"  Allowed from '{cur}': {', '.join(sorted(allowed))}\n"
                f"  Lifecycle: backlog -> in-progress -> verify -> done (with blocked)"
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        cur_owner = meta.get("owner")

        # Gate 1: Non-trivial plan and atomic claim when moving to in-progress
        if new_status == "in-progress":
            missing = check_required_sections(body, REQUIRED_SECTIONS)
            if missing:
                raise ValueError(
                    f"Cannot move to 'in-progress': required sections missing or empty: {', '.join(missing)}"
                )

            # Validate Todo Tree
            nodes, tree_err = parse_todo_tree(body)
            if tree_err:
                raise ValueError(f"Cannot move to 'in-progress': {tree_err}")
            is_valid, reason_msg = validate_todo_tree(nodes, for_inprogress=(cur == "backlog"), body=body)
            if not is_valid:
                raise ValueError(f"Cannot move to 'in-progress': {reason_msg}")

            # Check existing lease & ownership
            is_active, lease_desc = inspect_ticket_lease(cur_owner)
            if is_active and not force:
                cur_agent = cur_owner.get("agent")
                if agent_id and cur_agent != agent_id:
                    raise PermissionError(
                        f"Ticket is already {lease_desc} (session: {cur_owner.get('session_id')}). "
                        f"Use force=True to take over if the previous agent is inactive."
                    )
            if is_active and force:
                takeover_note = f"Force takeover from {cur_owner.get('agent')}: {reason.strip() or 'no reason provided'}"
                note = f"{note.strip()} | {takeover_note}" if note.strip() else takeover_note

            # Assign new lease
            lease_exp = now + datetime.timedelta(minutes=lease_minutes)
            meta["owner"] = {
                "agent": agent_id or "agent",
                "session_id": session_id or "",
                "claimed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lease_expires": lease_exp.strftime("%Y-%m-%dT%H:%M:%SZ")
            }

        # Gates 2, 3, 4: Physical Git Check, DAG Unbroken Path & Real Prove Command when moving to verify
        if new_status == "verify":
            # Gate 4: Real Prove Command
            ok_prove, prove_msg = check_prove_command(body)
            if not ok_prove:
                raise ValueError(f"Cannot move to 'verify': {prove_msg}")

            # Gate 3: Unbroken Todo Tree DAG Path
            nodes, tree_err = parse_todo_tree(body)
            if tree_err:
                raise ValueError(f"Cannot move to 'verify': {tree_err}")
            is_valid, path_msg = validate_todo_tree(nodes, for_verify=True, body=body)
            if not is_valid:
                raise ValueError(f"Cannot move to 'verify': {path_msg}")

            # Gate 2: Smart Git Physical Verification
            ws_root = workspace_root()
            git_info = inspect_git_status(ws_root)
            if git_info.get("has_git"):
                uncommitted = git_info.get("uncommitted", [])
                # If git has 0 modifications and ticket has 0 files, block
                declared_files = meta.get("files") or []
                if not uncommitted and not declared_files:
                    raise ValueError(
                        "Cannot move to 'verify': No file modifications detected in git. "
                        "You cannot claim work is done without writing code or tests."
                    )

                # Smart auto-population if exactly 1 ticket in-progress
                active_tickets = [t for t in api_list(board, status="in-progress") if t["ref"] != ref]
                if not active_tickets and uncommitted:
                    # Single active ticket: auto-merge uncommitted files into ticket
                    merged_files = sorted(set(declared_files + uncommitted))
                    meta["files"] = merged_files

            # Hand ownership over to kb-qa
            meta["owner"] = {
                "agent": "kb-qa",
                "session_id": "",
                "claimed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lease_expires": None
            }

        if new_status == "blocked" and not note.strip():
            raise ValueError("Moving to 'blocked' requires note with a reason.")

        # Nonce generation on verify
        generated_nonce = None
        if new_status == "verify":
            generated_nonce = generate_qa_nonce(path, board)
        elif cur == "verify" and new_status != "done":
            burn_qa_nonce(path, board)

        meta["status"] = new_status
        meta["since"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if note.strip():
            meta["note"] = note.strip()

        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    fref = full_ref(path, board)
    res = {
        "ref": fref,
        "from": cur,
        "to": new_status,
        "note": note.strip()
    }
    if meta.get("owner"):
        res["owner"] = meta["owner"]
    if generated_nonce:
        res["qa_nonce_generated"] = True
    return res


def api_claim(
    ref: str,
    agent_id: str,
    session_id: str = "",
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    force: bool = False,
    reason: str = "",
    board: Path = None
) -> dict:
    """Explicitly claim or forcefully take over a ticket."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        cur_owner = meta.get("owner")
        is_active, lease_desc = inspect_ticket_lease(cur_owner)
        if is_active and not force:
            cur_agent = cur_owner.get("agent")
            if cur_agent != agent_id:
                raise PermissionError(
                    f"Ticket {ref} is currently {lease_desc} (session: {cur_owner.get('session_id')}). "
                    f"Use force=True to take over if the agent is dead or inactive."
                )

        if meta.get("status") != "done":
            nodes, tree_err = parse_todo_tree(body)
            if tree_err:
                raise ValueError(f"Cannot claim ticket '{ref}': {tree_err}")
            is_valid, v_err = validate_todo_tree(nodes, for_inprogress=True, body=body)
            if not is_valid:
                raise ValueError(f"Cannot claim ticket '{ref}': {v_err}")

        now = datetime.datetime.now(datetime.timezone.utc)
        lease_exp = now + datetime.timedelta(minutes=lease_minutes)
        meta["owner"] = {
            "agent": agent_id,
            "session_id": session_id,
            "claimed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lease_expires": lease_exp.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if force and reason:
            audit_entry = f"\n- **Takeover by {agent_id}** at {now.isoformat()}: {reason}"
            if "## Handover" in body:
                body = body.replace("## Handover", f"## Handover{audit_entry}")
            else:
                body = body.rstrip() + f"\n\n## Handover{audit_entry}\n"

        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    return {
        "ref": full_ref(path, board),
        "status": meta.get("status"),
        "owner": meta["owner"],
        "forced": force
    }


def api_unclaim(ref: str, agent_id: str, board: Path) -> dict:
    """Release claim on a ticket."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        cur_owner = meta.get("owner")
        if cur_owner and cur_owner.get("agent") != agent_id:
            raise PermissionError(f"Cannot unclaim: ticket is claimed by '{cur_owner.get('agent')}', not '{agent_id}'.")

        meta["owner"] = None
        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    return {"ref": full_ref(path, board), "owner": None, "unclaimed": True}


def api_checkpoint(
    ref: str,
    checked_nodes: Optional[list[str]] = None,
    files: Optional[list[str]] = None,
    notes: Optional[str] = None,
    board: Path = None,
    node_proofs: Optional[dict[str, str]] = None,
    skip_nodes: Optional[list[str]] = None,
    skip_reason: str = "",
    uncheck_nodes: Optional[list[str]] = None,
) -> dict:
    """Log progress, enforce DAG order & execution proofs, renew lease, and track touched files."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        # Renew lease
        now = datetime.datetime.now(datetime.timezone.utc)
        if meta.get("owner") and isinstance(meta["owner"], dict):
            lease_exp = now + datetime.timedelta(minutes=DEFAULT_LEASE_MINUTES)
            meta["owner"]["lease_expires"] = lease_exp.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Track files
        if files:
            current_files = meta.get("files") or []
            meta["files"] = sorted(set(current_files + files))

        log_entries: list[str] = []
        ts = now.strftime("%Y-%m-%d %H:%M UTC")
        nodes, tree_err = parse_todo_tree(body)
        if (checked_nodes or skip_nodes or uncheck_nodes) and tree_err:
            raise ValueError(f"Cannot update Todo Tree: {tree_err}")

        if nodes:
            by_id = {n["id"]: n for n in nodes}
            plan_m = PLAN_SECTION_RE.search(body)
            plan_header, plan_content = plan_m.group(1), plan_m.group(2)

            def _resolve_node_id(query: str) -> str:
                q = query.strip()
                if q in by_id:
                    return q
                for n in nodes:
                    if n["text"].lower().startswith(q.lower()):
                        return n["id"]
                raise ValueError(f"Todo Tree node not found: '{query}'. Available IDs: {', '.join(by_id.keys())}")

            def _set_checkbox(plan_text: str, node_id: str, new_mark: str) -> str:
                line_pat = re.compile(
                    r'^(\s*-\s*\[)[ xX-](\]\s*' + re.escape(node_id) + r'\b.*)$',
                    re.M,
                )
                updated, count = line_pat.subn(rf'\g<1>{new_mark}\g<2>', plan_text, count=1)
                if count == 0:
                    raise ValueError(f"Failed to update checkbox for node '{node_id}'.")
                return updated

            # 1. Process skips first (allows optional/else dependencies to resolve cleanly)
            for item in (skip_nodes or []):
                nid = _resolve_node_id(item)
                plan_content = _set_checkbox(plan_content, nid, "-")
                by_id[nid]["status"] = "skipped"
                by_id[nid]["skipped"] = True
                by_id[nid]["checked"] = False
                reason_txt = skip_reason.strip() or (node_proofs or {}).get(nid, "branch not taken")
                log_entries.append(f"- [{ts}] [SKIP] {nid} | reason: {reason_txt}")

            # 2. Process unchecks
            for item in (uncheck_nodes or []):
                nid = _resolve_node_id(item)
                plan_content = _set_checkbox(plan_content, nid, " ")
                by_id[nid]["status"] = "pending"
                by_id[nid]["checked"] = False
                by_id[nid]["skipped"] = False
                log_entries.append(f"- [{ts}] [UNCHECK] {nid} | reason: reset to pending")

            # 3. Process completions with strict dependency-order check & execution proof logging
            for item in (checked_nodes or []):
                nid = _resolve_node_id(item)
                node = by_id[nid]
                unmet = [
                    c["alts"] for c in node["after_clauses"]
                    if not _clause_satisfied(c, by_id)
                ]
                if unmet:
                    raise ValueError(
                        f"Cannot check off '{nid}': prerequisite(s) not yet completed: {unmet}."
                    )
                proof = (node_proofs or {}).get(nid) or (node_proofs or {}).get(item) or (notes.strip() if notes else "")
                if len(proof.strip()) < 5:
                    raise ValueError(
                        f"Checkpoint '{nid}' requires execution proof via node_proofs['{nid}'] "
                        f"(e.g., command run, output summary, or artifact path) to verify process execution."
                    )
                plan_content = _set_checkbox(plan_content, nid, "x")
                node["status"] = "done"
                node["checked"] = True
                node["skipped"] = False
                log_entries.append(f"- [{ts}] [DONE] {nid} | proof: {proof.strip()}")

            body = body[:plan_m.start()] + plan_header + plan_content + body[plan_m.end():]

            if log_entries:
                block = "\n".join(log_entries)
                if "## Execution Log" in body:
                    body = body.replace("## Execution Log", f"## Execution Log\n{block}", 1)
                else:
                    body = body.rstrip() + f"\n\n## Execution Log\n{block}\n"

        # Append or update ## Handover
        if notes:
            ts = now.strftime("%Y-%m-%d %H:%M UTC")
            entry = f"- [{ts}]: {notes.strip()}"
            if "## Handover" in body:
                body = body.replace("## Handover", f"## Handover\n{entry}")
            else:
                body = body.rstrip() + f"\n\n## Handover\n{entry}\n"

        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    updated_nodes, _ = parse_todo_tree(body)
    return {
        "ref": full_ref(path, board),
        "status": meta.get("status"),
        "files": meta.get("files"),
        "owner": meta.get("owner"),
        "lease_renewed": True,
        "ready_nodes": compute_ready_nodes(updated_nodes) if updated_nodes else [],
    }


def api_ticket_edit(
    ref: str,
    board: Path,
    outcome: Optional[str] = None,
    scope: Optional[str] = None,
    plan: Optional[str] = None,
    prove: Optional[str] = None,
    body: Optional[str] = None,
) -> dict:
    """Safely update ticket markdown sections without touching YAML status frontmatter."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, cur_body = parse_frontmatter(text)
        if meta.get("status") == "done":
            raise PermissionError("Cannot edit a 'done' ticket.")

        if body is not None:
            cur_body = "\n" + body.strip() + "\n"
        else:
            replacements = {
                "Outcome": outcome,
                "Scope": scope,
                "Plan (Todo Tree)": plan,
                "Prove": prove,
            }
            for heading, new_val in replacements.items():
                if new_val is None:
                    continue
                sec_re = re.compile(r'(##\s+' + re.escape(heading) + r'\s*\n)(.*?)(?=\n##\s+|\Z)', re.S)
                if sec_re.search(cur_body):
                    cur_body = sec_re.sub(rf'\g<1>{new_val.strip()}\n\n', cur_body, count=1)
                else:
                    cur_body = cur_body.rstrip() + f"\n\n## {heading}\n{new_val.strip()}\n"

        path.write_text(render_frontmatter(meta, cur_body), encoding="utf-8")

    return {"ref": full_ref(path, board), "status": meta.get("status"), "updated": True}


def api_attach(ref: str, file_path: str, description: str, board: Path) -> dict:
    """Attach a workspace file to the ticket with security boundaries."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    ws_root = workspace_root()
    source_path = check_attachment_safety(file_path, ws_root)

    # Destination folder: board/<project>/<epic>/attachments/<tid>/
    tid = path.stem
    attach_dir = path.parent / ATTACHMENTS_DIR_NAME / tid
    attach_dir.mkdir(parents=True, exist_ok=True)
    dest_path = attach_dir / source_path.name
    shutil.copy2(source_path, dest_path)

    rel_dest = dest_path.relative_to(ws_root).as_posix()

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        attachments = meta.get("attachments") or []
        # Deduplicate by filename
        attachments = [a for a in attachments if not (isinstance(a, dict) and a.get("name") == source_path.name)]
        attachments.append({
            "name": source_path.name,
            "path": rel_dest,
            "size": dest_path.stat().st_size,
            "desc": description.strip()
        })
        meta["attachments"] = attachments

        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    return {
        "ref": full_ref(path, board),
        "attached": source_path.name,
        "path": rel_dest,
        "size": dest_path.stat().st_size
    }


def api_detach(ref: str, name: str, board: Path) -> dict:
    """Detach a file from the ticket."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    tid = path.stem
    target_file = path.parent / ATTACHMENTS_DIR_NAME / tid / name

    with board_lock(board):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        attachments = meta.get("attachments") or []
        meta["attachments"] = [a for a in attachments if not (isinstance(a, dict) and a.get("name") == name)]

        if target_file.exists():
            try:
                target_file.unlink()
            except OSError:
                pass

        path.write_text(render_frontmatter(meta, body), encoding="utf-8")

    return {"ref": full_ref(path, board), "detached": name}


def api_doc(
    action: str,
    project: str,
    epic: Optional[str] = None,
    name: Optional[str] = None,
    content: str = "",
    board: Path = None,
) -> dict:
    """Read, write, or list project/epic documentation. Defaults name to 'epic' or 'project'."""
    if not SLUG_RE.match(project):
        raise ValueError(f"Invalid project slug '{project}'")
    if epic and not SLUG_RE.match(epic):
        raise ValueError(f"Invalid epic slug '{epic}'")

    target_dir = board / project / epic if epic else board / project
    if action == "list":
        if not target_dir.exists():
            return {"action": "list", "path": str(target_dir), "docs": []}
        docs = sorted(p.stem for p in target_dir.glob("*.md") if not p.name.startswith("T"))
        return {"action": "list", "path": str(target_dir), "docs": docs}

    raw_name = name.strip() if name else ("epic" if epic else "project")
    doc_name = raw_name.replace(".md", "")
    if not SLUG_RE.match(doc_name):
        raise ValueError(f"Invalid document slug '{doc_name}'")

    target_file = target_dir / f"{doc_name}.md"

    if action == "write":
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content.strip() + "\n", encoding="utf-8")
        return {"action": "write", "path": str(target_file), "size": len(content)}
    elif action == "read":
        if not target_file.exists():
            raise FileNotFoundError(f"Document not found: {target_file}")
        return {"action": "read", "path": str(target_file), "content": target_file.read_text(encoding="utf-8")}
    else:
        raise ValueError(f"Unknown doc action '{action}'. Valid: read, write, list")


def api_overview(board: Path, project: Optional[str] = None, epic: Optional[str] = None) -> dict:
    """Unified discovery: returns projects, charters, epics, docs, and active tickets in one call."""
    overview: dict[str, Any] = {"projects": []}
    if not board.exists():
        return overview

    for proj_dir in sorted(board.iterdir()):
        if not proj_dir.is_dir() or proj_dir.name.startswith("."):
            continue
        p_slug = proj_dir.name
        if project and p_slug != project:
            continue

        proj_md = proj_dir / "project.md"
        proj_meta, proj_body = parse_frontmatter(proj_md.read_text(encoding="utf-8")) if proj_md.exists() else ({}, "")

        # Project docs
        proj_docs = []
        for f in sorted(proj_dir.glob("*.md")):
            if f.name != "project.md":
                proj_docs.append({"slug": f.stem, "path": str(f.relative_to(board))})

        epics_list = []
        for epic_dir in sorted(proj_dir.iterdir()):
            if not epic_dir.is_dir() or epic_dir.name.startswith("."):
                continue
            e_slug = epic_dir.name
            if epic and e_slug != epic:
                continue

            epic_md = epic_dir / "epic.md"
            epic_meta, epic_body = parse_frontmatter(epic_md.read_text(encoding="utf-8")) if epic_md.exists() else ({}, "")

            epic_docs = []
            for f in sorted(epic_dir.glob("*.md")):
                if f.name != "epic.md" and not TICKET_ID_RE.match(f.stem):
                    epic_docs.append({"slug": f.stem, "path": str(f.relative_to(board))})

            tickets = []
            status_counts = {s: 0 for s in VALID_STATUSES}
            for f in sorted(epic_dir.glob("T*.md")):
                if not TICKET_ID_RE.match(f.stem):
                    continue
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                st = meta.get("status", "backlog")
                status_counts[st] = status_counts.get(st, 0) + 1

                # Calculate Todo Tree completion progress
                nodes, _ = parse_todo_tree(body)
                progress_str = None
                if nodes:
                    checked_count = sum(1 for n in nodes if n["checked"])
                    progress_str = f"{checked_count}/{len(nodes)} nodes checked"

                is_active, lease_str = inspect_ticket_lease(meta.get("owner"))

                tickets.append({
                    "ref": f"{p_slug}/{e_slug}/{f.stem}",
                    "title": meta.get("title", ""),
                    "status": st,
                    "owner": meta.get("owner"),
                    "lease_status": lease_str,
                    "progress": progress_str,
                    "files": meta.get("files") or [],
                    "attachments_count": len(meta.get("attachments") or [])
                })

            epics_list.append({
                "slug": e_slug,
                "name": epic_meta.get("name", e_slug),
                "summary": epic_meta.get("summary", ""),
                "docs": epic_docs,
                "status_summary": status_counts,
                "tickets": tickets
            })

        overview["projects"].append({
            "slug": p_slug,
            "name": proj_meta.get("name", p_slug),
            "summary": proj_meta.get("summary", ""),
            "docs": proj_docs,
            "epics": epics_list
        })

    return overview


def api_qa_start(ref: str, board: Path) -> dict:
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    cur = meta.get("status")
    if cur != "verify":
        raise ValueError(f"Cannot start QA on ticket in '{cur}' state. Must be 'verify'.")

    nonce = read_qa_nonce(path, board)
    if not nonce:
        nonce = generate_qa_nonce(path, board)

    return {
        "ref": full_ref(path, board),
        "path": str(path),
        "status": cur,
        "qa_nonce": nonce,
        "metadata": meta,
        "body": body
    }


def api_qa_approve(ref: str, nonce: str, evidence_path: str, note: str, board: Path) -> dict:
    """Gate 5: Independent QA Approval with Process & Result Evidence Audit."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")

    if not nonce or not nonce.strip():
        raise PermissionError("Missing required qa_nonce.")

    stored_nonce = read_qa_nonce(path, board)
    if not stored_nonce or stored_nonce.strip() != nonce.strip():
        raise PermissionError("Invalid or expired qa_nonce. Anti-cheat check failed.")

    ws_root = workspace_root()
    ev_p = Path(evidence_path)
    if not ev_p.is_absolute():
        ev_p = ws_root / ev_p

    if not ev_p.exists():
        raise FileNotFoundError(f"QA Evidence file not found: {evidence_path}")

    # Substantive content check on evidence report with flexible regex matching
    ev_text = ev_p.read_text(encoding="utf-8")
    required_patterns = [
        (re.compile(r"process\s*(?:&|and)?\s*checkpoint(?:\s*execution)?\s*audit", re.I), "Process & Checkpoint Audit"),
        (re.compile(r"(?:minimal\s*)?diff(?:\s*review)?", re.I), "Diff Review"),
        (re.compile(r"living\s*architecture", re.I), "Living Architecture"),
        (re.compile(r"positive\s*tests?", re.I), "Positive Tests"),
        (re.compile(r"negative\s*(?:discriminator)?\s*(?:tests?|verification)", re.I), "Negative Discriminator Tests"),
        (re.compile(r"\bPASS\b", re.I), "PASS verdict"),
    ]
    for pat, label in required_patterns:
        if not pat.search(ev_text):
            raise ValueError(
                f"QA Evidence report fails audit: Missing required section or verdict '{label}'. "
                f"Report must contain Process & Checkpoint Audit, Diff Review, Living Architecture, "
                f"Positive Tests, Negative Discriminator Tests, and PASS."
            )

    # Verify all active mandatory acceptance checkpoints are cited in QA evidence
    ticket_text = path.read_text(encoding="utf-8")
    _, ticket_body = parse_frontmatter(ticket_text)
    nodes, tree_err = parse_todo_tree(ticket_body)
    if tree_err:
        raise ValueError(f"QA approval blocked: {tree_err}")
    ok_tree, tree_msg = validate_todo_tree(nodes, for_verify=True, body=ticket_body)
    if not ok_tree:
        raise ValueError(f"QA approval blocked by DAG/process check: {tree_msg}")
    active_mandatory_ids = [
        n["id"] for n in nodes
        if n["is_acceptance"] and n["acceptance_kind"] == "MANDATORY" and n["status"] != "skipped"
    ]
    uncited = [nid for nid in active_mandatory_ids if nid not in ev_text]
    if uncited:
        raise ValueError(
            f"QA Evidence report must explicitly verify all mandatory acceptance checkpoint(s): {', '.join(uncited)}."
        )

    # Approve move to done
    res = api_move(
        ref,
        new_status="done",
        note=note,
        board=board,
        caller_is_qa=True
    )
    burn_qa_nonce(path, board)
    res["evidence"] = str(ev_p)
    return res


def api_qa_reject(
    ref: str,
    nonce: str,
    note: str,
    board: Path,
    evidence_path: Optional[str] = None,
) -> dict:
    """Symmetric QA rejection: burns nonce, records failure reason, returns ticket to in-progress."""
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")
    if not nonce or not nonce.strip():
        raise PermissionError("Missing required qa_nonce.")
    stored_nonce = read_qa_nonce(path, board)
    if not stored_nonce or stored_nonce.strip() != nonce.strip():
        raise PermissionError("Invalid or expired qa_nonce.")
    if not note or not note.strip():
        raise ValueError("QA rejection requires a descriptive failure note.")

    full_note = f"[QA REJECTED] {note.strip()}"
    if evidence_path:
        full_note += f" (evidence: {evidence_path})"
    res = api_move(ref, new_status="in-progress", note=full_note, board=board, caller_is_qa=True)
    burn_qa_nonce(path, board)
    if evidence_path:
        res["evidence"] = evidence_path
    return res


def api_show(ref: str, board: Path) -> dict:
    path = resolve_ref(ref, board)
    if not path.exists():
        raise FileNotFoundError(f"Ticket not found: {ref}")
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return {
        "ref": full_ref(path, board),
        "path": str(path),
        "status": meta.get("status", "backlog"),
        "title": meta.get("title", ""),
        "metadata": meta,
        "body": body
    }


def api_list(
    board: Path,
    project: Optional[str] = None,
    epic: Optional[str] = None,
    status: Optional[str] = None
) -> list[dict]:
    tickets = []
    if not board.exists():
        return tickets

    for p_dir in sorted(board.iterdir()):
        if not p_dir.is_dir() or p_dir.name.startswith('.'):
            continue
        p_name = p_dir.name
        if project and p_name != project:
            continue
        for e_dir in sorted(p_dir.iterdir()):
            if not e_dir.is_dir() or e_dir.name.startswith('.'):
                continue
            e_name = e_dir.name
            if epic and e_name != epic:
                continue
            for f in sorted(e_dir.glob("T*.md")):
                if not TICKET_ID_RE.match(f.stem):
                    continue
                meta, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
                st = meta.get("status", "backlog")
                if status and st != status:
                    continue
                tickets.append({
                    "ref": f"{p_name}/{e_name}/{f.stem}",
                    "status": st,
                    "title": meta.get("title", ""),
                    "note": meta.get("note"),
                    "since": meta.get("since"),
                    "owner": meta.get("owner"),
                    "path": str(f)
                })
    return tickets


def api_lint(board: Path) -> dict:
    errors = []
    warnings = []
    if not board.exists():
        board.mkdir(parents=True, exist_ok=True)
        return {
            "errors": [],
            "warnings": ["Board directory ('board/') was just initialized and is empty. Use kanban_ticket to create your first ticket."]
        }

    all_tickets = set()
    ticket_depends = {}

    project_dirs = [p for p in sorted(board.iterdir()) if p.is_dir() and not p.name.startswith('.')]
    if not project_dirs:
        return {
            "errors": [],
            "warnings": ["Board directory is empty (no projects found). Use kanban_ticket to create your first ticket or kanban_doc to write a project charter."]
        }

    for p_dir in project_dirs:
        if not p_dir.is_dir() or p_dir.name.startswith('.'):
            continue
        if not (p_dir / "project.md").exists():
            errors.append(f"{p_dir.name}/: missing project.md")
        for e_dir in sorted(p_dir.iterdir()):
            if not e_dir.is_dir() or e_dir.name.startswith('.'):
                continue
            if not (e_dir / "epic.md").exists():
                errors.append(f"{p_dir.name}/{e_dir.name}/: missing epic.md")
            for f in sorted(e_dir.glob("*.md")):
                if f.name == "epic.md":
                    continue
                if not TICKET_ID_RE.match(f.stem):
                    continue
                ref = f"{p_dir.name}/{e_dir.name}/{f.stem}"
                all_tickets.add(ref)
                meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                ticket_depends[ref] = meta.get("depends") or []
                st = meta.get("status")
                if st not in VALID_STATUSES:
                    errors.append(f"{ref}: invalid status '{st}'")
                if st in GATE_STATUSES:
                    nodes, err = parse_todo_tree(body)
                    if err:
                        warnings.append(f"{ref}: {err}")

    # Check dependencies
    for ref, deps in ticket_depends.items():
        for d in deps:
            if d not in all_tickets:
                errors.append(f"{ref}: depends on non-existent ticket '{d}'")

    return {"errors": errors, "warnings": warnings}


def api_board_payload(board: Path) -> dict:
    """Payload for the web dashboard viewer."""
    projects = []
    if board.exists():
        for proj_dir in sorted(board.iterdir()):
            if not proj_dir.is_dir() or proj_dir.name.startswith('.'):
                continue
            proj_name = proj_dir.name
            proj_meta = {}
            proj_body = ""
            proj_md = proj_dir / "project.md"
            if proj_md.exists():
                proj_meta, proj_body = parse_frontmatter(proj_md.read_text(encoding="utf-8"))

            proj_docs = []
            for f in sorted(proj_dir.glob("*.md")):
                if f.name != "project.md":
                    proj_docs.append({"slug": f.stem, "name": f.stem, "path": str(f)})

            epics = []
            proj_tickets = []
            for epic_dir in sorted(proj_dir.iterdir()):
                if not epic_dir.is_dir() or epic_dir.name.startswith('.'):
                    continue
                epic_slug = epic_dir.name
                epic_meta = {}
                epic_body = ""
                epic_md = epic_dir / "epic.md"
                if epic_md.exists():
                    epic_meta, epic_body = parse_frontmatter(epic_md.read_text(encoding="utf-8"))

                epic_docs = []
                for f in sorted(epic_dir.glob("*.md")):
                    if f.name != "epic.md" and not TICKET_ID_RE.match(f.stem):
                        epic_docs.append({"slug": f.stem, "name": f.stem, "path": str(f)})

                epics.append({
                    "slug": epic_slug,
                    "name": epic_meta.get("name", epic_slug),
                    "state": epic_meta.get("state", "active"),
                    "summary": epic_meta.get("summary", ""),
                    "repo": epic_meta.get("repo", "."),
                    "body": epic_body,
                    "docs": epic_docs
                })

                for f in sorted(epic_dir.glob("T*.md")):
                    if not TICKET_ID_RE.match(f.stem):
                        continue
                    meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
                    ref = full_ref(f, board)
                    is_active, lease_str = inspect_ticket_lease(meta.get("owner"))
                    proj_tickets.append({
                        "reference": ref,
                        "id": f.stem,
                        "epic": epic_slug,
                        "status": meta.get("status", "backlog"),
                        "title": meta.get("title", ""),
                        "note": meta.get("note", ""),
                        "since": meta.get("since", ""),
                        "owner": meta.get("owner"),
                        "lease_status": lease_str,
                        "depends": meta.get("depends") or [],
                        "files": meta.get("files") or [],
                        "attachments": meta.get("attachments") or [],
                        "body": body,
                        "path": str(f)
                    })

            projects.append({
                "slug": proj_name,
                "name": proj_meta.get("name", proj_name),
                "state": proj_meta.get("state", "active"),
                "summary": proj_meta.get("summary", ""),
                "repo": proj_meta.get("repo", "."),
                "body": proj_body,
                "docs": proj_docs,
                "epics": epics,
                "tickets": proj_tickets
            })

    return {
        "board": {
            "projects": projects
        },
        "statuses": list(VALID_STATUSES)
    }


# ---------------------------------------------------------------------------
# CLI Command Wrappers
# ---------------------------------------------------------------------------

def die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Kanban Board CLI")
    parser.add_argument("--board", default=None, help="Explicit path to board directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("overview", help="Unified board discovery")

    p_init = sub.add_parser("init", help="Initialize board, project charter, and optional epic")
    p_init.add_argument("project", nargs="?", default="default", help="Project slug")
    p_init.add_argument("epic", nargs="?", default=None, help="Optional epic slug")

    p_create = sub.add_parser("create", help="Create a ticket in backlog")
    p_create.add_argument("ref", help="project/epic/Tnnn")
    p_create.add_argument("title", help="One-line summary")
    p_create.add_argument("--pattern", choices=list(SCAFFOLD_PATTERNS.keys()), default="agile", help="DAG template pattern")

    p_scaffold = sub.add_parser("scaffold", help="Generate an agile DAG Todo Tree template")
    p_scaffold.add_argument("--pattern", choices=list(SCAFFOLD_PATTERNS.keys()), default="agile", help="DAG template pattern")

    p_move = sub.add_parser("move", help="Move ticket through lifecycle")
    p_move.add_argument("ref", help="Ticket ref")
    p_move.add_argument("status", choices=list(VALID_STATUSES))
    p_move.add_argument("-n", "--note", default="")
    p_move.add_argument("--agent", default=None)
    p_move.add_argument("--force", action="store_true")

    p_claim = sub.add_parser("claim", help="Claim ownership of ticket")
    p_claim.add_argument("ref")
    p_claim.add_argument("agent")
    p_claim.add_argument("--force", action="store_true")
    p_claim.add_argument("--reason", default="")

    p_qa_start = sub.add_parser("qa-start", help="Initiate QA audit session")
    p_qa_start.add_argument("ref")

    p_qa_app = sub.add_parser("qa-approve", help="Approve ticket to done")
    p_qa_app.add_argument("ref")
    p_qa_app.add_argument("nonce")
    p_qa_app.add_argument("evidence")
    p_qa_app.add_argument("-n", "--note", default="Approved by QA")

    p_show = sub.add_parser("show", help="Show ticket details")
    p_show.add_argument("ref")

    p_list = sub.add_parser("list", help="List tickets")
    p_list.add_argument("-p", "--project", default=None)
    p_list.add_argument("-e", "--epic", default=None)
    p_list.add_argument("-s", "--status", default=None)

    p_doc = sub.add_parser("doc", help="Read or write project/epic documentation")
    p_doc.add_argument("project", help="Project slug")
    p_doc.add_argument("name", help="Document name/slug")
    p_doc.add_argument("-e", "--epic", default=None, help="Optional epic slug")
    p_doc.add_argument("-w", "--write", default=None, help="Content to write (omit to read)")

    p_serve = sub.add_parser("serve", help="Run live local loopback web dashboard")
    p_serve.add_argument("--port", type=int, default=7890, help="Port to listen on (default 7890)")
    p_serve.add_argument("--no-browser", action="store_true", help="Do not open browser")

    sub.add_parser("lint", help="Lint board health")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    board = Path(args.board).resolve() if args.board else board_root()

    try:
        if args.command == "overview":
            data = api_overview(board)
            print(json.dumps(data, indent=2))
        elif args.command == "init":
            api_init(args.project, args.epic, board)
            print(f"Initialized board and project '{args.project}' at {board / args.project}")
        elif args.command == "create":
            res = api_create(args.ref, args.title, board, pattern=args.pattern)
            print(f"Created {res['ref']} in backlog [{res['path']}]")
        elif args.command == "scaffold":
            dag = api_scaffold_dag(args.pattern)
            print(dag)
        elif args.command == "move":
            res = api_move(args.ref, args.status, args.note, board, agent_id=args.agent, force=args.force)
            print(f"Moved {res['ref']}: {res['from']} -> {res['to']}")
        elif args.command == "claim":
            res = api_claim(args.ref, args.agent, force=args.force, reason=args.reason, board=board)
            print(f"Claimed {res['ref']} for {res['owner']['agent']}")
        elif args.command == "qa-start":
            res = api_qa_start(args.ref, board)
            print(json.dumps(res, indent=2))
        elif args.command == "qa-approve":
            res = api_qa_approve(args.ref, args.nonce, args.evidence, args.note, board)
            print(f"Approved {res['ref']} -> done")
        elif args.command == "show":
            res = api_show(args.ref, board)
            print(json.dumps(res, indent=2))
        elif args.command == "list":
            tickets = api_list(board, args.project, args.epic, args.status)
            print(json.dumps(tickets, indent=2))
        elif args.command == "doc":
            action = "write" if args.write is not None else "read"
            res = api_doc(action, args.project, args.epic, args.name, content=args.write or "", board=board)
            if action == "read":
                print(res.get("content", ""))
            else:
                print(f"Wrote {res.get('doc', args.name)} [{res.get('path', '')}]")
        elif args.command == "serve":
            import viewer
            viewer.run_server(board, port=args.port, open_browser=not args.no_browser)
        elif args.command == "lint":
            res = api_lint(board)
            print(json.dumps(res, indent=2))
    except Exception as e:
        die(str(e))


if __name__ == "__main__":
    main()
