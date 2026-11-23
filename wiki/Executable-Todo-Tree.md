# Executable Todo Tree Grammar & True DAG Verification

The **Todo Tree** is KanbanBoard's core mechanism for structured, verifiable planning and execution. It organizes tasks into a true **Directed Acyclic Graph (DAG)** using standard Markdown list syntax, supporting parallel execution lanes, conditional `if/else` forks, cross-branch merges, and machine-verifiable execution proofs.

---

## 1. Syntax & Grammar Specification

The Todo Tree lives inside the ticket markdown under the header `## Plan (Todo Tree)`.

### 1.1 Grammar & Tags
- **Checkboxes:**
  - `- [ ]`: Pending task.
  - `- [x]`: Executed task (requires recorded proof in `## Execution Log`).
  - `- [-]`: Skipped task (used for untaken `if/else` branches or skipped optional branches).
- **Node IDs:**
  - Placed at the start of the item (e.g., `A1`, `B2`, `D4`).
- **Tags:**
  - `[START]`: Marks workflow entry point(s). Every path begins at a start node.
  - `[lane:<name>]`: Identifies execution swimlanes (e.g., `[lane:A]`, `[lane:D]`).
  - `[after:<expr>]`: Declares prerequisites:
    - `[after:A1]`: Single prerequisite.
    - `[after:A2,B3]`: AND join (must wait for both `A2` and `B3` to be done).
    - `[after:B5|C5]`: XOR / OR join (satisfied if either `B5` or `C5` is done).
    - `[after:A2,B3?]`: Conditional/optional merge (waits for `B3` if taken; does not block if `B3` was skipped).
  - `[when:if(cond):fork]`: Declares conditional branch `if` arm.
  - `[when:else(cond):fork]`: Declares conditional branch `else` arm.
  - `[parallel]`: Marks independent parallel lane (runs concurrently with main branch).
  - `[optional]`: Marks optional branch (may be skipped cleanly via `- [-]`).
  - `[ACCEPTANCE:MANDATORY]`: Mandatory acceptance checkpoint. **ALL** active mandatory acceptances must be satisfied and proven before moving to `verify`.
  - `[ACCEPTANCE:OPTIONAL]`: Optional acceptance checkpoint. Must be either fully completed or cleanly skipped.

### 1.2 Example 5-Lane DAG (A/B/C/D/E)
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:A] Initialize workflow & evaluate condition 1
- [ ] A2 [lane:A] [after:A1] Happy-path step 2
- [ ] B1 [lane:B] [after:A1] [when:if(cond1):fork1] Conditional branch B step 1
- [ ] B2 [lane:B] [after:B1] Conditional branch B step 2
- [ ] B3 [lane:B] [after:B2] Conditional branch B step 3
- [ ] C1 [lane:C] [after:A1] [when:else(cond1):fork1] Conditional branch C step 1
- [ ] C2 [lane:C] [after:C1] [ACCEPTANCE:MANDATORY] Early-exit acceptance for branch C
- [ ] A3 [lane:A] [after:A2,B3?] Merge point waiting on A2 and (if taken) B3
- [ ] A4 [lane:A] [after:A3] Decision & fan-out checkpoint
- [ ] B4 [lane:B] [after:A4] [when:if(cond2):fork2] Branch B second phase
- [ ] B5 [lane:B] [after:B4] Branch B second phase complete
- [ ] C4 [lane:C] [after:A4] [when:else(cond2):fork2] Branch C second phase
- [ ] C5 [lane:C] [after:C4] Branch C second phase complete
- [ ] A5 [lane:A] [after:A4,B5|C5] Converge after A4 and whichever of B5/C5 ran
- [ ] A6 [lane:A] [after:A5] [ACCEPTANCE:MANDATORY] Happy-path final acceptance
- [ ] D1 [lane:D] [after:A1] [parallel] Parallel lane D start (runs with A)
- [ ] D2 [lane:D] [after:D1] Parallel lane D step 2
- [ ] D3 [lane:D] [after:D2] Parallel lane D step 3
- [ ] D4 [lane:D] [after:D3] [ACCEPTANCE:MANDATORY] Parallel lane D mandatory acceptance
- [ ] E1 [lane:E] [after:A4] [optional] Optional branch E step 1 (independent of D)
- [ ] E2 [lane:E] [after:E1] [ACCEPTANCE:OPTIONAL] Optional branch E acceptance
```

---

## 2. Process Verification & Append-Only Execution Log

Checkpoints are NOT self-declared honors-system booleans. When checking off nodes via `kanban_update`:
1. **Topological Order**: Predecessors declared in `[after:...]` must already be done.
2. **Proof Required**: Callers must provide `node_proofs: {nid: "evidence..."}` containing commands run, output, or artifact paths.
3. **Execution Log**: The engine automatically writes structured audit records to `## Execution Log`:
   ```markdown
   ## Execution Log
   - [2026-11-23 07:00 UTC] [DONE] A1 | proof: Read epic.md and initialized schema
   - [2026-11-23 07:05 UTC] [SKIP] C1 | reason: cond1 evaluated true; took B branch
   - [2026-11-23 07:10 UTC] [DONE] A2 | proof: pytest tests/test_core.py -> 10 passed
   ```

---

## 3. Strict Verification Gates

- **Gate 1 (`backlog -> in-progress`)**: Validates acyclic DAG topology, `[START]` root, terminal leaves ending at acceptance checkpoints, and ensures no acceptance checkpoint is pre-checked.
- **Gate 3 (`in-progress -> verify`)**: Validates that **all** active mandatory acceptances are completed (`- [x]`), all active paths trace back continuously to `[START]`, all intermediate checkpoints have recorded proofs in `## Execution Log`, and optional branches are either completed or cleanly marked `- [-]`.
- **Gate 5 (`kb-qa` Certification)**: `kb-qa` executes **Tier 0 Process Audit**, verifying that every checkpoint was executed in order and citing every active mandatory acceptance ID in the QA evidence report before certifying to `done`.
