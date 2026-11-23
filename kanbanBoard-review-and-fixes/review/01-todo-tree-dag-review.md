# 1. Todo Tree DAG & Process-Verification Review

**Repository Audited:** [`japlie214-dot/kanbanBoard`](https://github.com/japlie214-dot/kanbanBoard)  
**Key Files Audited:** [`kb.py`](https://github.com/japlie214-dot/kanbanBoard/blob/main/kb.py), [`wiki/Executable-Todo-Tree.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/wiki/Executable-Todo-Tree.md), [`agents/kb-qa.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/agents/kb-qa.md), [`skills/kanban-qa/SKILL.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/skills/kanban-qa/SKILL.md)

---

## Executive Verdict

The current `Todo Tree` implementation in `kb.py` is **not a Directed Acyclic Graph (DAG)** — it is a **single-parent indentation tree** that validates only whether *any single* `[ACCEPTANCE]` leaf has a checked parent chain. It cannot represent your swimlane workflow drawing (parallel lanes, conditional `if/else` forks, cross-branch merges/joins, mandatory vs. optional acceptance endpoints, or strict start-to-end path invariants), and neither the engine nor `kb-qa` verifies that intermediate checkpoints were actually executed in order.

---

## Gap Analysis: Current Implementation vs. Expected Drawing

| Capability | Expected (Your Drawing & Requirements) | Current Implementation (`kb.py`) | Verdict |
|---|---|---|---|
| **Graph Topology** | True DAG with swimlane branches (`A`, `B`, `C`, `D`, `E`), fan-out forks, and fan-in merges (e.g., `B3 -> A3`, `B5/C5 -> A5`, `A4 -> E1` hopping over `D`). | Indentation-only tree (`parents[i] = stack[-1][0]`). Every node has at most 1 parent; merges and cross-branch edges are impossible. | **Broken / Mismatched** |
| **Start & End Invariant** | Every path must begin at `START` and terminate at an acceptance checkpoint (red circle). No dangling non-acceptance leaves. | No `START` node concept. Any branch can terminate at a plain non-acceptance checkbox without error. | **Missing** |
| **Mandatory vs. Optional Acceptance** | Red circles can be mandatory (`A`, `D`) or optional (`E`). ALL active mandatory acceptances must be satisfied; optional ones may be skipped. | Only a single `[ACCEPTANCE]` tag exists. `validate_todo_tree` passes as soon as **1** acceptance path is checked (`if valid_paths: return True`), silently ignoring unchecked mandatory branches like `D`. | **Critical Bug** |
| **Parallel Execution** | Independent branches (e.g., `D` alongside `A`) run concurrently and independently; `A4 -> E1` hops over `D` without blocking `D`. | No concept of parallel lanes or independent branch progress. | **Missing** |
| **Conditional `if/else` Branches** | `B` & `C` are conditional `if/else` branches of `A`. Untaken branches are skipped cleanly; taken branches either merge back (`B3 -> A3`, `B5/C5 -> A5`) or terminate early at an acceptance (`C2`). | `[CHOSEN]` and `[SKIPPED]` appear only as decorative text in `api_create`'s template; `parse_todo_tree` completely ignores them. | **Cosmetic Only** |
| **Cross-Branch Waits / Dependencies** | Nodes can wait on nodes or `if/else` outcomes from other branches before becoming executable. | `api_checkpoint` does a blind regex replace `re.sub(r'(\s*)-\s*\[ \]\s*(item)', ...)` across the entire markdown body with **zero** dependency-order checking and silent no-op on typos. | **Broken / Bypassable** |
| **Process Verification (Engine + `kb-qa`)** | System and `kb-qa` verify that ALL checkpoints from `START` to ALL mandatory acceptances were checked **and actually executed** (process + result). | Checkboxes are self-declared booleans (`- [x]`). An agent can bulk-check every box in one call without executing any step. `api_qa_approve` only checks substrings `("Diff", "Positive Tests", "Negative Discriminator Tests", "PASS")`. | **Critical Gap** |

---

## Tracing Your Drawing (`A`–`E`)

From your diagram:
- **Lane A (Happy Path, Mandatory Acceptance `A6`):**
  `START -> A1 -> A2 -> A3 (merges B3) -> A4 -> A5 (merges B5/C5) -> A6 [ACCEPTANCE:MANDATORY]`
- **Lane B (`if/else` of A):**
  - Fork 1 from `A1`: `B1 -> B2 -> B3`, then merges back into `A3`.
  - Fork 2 from `A4`: `B4 -> B5`, then merges back into `A5`.
- **Lane C (`if/else` of A):**
  - Fork 1 from `A1`: `C1 -> C2 [ACCEPTANCE:MANDATORY]` (early terminal acceptance if the `else` path is taken).
  - Fork 2 from `A4`: `C4 -> C5`, then merges back into `A5`.
- **Lane D (Parallel to A, Mandatory Acceptance `D4`):**
  Forked at `A1` in parallel with `A`: `D1 -> D2 -> D3 -> D4 [ACCEPTANCE:MANDATORY]`. Note the bridge/hop where `A4 -> E1` crosses over `D` without touching `D`.
- **Lane E (Optional Branch, Optional Acceptance `E2`):**
  Forked from `A4` (crossing over `D`): `E1 -> E2 [ACCEPTANCE:OPTIONAL]`.

---

## Recommended Redesign (Implemented in `diffs/01-kb-dag-and-process-qa.patch`)

### 1. Zero-Dependency Markdown DAG Grammar

Keep the file-backed, human-readable Markdown ethos while making the graph explicit and machine-verifiable:

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

**Dependency & Status Semantics:**
- **Checkboxes:** `- [ ]` = `pending`, `- [x]` = `done` (executed), `- [-]` = `skipped` (untaken `if/else` or skipped optional branch).
- **`[after:...]` expressions:**
  - `A2,B3` = **AND join** (must wait for both `A2` and `B3` to be `done`).
  - `B5|C5` = **XOR / OR join** (must wait for whichever active `if/else` branch ran).
  - `B3?` = **Optional/conditional dependency** (if `B3` is active, must wait for `B3` to be `done`; if `B3` was skipped via `if/else`, does not block `A3`).
- **Structural Rules (Gate 1 — `backlog -> in-progress`):**
  1. Exactly one `[START]` root node (or all zero-in-degree nodes must be `[START]`).
  2. Acyclic graph (Kahn's topological sort / DFS cycle check).
  3. All referenced `after:` node IDs exist.
  4. All nodes are reachable from `[START]`.
  5. **Every terminal node (out-degree == 0) MUST be `[ACCEPTANCE:MANDATORY]` or `[ACCEPTANCE:OPTIONAL]`** (guarantees every path has a start and ends at an acceptance checkpoint).
  6. At least one `[ACCEPTANCE:MANDATORY]` node exists, and zero acceptance nodes are checked (`- [x]`) prior to `in-progress`.
- **Runtime Ordering & Process Proof (`api_checkpoint`):**
  1. Cannot check off node `X` if any required predecessor in `after:` is still `pending`.
  2. Checking off a node **requires an execution proof** (`proof` string or `{node_id: {cmd, output, artifact}}`) and writes an append-only `## Execution Log` entry with UTC timestamp, node ID, command/action, and observed proof.
  3. Unknown node IDs raise `ValueError` instead of silently succeeding.
  4. Untaken `if/else` or optional branches are explicitly marked `- [-]` via `skip_nodes` with a recorded branch-decision reason.
- **Gate 3 (`in-progress -> verify`):**
  1. **Every non-skipped `[ACCEPTANCE:MANDATORY]` node** must be `- [x]` (so BOTH `A6` and `D4` must pass; passing `A6` alone fails Gate 3!).
  2. For every reached acceptance node, **every active ancestor from `[START]` to that acceptance** must be `- [x]` AND present in `## Execution Log` with non-trivial execution proof.
  3. Optional branches (`[optional]` / `[ACCEPTANCE:OPTIONAL]`) must be either **fully executed to their acceptance** OR **cleanly skipped (`- [-]`)** — no half-finished optional branches.
  4. Each `if/else` fork group must have a valid branch decision (not all branches skipped when downstream requires them).
- **Gate 5 (`kb-qa` Process + Result Verification):**
  1. `kb-qa` executes **Tier 0: Process & Checkpoint Execution Audit** before diff/forest/tests: inspects `## Execution Log`, verifies chronological dependency order, verifies no rubber-stamped bulk-checking without real execution proof, verifies `if/else` branch conditions against actual code/runtime state, and spot-checks intermediate checkpoint artifacts/commands.
  2. `api_qa_approve` mechanically validates that the QA evidence file includes a `Process & Checkpoint Audit` section explicitly citing every satisfied mandatory acceptance ID (e.g., `A6`, `D4`) alongside `Diff`, `Living Architecture`, `Positive Tests`, `Negative Discriminator Tests`, and `Verdict: PASS`.
