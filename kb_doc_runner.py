#!/usr/bin/env python3
"""kb_doc_runner.py — Sterilized Antigravity (agy) & Codex CLI runner for kb-doc.

Mirrors memberBerries's exact CLI sterilization (crates/memb/src/curate.rs,
crates/memb-curator/src/backend.rs, crates/memb/src/config.rs):
  - Empty `cwd` at `<board>/_doc_sandbox` (no repo files contaminate the session).
  - `KANBAN_INTERNAL=1` in child env.
  - For `agy`: empty `USERPROFILE` & `HOME` at `<board>/_doc_home` so user plugins,
    MCP servers, rules, and skills never leak in (saved sign-in stays outside);
    prompt piped via `stdin` as `{"event": "user", "message": {"content": prompt}}\n`.
  - For `codex`: `--ignore-user-config --ignore-rules -s read-only --ephemeral
    --skip-git-repo-check -c project_doc_max_bytes=0` + full `--disable ...` list;
    raw UTF-8 prompt piped via `stdin`.
  - Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) on win32 so child
    processes die cleanly on timeout/exit.
  - Read-only CLI: Python passes a structured context bundle on `stdin` and validates
    + writes the returned JSON section CRUD ops via `kb_doc_store`.
  - Automatic fallback from primary backend to fallback backend on failure/timeout.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import kb_doc_store
import kb_version

CODEX_DISABLED_FEATURES = (
    "apps",
    "plugins",
    "hooks",
    "goals",
    "multi_agent",
    "in_app_browser",
    "browser_use",
    "computer_use",
    "tool_suggest",
    "skill_search",
    "skill_mcp_dependency_install",
    "view_image",
    "sleep_tool",
    "remote_plugin",
    "plugin_sharing",
    "memories",
)


def build_cli_invocation(
    backend: str,
    model: str,
    timeout_seconds: int,
    board: Path,
    prompt: str,
    reasoning_effort: str = "medium",
) -> dict[str, Any]:
    """Construct exact sterilized argv, env, cwd, and stdin_bytes for `agy` or `codex`."""
    b = backend.strip().lower()
    sandbox_dir = board / "_doc_sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["KANBAN_INTERNAL"] = "1"

    if b == "agy":
        home_dir = board / "_doc_home"
        home_dir.mkdir(parents=True, exist_ok=True)
        env["USERPROFILE"] = str(home_dir)
        env["HOME"] = str(home_dir)
        argv = [
            "agy",
            "--model",
            model,
            "--disable-slash-commands",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--print-timeout",
            f"{int(timeout_seconds)}s",
        ]
        stdin_bytes = (json.dumps({"event": "user", "message": {"content": prompt}}, ensure_ascii=False) + "\n").encode("utf-8")
        return {"backend": "agy", "argv": argv, "env": env, "cwd": str(sandbox_dir), "stdin_bytes": stdin_bytes}

    if b == "codex":
        argv = [
            "codex",
            "exec",
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={reasoning_effort}",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "-c",
            "project_doc_max_bytes=0",
        ]
        for feat in CODEX_DISABLED_FEATURES:
            argv.extend(["--disable", feat])
        stdin_bytes = prompt.encode("utf-8")
        return {"backend": "codex", "argv": argv, "env": env, "cwd": str(sandbox_dir), "stdin_bytes": stdin_bytes}

    raise ValueError(f"Unsupported kb-doc backend: {backend}")


def _attach_windows_kill_job(proc: subprocess.Popen) -> Optional[int]:
    """Bind a child process to a Windows KillOnClose Job Object so timeouts kill the whole tree."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        kernel32.AssignProcessToJobObject(job, int(proc._handle))
        return job
    except Exception:
        return None


def _close_windows_job(job: Optional[int]) -> None:
    if job and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(job)
        except Exception:
            pass


def _extract_agy_stream_text(stdout: str) -> str:
    """Extract assistant text from Antigravity `--output-format stream-json` NDJSON."""
    result_chunks: list[str] = []
    assistant_chunks: list[str] = []
    delta_chunks: list[str] = []
    plain_chunks: list[str] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            plain_chunks.append(line)
            continue
        if isinstance(ev, dict):
            ev_name = str(ev.get("event") or ev.get("type") or "").lower()
            msg = ev.get("message")
            txt = ""
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                txt = msg["content"]
            elif isinstance(ev.get("content"), str):
                txt = ev["content"]
            elif isinstance(ev.get("text"), str):
                txt = ev["text"]
            if not txt:
                continue
            if ev_name == "result":
                result_chunks.append(txt)
            elif ev_name in ("assistant", "message", ""):
                assistant_chunks.append(txt)
            else:
                delta_chunks.append(txt)
    if result_chunks:
        return result_chunks[-1].strip()
    if assistant_chunks:
        return "\n".join(assistant_chunks).strip()
    if delta_chunks:
        return "".join(delta_chunks).strip()
    if plain_chunks:
        return "\n".join(plain_chunks).strip()
    return (stdout or "").strip()


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object from CLI stdout (tolerates ```json fences)."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty response from kb-doc CLI.")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("kb-doc response must be a JSON object.")
    return obj


def _default_subprocess_executor(inv: dict[str, Any], timeout_seconds: int) -> tuple[int, str, str]:
    argv = list(inv["argv"])
    resolved = shutil.which(argv[0])
    if resolved:
        argv[0] = resolved
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=inv["cwd"],
        env=inv["env"],
        shell=False,
    )
    job = _attach_windows_kill_job(proc)
    try:
        out_b, err_b = proc.communicate(input=inv["stdin_bytes"], timeout=timeout_seconds + 15)
        return proc.returncode, out_b.decode("utf-8", errors="replace"), err_b.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return 124, "", f"Timed out after {timeout_seconds}s"
    finally:
        _close_windows_job(job)


def _run_with_fallback(
    board: Path,
    cfg: dict[str, Any],
    prompt: str,
    executor: Optional[Callable[[dict[str, Any], int], tuple[int, str, str]]] = None,
) -> tuple[dict[str, Any], str, bool]:
    """Execute sterilized primary backend; on error/timeout/invalid JSON, retry once on fallback."""
    exec_fn = executor or _default_subprocess_executor
    timeout = int(cfg.get("timeout_seconds", 150))
    attempts = [
        (cfg["primary_backend"], cfg["primary_model"], False),
        (cfg["fallback_backend"], cfg["fallback_model"], True),
    ]
    last_err = "unknown error"
    for backend, model, is_fallback in attempts:
        inv = build_cli_invocation(
            backend=backend,
            model=model,
            timeout_seconds=timeout,
            board=board,
            prompt=prompt,
            reasoning_effort=str(cfg.get("fallback_reasoning_effort", "medium")),
        )
        try:
            rc, stdout, stderr = exec_fn(inv, timeout)
            if rc != 0:
                last_err = f"{backend} exited {rc}: {stderr[:300]}"
                continue
            raw_text = _extract_agy_stream_text(stdout) if backend == "agy" else stdout
            parsed = extract_json_object(raw_text)
            return parsed, backend, is_fallback
        except FileNotFoundError as exc:
            last_err = f"{backend} binary not found: {exc}"
        except Exception as exc:
            last_err = f"{backend} failed: {exc}"
    raise RuntimeError(f"Both kb-doc backends failed. Last error: {last_err}")


def build_tell_prompt(
    board: Path,
    project: str,
    version: str,
    shipped_tickets: list[str],
) -> str:
    """Build a self-contained read-only context bundle for kb-doc TELL mode."""
    manifest = kb_doc_store.load_manifest(board, project)
    open_fb = kb_doc_store.list_feedback(board, project, status="open")
    done_tickets = {t["ref"]: t for t in kb_version.scan_project_done_tickets(board, project)}
    ticket_summaries = [
        {
            "ref": ref,
            "epic": done_tickets[ref]["epic"],
            "title": done_tickets[ref]["title"],
            "files": done_tickets[ref]["files"],
            "cases": done_tickets[ref]["cases"],
        }
        for ref in shipped_tickets
        if ref in done_tickets
    ]
    bundle = {
        "mode": "TELL",
        "project": project,
        "version": version,
        "shipped_tickets": ticket_summaries,
        "current_manifest": manifest,
        "open_boss_feedback": open_fb,
    }
    return (
        "You are kb-doc running in TELL mode for a containerized living documentation site.\n"
        "Update ONLY the sections affected by this version bump (and address open Boss feedback).\n"
        "Return STRICT JSON ONLY with schema:\n"
        '{"upsert_sections": [{"slug": "kebab-case", "title": "...", "summary": "...", '
        '"order": 0, "source_tickets": ["proj/epic/T001"], "tell_html": "<article>...</article>"}], '
        '"delete_sections": ["old-slug"], '
        '"resolve_feedback": [{"id": "fb-xxxx", "resolution_note": "..."}], '
        '"overrides_css": null}\n'
        "Rules: tell_html is a pure HTML fragment (no <script> tags, no inline event handlers). "
        "Be deeply technical for engineers, vary layout per section, and never repeat identical templates.\n\n"
        f"CONTEXT_BUNDLE:\n{json.dumps(bundle, indent=2, ensure_ascii=False)}\n"
    )


def build_show_prompt(board: Path, project: str, slug: str) -> str:
    """Build a read-only context bundle for on-demand Boss SHOW generation (480x270 2D retro Canvas)."""
    sec = kb_doc_store.read_section(board, project, slug)
    open_fb = [
        fb for fb in kb_doc_store.list_feedback(board, project, status="open")
        if fb.get("section") in (slug, "global")
    ]
    bundle = {
        "mode": "SHOW",
        "project": project,
        "slug": slug,
        "meta": sec["meta"],
        "tell_html": sec["tell_html"],
        "open_boss_feedback": open_fb,
    }
    return (
        "You are kb-doc running in SHOW mode (Boss on-demand).\n"
        "Generate an interactive 2D Retro Widescreen Cinema (480x270) JavaScript module using "
        "window.CinemaEngine (integer-snapped flat sprites, 4x4 Bayer dithering, passive annotated "
        "animation loop by default + physical scrubbers ONLY where manipulation teaches, concrete "
        "real-world metaphors or mini-UI instead of abstract orbs).\n"
        "Return STRICT JSON ONLY with schema:\n"
        '{"show_js": "export function mountShow(container, engine, meta) { ... }", '
        '"resolve_feedback": [{"id": "fb-xxxx", "resolution_note": "..."}]}\n\n'
        f"CONTEXT_BUNDLE:\n{json.dumps(bundle, indent=2, ensure_ascii=False)}\n"
    )


def run_tell_update(
    board: Path,
    project: str,
    version: str,
    shipped_tickets: list[str],
    executor: Optional[Callable[[dict[str, Any], int], tuple[int, str, str]]] = None,
) -> dict[str, Any]:
    """Run sterilized kb-doc TELL update and apply validated CRUD ops atomically."""
    cfg = kb_doc_store.load_effective_config(board, project)
    kb_doc_store.purge_expired_feedback(board, project, retention_days=int(cfg.get("feedback_retention_days", 120)))
    run_id = "run-" + uuid.uuid4().hex[:8]
    t0 = time.monotonic()
    prompt = build_tell_prompt(board, project, version, shipped_tickets)

    try:
        payload, backend_used, fallback_used = _run_with_fallback(board, cfg, prompt, executor=executor)
        upserted: list[str] = []
        for sec in payload.get("upsert_sections") or []:
            meta = kb_doc_store.upsert_section(
                board,
                project,
                sec["slug"],
                title=sec.get("title", sec["slug"]),
                summary=sec.get("summary", ""),
                tell_html=sec.get("tell_html", ""),
                version=version,
                source_tickets=sec.get("source_tickets", shipped_tickets),
                order=sec.get("order"),
            )
            upserted.append(meta["slug"])

        deleted: list[str] = []
        for slug in payload.get("delete_sections") or []:
            if kb_doc_store.delete_section(board, project, slug):
                deleted.append(slug)

        resolved_fb: list[str] = []
        for fb in payload.get("resolve_feedback") or []:
            if isinstance(fb, dict) and fb.get("id"):
                res = kb_doc_store.resolve_feedback(
                    board, project, str(fb["id"]), version, str(fb.get("resolution_note", ""))
                )
                if res:
                    resolved_fb.append(res["id"])

        if isinstance(payload.get("overrides_css"), str) and payload["overrides_css"].strip():
            kb_doc_store.write_overrides_css(board, project, payload["overrides_css"])

        dur_ms = int((time.monotonic() - t0) * 1000)
        rec = {
            "run_id": run_id,
            "mode": "tell",
            "project": project,
            "version": version,
            "backend_used": backend_used,
            "fallback_used": fallback_used,
            "status": "ok",
            "upserted": upserted,
            "deleted": deleted,
            "resolved_feedback": resolved_fb,
            "duration_ms": dur_ms,
        }
        kb_doc_store.append_run_log(board, project, rec)
        return {"ok": True, **rec}
    except Exception as exc:
        dur_ms = int((time.monotonic() - t0) * 1000)
        rec = {
            "run_id": run_id,
            "mode": "tell",
            "project": project,
            "version": version,
            "status": "error",
            "error": str(exc),
            "duration_ms": dur_ms,
        }
        kb_doc_store.append_run_log(board, project, rec)
        return {"ok": False, **rec}


def run_show_generate(
    board: Path,
    project: str,
    slug: str,
    executor: Optional[Callable[[dict[str, Any], int], tuple[int, str, str]]] = None,
) -> dict[str, Any]:
    """Run on-demand Boss SHOW generation for a single section."""
    cfg = kb_doc_store.load_effective_config(board, project)
    sec = kb_doc_store.read_section(board, project, slug)
    version = sec["meta"].get("tell_version") or kb_version.load_version_state(board, project)["version"]
    run_id = "run-" + uuid.uuid4().hex[:8]
    t0 = time.monotonic()
    prompt = build_show_prompt(board, project, slug)

    try:
        payload, backend_used, fallback_used = _run_with_fallback(board, cfg, prompt, executor=executor)
        show_js = str(payload.get("show_js") or "").strip()
        if not show_js:
            raise ValueError("kb-doc returned empty show_js.")
        kb_doc_store.upsert_section(
            board,
            project,
            slug,
            title=sec["meta"]["title"],
            summary=sec["meta"].get("summary", ""),
            show_js=show_js,
            version=version,
        )
        resolved_fb: list[str] = []
        for fb in payload.get("resolve_feedback") or []:
            if isinstance(fb, dict) and fb.get("id"):
                res = kb_doc_store.resolve_feedback(
                    board, project, str(fb["id"]), version, str(fb.get("resolution_note", ""))
                )
                if res:
                    resolved_fb.append(res["id"])
        dur_ms = int((time.monotonic() - t0) * 1000)
        rec = {
            "run_id": run_id,
            "mode": "show",
            "project": project,
            "section": slug,
            "version": version,
            "backend_used": backend_used,
            "fallback_used": fallback_used,
            "status": "ok",
            "resolved_feedback": resolved_fb,
            "duration_ms": dur_ms,
        }
        kb_doc_store.append_run_log(board, project, rec)
        return {"ok": True, **rec}
    except Exception as exc:
        dur_ms = int((time.monotonic() - t0) * 1000)
        rec = {
            "run_id": run_id,
            "mode": "show",
            "project": project,
            "section": slug,
            "version": version,
            "status": "error",
            "error": str(exc),
            "duration_ms": dur_ms,
        }
        kb_doc_store.append_run_log(board, project, rec)
        return {"ok": False, **rec}
