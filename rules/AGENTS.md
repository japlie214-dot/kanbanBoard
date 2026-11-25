# kanban-board Antigravity Rules (Caveman)

- Non-trivial work = ticket first. Central board only; never create `board/` in app repo.
- Lifecycle: `backlog -> in-progress -> verify -> done` (`blocked` anytime).
- `done` gate: ONLY `kb-qa` subagent or human via web app (`http://127.0.0.1:7890`). Never self-approve, never edit `board/` directly, never call `kb.py qa` or `manual-approve`.
- Never commit/push before ticket is `done`.
- Load `kanban` skill for tool usage. When ticket enters `verify`, spawn `kb-qa`.
- Keep changes Ponytail-minimal (no bloat, never cut validation/error handling/security). Update `epic.md`/`project.md` only when public CLI/API/schema changes.
