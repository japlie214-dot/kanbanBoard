---
name: kanban
description: Unified Kanban board management for Antigravity agents. Unified discovery, atomic move-and-claim, Todo Tree DAG execution, checkpoints, and safe attachments.
---

# Kanban Board Skill

This skill guides agents on interacting with the local file-backed Kanban board using the streamlined 7-tool MCP suite.

## The 7 Harmonized Tools

| Tool | Core Capability | Typical Usage |
|---|---|---|
| `kanban_board` | Discover, init, list, or lint | `kanban_board(view="overview")` or `kanban_board(view="init", project="myproj")` |
| `kanban_ticket` | Create or inspect ticket (auto-assigns ID) | `kanban_ticket(project="web", epic="auth", title="OAuth")` or `kanban_ticket(ref="web/auth/T001")` |
| `kanban_move` | Move status & claim lease | `kanban_move(ref="web/auth/T001", status="in-progress")` |
| `kanban_update` | Check nodes, log files/notes, attach | `kanban_update(ref="web/auth/T001", checked_nodes=["..."], files=["..."])` |
| `kanban_doc` | Read/write charters & specs | `kanban_doc(action="write", project="web", name="arch", content="...")` |
| `kanban_view` | Open live web dashboard | `kanban_view()` |
| `kanban_qa` | Independent QA audit (kb-qa only) | `kanban_qa(action="start", ref="...")` & `kanban_qa(action="approve", ...)` |

---

## Standard Workflow Runbook

### 1. Unified Discovery (`kanban_board`)
Discover projects, charters, epics, docs (`docs: []`), and all active tickets in a single call:
```python
kanban_board(view="overview")
```
*Note: If the board is fresh/empty (returns `{"projects": []}`), proceed directly to step 2 to create the first ticket. `view="lint"` is reserved for auditing existing tickets.*

### 2. Creating a Ticket (`kanban_ticket`)
```python
kanban_ticket(ref="web/auth/T001", title="Implement JWT refresh token rotation")
```
Edit `board/<project>/<epic>/<Tnnn>.md` to fill in:
- `## Outcome`: Observable end result.
- `## Scope`: Allowed files and out-of-scope files.
- `## Plan (Todo Tree)`: Branching checklist with at least one `[ACCEPTANCE]` leaf tag.
- `## Prove`: Real terminal commands to prove correctness.

### 3. Claiming & Starting Work (`kanban_move`)
Moving to `in-progress` atomically claims ownership with a 60-minute lease:
```python
kanban_move(ref="web/auth/T001", status="in-progress", agent_id="antigravity", note="Starting work")
```
*Note: Gate 1 automatically validates that required sections and the Todo Tree DAG are properly structured, and that no `[ACCEPTANCE]` leaf is already checked.*

### 4. Logging Progress & Attachments (`kanban_update`)
As work progresses, log progress notes, check off Todo Tree nodes, declare modified files, and attach test logs:
```python
kanban_update(
    ref="web/auth/T001",
    checked_nodes=["1. Core OAuth flow", "2A. Token endpoint"],
    files=["src/auth.py", "tests/test_auth.py"],
    notes="Finished refresh handler. Next: wire up middleware.",
    attach_file="test_output.log",
    attach_desc="Unit test execution log"
)
```

### 5. Submitting for Verification (`kanban_move`)
When code is written, prove commands pass, and Todo Tree DAG has a complete checked path to `[ACCEPTANCE]`:
```python
kanban_move(ref="web/auth/T001", status="verify", note="Implementation complete, unit tests passing")
```
This automatically verifies physical git modifications, checks DAG path continuity, generates the secret ephemeral `qa_nonce`, and transfers ticket ownership to `kb-qa`.

### 6. Launching Independent QA
Invoke the `kb-qa` subagent protocol to audit the diff, inspect the surrounding ecosystem, and run Horse vs. Zebra tests via `kanban_qa`.
