# /kanban-status — Show board status & overview

Show the current state of the kanban board using native MCP tools.

**Steps:**

1. ALWAYS call `kanban_board(view="overview")` first to discover projects, charters, epics, docs, active tickets, and owners.
2. If the board is empty or contains no projects yet, inform the user that the board is fresh and ready, and guide them to create their first ticket using `kanban_ticket(ref="project/epic/T001", title="...")` or project charter with `kanban_doc`.
3. If tickets exist, highlight active `in-progress` leases, tickets in `verify` ready for `/kanban-qa`, and any `blocked` items.
4. Call `kanban_board(view="lint")` only to verify structural integrity when tickets exist.
