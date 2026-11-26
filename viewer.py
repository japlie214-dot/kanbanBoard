"""viewer.py – Scalable loopback HTTP server for the Kanban board web UI (v2.5).

Exposes:
  - GET /                 -> Serves Jira-inspired board.html with ephemeral CSRF token
  - GET /favicon.svg      -> Serves Concept B SVG logo for browser tab favicon
  - GET /assets/logo.svg  -> Serves Concept B SVG logo
  - GET /assets/board.css -> Serves external stylesheet (strict CSP, zero unsafe-inline)
  - GET /assets/board.js  -> Serves external script (strict CSP, zero unsafe-inline)
  - GET /api/board        -> Board JSON (?summary=1 strips heavy bodies/docs for 10x scale)
  - GET /api/ticket?ref=  -> On-demand full ticket detail (body, dag_nodes, execution_log, docs)
  - GET /events           -> Server-Sent Events stream for live board updates
  - GET /health           -> Health check {"ok": true, "mode": "viewer+human-approve", "version": "2.6.0"}
  - POST /api/ticket/manual-approve -> Human-only approval gated by CSRF, Origin, and native OS dialog
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).parent.resolve()))
import kb
import kb_crud

HOST = "127.0.0.1"
DEFAULT_PORT = 7890
REPO_ROOT = Path(__file__).parent.resolve()

CSP = (
    "default-src 'none'; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def confirm_human_approval_os(ref: str, approver: str, reason: str) -> bool:
    """Require a physical human click on a native OS modal dialog before moving a ticket to done."""
    if os.environ.get("KANBAN_TEST_AUTO_CONFIRM") == "1":
        return True

    prompt = (
        f"Approve Kanban ticket to DONE?\n\n"
        f"Ticket: {ref}\n"
        f"Approver: {approver}\n"
        f"Reason: {reason}\n\n"
        f"Click YES only if YOU slid to approve from the Kanban web app."
    )
    if sys.platform == "win32":
        import ctypes
        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_DEFBUTTON2 = 0x00000100
        MB_TOPMOST = 0x00040000
        MB_SETFOREGROUND = 0x00010000
        IDYES = 6
        res = ctypes.windll.user32.MessageBoxW(
            0,
            prompt,
            "Kanban Board — Confirm Human Approval",
            MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2 | MB_TOPMOST | MB_SETFOREGROUND,
        )
        return res == IDYES

    if sys.platform == "darwin":
        safe = prompt.replace('"', '\\"')
        script = f'display dialog "{safe}" buttons {{"No", "Yes"}} default button "No"'
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        return proc.returncode == 0 and "button returned:Yes" in proc.stdout

    try:
        proc = subprocess.run(
            ["zenity", "--question", "--title=Kanban Board — Confirm Human Approval", f"--text={prompt}"],
            capture_output=True,
            timeout=60,
        )
        return proc.returncode == 0
    except Exception:
        return False


def get_html_page(csrf_token: str) -> str:
    html_file = REPO_ROOT / "resources" / "board.html"
    if not html_file.exists():
        return "<html><body><h1>resources/board.html missing</h1></body></html>"
    template = html_file.read_text(encoding="utf-8")
    return template.replace("__CSRF_TOKEN__", csrf_token, 1)


def board_stamp(board: Path) -> str:
    """Hash timestamps and sizes of board markdown files for fast change detection."""
    entries = []
    if board.exists():
        for root, dirs, files in os.walk(board):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in sorted(files):
                if f.endswith(".md"):
                    p = Path(root) / f
                    try:
                        st = p.stat()
                        entries.append((f, st.st_mtime_ns, st.st_size))
                    except OSError:
                        pass
    return hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()


def _extract_owner_name(owner: Any) -> str:
    if isinstance(owner, str):
        return owner.strip()
    if isinstance(owner, dict):
        for key in ("agent", "agent_id", "owner", "name", "id"):
            val = owner.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _normalize_tickets(raw_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Flatten kb.api_board_payload into normalized summary rows + full detail lookup by ref."""
    board_obj = raw_payload.get("board") if isinstance(raw_payload.get("board"), dict) else raw_payload
    projects = board_obj.get("projects") if isinstance(board_obj, dict) else []
    summaries: list[dict[str, Any]] = []
    details_by_ref: dict[str, dict[str, Any]] = {}

    if isinstance(projects, list):
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pslug = str(proj.get("slug") or proj.get("name") or "").strip()
            pdoc = proj.get("doc") or proj.get("charter") or ""
            epics_map: dict[str, str] = {}
            for ep in proj.get("epics") or []:
                if isinstance(ep, dict):
                    eslug = str(ep.get("slug") or ep.get("name") or "").strip()
                    if eslug:
                        epics_map[eslug] = str(ep.get("doc") or ep.get("spec") or "")

            # Support both proj["tickets"] and proj["epics"][i]["tickets"]
            proj_tickets = list(proj.get("tickets") or [])
            for ep in proj.get("epics") or []:
                if isinstance(ep, dict) and isinstance(ep.get("tickets"), list):
                    eslug = str(ep.get("slug") or ep.get("name") or "").strip()
                    for t in ep["tickets"]:
                        if isinstance(t, dict):
                            tc = dict(t)
                            tc.setdefault("epic", eslug)
                            proj_tickets.append(tc)

            for t in proj_tickets:
                if not isinstance(t, dict):
                    continue
                ref = str(t.get("reference") or t.get("ref") or "").strip()
                if not ref:
                    continue
                eslug = str(t.get("epic") or "").strip()
                dag_nodes = t.get("dag_nodes") if isinstance(t.get("dag_nodes"), list) else (t.get("nodes") if isinstance(t.get("nodes"), list) else [])
                done_cnt = sum(1 for n in dag_nodes if isinstance(n, dict) and (n.get("checked") or n.get("status") == "done"))
                total_cnt = len(dag_nodes)
                owner_name = _extract_owner_name(t.get("owner") or t.get("agent"))
                lease_status = str(t.get("lease_status") or "").strip()
                lease_expired = "expired" in lease_status.lower()

                tpath_str = t.get("path")
                retired = bool(t.get("retired"))
                retired_at = t.get("retired_at")
                retire_reason = t.get("retire_reason") or ""
                purge_days = None
                if tpath_str and Path(tpath_str).is_file() and not retired:
                    try:
                        fmeta, _ = kb_crud.split_frontmatter(Path(tpath_str).read_text(encoding="utf-8"))
                        if fmeta.get("retired"):
                            retired = True
                            retired_at = fmeta.get("retired_at")
                            retire_reason = str(fmeta.get("retire_reason") or "")
                            purge_days = kb_crud.days_until_purge(fmeta)
                    except Exception:
                        pass
                elif retired:
                    purge_days = kb_crud.days_until_purge({"retired": True, "retired_at": retired_at, "purge_after_days": t.get("purge_after_days", 120)})

                summary = {
                    "ref": ref,
                    "retired": retired,
                    "retired_at": retired_at,
                    "retire_reason": retire_reason,
                    "days_until_purge": purge_days,
                    "reference": ref,
                    "id": str(t.get("id") or ref.split("/")[-1]),
                    "project": pslug or ref.split("/")[0],
                    "epic": eslug,
                    "status": str(t.get("status") or "backlog"),
                    "title": str(t.get("title") or ""),
                    "agent": owner_name,
                    "lease_status": lease_status,
                    "lease_expired": lease_expired,
                    "is_rejected": bool(t.get("is_rejected")),
                    "since": str(t.get("since") or ""),
                    "todo_done": done_cnt,
                    "todo_total": total_cnt,
                    "depends": t.get("depends") or [],
                }
                summaries.append(summary)
                details_by_ref[ref] = {
                    **summary,
                    "note": str(t.get("note") or ""),
                    "qa_rejection": t.get("qa_rejection"),
                    "owner": t.get("owner"),
                    "files": t.get("files") or [],
                    "attachments": t.get("attachments") or [],
                    "body": str(t.get("body") or ""),
                    "dag_nodes": dag_nodes,
                    "ready_nodes": t.get("ready_nodes") or [],
                    "execution_log": t.get("execution_log") or [],
                    "project_doc": str(pdoc or ""),
                    "epic_doc": epics_map.get(eslug, ""),
                }

    return summaries, details_by_ref


class BoardCache:
    """Thread-safe stamp-keyed cache so thousands of tickets aren't re-parsed on every HTTP request."""

    def __init__(self, board: Path):
        self.board = board
        self._lock = threading.Lock()
        self._stamp: str | None = None
        self._raw: dict[str, Any] = {}
        self._summaries: list[dict[str, Any]] = []
        self._details: dict[str, dict[str, Any]] = {}

    def _refresh_locked(self, stamp: str):
        kb_crud.purge_expired_retired(self.board)
        raw = kb.api_board_payload(self.board)
        summaries, details = _normalize_tickets(raw)
        self._stamp = stamp
        self._raw = raw
        self._summaries = summaries
        self._details = details

    def get_summary_payload(self) -> dict[str, Any]:
        stamp = board_stamp(self.board)
        with self._lock:
            if stamp != self._stamp:
                self._refresh_locked(stamp)
            return {
                "ok": True,
                "stamp": self._stamp,
                "board_dir": str(self.board),
                "total": len(self._summaries),
                "tickets": self._summaries,
            }

    def get_full_payload(self) -> dict[str, Any]:
        stamp = board_stamp(self.board)
        with self._lock:
            if stamp != self._stamp:
                self._refresh_locked(stamp)
            return self._raw

    def get_ticket(self, ref: str) -> dict[str, Any] | None:
        stamp = board_stamp(self.board)
        with self._lock:
            if stamp != self._stamp:
                self._refresh_locked(stamp)
            return self._details.get(ref)

    def invalidate(self):
        with self._lock:
            self._stamp = None


class KanbanHandler(BaseHTTPRequestHandler):
    server_version = "KanbanViewer/2.6"
    sys_version = ""
    timeout = 15

    def log_message(self, fmt, *args):
        if getattr(self.server, "verbose", False):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _headers(self, code: int, size: int, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()

    def _send(self, code: int, body: bytes, ctype: str, head: bool = False):
        self._headers(code, len(body), ctype)
        if not head:
            self.wfile.write(body)

    def _json(self, code: int, obj: dict, head: bool = False):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8", head)

    def _serve_file(self, path: Path, ctype: str, head: bool = False):
        if not path.is_file():
            return self._json(404, {"error": "asset not found"}, head)
        self._send(200, path.read_bytes(), ctype, head)

    def do_GET(self):
        self._handle(head=False)

    def do_HEAD(self):
        self._handle(head=True)

    def _deny(self):
        self._json(405, {"error": "method not allowed: only GET, HEAD and /api/ticket/manual-approve are allowed"}, False)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _deny

    def do_POST(self):
        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            return self._json(403, {"ok": False, "error": "forbidden: loopback access only"}, False)

        path = urlsplit(self.path).path
        board = self.server.board

        if path == "/api/ticket/manual-approve":
            ctype = (self.headers.get("Content-Type") or "").lower()
            if not ctype.startswith("application/json"):
                return self._json(415, {"ok": False, "error": "Content-Type must be application/json"}, False)

            port = self.server.server_address[1]
            origin = (self.headers.get("Origin") or "").strip()
            allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
            if origin not in allowed_origins:
                return self._json(403, {"ok": False, "error": "forbidden: invalid Origin header"}, False)

            token = (self.headers.get("X-Kanban-CSRF") or "").strip()
            if not token or not hmac.compare_digest(token, self.server.csrf_token):
                return self._json(403, {"ok": False, "error": "forbidden: invalid or missing CSRF token"}, False)

            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 32768:
                    return self._json(400, {"ok": False, "error": "invalid request body size"}, False)
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
            except Exception as e:
                return self._json(400, {"ok": False, "error": f"invalid json payload: {e}"}, False)

            ref = str(payload.get("ref") or "").strip()
            approver = str(payload.get("approver") or "").strip()
            reason = str(payload.get("reason") or "").strip()

            if not ref:
                return self._json(400, {"ok": False, "error": "missing 'ref' parameter"}, False)
            if len(approver) < 2:
                return self._json(400, {"ok": False, "error": "approver name is required (min 2 characters)"}, False)
            if len(reason) < 10:
                return self._json(400, {"ok": False, "error": "approval reason is required (min 10 characters)"}, False)

            if not confirm_human_approval_os(ref, approver, reason):
                return self._json(403, {"ok": False, "error": "approval cancelled or denied at OS confirmation dialog"}, False)

            try:
                res = kb.api_manual_approve(ref, approver, reason, board)
                self.server.cache.invalidate()
                return self._json(200, res, False)
            except (ValueError, FileNotFoundError, PermissionError) as e:
                return self._json(400, {"ok": False, "error": str(e)}, False)
            except Exception as e:
                return self._json(500, {"ok": False, "error": f"server error: {e}"}, False)

        if path in ("/api/ticket/retire", "/api/ticket/restore"):
            ctype = (self.headers.get("Content-Type") or "").lower()
            if not ctype.startswith("application/json"):
                return self._json(415, {"ok": False, "error": "Content-Type must be application/json"}, False)
            port = self.server.server_address[1]
            origin = (self.headers.get("Origin") or "").strip()
            if origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                return self._json(403, {"ok": False, "error": "forbidden: invalid Origin header"}, False)
            token = (self.headers.get("X-Kanban-CSRF") or "").strip()
            if not token or not hmac.compare_digest(token, self.server.csrf_token):
                return self._json(403, {"ok": False, "error": "forbidden: invalid or missing CSRF token"}, False)
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                ref = str(payload.get("ref") or "").strip()
                if path == "/api/ticket/retire":
                    reason = str(payload.get("reason") or "").strip()
                    res = kb_crud.api_retire(ref, reason, board)
                else:
                    res = kb_crud.api_restore(ref, board)
                self.server.cache.invalidate()
                return self._json(200, res, False)
            except (ValueError, FileNotFoundError, PermissionError) as e:
                return self._json(400, {"ok": False, "error": str(e)}, False)
            except Exception as e:
                return self._json(500, {"ok": False, "error": f"server error: {e}"}, False)

        return self._deny()

    def _handle(self, head: bool):
        parsed = urlsplit(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            html = get_html_page(self.server.csrf_token)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", head)

        if path in ("/favicon.svg", "/assets/logo.svg"):
            return self._serve_file(REPO_ROOT / "assets" / "logo.svg", "image/svg+xml", head)

        if path == "/assets/board.css":
            return self._serve_file(REPO_ROOT / "resources" / "board.css", "text/css; charset=utf-8", head)

        if path == "/assets/board.js":
            return self._serve_file(REPO_ROOT / "resources" / "board.js", "application/javascript; charset=utf-8", head)

        if path in ("/health", "/api/health"):
            return self._json(
                200,
                {
                    "ok": True,
                    "mode": "viewer+human-approve",
                    "version": "2.6.0",
                    "port": self.server.server_address[1],
                },
                head,
            )

        if path == "/api/board":
            if qs.get("summary", ["0"])[0] in ("1", "true"):
                return self._json(200, self.server.cache.get_summary_payload(), head)
            return self._json(200, self.server.cache.get_full_payload(), head)

        if path == "/api/ticket":
            ref = (qs.get("ref") or [""])[0].strip()
            if not ref:
                return self._json(400, {"ok": False, "error": "missing ref query parameter"}, head)
            detail = self.server.cache.get_ticket(ref)
            if detail is None:
                return self._json(404, {"ok": False, "error": f"ticket not found: {ref}"}, head)
            return self._json(200, {"ok": True, "ticket": detail}, head)

        if path in ("/events", "/api/events"):
            return self._events(head)

        return self._json(404, {"error": "not found"}, head)

    def _events(self, head: bool):
        if head:
            return self._send(200, b"", "text/event-stream; charset=utf-8", True)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.end_headers()

            previous = None
            board = self.server.board
            while not self.server.closing.is_set():
                stamp = board_stamp(board)
                data = f"data: {stamp}\n\n" if stamp != previous else ": keepalive\n\n"
                self.wfile.write(data.encode("ascii"))
                self.wfile.flush()
                previous = stamp
                if self.server.closing.wait(1.5):
                    break
        except OSError:
            pass


class KanbanServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, board: Path, port: int = DEFAULT_PORT, verbose: bool = False):
        self.board = board
        self.verbose = verbose
        self.closing = threading.Event()
        self.csrf_token = secrets.token_hex(24)
        self.cache = BoardCache(board)
        super().__init__((HOST, port), KanbanHandler)

    def server_close(self):
        self.closing.set()
        try:
            self.shutdown()
        except Exception:
            pass
        super().server_close()


def find_available_server(board: Path, preferred_port: int = DEFAULT_PORT, max_attempts: int = 10, verbose: bool = False) -> tuple[KanbanServer, int]:
    for offset in range(max_attempts):
        port = preferred_port + offset
        try:
            server = KanbanServer(board, port, verbose)
            return server, port
        except OSError:
            if offset == max_attempts - 1:
                raise OSError(f"Unable to bind Kanban server to any port in range {preferred_port}-{preferred_port + max_attempts - 1}")
            continue
    raise OSError("No port available")


def run_server(board: Path, port: int = DEFAULT_PORT, open_browser: bool = True, verbose: bool = False):
    server, bound_port = find_available_server(board, port, verbose=verbose)
    url = f"http://{HOST}:{bound_port}"
    print(f"Kanban Board Viewer v2.6 running at: {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Kanban Board HTTP Server v2.5")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default 7890)")
    parser.add_argument("--board-root", default=None, help="Explicit path to board/ directory")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    board_path = Path(args.board_root).resolve() if args.board_root else kb.board_root()
    board_path.mkdir(parents=True, exist_ok=True)
    run_server(board_path, port=args.port, open_browser=not args.no_browser)
