---
name: ui
state: active
summary: Interactive view-only web dashboard with live board state, instant __INITIAL_DATA__ hydration, and responsive inspector pane.
repo: .
---

# Interactive Web Dashboard

The `ui` epic covers the browser-based visualization dashboard implemented in `viewer.py` and `resources/board.html`.

## Features
- **Instant Hydration**: Embedded `window.__INITIAL_DATA__` provides instant offline board rendering without roundtrip delay.
- **Live State Polling**: Periodic polling of `/api/board` keeps column cards synchronized with multi-agent activity.
- **Rich DAG Badges**: Visual indicators for `[START]`, `[ACCEPTANCE:MANDATORY]`, `[ACCEPTANCE:OPTIONAL]`, `[lane:...]`, `[after:...]`, and skipped `⊝` nodes.
- **Bottom Inspector Pane**: Ticket details, Todo Tree hierarchy, execution logs, and attachments displayed in an unobtrusive bottom drawer preserving full board column visibility.
