"""kb_qa_otp.py – Prompt-Injected `qa_passkey` + Auto-Rotating Single-Use OTP for `kb-qa` (v2.7).

Works identically across Antigravity (agy) and Claude Code Desktop:
  - Generates a 144-bit random `qa_passkey` stored in `~/.kanban/.qa_passkey` (restricted permissions).
  - Injects `QA_PASSKEY: <key>` into installed `kb-qa.md` agent files (`~/.claude/agents/kb-qa.md`
    and `~/.gemini/config/agents/kb-qa.md`). `hooks/guard.py` blocks all agents from reading
    `kb-qa.md` or `.qa_passkey`, so ONLY the host-spawned `kb-qa` subagent has the key in its system prompt.
  - Verifies `qa_passkey` in constant time (`hmac.compare_digest`) on every `kanban_qa` call.
  - Auto-rotates `.qa_passkey` and re-injects the new key into installed `kb-qa.md` files immediately
    after every successful `approve` or `reject`, making each OTP single-use.
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import stat
import string
import subprocess
import sys
from pathlib import Path

PASSKEY_LINE_RE = re.compile(r"^(QA_PASSKEY:\s*)([^\s]+)\s*$", re.M)
PASSKEY_ALPHABET = string.ascii_letters + string.digits
PASSKEY_LENGTH = 8


def passkey_file() -> Path:
    env = os.environ.get("KANBAN_QA_PASSKEY_FILE", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".kanban" / ".qa_passkey"


def default_agent_targets() -> list[Path]:
    env = os.environ.get("KANBAN_QA_AGENT_TARGETS", "").strip()
    if env:
        return [Path(p.strip()) for p in env.split(os.pathsep) if p.strip()]
    return [
        Path.home() / ".claude" / "agents" / "kb-qa.md",
        Path.home() / ".gemini" / "config" / "agents" / "kb-qa.md",
    ]


def generate_passkey() -> str:
    return "".join(secrets.choice(PASSKEY_ALPHABET) for _ in range(PASSKEY_LENGTH))


def _restrict_file_permissions(path: Path):
    try:
        if sys.platform == "win32":
            user = os.environ.get("USERNAME", "")
            if user:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
                    capture_output=True,
                    timeout=10,
                )
        else:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def load_passkey() -> str | None:
    p = passkey_file()
    if not p.is_file():
        return None
    val = p.read_text(encoding="utf-8").strip()
    return val or None


def write_passkey(key: str) -> Path:
    p = passkey_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(key + "\n", encoding="utf-8", newline="\n")
    tmp.replace(p)
    _restrict_file_permissions(p)
    return p


def inject_passkey_into_agent_file(agent_md: Path, key: str) -> bool:
    """Replace `QA_PASSKEY: <old>` in an installed `kb-qa.md` file atomically."""
    if not agent_md.is_file():
        return False
    text = agent_md.read_text(encoding="utf-8")
    if PASSKEY_LINE_RE.search(text):
        new_text = PASSKEY_LINE_RE.sub(rf"\g<1>{key}", text, count=1)
    elif "__QA_PASSKEY__" in text:
        new_text = text.replace("__QA_PASSKEY__", key)
    else:
        new_text = text.rstrip() + f"\n\n## QA Capability OTP (Confidential — Never Echo)\nQA_PASSKEY: {key}\n"
    tmp = agent_md.with_suffix(".md.tmp")
    tmp.write_text(new_text, encoding="utf-8", newline="\n")
    tmp.replace(agent_md)
    _restrict_file_permissions(agent_md)
    return True


def ensure_and_inject_passkey(agent_targets: list[Path] | None = None, force_rotate: bool = False) -> tuple[str, list[str]]:
    """Ensure a passkey exists (or rotate if requested) and inject it into all installed kb-qa.md files."""
    key = None if force_rotate else load_passkey()
    if not key:
        key = generate_passkey()
        write_passkey(key)

    updated: list[str] = []
    for target in (agent_targets if agent_targets is not None else default_agent_targets()):
        if inject_passkey_into_agent_file(target, key):
            updated.append(str(target))
    return key, updated


def rotate_passkey(agent_targets: list[Path] | None = None) -> tuple[str, list[str]]:
    """Rotate `.qa_passkey` and update all installed `kb-qa.md` files (single-use OTP)."""
    return ensure_and_inject_passkey(agent_targets=agent_targets, force_rotate=True)


def verify_passkey(provided: str | None) -> tuple[bool, str]:
    """Constant-time verification of `qa_passkey`."""
    expected = load_passkey()
    if not expected:
        return False, (
            "FORBIDDEN: QA passkey is not initialized. Run `python scripts/install_qa_lock.py` "
            "to generate ~/.kanban/.qa_passkey and inject it into kb-qa.md."
        )
    cand = str(provided or "").strip()
    if not cand:
        return False, "FORBIDDEN: missing 'qa_passkey'. Only the kb-qa subagent holds the QA capability OTP."
    if not hmac.compare_digest(cand, expected):
        return False, "FORBIDDEN: invalid or already-rotated 'qa_passkey'. Spawn a fresh kb-qa subagent."
    return True, ""


def contains_passkey_leak(text: str | None, passkey: str | None = None) -> bool:
    """Return True if the secret passkey appears inside a note or evidence file."""
    key = passkey or load_passkey()
    if not key or not text:
        return False
    return key in text
