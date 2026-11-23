# /kanban-init — Initialize a new kanban board and project

Initialize a clean Kanban board, project directory, and initial charters in the current workspace.

**Steps:**

1. Ask for the project name (e.g. `snowball`, `web-app`) and an optional initial epic (defaults to `core`).
2. Call `kanban_board(view="init", project="<project>", epic="<epic>")`.
3. Inform the user that the board and project charters have been successfully initialized.
4. Guide them to create their first ticket using `/kanban-new` or `kanban_ticket(ref="<project>/<epic>/T001", title="...")`.
