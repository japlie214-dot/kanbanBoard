#!/usr/bin/env python3
"""package.py — Build standard POSIX-compliant .plugin archives for KanbanBoard.

Outputs exclusively .plugin archives to dist/ (zero .zip files).
Bundles universal assets for both Antigravity and Claude Code environments,
including the comprehensive technical documentation wiki.
"""
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST_DIR = ROOT / "dist"

CORE_FILES = [
    "plugin.json",
    "mcp_config.json",
    ".mcp.json",
    "hooks.json",
    "hooks/guard.py",
    "hooks/hooks.json",
    "scripts/install_qa_lock.py",
    "scripts/pre_commit_verify_done.py",
    "README.md",
    "CLAUDE.md",
    "assets/logo.svg",
    "rules/AGENTS.md",
    "skills/kanban/SKILL.md",
    "skills/kanban-qa/SKILL.md",
    ".claude-plugin/plugin.json",
    "commands/kanban-init.md",
    "commands/kanban-move.md",
    "commands/kanban-new.md",
    "commands/kanban-qa.md",
    "commands/kanban-status.md",
    "agents/kb-qa.md",
    "kb.py",
    "kb_ergonomics.py",
    "mcp_server.py",
    "viewer.py",
    "apps/Board.bat",
    "resources/board.html",
    "tests/test_kanban.py",
    "tests/test_qa_lock.py",
    "tests/test_qa_e2e_isolation.py",
    "tests/test_v24_upgrades.py",
]

def collect_all_files():
    """Collect core files plus all wiki technical docs and templates."""
    files = list(CORE_FILES)
    
    # Include all wiki markdown files
    wiki_dir = ROOT / "wiki"
    if wiki_dir.exists():
        for p in sorted(wiki_dir.glob("*.md")):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in files:
                files.append(rel)
                
    # Include resources if any
    res_dir = ROOT / "resources"
    if res_dir.exists():
        for p in sorted(res_dir.glob("*")):
            if p.is_file():
                rel = p.relative_to(ROOT).as_posix()
                if rel not in files:
                    files.append(rel)

    return sorted(files)

def clean_zip_archives():
    """Delete any stray .zip files in root or dist directory."""
    for z in ROOT.glob("*.zip"):
        print(f"Removing stray zip: {z}")
        z.unlink()
    if DIST_DIR.exists():
        for z in DIST_DIR.glob("*.zip"):
            print(f"Removing stray zip from dist: {z}")
            z.unlink()

def make_plugin_archive(dest_path: Path, files_to_include):
    """Build a standard POSIX-compliant .plugin archive (zip container)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dest_path.exists():
            dest_path.unlink()
    except OSError:
        pass

    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_str in files_to_include:
            file_path = ROOT / rel_str
            if not file_path.exists():
                print(f"  [SKIP] Missing: {rel_str}")
                continue

            # Ensure pure POSIX path with forward slashes only
            arcname = rel_str.replace("\\", "/")

            data = file_path.read_bytes()
            zinfo = zipfile.ZipInfo(arcname)
            zinfo.create_system = 3  # Unix
            # 0o755 for scripts/executables, 0o644 for regular files
            if arcname.endswith(".py") or arcname.endswith(".bat"):
                zinfo.external_attr = 0o755 << 16
            else:
                zinfo.external_attr = 0o644 << 16
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zinfo, data)
            print(f"  + {arcname}")

    print(f"--> Built: {dest_path.name} ({dest_path.stat().st_size:,} bytes)")

def main():
    print("=" * 60)
    print("KanbanBoard Universal Package Builder")
    print("=" * 60)
    
    clean_zip_archives()
    
    files = collect_all_files()
    print(f"Collected {len(files)} files to bundle.")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # Output kanbanBoard.plugin only
    make_plugin_archive(DIST_DIR / "kanbanBoard.plugin", files)
    
    print("\nPackage build complete. Only .plugin archives generated in dist/.")

if __name__ == "__main__":
    main()
