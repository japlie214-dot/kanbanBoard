#!/usr/bin/env python3
"""mcp_server.py — Zero-dependency native Model Context Protocol (MCP) server for kanban-board.

Streamlined 7-Tool Harmonized Arsenal:
  1. kanban_board   - Discovery, listing, and board health linting (view="overview"|"list"|"lint")
  2. kanban_ticket  - Create or inspect tickets (create if title given, show if title omitted)
  3. kanban_move    - Status transitions with atomic claim, 60m lease, force takeover, & Anti-Laziness Gates
  4. kanban_update  - In-flight progress: check Todo Tree nodes, declare files, log notes, attach/detach files
  5. kanban_doc     - Read or write project/epic architectural documentation (docs: [])
  6. kanban_view    - Launch/render interactive view-only web dashboard widget
  7. kanban_qa      - Restricted 3-tier QA protocol for kb-qa (action="start"|"approve")
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Add project root to path to import kb
sys.path.insert(0, str(Path(__file__).parent.resolve()))
import kb

SERVER_NAME = "kanban"
SERVER_VERSION = "2.0.0"

TOOLS = [
    {
        "name": "kanban_board",
        "description": "Unified board discovery, ticket listing, and structural health linting in one tool. Use view='overview' (default) for charters, epics, docs, active tickets & owners; view='list' for compact ticket lists; view='lint' for integrity checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "view": {
                    "type": "string",
                    "enum": ["overview", "list", "lint"],
                    "description": "View mode: 'overview' (default), 'list', or 'lint'",
                    "default": "overview"
                },
                "project": {"type": "string", "description": "Optional project slug filter"},
                "epic": {"type": "string", "description": "Optional epic slug filter"},
                "status": {"type": "string", "description": "Optional status filter (backlog, in-progress, verify, done, blocked)"}
            }
        }
    },
    {
        "name": "kanban_ticket",
        "description": "Create or inspect tickets. If 'title' is provided, creates a new ticket in backlog with standard template sections and Todo Tree DAG. If 'title' is omitted, shows ticket metadata, frontmatter, attachments, and body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Ticket reference (e.g. web/auth/T001)"},
                "title": {"type": "string", "description": "Optional title. If provided, creates ticket; if omitted, shows ticket details."}
            },
            "required": ["ref"]
        }
    },
    {
        "name": "kanban_move",
        "description": "Move a ticket between backlog, in-progress, verify, and blocked. Moving to 'in-progress' atomically claims ownership with a 60-minute lease. Moving to 'verify' enforces the 5 Anti-Laziness Gates (Git modifications, unbroken DAG path, Prove command). NOTE: 'done' is strictly forbidden here (only kb-qa approves to done via kanban_qa).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Ticket ref (e.g. web/auth/T001)"},
                "status": {
                    "type": "string",
                    "enum": ["backlog", "in-progress", "verify", "blocked"],
                    "description": "Target status. NOTE: 'done' is forbidden via this tool."
                },
                "note": {"type": "string", "description": "Note (required when moving to blocked)"},
                "agent_id": {"type": "string", "description": "Agent identifier claiming ticket on in-progress"},
                "session_id": {"type": "string", "description": "Optional session/conversation ID"},
                "lease_minutes": {"type": "integer", "description": "Lease duration in minutes (default: 60)"},
                "force": {"type": "boolean", "description": "Force takeover if ticket is held by another agent"},
                "reason": {"type": "string", "description": "Reason for forceful takeover"}
            },
            "required": ["ref", "status"]
        }
    },
    {
        "name": "kanban_update",
        "description": "Update in-flight progress on an active ticket: check off Todo Tree DAG nodes, declare modified files, log progress/handover notes (renews lease), and attach or detach files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Ticket ref (e.g. web/auth/T001)"},
                "checked_nodes": {"type": "array", "items": {"type": "string"}, "description": "Node labels or text to check off in Todo Tree (- [x])"},
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
        "description": "Read or write project/epic architectural documentation and charters (docs: []).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write"], "description": "Action to perform"},
                "project": {"type": "string", "description": "Project slug"},
                "epic": {"type": "string", "description": "Optional epic slug"},
                "name": {"type": "string", "description": "Document slug/filename (without .md)"},
                "content": {"type": "string", "description": "Document content (required for action='write')"}
            },
            "required": ["action", "project", "name"]
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
                    "description": "If true, also launches the local loopback browser viewer on localhost:7890+",
                    "default": True
                }
            }
        }
    },
    {
        "name": "kanban_qa",
        "description": "RESTRICTED: Exclusively for kb-qa subagent to execute the 3-tier QA protocol. 'start' initiates the session and returns ticket spec + secret qa_nonce. 'approve' validates substantive evidence (Diff, Positive Tests, Negative Discriminator Tests) and certifies ticket to 'done'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["start", "approve"], "description": "QA action to perform"},
                "ref": {"type": "string", "description": "Ticket ref in 'verify' state"},
                "qa_nonce": {"type": "string", "description": "Ephemeral cryptographic nonce (required for action='approve')"},
                "evidence_path": {"type": "string", "description": "Path to QA evidence markdown report (required for action='approve')"},
                "note": {"type": "string", "description": "Acceptance certification summary note (required for action='approve')"}
            },
            "required": ["action", "ref"]
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


def handle_tool_call(req_id: Any, name: str, args: dict, board: Path):
    try:
        # Tool 1: kanban_board
        if name == "kanban_board":
            view = args.get("view", "overview").lower()
            project = args.get("project")
            epic = args.get("epic")
            status = args.get("status")

            if view == "list":
                tickets = kb.api_list(board, project, epic, status)
                text = json.dumps(tickets, indent=2)
                send_tool_result(req_id, text)
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
                text = json.dumps(res, indent=2)
                send_tool_result(req_id, text)

        # Tool 2: kanban_ticket
        elif name == "kanban_ticket":
            ref = args["ref"]
            title = args.get("title")
            if title:
                # Create ticket
                res = kb.api_create(ref, title, board)
                text = f"Created ticket {res['ref']} in backlog [{res['path']}]\n"
                text += "Fill in Outcome, Scope, Plan (Todo Tree), and Prove before moving to in-progress."
                send_tool_result(req_id, text)
            else:
                # Show ticket
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
                caller_is_qa=False
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

            if checked_nodes or files or notes or not (attach_file or detach_file):
                cp_res = kb.api_checkpoint(ref, checked_nodes, files, notes, board)
                results.append(f"Checkpoint saved for {cp_res['ref']}. Lease renewed.")
                if cp_res.get("files"):
                    results.append(f"Tracked Files: {', '.join(cp_res['files'])}")

            send_tool_result(req_id, "\n".join(results))

        # Tool 5: kanban_doc
        elif name == "kanban_doc":
            action = args["action"].lower()
            project = args["project"]
            epic = args.get("epic")
            doc_name = args["name"]
            content = args.get("content", "")
            res = kb.api_doc(action, project, epic, doc_name, content, board)
            if action == "write":
                text = f"Document written: {res['path']} ({res['size']} bytes)"
            else:
                text = f"Document {res['path']}:\n\n{res['content']}"
            send_tool_result(req_id, text)

        # Tool 6: kanban_view
        elif name == "kanban_view":
            open_browser = args.get("open_browser", True)
            tickets = kb.api_list(board)
            counts = {}
            for t in tickets:
                counts[t["status"]] = counts.get(t["status"], 0) + 1
            summary_parts = [f"{st}: {counts.get(st, 0)}" for st in ["backlog", "in-progress", "verify", "done", "blocked"]]
            text = f"Kanban Board Overview ({len(tickets)} tickets):\n" + " | ".join(summary_parts) + "\n\n"
            text += "Interactive view-only UI rendered via resource ui://kanban/board."
            if open_browser:
                import viewer, threading
                threading.Thread(target=lambda: viewer.run_server(board, port=7890, open_browser=True), daemon=True).start()
                text += "\nLaunched local loopback viewer in browser (default port 7890)."
            send_tool_result(req_id, text, extra_result={"_meta": {"ui": {"resourceUri": "ui://kanban/board"}}})

        # Tool 7: kanban_qa
        elif name == "kanban_qa":
            action = args["action"].lower()
            ref = args["ref"]
            if action == "start":
                res = kb.api_qa_start(ref, board)
                text = json.dumps(res, indent=2)
                send_tool_result(req_id, text)
            elif action == "approve":
                qa_nonce = args.get("qa_nonce")
                evidence_path = args.get("evidence_path")
                note = args.get("note")
                if not qa_nonce or not evidence_path or not note:
                    send_tool_result(req_id, "Error: action='approve' requires 'qa_nonce', 'evidence_path', and 'note'.", is_error=True)
                    return
                res = kb.api_qa_approve(ref, qa_nonce, evidence_path, note, board)
                text = f"SUCCESS: {res['ref']} verified and transitioned {res['from']} -> {res['to']} [CERTIFIED BY QA]\nEvidence: {res['evidence']}\nAcceptance summary: {res['note']}"
                send_tool_result(req_id, text)
            else:
                send_tool_result(req_id, f"Unknown kanban_qa action: {action}. Must be 'start' or 'approve'.", is_error=True)

        else:
            send_tool_result(req_id, f"Unknown tool: {name}", is_error=True)

    except Exception as e:
        send_tool_result(req_id, f"Error executing {name}: {str(e)}", is_error=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kanban MCP Server")
    parser.add_argument("--board-root", default=None, help="Explicit path to board/ directory")
    args, unknown = parser.parse_known_args()

    board = Path(args.board_root).resolve() if args.board_root else kb.board_root()

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
                        "name": SERVER_NAME,
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
                    "tools": TOOLS
                }
            })

        elif method == "resources/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": RESOURCES
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
            handle_tool_call(req_id, name, tool_args, board)

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
