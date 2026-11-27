#!/usr/bin/env python3
"""kb_doc_export.py — Offline HTML export & formal TELL-only PDF export (Snowflake Docs × Wikipedia).

Strategy:
  - Builds a dedicated formal Print HTML document directly from raw `sections/<slug>/`
    fragments (Page 1 Cover + Wikipedia infobox, Page 2 Dedicated Table of Contents with
    `page-break-after: always`, Page 3+ formal Snowflake-style technical sections + crisp
    light-mode vector stack-diagram SVGs).
  - Converts to PDF via locally installed headless Edge (`msedge.exe`) or Chrome
    (`--headless --disable-gpu --no-pdf-header-footer --print-to-pdf=...`) with zero pip deps.
  - Falls back cleanly to returning print-ready HTML if no Chromium browser is available.
"""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import kb_doc_store
import kb_version


def _esc(s: Any) -> str:
    return html.escape(str(s or ""), quote=True)


def _find_chromium_binary() -> Optional[str]:
    candidates = [
        "msedge",
        "msedge.exe",
        "chrome",
        "chrome.exe",
        "chromium",
        "chromium-browser",
        "google-chrome",
    ]
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
    # Standard Windows install paths for Microsoft Edge / Chrome
    win_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for wp in win_paths:
        if os.path.isfile(wp):
            return wp
    return None


def _group_sections(manifest: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group manifest sections by `parent_section` preserving order."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for sec in manifest.get("sections") or []:
        parent = str(sec.get("parent_section") or "General").strip() or "General"
        if parent not in groups:
            groups[parent] = []
            order.append(parent)
        groups[parent].append(sec)
    return [(p, groups[p]) for p in order]


FORMAL_PRINT_CSS = """
@page {
  size: A4;
  margin: 20mm 18mm 20mm 18mm;
  @bottom-left { content: attr(data-doc-title); font-family: Georgia, serif; font-size: 9pt; color: #555; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font-family: ui-monospace, monospace; font-size: 8.5pt; color: #555; }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: #16181d;
  background: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
}
/* Page 1: Formal Cover + Wikipedia-style Metadata Infobox */
.cover-page {
  page-break-after: always;
  display: flex;
  flex-direction: column;
  min-height: 240mm;
  padding-top: 16mm;
}
.cover-kicker {
  font-family: ui-monospace, monospace;
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #1d4ed8;
  margin-bottom: 6mm;
}
.cover-title {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 28pt;
  font-weight: 700;
  margin: 0 0 4mm 0;
  border-bottom: 2px solid #16181d;
  padding-bottom: 4mm;
}
.cover-sub { font-size: 11.5pt; color: #475569; margin: 0 0 12mm 0; }
.wiki-infobox {
  width: 72%;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  border-collapse: collapse;
  font-size: 9.5pt;
  margin-bottom: 12mm;
}
.wiki-infobox th, .wiki-infobox td {
  padding: 6px 10px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}
.wiki-infobox th { width: 36%; color: #475569; font-weight: 600; background: #f1f5f9; }
/* Page 2: Dedicated Table of Contents */
.toc-page { page-break-after: always; }
.toc-title {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 18pt;
  border-bottom: 1.5px solid #16181d;
  padding-bottom: 4px;
  margin: 0 0 14px 0;
}
.toc-group { margin-bottom: 12px; }
.toc-group-head { font-weight: 700; font-size: 11pt; color: #0f172a; margin-bottom: 4px; }
.toc-list { list-style: none; margin: 0; padding-left: 16px; }
.toc-list li {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dotted #cbd5e1;
  padding: 3px 0;
  font-size: 10pt;
}
.toc-list a { color: #1d4ed8; text-decoration: none; }
.toc-ver { font-family: ui-monospace, monospace; font-size: 8.5pt; color: #64748b; }
/* Page 3+: Snowflake Docs × Wikipedia Formal Body */
.doc-section { margin-bottom: 14mm; }
.doc-crumb {
  font-size: 8.5pt;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 3px;
}
.doc-h2 {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 16pt;
  border-bottom: 1px solid #cbd5e1;
  padding-bottom: 3px;
  margin: 0 0 8px 0;
  page-break-after: avoid;
}
.doc-meta-strip {
  font-family: ui-monospace, monospace;
  font-size: 8.5pt;
  color: #475569;
  background: #f8fafc;
  border-left: 3px solid #2563eb;
  padding: 5px 10px;
  margin-bottom: 10px;
}
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9.5pt; break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
th { background: #f1f5f9; font-weight: 600; }
pre, code { font-family: ui-monospace, Consolas, monospace; font-size: 8.8pt; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 8px 10px; overflow-x: auto; break-inside: avoid; }
.sd-frame { border: 1px solid #cbd5e1; margin: 10px 0; break-inside: avoid; }
.sd-toolbar { display: none; }
.sd-svg { display: block; width: 100%; height: auto; }
"""


def build_formal_tell_print_html(board: Path, project: str, inline_css: bool = True) -> str:
    """Assemble a Snowflake Docs × Wikipedia formal TELL-only print HTML document."""
    manifest = kb_doc_store.load_manifest(board, project)
    vstate = kb_version.load_version_state(board, project)
    ver = manifest.get("version") or vstate.get("version") or "V0.0.0"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    grouped = _group_sections(manifest)

    toc_html_parts: list[str] = []
    body_html_parts: list[str] = []

    for g_idx, (parent, subs) in enumerate(grouped, start=1):
        toc_rows: list[str] = []
        for s_idx, item in enumerate(subs, start=1):
            num = f"{g_idx:02d}.{s_idx}"
            slug = item["slug"]
            try:
                sec = kb_doc_store.read_section(board, project, slug)
            except FileNotFoundError:
                continue
            meta = sec["meta"]
            tver = meta.get("tell_version") or ver
            tdate = (meta.get("tell_updated_at") or generated)[:10]
            tickets = ", ".join(meta.get("source_tickets") or []) or "—"
            toc_rows.append(
                f'<li><a href="#sec-{_esc(slug)}">{num} &nbsp; {_esc(meta.get("title") or slug)}</a>'
                f'<span class="toc-ver">{_esc(tver)}</span></li>'
            )
            diag_path = kb_doc_store.doc_root(board, project) / "sections" / slug / "diagram.html"
            diag_html = kb_doc_store.sanitize_tell_html(diag_path.read_text(encoding="utf-8")) if diag_path.is_file() else ""
            safe_tell = kb_doc_store.sanitize_tell_html(sec.get("tell_html") or "")
            body_html_parts.append(
                f'<section class="doc-section" id="sec-{_esc(slug)}">\n'
                f'  <div class="doc-crumb">{g_idx:02d} · {_esc(parent)} / {num}</div>\n'
                f'  <h2 class="doc-h2">{num} &nbsp; {_esc(meta.get("title") or slug)}</h2>\n'
                f'  <div class="doc-meta-strip">TELL {_esc(tver)} ({_esc(tdate)}) &nbsp;·&nbsp; Source tickets: {_esc(tickets)}</div>\n'
                f'  {diag_html}\n'
                f'  <div class="tell-body">{safe_tell}</div>\n'
                f'</section>'
            )
        toc_html_parts.append(
            f'<div class="toc-group">'
            f'<div class="toc-group-head">{g_idx:02d}. {_esc(parent)}</div>'
            f'<ul class="toc-list">{"".join(toc_rows)}</ul>'
            f'</div>'
        )

    sec_count = sum(len(s) for _, s in grouped)
    css_tag = (
        f"<style>{FORMAL_PRINT_CSS}</style>"
        if inline_css
        else '<link rel="stylesheet" href="/api/doc/export/print.css" />'
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"UTF-8\" />\n"
        f"<title>{_esc(project)} — Technical Documentation ({_esc(ver)})</title>\n"
        f"{css_tag}\n"
        "</head>\n"
        f"<body data-doc-title=\"{_esc(project)} ({_esc(ver)})\">\n"
        "<section class=\"cover-page\">\n"
        "  <div class=\"cover-kicker\">Technical Reference Documentation (TELL Export)</div>\n"
        f"  <h1 class=\"cover-title\">{_esc(project)}</h1>\n"
        f"  <p class=\"cover-sub\">Formal engineering specification generated from KanbanBoard living documentation at release <strong>{_esc(ver)}</strong>.</p>\n"
        "  <table class=\"wiki-infobox\">\n"
        f"    <tr><th>Project</th><td>{_esc(project)}</td></tr>\n"
        f"    <tr><th>Current Version</th><td>{_esc(ver)}</td></tr>\n"
        f"    <tr><th>Export Date</th><td>{_esc(generated)}</td></tr>\n"
        f"    <tr><th>Sections Covered</th><td>{sec_count}</td></tr>\n"
        f"    <tr><th>Releases Logged</th><td>{len(vstate.get('history') or [])}</td></tr>\n"
        "  </table>\n"
        "</section>\n"
        "<section class=\"toc-page\">\n"
        "  <h2 class=\"toc-title\">Table of Contents</h2>\n"
        f"  {''.join(toc_html_parts) or '<p>No TELL sections documented yet.</p>'}\n"
        "</section>\n"
        f"{''.join(body_html_parts)}\n"
        "</body>\n</html>\n"
    )


def export_tell_pdf(
    board: Path,
    project: str,
    out_path: Optional[Path] = None,
    browser_bin: Optional[str] = None,
) -> dict[str, Any]:
    """Export formal Snowflake×Wikipedia TELL-only PDF using headless Edge/Chrome."""
    print_html = build_formal_tell_print_html(board, project)
    browser = _find_chromium_binary() if browser_bin is None else browser_bin
    if not browser:
        return {
            "ok": False,
            "fallback": "print_html",
            "error": "No headless Edge/Chrome binary found. Open /api/doc/export/print-html and use browser Print -> Save as PDF.",
        }

    target_pdf = out_path or (kb_doc_store.doc_root(board, project) / f"{project}-tell.pdf")
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(print_html)
        tmp_html = Path(tf.name)

    try:
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={target_pdf}",
            tmp_html.as_uri(),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"ok": False, "fallback": "print_html", "error": str(exc)[:300]}
        if res.returncode != 0 or not target_pdf.is_file():
            return {"ok": False, "fallback": "print_html", "error": (res.stderr or "PDF render failed")[:300]}
        return {"ok": True, "pdf_path": str(target_pdf), "size": target_pdf.stat().st_size, "browser": browser}
    finally:
        try:
            tmp_html.unlink()
        except OSError:
            pass


def build_offline_html(board: Path, project: str) -> str:
    """Build a self-contained single-file offline HTML export of TELL + diagrams for sharing."""
    # Reuses the clean formal HTML with an interactive light/dark diagram toggle (no server needed)
    return build_formal_tell_print_html(board, project)
