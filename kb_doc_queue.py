#!/usr/bin/env python3
"""kb_doc_queue.py — Global single-worker persistent FIFO queue for kb-doc.

Guarantees:
  - Strictly 1 kb-doc subprocess runs at a time globally across all projects.
  - Persistent queue at `board/_doc_queue.jsonl` survives viewer/server restarts.
  - Coalesces duplicate queued TELL jobs for the same project (latest version + union tickets).
  - Smart rate-limit / usage-limit handling: when both primary and fallback fail due to
    transient rate/quota errors, marks job `deferred` with exponential backoff (2m -> 10m -> 30m)
    instead of losing queued work.
  - Supports manual `retry_job_now()` from Boss Web App.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|quota|usage[\s_-]*limit|too many requests|overloaded|capacity|temporarily unavailable)",
    re.I,
)
BACKOFF_SECONDS = (120, 600, 1800)  # 2m, 10m, 30m
MAX_RETRIES = 3

_GLOBAL_LOCK = threading.Lock()
_WORKER_THREAD: Optional[threading.Thread] = None
_WORKER_BOARD: Optional[Path] = None
_WORKER_STOP = threading.Event()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def queue_path(board: Path) -> Path:
    return board / "_doc_queue.jsonl"


def is_rate_limit_error(err: str) -> bool:
    return bool(RATE_LIMIT_RE.search(err or ""))


def _load_jobs(board: Path) -> list[dict[str, Any]]:
    p = queue_path(board)
    if not p.is_file():
        return []
    jobs: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("id"):
                jobs.append(obj)
        except json.JSONDecodeError:
            continue
    return jobs


def _save_jobs(board: Path, jobs: list[dict[str, Any]]) -> None:
    p = queue_path(board)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Keep last 200 completed/failed records + all active/deferred jobs
    active = [j for j in jobs if j.get("status") in ("queued", "running", "deferred")]
    done = [j for j in jobs if j.get("status") not in ("queued", "running", "deferred")][-200:]
    merged = done + active
    tmp = p.with_name(p.name + ".tmp")
    text = ("\n".join(json.dumps(j, ensure_ascii=False) for j in merged) + "\n") if merged else ""
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(p)


def recover_interrupted_jobs(board: Path) -> int:
    """On startup, reset any crashed `running` jobs back to `queued` so no work is lost."""
    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
        recovered = 0
        for j in jobs:
            if j.get("status") == "running":
                j["status"] = "queued"
                j["updated_at"] = _iso()
                recovered += 1
        if recovered:
            _save_jobs(board, jobs)
        return recovered


def enqueue_job(
    board: Path,
    *,
    project: str,
    mode: str,
    version: str = "V0.0.0",
    shipped_tickets: Optional[list[str]] = None,
    slug: Optional[str] = None,
    reason: str = "",
) -> dict[str, Any]:
    """Persistently enqueue a TELL or SHOW job; coalesces duplicate queued TELL jobs per project."""
    proj = (project or "").strip()
    if not proj or ".." in proj or "/" in proj or "\\" in proj or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", proj):
        raise ValueError(f"Invalid project slug '{project}'.")
    project = proj
    m = mode.strip().lower()
    if m not in ("tell", "show"):
        raise ValueError(f"Invalid kb-doc job mode: {mode}")
    if m == "show" and not slug:
        raise ValueError("SHOW job requires a section slug.")

    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
        now_s = _iso()

        # Coalesce duplicate queued TELL jobs for the same project
        if m == "tell":
            for j in jobs:
                if j.get("project") == project and j.get("mode") == "tell" and j.get("status") == "queued":
                    merged_tickets = list(dict.fromkeys((j.get("shipped_tickets") or []) + (shipped_tickets or [])))
                    j["version"] = version or j.get("version", "V0.0.0")
                    j["shipped_tickets"] = merged_tickets
                    j["updated_at"] = now_s
                    j["coalesced"] = int(j.get("coalesced", 0)) + 1
                    _save_jobs(board, jobs)
                    return j

        # Deduplicate identical queued SHOW job for same project+slug
        if m == "show":
            for j in jobs:
                if j.get("project") == project and j.get("mode") == "show" and j.get("slug") == slug and j.get("status") in ("queued", "running"):
                    return j

        job = {
            "id": "job-" + uuid.uuid4().hex[:8],
            "project": project,
            "mode": m,
            "version": version,
            "shipped_tickets": list(shipped_tickets or []),
            "slug": slug,
            "reason": reason,
            "status": "queued",
            "retries": 0,
            "next_retry_at": None,
            "last_error": None,
            "created_at": now_s,
            "updated_at": now_s,
        }
        jobs.append(job)
        _save_jobs(board, jobs)
        return job


def retry_job_now(board: Path, job_id: str) -> Optional[dict[str, Any]]:
    """Reset a deferred or failed job back to `queued` immediately."""
    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
        for j in jobs:
            if j.get("id") == job_id and j.get("status") in ("deferred", "failed"):
                j["status"] = "queued"
                j["next_retry_at"] = None
                j["updated_at"] = _iso()
                _save_jobs(board, jobs)
                return j
    return None


def get_queue_status(board: Path, project: Optional[str] = None) -> dict[str, Any]:
    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
    if project:
        jobs = [j for j in jobs if j.get("project") == project]
    running = [j for j in jobs if j.get("status") == "running"]
    queued = [j for j in jobs if j.get("status") == "queued"]
    deferred = [j for j in jobs if j.get("status") == "deferred"]
    recent = list(reversed(jobs[-20:]))
    return {
        "ok": True,
        "running": running,
        "queued_count": len(queued),
        "deferred_count": len(deferred),
        "busy": bool(running),
        "jobs": recent,
    }


def process_next_job(
    board: Path,
    runner_fn: Callable[[Path, dict[str, Any]], dict[str, Any]],
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Pop and execute at most ONE ready job globally. Returns updated job or None if idle."""
    ref_now = now or _now()
    chosen_id: Optional[str] = None
    chosen_copy: Optional[dict[str, Any]] = None

    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
        # Strict global single-worker invariant: if any job is already running, do nothing
        if any(j.get("status") == "running" for j in jobs):
            return None
        for j in jobs:
            st = j.get("status")
            if st == "queued":
                chosen_id = j["id"]
                j["status"] = "running"
                j["updated_at"] = _iso(ref_now)
                chosen_copy = dict(j)
                break
            if st == "deferred":
                nra = _parse_iso(j.get("next_retry_at"))
                if nra is None or nra <= ref_now:
                    chosen_id = j["id"]
                    j["status"] = "running"
                    j["updated_at"] = _iso(ref_now)
                    chosen_copy = dict(j)
                    break
        if chosen_id is None:
            return None
        _save_jobs(board, jobs)

    # Execute outside global lock so enqueue/status reads never block
    try:
        res = runner_fn(board, chosen_copy)
        ok = bool(res.get("ok"))
        err = str(res.get("error") or "")
    except Exception as exc:
        res = {"ok": False, "error": str(exc)}
        ok = False
        err = str(exc)

    fin_now = now or _now()
    with _GLOBAL_LOCK:
        jobs = _load_jobs(board)
        updated: Optional[dict[str, Any]] = None
        for j in jobs:
            if j.get("id") != chosen_id:
                continue
            j["updated_at"] = _iso(fin_now)
            if ok:
                j["status"] = "done"
                j["last_error"] = None
                j["result"] = {k: res.get(k) for k in ("run_id", "backend_used", "fallback_used", "duration_ms") if k in res}
            else:
                j["last_error"] = err[:400]
                retries = int(j.get("retries", 0))
                if is_rate_limit_error(err) and retries < MAX_RETRIES:
                    delay = BACKOFF_SECONDS[min(retries, len(BACKOFF_SECONDS) - 1)]
                    j["retries"] = retries + 1
                    j["status"] = "deferred"
                    j["next_retry_at"] = _iso(fin_now + timedelta(seconds=delay))
                else:
                    j["status"] = "failed"
            updated = dict(j)
            break
        _save_jobs(board, jobs)
        return updated


def stop_background_worker(timeout: float = 2.0) -> None:
    """Signal the singleton background queue worker thread to stop and wait briefly."""
    global _WORKER_THREAD, _WORKER_BOARD
    _WORKER_STOP.set()
    t = _WORKER_THREAD
    if t is not None and t.is_alive():
        t.join(timeout=timeout)
    _WORKER_THREAD = None
    _WORKER_BOARD = None


def start_background_worker(
    board: Path,
    runner_fn: Callable[[Path, dict[str, Any]], dict[str, Any]],
    poll_seconds: float = 2.0,
) -> None:
    """Start the singleton background queue worker thread for `board` (restarts if board changed)."""
    global _WORKER_THREAD, _WORKER_BOARD
    resolved = board.resolve()
    if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
        if _WORKER_BOARD == resolved:
            return
        stop_background_worker()
    recover_interrupted_jobs(board)
    _WORKER_STOP.clear()
    _WORKER_BOARD = resolved

    def _loop() -> None:
        while not _WORKER_STOP.is_set():
            try:
                ran = process_next_job(board, runner_fn)
                if ran is None:
                    _WORKER_STOP.wait(poll_seconds)
            except Exception:
                _WORKER_STOP.wait(poll_seconds)

    _WORKER_THREAD = threading.Thread(target=_loop, name="kb-doc-queue-worker", daemon=True)
    _WORKER_THREAD.start()
