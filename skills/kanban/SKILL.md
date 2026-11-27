---
name: kanban
description: "Central Kanban workflow. Load when creating, claiming, updating, retiring, rehoming, or verifying tickets, or posting QA/discovery Cases."
---
# Kanban

1. **Orient**: read `project.md` (repo identity, verify commands, feature index, gotchas) and `epic.md` (shared contracts).
2. **Plan**: create a ticket with concrete outcome, scope, and runnable `## Prove` command. Keep steps flat unless a real fork or parallel lane exists (for branching syntax, read `DAG-SYNTAX.md`).
3. **Build**: claim `build`, write **Ponytail** minimal code (preserve validation, error handling, security), and prove positive + **Pluto** negative cases at the matching test rung (`unit`, `integration`, `component`, `e2e`). Prefer no new test over a mock-only test.
4. **Verify**: move to `verify`, link discoveries or proof in a **Case** (`kanban_case`) when useful, and spawn `kb-qa` (keep default model).
5. **Maintain**: retire obsolete tickets (`retire`; moves to `backlog`, auto-purges after 120d) and move cross-epic work with `rehome`.
