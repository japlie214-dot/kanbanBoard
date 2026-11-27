#!/usr/bin/env python3
"""mcp_server.py — Zero-dependency native Model Context Protocol (MCP) server for kanban-board.

Dual-Mode Capability Isolation:
  --mode work (default): Exposes ONLY the 6 worker tools (kanban_qa is physically absent).
  --mode qa:             Exposes ONLY kanban_qa plus read-only kanban_board and kanban_ticket(show).

7-Tool Harmonized Arsenal:
1. kanban_board  - Discovery, listing, and board health linting (view="overview"|"init"|"list"|"lint")
2. kanban_ticket - Create, inspect, scaffold, or edit tickets
3. kanban_move   - Status transitions with atomic claim, 60m lease, force takeover, & Anti-Laziness Gates
4. kanban_update - In-flight progress: check Todo Tree nodes, declare files, log notes, attach/detach files
5. kanban_doc    - Read or write project/epic architectural documentation (docs: [])
6. kanban_view   - Launch/render interactive view-only web dashboard widget (detached subprocess)
7. kanban_qa     - Restricted 4-tier QA protocol exclusively for kb-qa (--mode qa only)
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

# Add project root to path to import kb
sys.path.insert(0, str(Path(__file__).parent.resolve()))
import kb
import kb_cases
import kb_crud
import kb_doc_queue
import kb_doc_runner
import kb_doc_store
import kb_ergonomics
import kb_history
import kb_qa_otp
import kb_version

SERVER_NAME = "kanban"
SERVER_VERSION = "4.0.1"
_VIEWER_PORT: Optional[int] = None

WORK_TOOL_NAMES = frozenset({
    "kanban_board",
    "kanban_ticket",
    "kanban_move",
    "kanban_update",
    "kanban_doc",
    "kanban_view",
    "kanban_qa",
    "kanban_case",
    "kanban_project",
})

QA_TOOL_NAMES = frozenset({
    "kanban_board",
    "kanban_ticket",
    "kanban_qa",
    "kanban_case",
})

TOOLS = [
    {
        "name": "kanban_board",
        "description": "Unified board management: discovery, listing, linting, and explicit board initialization. Use view='overview' (default) for charters, epics, docs, active tickets & owners; view='init' to explicitly initialize a board and project charter; view='list' for compact ticket lists; view='lint' for integrity checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "view": {
                    "type": "string",
                    "enum": ["overview", "init", "list", "lint"],
                    "description": "Action mode: 'overview' (default), 'init' (initialize board & project/epic), 'list', or 'lint'",
                    "default": "overview"
                },
                "project": {"type": "string", "description": "Project slug (used for filter or initialization)"},
                "epic": {"type": "string", "description": "Epic slug (used for filter or initialization)"},
                "page": {"type": "integer", "description": "1-based page number (default 1)"},
                "page_size": {"type": "integer", "description": "Items per page (default 25, max 100)"},
                "q": {"type": "string", "description": "Optional search query across ref, title, owner"},
                "include_retired": {"type": "boolean", "description": "Include retired backlog tickets (default false)"},
                "status": {"type": "string", "description": "Optional status filter (backlog, build, verify, done, blocked; 'in-progress' aliases to 'build')"}
            }
        }
    },
    {
        "name": "kanban_ticket",
        "description": "Create, inspect, edit, retire, restore, or rehome tickets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["show", "create", "edit", "retire", "restore", "rehome"],
                    "description": "Explicit mode (recommended; inferred if unambiguous)"
                },
                "ref": {"type": "string", "description": "Ticket reference (e.g. web/auth/T001). Optional when creating if project and epic are provided."},
                "project": {"type": "string", "description": "Project slug (when creating without explicit ref)"},
                "epic": {"type": "string", "description": "Epic slug (when creating without explicit ref)"},
                "title": {"type": "string", "description": "Ticket title (required for action='create')"},
                "pattern": {
                    "type": "string",
                    "enum": ["agile", "feature", "spike", "refactor"],
                    "description": "DAG template pattern when scaffolding or creating (default: agile)"
                },
                "outcome": {"type": "string", "description": "Updated ## Outcome content (for action='edit')"},
                "scope": {"type": "string", "description": "Updated ## Scope content (for action='edit')"},
                "plan": {"type": "string", "description": "Updated ## Plan (Todo Tree) DAG content (for action='edit' or 'create')"},
                "prove": {"type": "string", "description": "Updated ## Prove content (for action='edit')"},
                "body": {"type": "string", "description": "Full replacement markdown body (for action='edit')"},
                "force": {"type": "boolean", "description": "Force edit even if ticket is in verify or done state", "default": False},
                "reason": {"type": "string", "description": "Reason for retiring ticket (min 5 chars, for action='retire')"},
                "purge_after_days": {"type": "integer", "description": "Days before auto hard-delete when retired (default: 120)"},
                "new_epic": {"type": "string", "description": "Target epic slug (for action='rehome')"},
                "new_project": {"type": "string", "description": "Optional target project slug (for action='rehome')"},
                "note": {"type": "string", "description": "Optional note (for action='retire' or 'restore')"}
            }
        }
    },
    {
        "name": "kanban_move",
        "description": "Move a ticket between backlog, build, verify, and blocked ('in-progress' accepted as alias for 'build'). Moving to 'build' atomically claims ownership with a 60-minute lease. Moving to 'verify' enforces the 5 Anti-Laziness Gates (Git modifications, unbroken DAG path, Prove command). NOTE: 'done' is strictly forbidden here (only kb-qa approves to done via kanban_qa).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Ticket ref (e.g. web/auth/T001)"},
                "status": {
                    "type": "string",
                    "enum": ["backlog", "build", "in-progress", "verify", "blocked"],
                    "description": "Target status ('build' preferred; 'in-progress' aliases to 'build'). NOTE: 'done' is forbidden via this tool."
                },
                "note": {"type": "string", "description": "Note (required when moving to blocked)"},
                "agent_id": {"type": "string", "description": "Agent identifier claiming ticket on build"},
                "session_id": {"type": "string", "description": "Optional session/conversation ID"},
                "lease_minutes": {"type": "integer", "description": "Lease duration in minutes (default: 60)"},
                "force": {"type": "boolean", "description": "Force takeover if ticket is held by another agent"},
                "reason": {"type": "string", "description": "Reason for forceful takeover"},
                "workspace": {"type": "string", "description": "Explicit target repository root path for Gate 2 git status check (recommended for centralized multi-project boards)"}
            },
            "required": ["ref", "status"]
        }
    },
    {
        "name": "kanban_update",
        "description": "Update in-flight progress on an active ticket: check off Todo Tree DAG checkpoints with execution proofs (enforces dependency order), skip untaken if/else or optional branches (- [-]), uncheck nodes, declare modified files, log handover notes (renews lease), and attach or detach files. Returns newly unblocked ready_nodes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Ticket ref (e.g. web/auth/T001)"},
                "checked_nodes": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to mark executed (- [x]). Prerequisites in [after:...] must already be done."},
                "node_proofs": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Execution proof per node ID (e.g. {'A1': 'pytest tests/test_a.py -> 5 passed'}). Recorded in ## Execution Log for kb-qa process audit."
                },
                "skip_nodes": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to mark skipped (- [-]) for untaken if/else or optional branches"},
                "skip_reason": {"type": "string", "description": "Branch decision reason recorded when skipping nodes"},
                "uncheck_nodes": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to reset back to pending (- [ ])"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "List of files modified for this ticket"},
                "notes": {"type": "string", "description": "Progress or handover notes (automatically renews lease)"},
                "attach_file": {"type": "string", "description": "Workspace-relative path of file to attach"},
                "attach_desc": {"type": "string", "description": "Optional description for attachment"},
                "detach_file": {"type": "string", "description": "Filename of attachment to remove"}
            },
            "required": ["ref"]
        }
    },
    {
        "name": "kanban_doc",
        "description": "Read, write, or list project/epic architectural documentation and charters. If 'name' is omitted, automatically defaults to 'epic' (when epic is set) or 'project' (project charter).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write", "list"], "description": "Action to perform"},
                "project": {"type": "string", "description": "Project slug"},
                "epic": {"type": "string", "description": "Optional epic slug"},
                "name": {"type": "string", "description": "Optional document slug/filename without .md (defaults to 'epic' or 'project')"},
                "content": {"type": "string", "description": "Document content (required for action='write')"}
            },
            "required": ["action", "project"]
        }
    },
    {
        "name": "kanban_view",
        "description": "Render or launch the interactive view-only Kanban board web dashboard widget.",
        "_meta": {
            "ui": {
                "resourceUri": "ui://kanban/board"
            }
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "open_browser": {
                    "type": "boolean",
                    "description": "If true, also launches the local loopback browser viewer on an available port (default 7890+)",
                    "default": True
                }
            }
        }
    },
    {
        "name": "kanban_qa",
        "description": "RESTRICTED (--mode qa ONLY): Exclusively for kb-qa subagent to execute the 4-tier Process + Result QA protocol. 'start' fetches ticket spec + execution log + secret qa_nonce. 'approve' validates process & checkpoint audit + diff + living docs + Horse vs. Zebra evidence, signs with HMAC, and certifies to 'done'. 'reject' burns nonce and returns ticket to 'in-progress' with failure reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["start", "approve", "reject"], "description": "QA action to perform"},
                "ref": {"type": "string", "description": "Ticket ref in 'verify' state"},
                "qa_passkey": {"type": "string", "description": "Confidential single-use OTP from kb-qa system prompt (required)"},
                "qa_nonce": {"type": "string", "description": "Ephemeral cryptographic nonce (required for approve/reject)"},
                "evidence_path": {"type": "string", "description": "Path to QA evidence markdown report (required for approve, optional for reject)"},
                "note": {"type": "string", "description": "Certification summary (approve) or failure reason (reject)"},
                "workspace": {"type": "string", "description": "Optional target repository root for resolving relative evidence_path"}
            },
            "required": ["action", "ref"]
        }
    },
    {
        "name": "kanban_case",
        "description": "Ticket-linked Case threads (board/_cases/): post QA verdicts, discoveries, discussions, bugs, or decisions linked to 1..100 tickets across projects/epics, reply with attachments, inspect/list Cases, or archive done >=180d Cases.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "reply", "show", "list", "archive"], "description": "Case action to perform"},
                "title": {"type": "string", "description": "Case title (min 3 chars, for action='create')"},
                "tickets": {"type": "array", "items": {"type": "string"}, "description": "1..100 linked ticket refs (for action='create')"},
                "body": {"type": "string", "description": "Markdown post/reply content"},
                "kind": {"type": "string", "enum": ["qa", "discovery", "discussion", "bug", "decision"], "description": "Case category (default: 'qa')"},
                "author": {"type": "string", "description": "Author name (e.g. 'kb-qa', agent id)"},
                "attachments": {"type": "array", "items": {"type": "string"}, "description": "Optional file paths to copy into _cases/attachments/<cid>/"},
                "case_id": {"type": "string", "description": "Case ID (e.g. C001, for reply/show)"},
                "ticket": {"type": "string", "description": "Filter Cases by ticket ref (action='list')"},
                "project": {"type": "string", "description": "Filter Cases by project slug (action='list')"},
                "epic": {"type": "string", "description": "Filter Cases by epic slug (action='list')"},
                "page": {"type": "integer", "description": "1-based page number (default 1)"},
                "page_size": {"type": "integer", "description": "Page size (default 20, max 100)"},
                "max_done_days": {"type": "integer", "description": "Archive threshold in days (default 180)"},
                "dry_run": {"type": "boolean", "description": "Preview archive without moving files"},
                "force": {"type": "boolean", "description": "Bypass hourly throttle for archive"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "kanban_project",
        "description": "Project-level SemVer (V0.0.0, n-1 ticket accounting), disjoint pending-done cluster history, and living doc (kb-doc) Boss configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["version_history", "bump_version", "doc_config"],
                    "description": "Project action to execute"
                },
                "project": {"type": "string", "description": "Project slug"},
                "version": {"type": "string", "description": "Strictly increasing SemVer string (e.g. V1.0.0) for action='bump_version'"},
                "bumped_by": {"type": "string", "description": "Actor name recording the version bump (default: agent)"},
                "note": {"type": "string", "description": "Optional release note for version bump"},
                "run_doc": {"type": "boolean", "description": "Auto-queue kb-doc TELL run on bump when configured (default: true)", "default": True},
                "scope": {"type": "string", "enum": ["global", "project"], "description": "Config scope for action='doc_config'"},
                "config": {"type": "object", "description": "Optional Boss config fields to update for action='doc_config'"}
            },
            "required": ["action"]
        }
    }
]

RESOURCES = [
    {
        "uri": "ui://kanban/board",
        "name": "Kanban Board Interactive View",
        "description": "Interactive view-only web visualization of the Kanban board with live columns and ticket detail drawers.",
        "mimeType": "text/html"
    }
]


def tools_for_mode(mode: str) -> list[dict]:
    allowed = QA_TOOL_NAMES if mode == "qa" else WORK_TOOL_NAMES
    return [t for t in TOOLS if t["name"] in allowed]


def _pick_free_port(preferred: int = 7890, max_tries: int = 20) -> int:
    for port in range(preferred, preferred + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def send_response(response: dict):
    line = json.dumps(response) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def send_error(req_id: Any, code: int, message: str, data: Any = None):
    res = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": message
        }
    }
    if data:
        res["error"]["data"] = data
    send_response(res)


def send_tool_result(req_id: Any, text: str, is_error: bool = False, extra_result: Optional[dict] = None):
    result = {
        "content": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    if is_error:
        result["isError"] = True
    if extra_result:
        result.update(extra_result)

    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    })


def handle_tool_call(req_id: Any, name: str, args: dict, board: Path, mode: str = "work"):
    allowed = QA_TOOL_NAMES if mode == "qa" else WORK_TOOL_NAMES
    if name not in allowed:
        send_tool_result(
            req_id,
            f"PermissionError: Tool '{name}' is not available in MCP server mode '{mode}'. "
            "Worker agents must use '--mode work'; only the isolated kb-qa subagent may use '--mode qa'.",
            is_error=True,
        )
        return

    try:
        # Tool 1: kanban_board
        if name == "kanban_board":
            view = args.get("view", "overview").lower()
            project = args.get("project")
            epic = args.get("epic")
            status = args.get("status")

            if mode == "qa" and view == "init":
                send_tool_result(req_id, "PermissionError: 'init' is disabled in read-only QA mode.", is_error=True)
                return

            if view == "init":
                proj = project or "default"
                ep = epic or "core"
                kb.api_init(proj, ep, board)
                text = f"Initialized Kanban board and project '{proj}' with epic '{ep}' at {board / proj}."
                send_tool_result(req_id, text)
            elif view == "list":
                kb_crud.purge_expired_retired(board)
                kb_cases.archive_stale_cases(board)
                norm_status = kb.normalize_status(status) if status else None
                raw_tickets = kb.api_list(board, project, epic, norm_status)
                norm_tickets = []
                for t in raw_tickets:
                    parts = str(t.get("ref") or "").split("/")
                    owner_val = t.get("owner")
                    agent_str = owner_val.get("agent", "") if isinstance(owner_val, dict) else (owner_val or "")
                    norm_tickets.append({
                        **t,
                        "status": kb.normalize_status(str(t.get("status") or "backlog")),
                        "project": parts[0] if len(parts) >= 1 else "",
                        "epic": parts[1] if len(parts) >= 2 else "",
                        "agent": agent_str,
                    })
                paged = kb_crud.paginate_items(
                    norm_tickets,
                    page=int(args.get("page") or 1),
                    page_size=int(args.get("page_size") or 25),
                    status=norm_status,
                    project=project,
                    epic=epic,
                    q=args.get("q"),
                    include_retired=bool(args.get("include_retired", False)),
                )
                if mode != "qa" and project and (board / project).is_dir():
                    cfg = kb_doc_store.load_effective_config(board, project)
                    nudge = kb_version.evaluate_version_nudge(board, project, config=cfg)
                    if nudge:
                        paged["version_nudge"] = nudge
                send_tool_result(req_id, json.dumps(paged, indent=2))
            elif view == "lint":
                lint_res = kb.api_lint(board)
                errors = lint_res.get("errors", [])
                warnings = lint_res.get("warnings", [])
                if not errors and not warnings:
                    text = "Lint: OK (no errors or warnings)"
                else:
                    lines = []
                    if errors:
                        lines.append(f"ERRORS ({len(errors)}):")
                        for e in errors:
                            lines.append(f"  ✗ {e}")
                    if warnings:
                        lines.append(f"WARNINGS ({len(warnings)}):")
                        for w in warnings:
                            lines.append(f"  ⚠ {w}")
                    text = "\n".join(lines)
                send_tool_result(req_id, text, is_error=bool(errors))
            else:
                # Default: overview
                res = kb.api_overview(board, project, epic)
                if mode != "qa":
                    for p_entry in res.get("projects") or []:
                        p_slug = p_entry.get("slug")
                        if p_slug:
                            cfg = kb_doc_store.load_effective_config(board, p_slug)
                            nudge = kb_version.evaluate_version_nudge(board, p_slug, config=cfg)
                            if nudge:
                                p_entry["version_nudge"] = nudge
                text = json.dumps(res, indent=2)
                send_tool_result(req_id, text)

        # Tool 2: kanban_ticket
        elif name == "kanban_ticket":
            action = (args.get("action") or "").lower()
            ref = args.get("ref")
            project = args.get("project")
            epic = args.get("epic", "core")
            title = args.get("title")
            pattern = args.get("pattern", "agile")
            edit_fields = {
                k: args.get(k) for k in ("outcome", "scope", "plan", "prove", "body")
                if args.get(k) is not None
            }

            if mode == "qa" and action not in {"", "show"}:
                send_tool_result(req_id, "PermissionError: Only action='show' is permitted in QA mode.", is_error=True)
                return

            if action == "scaffold":
                dag_template = kb.api_scaffold_dag(pattern)
                send_tool_result(req_id, dag_template)
                return

            if not action:
                if mode == "qa":
                    action = "show"
                elif title and any(k in edit_fields for k in ("outcome", "scope", "prove", "body")):
                    send_tool_result(
                        req_id,
                        "Error: Ambiguous kanban_ticket call — both 'title' and edit fields were supplied without 'action'. "
                        "Specify action='create' or action='edit' explicitly.",
                        is_error=True,
                    )
                    return
                elif title:
                    action = "create"
                elif edit_fields:
                    action = "edit"
                else:
                    action = "show"

            if not ref:
                if project and action == "create":
                    ref = f"{project}/{epic}"
                else:
                    send_tool_result(req_id, "Error: Either 'ref' (e.g. web/auth/T001) or 'project' must be provided.", is_error=True)
                    return

            if action == "create":
                if not title:
                    send_tool_result(req_id, "Error: 'title' is required when creating a ticket.", is_error=True)
                    return
                plan_custom = args.get("plan")
                res = kb.api_create(ref, title, board, pattern=pattern, plan=plan_custom)
                text = f"Created ticket {res['ref']} in backlog [{res['path']}] with pattern '{pattern}'\n"
                text += "Use kanban_ticket(action='edit', ref=..., outcome=..., scope=..., plan=..., prove=...) before moving to build."
                send_tool_result(req_id, text)
            elif action == "edit":
                force_edit = bool(args.get("force", False))
                res = kb.api_ticket_edit(ref, board=board, force=force_edit, **edit_fields)
                send_tool_result(req_id, f"Updated ticket {res['ref']} (status: {res['status']}).")
            elif action == "retire":
                res = kb_crud.api_retire(
                    ref,
                    str(args.get("reason") or args.get("note") or ""),
                    board,
                    int(args.get("purge_after_days") or 120),
                )
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "restore":
                res = kb_crud.api_restore(ref, board, str(args.get("note") or "Restored to active backlog"))
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "rehome":
                res = kb_crud.api_rehome(ref, str(args.get("new_epic") or ""), board, args.get("new_project"))
                send_tool_result(req_id, json.dumps(res, indent=2))
            else:
                ticket = kb.api_show(ref, board)
                text = f"Ticket: {ticket['ref']}\nStatus: {ticket['status']}\nTitle: {ticket['title']}\n"
                text += f"Owner: {json.dumps(ticket['metadata'].get('owner'))}\n"
                text += f"Attachments: {json.dumps(ticket['metadata'].get('attachments'))}\n\n"
                text += "--- Frontmatter ---\n" + json.dumps(ticket["metadata"], indent=2) + "\n\n"
                text += "--- Body ---\n" + ticket["body"]
                send_tool_result(req_id, text)

        # Tool 3: kanban_move
        elif name == "kanban_move":
            ref = args["ref"]
            status = args["status"].lower()
            note = args.get("note", "")
            agent_id = args.get("agent_id")
            session_id = args.get("session_id")
            lease_minutes = args.get("lease_minutes", 60)
            force = args.get("force", False)
            reason = args.get("reason", "")
            workspace = args.get("workspace")

            if status == "done":
                send_tool_result(
                    req_id,
                    "Error: 'done' transition is strictly forbidden via kanban_move. "
                    "Only kb-qa can approve a ticket to done using kanban_qa(action='approve').",
                    is_error=True
                )
                return

            res = kb.api_move(
                ref,
                status,
                note,
                board,
                agent_id=agent_id,
                session_id=session_id,
                lease_minutes=lease_minutes,
                force=force,
                caller_is_qa=False,
                reason=reason,
                workspace=workspace,
            )
            text = f"Moved {res['ref']}: {res['from']} -> {res['to']}"
            if res.get("owner"):
                text += f"\nOwner: {res['owner'].get('agent')} (lease expires: {res['owner'].get('lease_expires')})"
            if res.get("note"):
                text += f"\nNote: {res['note']}"
            if res.get("qa_nonce_generated"):
                text += "\n[QA Session Nonce generated for verify state. Ready for kb-qa]."
            send_tool_result(req_id, text)

        # Tool 4: kanban_update
        elif name == "kanban_update":
            ref = args["ref"]
            checked_nodes = args.get("checked_nodes")
            node_proofs = args.get("node_proofs")
            skip_nodes = args.get("skip_nodes")
            skip_reason = args.get("skip_reason", "")
            uncheck_nodes = args.get("uncheck_nodes")
            files = args.get("files")
            notes = args.get("notes")
            attach_file = args.get("attach_file")
            attach_desc = args.get("attach_desc", "")
            detach_file = args.get("detach_file")

            results = []
            if attach_file:
                att_res = kb.api_attach(ref, attach_file, attach_desc, board)
                results.append(f"Attached {att_res['attached']} ({att_res['size']} bytes)")

            if detach_file:
                det_res = kb.api_detach(ref, detach_file, board)
                results.append(f"Detached {det_res['detached']}")

            if checked_nodes or skip_nodes or uncheck_nodes or files or notes or not (attach_file or detach_file):
                cp_res = kb.api_checkpoint(
                    ref,
                    checked_nodes=checked_nodes,
                    files=files,
                    notes=notes,
                    board=board,
                    node_proofs=node_proofs,
                    skip_nodes=skip_nodes,
                    skip_reason=skip_reason,
                    uncheck_nodes=uncheck_nodes,
                )
                results.append(f"Checkpoint saved for {cp_res['ref']}. Lease renewed.")
                if cp_res.get("files"):
                    results.append(f"Tracked Files: {', '.join(cp_res['files'])}")
                if cp_res.get("ready_nodes") is not None:
                    results.append(f"Ready Next Nodes: {', '.join(cp_res['ready_nodes']) or 'none (all done/blocked)'}")

            send_tool_result(req_id, "\n".join(results))

        # Tool 5: kanban_doc
        elif name == "kanban_doc":
            action = args["action"].lower()
            project = args["project"]
            epic = args.get("epic")
            doc_name = args.get("name")
            content = args.get("content", "")
            res = kb.api_doc(action, project, epic, doc_name, content, board)
            if action == "write":
                text = f"Document written: {res['path']} ({res['size']} bytes)"
            elif action == "list":
                text = json.dumps(res, indent=2)
            else:
                text = f"Document {res['path']}:\n\n{res['content']}"
            send_tool_result(req_id, text)

        # Tool 6: kanban_view
        elif name == "kanban_view":
            global _VIEWER_PORT
            open_browser = args.get("open_browser", True)
            tickets = kb.api_list(board)
            counts = {}
            for t in tickets:
                counts[t["status"]] = counts.get(t["status"], 0) + 1
            summary_parts = [f"{st}: {counts.get(st, 0)}" for st in ["backlog", "build", "verify", "done", "blocked"]]
            text = f"Kanban Board Overview ({len(tickets)} tickets):\n" + " | ".join(summary_parts) + "\n\n"
            text += "Interactive view-only UI rendered via resource ui://kanban/board."
            if open_browser:
                if _VIEWER_PORT is None:
                    port = _pick_free_port(7890)
                    kb_script = str(Path(__file__).parent.resolve() / "kb.py")
                    subprocess.Popen(
                        [sys.executable, kb_script, "--board", str(board), "serve", "--port", str(port)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        start_new_session=(os.name != "nt"),
                    )
                    _VIEWER_PORT = port
                    text += f"\nLaunched isolated local loopback viewer on http://127.0.0.1:{port}."
                else:
                    text += f"\nLocal loopback viewer already running on http://127.0.0.1:{_VIEWER_PORT}."
            send_tool_result(req_id, text, extra_result={"_meta": {"ui": {"resourceUri": "ui://kanban/board"}}})

        # Tool 7: kanban_qa (OTP-gated via auto-rotating qa_passkey)
        elif name == "kanban_qa":
            otp = str(args.get("qa_passkey") or "").strip()
            ok_otp, otp_err = kb_qa_otp.verify_passkey(otp)
            if not ok_otp:
                send_tool_result(req_id, otp_err, is_error=True)
                return
            if kb_qa_otp.contains_passkey_leak(str(args.get("note") or ""), otp):
                send_tool_result(req_id, "FORBIDDEN: qa_passkey must never be echoed in note.", is_error=True)
                return
            action = args["action"].lower()
            ref = args["ref"]
            workspace = args.get("workspace")
            ev_arg = args.get("evidence_path")
            if ev_arg:
                ev_candidate = Path(ev_arg)
                if not ev_candidate.is_absolute() and workspace:
                    ev_candidate = Path(workspace) / ev_candidate
                if ev_candidate.is_file() and kb_qa_otp.contains_passkey_leak(ev_candidate.read_text(encoding="utf-8", errors="ignore"), otp):
                    send_tool_result(req_id, "FORBIDDEN: qa_passkey must never be echoed in evidence report.", is_error=True)
                    return
            if action == "start":
                res = kb.api_qa_start(ref, board)
                text = json.dumps(res, indent=2)
                send_tool_result(req_id, text)
            elif action == "approve":
                qa_nonce = args.get("qa_nonce")
                evidence_path = ev_arg
                note = args.get("note")
                if not qa_nonce or not evidence_path or not note:
                    send_tool_result(req_id, "Error: action='approve' requires 'qa_nonce', 'evidence_path', and 'note'.", is_error=True)
                    return
                res = kb.api_qa_approve(
                    ref,
                    qa_nonce,
                    evidence_path,
                    note,
                    board,
                    workspace=workspace,
                )
                sig_note = f"\nHMAC Signature: {res['qa_signature'][:16]}..." if res.get("qa_signature") else ""
                text = (
                    f"SUCCESS: {res['ref']} verified and transitioned {res['from']} -> {res['to']} [CERTIFIED BY QA]\n"
                    f"Evidence: {res['evidence']}{sig_note}\n"
                    f"Acceptance summary: {res['note']}"
                )
                send_tool_result(req_id, text)
            elif action == "reject":
                qa_nonce = args.get("qa_nonce")
                note = args.get("note")
                evidence_path = ev_arg
                if not qa_nonce or not note:
                    send_tool_result(req_id, "Error: action='reject' requires 'qa_nonce' and 'note'.", is_error=True)
                    return
                res = kb.api_qa_reject(ref, qa_nonce, note, board, evidence_path=evidence_path)
                text = f"REJECTED: {res['ref']} returned {res['from']} -> {res['to']}\nReason: {res['note']}"
                send_tool_result(req_id, text)
            else:
                send_tool_result(req_id, f"Unknown kanban_qa action: {action}. Must be 'start', 'approve', or 'reject'.", is_error=True)

        # Tool 8: kanban_case
        elif name == "kanban_case":
            action = (args.get("action") or "").strip().lower()
            if action == "create":
                res = kb_cases.api_case_create(
                    title=str(args.get("title") or ""),
                    tickets=list(args.get("tickets") or []),
                    body=str(args.get("body") or ""),
                    board=board,
                    kind=str(args.get("kind") or "qa"),
                    author=str(args.get("author") or "agent"),
                    attachments=args.get("attachments"),
                )
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "reply":
                res = kb_cases.api_case_reply(
                    case_id=str(args.get("case_id") or ""),
                    author=str(args.get("author") or "agent"),
                    body=str(args.get("body") or ""),
                    board=board,
                    attachments=args.get("attachments"),
                )
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "show":
                res = kb_cases.api_case_show(str(args.get("case_id") or ""), board)
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "list":
                res = kb_cases.api_case_list(
                    board,
                    ticket=args.get("ticket"),
                    project=args.get("project"),
                    epic=args.get("epic"),
                    kind=args.get("kind"),
                    page=int(args.get("page") or 1),
                    page_size=int(args.get("page_size") or 20),
                )
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "archive":
                res = kb_cases.archive_stale_cases(
                    board,
                    max_done_days=int(args.get("max_done_days") or kb_cases.DEFAULT_ARCHIVE_DONE_DAYS),
                    dry_run=bool(args.get("dry_run", False)),
                    force=bool(args.get("force", False)),
                )
                send_tool_result(req_id, json.dumps(res, indent=2))
            else:
                send_tool_result(req_id, f"Unknown kanban_case action: {action}. Must be 'create', 'reply', 'show', 'list', or 'archive'.", is_error=True)

        # Tool 9: kanban_project
        elif name == "kanban_project":
            action = (args.get("action") or "").strip().lower()
            proj = str(args.get("project") or "").strip()
            if action == "version_history":
                if not proj:
                    send_tool_result(req_id, "Error: 'project' is required for action='version_history'.", is_error=True)
                    return
                cfg = kb_doc_store.load_effective_config(board, proj)
                res = kb_version.get_version_history(board, proj, config=cfg)
                if mode != "qa":
                    nudge = kb_version.evaluate_version_nudge(board, proj, config=cfg, record_nudge=False)
                    if nudge:
                        res["version_nudge"] = nudge
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "bump_version":
                ver = str(args.get("version") or "").strip()
                if not proj or not ver:
                    send_tool_result(req_id, "Error: 'project' and 'version' are required for action='bump_version'.", is_error=True)
                    return
                res = kb_version.bump_project_version(
                    board,
                    proj,
                    ver,
                    bumped_by=str(args.get("bumped_by") or "agent"),
                    note=str(args.get("note") or ""),
                )
                cfg = kb_doc_store.load_effective_config(board, proj)
                tell_queued = bool(args.get("run_doc", True) and cfg.get("auto_tell_on_bump", True))
                if tell_queued:
                    kb_doc_queue.start_background_worker(board, kb_doc_runner.run_queued_job)
                    res["job"] = kb_doc_queue.enqueue_job(
                        board,
                        project=proj,
                        mode="tell",
                        version=res["new_version"],
                        shipped_tickets=res["shipped_tickets"],
                        reason="mcp_version_bump",
                    )
                res["tell_queued"] = tell_queued
                send_tool_result(req_id, json.dumps(res, indent=2))
            elif action == "doc_config":
                patch = args.get("config")
                scope = str(args.get("scope") or ("project" if proj else "global")).strip().lower()
                if isinstance(patch, dict):
                    if scope == "project" and proj:
                        kb_doc_store.save_project_config(board, proj, patch)
                    else:
                        kb_doc_store.save_global_config(board, patch)
                out = {
                    "ok": True,
                    "global": kb_doc_store.load_global_config(board),
                    "effective": kb_doc_store.load_effective_config(board, proj or None),
                    "runs": kb_doc_store.list_runs(board, proj) if proj else [],
                }
                send_tool_result(req_id, json.dumps(out, indent=2))
            else:
                send_tool_result(req_id, f"Unknown kanban_project action: {action}. Must be 'version_history', 'bump_version', or 'doc_config'.", is_error=True)

        else:
            send_tool_result(req_id, f"Unknown tool: {name}", is_error=True)

    except Exception as e:
        send_tool_result(req_id, f"Error executing {name}: {str(e)}", is_error=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kanban MCP Server")
    parser.add_argument("--board-root", default=None, help="Explicit path to board/ directory")
    parser.add_argument(
        "--mode",
        choices=["work", "qa"],
        default="work",
        help="Server capability mode: 'work' (default, excludes kanban_qa) or 'qa' (kb-qa subagent only)",
    )
    args, unknown = parser.parse_known_args()

    board = Path(args.board_root).resolve() if args.board_root else kb.board_root()
    mode = args.mode
    server_name = f"{SERVER_NAME}-qa" if mode == "qa" else SERVER_NAME

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error: invalid JSON")
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": server_name,
                        "version": SERVER_VERSION
                    },
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False}
                    }
                }
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tools_for_mode(mode)
                }
            })

        elif method == "resources/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": RESOURCES if mode == "work" else []
                }
            })

        elif method == "resources/read":
            uri = params.get("uri")
            if uri == "ui://kanban/board":
                try:
                    import viewer
                    html = viewer.get_html_page(board)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "contents": [
                                {
                                    "uri": "ui://kanban/board",
                                    "mimeType": "text/html",
                                    "text": html
                                }
                            ]
                        }
                    })
                except Exception as e:
                    send_error(req_id, -32603, f"Failed to read board UI: {str(e)}")
            else:
                send_error(req_id, -32602, f"Resource not found: {uri}")

        elif method == "tools/call":
            name = params.get("name")
            tool_args = params.get("arguments", {})
            handle_tool_call(req_id, name, tool_args, board, mode=mode)

        elif method == "ping":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            })

        else:
            if req_id is not None:
                send_error(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
