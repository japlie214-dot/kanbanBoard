#!/usr/bin/env python3
"""Git pre-commit hook: blocks commits if any 'done' ticket on the central Kanban board lacks a valid HMAC qa_signature."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

KANBAN_ROOT = Path(os.environ.get("KANBAN_REPO_ROOT", Path(__file__).parent.parent.resolve()))
KB_PY = KANBAN_ROOT / "kb.py"


def main() -> int:
    if not KB_PY.is_file():
        print(f"pre-commit: kb.py not found at {KB_PY}, skipping.", file=sys.stderr)
        return 0
    proc = subprocess.run([sys.executable, str(KB_PY), "verify-done", "--strict"])
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
