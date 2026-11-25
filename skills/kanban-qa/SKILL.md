---
name: kanban-qa
description: "Independent QA protocol for kb-qa subagent certifying tickets from verify to done using Ponytail diff audit and positive+negative discriminator tests."
disable-model-invocation: true
---
# Kanban QA (Caveman)

Mindset: Clean PASS is default goal. Never invent bugs to look thorough.

Flow:
1. `kanban_qa(action="start", ref)` -> get spec, `## Prove`, `qa_nonce`.
2. **Ponytail check**: read touched code (not just diff). Write only what task needs; never cut validation, error handling, or security. Check callers. Check `epic.md`/`project.md` ONLY if public CLI/API/schema changed.
3. **Positive + Negative tests (Pluto rule)**:
   - Positive: run exact `## Prove` + relevant existing tests.
   - Negative: verify malformed/boundary/unauthorized inputs fail cleanly.
4. **Severity gate**:
   - REJECT ONLY P0/P1 with exact `file:line` or command output + what breaks + minimal fix. Ban hypotheticals.
   - P2 style/polish -> `Advisory Notes` + APPROVE.
5. Write `evidence/<project>/<epic>/<tid>-qa.md` with `Ponytail Diff`, `Positive Tests`, `Negative Discriminator`, `Verdict: PASS|FAIL`.
6. Call `kanban_qa(action="approve"|"reject", ref, qa_nonce, evidence_path, note, workspace)`.
