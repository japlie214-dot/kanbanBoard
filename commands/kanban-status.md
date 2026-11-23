# /kanban-status — Show board status & overview

Show the current state of the kanban board using native MCP tools.

**Steps:**

1. Call `kanban_board(view="overview")` to retrieve projects, charters, epics, docs, active tickets, and owners.
2. For compact listings or health checks, call `kanban_board(view="list")` or `kanban_board(view="lint")`.
3. Highlight any tickets in `verify` that require launching `/kanban-qa`.
4. Flag any `blocked` tickets requiring attention or any `lint` errors.
