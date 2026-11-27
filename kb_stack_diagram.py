#!/usr/bin/env python3
"""kb_stack_diagram.py — Declarative light-default orthogonal architecture diagram renderer.

Inspired by caru-ini/stack-diagram (MIT):
  - Accepts a compact declarative JSON spec from kb-doc (never feeds built SVGs back to LLM).
  - Renders grouped containers, crisp white icon tiles, orthogonal elbow connectors routed
    cleanly through open gutters (zero arrows through text), and theme-aware CSS variables
    (Light mode default, smooth Light/Dark transition).
  - Caches fetched brand SVGs locally in `board/_doc_logo_cache/` and falls back cleanly
    to crisp monochrome vector badges when offline.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Optional

SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")

# Built-in offline vector icon fallbacks (white tile preserves brand color)
BUILTIN_ICONS: dict[str, str] = {
    "python": '<path d="M12 10 h11 v6 h-7 v7 h-4 Z" fill="#3776AB"/><path d="M26 22 h-11 v-6 h7 v-7 h4 Z" fill="#F59E0B"/>',
    "git": '<circle cx="13" cy="19" r="3.5" fill="#F05032"/><circle cx="25" cy="13" r="3.5" fill="#F05032"/><circle cx="25" cy="25" r="3.5" fill="#F05032"/><path d="M16 17 L22 14 M16 21 L22 24" stroke="#F05032" stroke-width="2"/>',
    "claude": '<circle cx="19" cy="19" r="10" fill="#D97757"/><path d="M19 12 v14 M12 19 h14 M14 14 l10 10 M24 14 l-10 10" stroke="#FFF" stroke-width="1.8"/>',
    "gemini": '<path d="M19 8 L23 16 L31 16 L23 20 L19 29 L15 20 L7 16 L15 16 Z" fill="#4F46E5"/>',
    "codex": '<circle cx="19" cy="19" r="9.5" fill="none" stroke="#059669" stroke-width="2.6"/><circle cx="19" cy="19" r="3.5" fill="#059669"/>',
    "browser": '<rect x="8" y="10" width="22" height="17" rx="2.5" fill="none" stroke="#0F172A" stroke-width="2"/><line x1="8" y1="16" x2="30" y2="16" stroke="#0F172A" stroke-width="1.8"/>',
    "db": '<ellipse cx="19" cy="12" rx="9" ry="3.5" fill="#0284C7"/><path d="M10 12 v13 c0 2 4 3.5 9 3.5 s9-1.5 9-3.5 V12" fill="none" stroke="#0284C7" stroke-width="2"/>',
    "default": '<rect x="10" y="10" width="18" height="18" rx="4" fill="#334155"/><circle cx="19" cy="19" r="4" fill="#FFFFFF"/>',
}


def _esc(s: Any) -> str:
    return html.escape(str(s or "").strip(), quote=True)


def _safe_id(raw: Any, fallback: str) -> str:
    s = str(raw or "").strip()
    return s if SAFE_ID_RE.match(s) else fallback


def _icon_markup(icon_name: str, board: Optional[Path] = None) -> str:
    key = re.sub(r"[^a-z0-9_-]", "", (icon_name or "").lower())
    if board is not None and key:
        cached = board / "_doc_logo_cache" / f"{key}.svg"
        if cached.is_file():
            raw = cached.read_text(encoding="utf-8", errors="replace")
            # Strip <script>, <foreignObject>, inline on* handlers, and scriptable URIs safely
            raw = re.sub(r"<\s*(?:script|foreignObject)\b[^>]*>.*?<\s*/\s*(?:script|foreignObject)\s*>", "", raw, flags=re.I | re.S)
            raw = re.sub(r"\son[a-z]+\s*=\s*(['\"]).*?\1", "", raw, flags=re.I | re.S)
            raw = re.sub(r"\son[a-z]+\s*=\s*[^\s>]+", "", raw, flags=re.I)
            raw = re.sub(r"(?:javascript|vbscript):", "", raw, flags=re.I)
            m = re.search(r"<svg[^>]*>(.*)</svg>", raw, flags=re.I | re.S)
            if m:
                return f'<g transform="translate(5,5) scale(0.75)">{m.group(1)}</g>'
    return BUILTIN_ICONS.get(key, BUILTIN_ICONS["default"])


def render_stack_diagram_svg(spec: dict[str, Any], board: Optional[Path] = None) -> str:
    """Render a declarative stack_diagram JSON spec into a theme-aware orthogonal SVG."""
    if not isinstance(spec, dict):
        raise ValueError("stack_diagram spec must be a JSON object.")
    groups = spec.get("groups") or []
    edges = spec.get("edges") or []
    if not isinstance(groups, list) or not groups:
        raise ValueError("stack_diagram spec must contain at least one group.")

    col_w = 240
    gutter = 82
    pad_x = 20
    pad_y = 22
    node_h = 62
    node_gap = 14
    head_h = 34

    max_nodes = max(len(g.get("nodes") or []) for g in groups)
    group_h = max(160, head_h + max_nodes * (node_h + node_gap) + 16)
    total_w = pad_x * 2 + len(groups) * col_w + max(0, len(groups) - 1) * gutter
    total_h = pad_y * 2 + group_h

    node_coords: dict[str, tuple[int, int, int, int, int]] = {}
    svg_parts: list[str] = [
        f'<svg class="sd-svg" viewBox="0 0 {total_w} {total_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{_esc(spec.get("title") or "Architecture Stack Diagram")}">',
        "<defs>",
        '<marker id="sd-arr-t" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 1 L10 5 L0 9 Z" fill="var(--sd-edge-teal, #0F766E)"/></marker>',
        '<marker id="sd-arr-v" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 1 L10 5 L0 9 Z" fill="var(--sd-edge-vio, #6D28D9)"/></marker>',
        '<marker id="sd-arr-a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 1 L10 5 L0 9 Z" fill="var(--sd-edge-amb, #D97706)"/></marker>',
        "</defs>",
        f'<rect x="0" y="0" width="{total_w}" height="{total_h}" fill="var(--sd-bg, #F8FAFC)"/>',
    ]

    for g_idx, grp in enumerate(groups):
        gx = pad_x + g_idx * (col_w + gutter)
        gy = pad_y
        tone = str(grp.get("tone") or "default").lower()
        stroke_var = "var(--sd-group-sandbox, #6D28D9)" if tone == "sandbox" else "var(--sd-group-stroke, #1E293B)"
        dash = ' stroke-dasharray="6 4"' if tone == "sandbox" else ""
        lbl_var = (
            "var(--sd-lbl-sandbox, #5B21B6)"
            if tone == "sandbox"
            else ("var(--sd-lbl-core, #0F766E)" if tone == "core" else "var(--sd-lbl-harness, #334155)")
        )
        svg_parts.append(
            f'<rect x="{gx}" y="{gy}" width="{col_w}" height="{group_h}" rx="10" '
            f'fill="var(--sd-group-bg, #EFF3F8)" stroke="{stroke_var}" stroke-width="1.6"{dash}/>'
        )
        svg_parts.append(
            f'<text x="{gx + 14}" y="{gy + 22}" fill="{lbl_var}" font-family="monospace" '
            f'font-size="11" font-weight="800">{_esc(grp.get("label") or f"GROUP {g_idx + 1}").upper()}</text>'
        )

        for n_idx, node in enumerate(grp.get("nodes") or []):
            nid = _safe_id(node.get("id"), f"n_{g_idx}_{n_idx}")
            nx = gx + 14
            ny = gy + head_h + n_idx * (node_h + node_gap)
            nw = col_w - 28
            node_coords[nid] = (nx, ny, nw, node_h, g_idx)
            svg_parts.append(
                f'<rect x="{nx}" y="{ny}" width="{nw}" height="{node_h}" rx="8" '
                f'fill="var(--sd-node-bg, #FFFFFF)" stroke="var(--sd-node-stroke, #334155)" stroke-width="1.2"/>'
            )
            # White icon tile (preserves brand colors in both Light & Dark themes)
            svg_parts.append(
                f'<rect x="{nx + 10}" y="{ny + 12}" width="38" height="38" rx="7" fill="#FFFFFF" stroke="#E2E8F0"/>'
            )
            svg_parts.append(
                f'<g transform="translate({nx + 10},{ny + 12})">{_icon_markup(str(node.get("icon") or ""), board)}</g>'
            )
            svg_parts.append(
                f'<text x="{nx + 58}" y="{ny + 28}" fill="var(--sd-title, #0F172A)" '
                f'font-family="sans-serif" font-size="12.5" font-weight="700">{_esc(node.get("title") or nid)}</text>'
            )
            if node.get("subtitle"):
                svg_parts.append(
                    f'<text x="{nx + 58}" y="{ny + 45}" fill="var(--sd-sub, #475569)" '
                    f'font-family="monospace" font-size="9.5">{_esc(node.get("subtitle"))}</text>'
                )

    # Orthogonal connectors routed through vertical gutters between groups
    for e_idx, edge in enumerate(edges):
        src = node_coords.get(str(edge.get("from") or ""))
        dst = node_coords.get(str(edge.get("to") or ""))
        if not src or not dst:
            continue
        sx, sy, sw, sh, sg = src
        dx, dy, dw, dh, dg = dst
        cy1 = sy + sh // 2
        cy2 = dy + dh // 2
        tone = str(edge.get("tone") or "teal").lower()
        stroke = (
            "var(--sd-edge-vio, #6D28D9)" if tone == "violet"
            else ("var(--sd-edge-amb, #D97706)" if tone == "amber" else "var(--sd-edge-teal, #0F766E)")
        )
        marker = "sd-arr-v" if tone == "violet" else ("sd-arr-a" if tone == "amber" else "sd-arr-t")
        dash = ' stroke-dasharray="4 3"' if str(edge.get("style") or "") == "dashed" else ""

        if dg == sg:
            x1 = sx
            x2 = dx
            mid_x = sx - 16 - ((e_idx % 3) * 6)
        elif dg > sg:
            x1 = sx + sw
            x2 = dx - 4
            mid_x = (x1 + x2) // 2 + ((e_idx % 3) - 1) * 6
        else:
            x1 = sx
            x2 = dx + dw + 4
            mid_x = (x1 + x2) // 2 + ((e_idx % 3) - 1) * 6

        svg_parts.append(
            f'<path d="M {x1} {cy1} H {mid_x} V {cy2} H {x2}" fill="none" '
            f'stroke="{stroke}" stroke-width="2"{dash} marker-end="url(#{marker})"/>'
        )
        lbl = str(edge.get("label") or "").strip()
        if lbl:
            pw = max(56, len(lbl) * 6 + 18)
            px = mid_x - pw // 2
            py = (cy1 + cy2) // 2 - 9
            bg_v = "var(--sd-pill-vio-bg, #EDE9FE)" if tone == "violet" else "var(--sd-pill-amb-bg, #FEF3C7)"
            fg_v = "var(--sd-pill-vio-fg, #4C1D95)" if tone == "violet" else "var(--sd-pill-amb-fg, #92400E)"
            bd_v = "var(--sd-pill-vio-bd, #7C3AED)" if tone == "violet" else "var(--sd-pill-amb-bd, #D97706)"
            svg_parts.append(
                f'<rect x="{px}" y="{py}" width="{pw}" height="18" rx="4" fill="{bg_v}" stroke="{bd_v}" stroke-width="1.2"/>'
                f'<text x="{mid_x}" y="{py + 12}" text-anchor="middle" fill="{fg_v}" font-family="monospace" font-size="9.5" font-weight="700">{_esc(lbl)}</text>'
            )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def render_stack_diagram_fragment(spec: dict[str, Any], board: Optional[Path] = None) -> str:
    """Wrap the orthogonal SVG in a strict-CSP light-default interactive frame."""
    title = _esc(spec.get("title") or "Architecture Stack Diagram")
    svg = render_stack_diagram_svg(spec, board=board)
    return (
        '<div class="sd-frame" data-sd-theme="light">\n'
        '  <div class="sd-toolbar">\n'
        f'    <span>stack-diagram · {title}</span>\n'
        '    <button type="button" class="hw-btn sd-theme-toggle">Dark Graph</button>\n'
        '  </div>\n'
        f'{svg}\n'
        '</div>\n'
    )
