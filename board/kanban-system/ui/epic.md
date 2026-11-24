---
name: ui
state: active
summary: Reactive view-only web dashboard with instant __INITIAL_DATA__ hydration, real-time SSE push telemetry, visual DAG graph, and multi-tab bottom inspector drawer.
repo: .
---

# Interactive Web Dashboard & Real-Time Telemetry

The `ui` epic covers the browser-based visualization dashboard implemented in `viewer.py` and `resources/board.html`.

## Core Architectural Capabilities
1. **Instant Offline Hydration**: Embedded `window.__INITIAL_DATA__` renders full board layout in 0ms without async waterfall delays or loading spinners.
2. **Dual-Transport Telemetry**:
   - Primary: Server-Sent Events (`GET /events` / `GET /api/events`) for instantaneous push updates when board files change.
   - Fallback: Dynamic debounced HTTP polling with ETag change detection and live connection badge (`live (SSE)`, `polling`, `offline`).
3. **Live Agent Lease HUD**:
   - Header bar displaying ticking live lease countdowns (`[👤 antigravity: ⏱ 52m 14s]`) with color-coded urgency (normal, warn under 15m, expired).
4. **Interactive Bottom Inspector Drawer**:
   - Resizable height via drag handle, fullscreen toggle (`⛶ Expand`), sticky top control bar, and prominent close button (`✕ Close` / `Esc`).
   - Maintains full line-of-sight to board columns.
5. **5-Tab Deep Inspector Architecture**:
   - **Tab 1 (Visual DAG Graph)**: Structured visualization grouped by lanes (`dag-lane-row`), execution nodes with status styling (emerald for done, glowing animated border for `ready_nodes`, gold for mandatory acceptance, muted strikethrough for skipped), prerequisite chips, and decision badges.
   - **Tab 2 (Ticket Spec & Plan)**: Zero-void layout parsing Markdown sections (`## Outcome`, `## Scope`, `## Plan`, `## Prove`), with quick-copy command button for verification CLI snippets.
   - **Tab 3 (Process Audit Stream)**: Chronological execution proof timeline displaying checkpoint timestamps, kind badges (`DONE`, `SKIP`), and recorded evidence snippets.
   - **Tab 4 (Touched Files & Attachments)**: Register of modified workspace files with quick-copy buttons and safe attachments register.
   - **Tab 5 (Living Architecture Reader)**: Slide-over markdown reader displaying project charter (`project.md`) and epic specification (`epic.md`) for instant context alignment.
