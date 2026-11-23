---
title: Example Workflow Matching A/B/C/D/E Drawing
status: backlog
since: 2026-11-23
note: null
depends: []
files: []
owner: null
attachments: []
---

## Outcome
Demonstrates the upgraded Todo Tree DAG encoding the exact 5-lane (A, B, C, D, E) workflow drawing:
- Lane A: Happy path with mandatory acceptance `A6`
- Lane B & C: `if/else` conditional branches off `A1` and `A4` (with `B3 -> A3` merge, `C2` early-exit acceptance, and `B5|C5 -> A5` merge)
- Lane D: Parallel independent lane running concurrently with `A`, ending in mandatory acceptance `D4`
- Lane E: Optional branch forked from `A4` (crossing over `D` independently), ending in optional acceptance `E2`

## Scope
- Allowed files/surfaces:
  - `kb.py`
  - `mcp_server.py`
- Explicitly out of scope:
  - External third-party dependencies

## Plan (Todo Tree)
- [ ] A1 [START] [lane:A] Initialize task & evaluate fork1 condition
- [ ] A2 [lane:A] [after:A1] Happy-path step 2
- [ ] B1 [lane:B] [after:A1] [when:if(cond1):fork1] Conditional branch B step 1
- [ ] B2 [lane:B] [after:B1] Conditional branch B step 2
- [ ] B3 [lane:B] [after:B2] Conditional branch B step 3 (merges back to A3)
- [ ] C1 [lane:C] [after:A1] [when:else(cond1):fork1] Conditional branch C step 1
- [ ] C2 [lane:C] [after:C1] [ACCEPTANCE:MANDATORY] Early-exit acceptance if C path taken
- [ ] A3 [lane:A] [after:A2,B3?] Merge point waiting on A2 and B3 (if B taken)
- [ ] A4 [lane:A] [after:A3] Mid-workflow decision & fan-out checkpoint
- [ ] B4 [lane:B] [after:A4] [when:if(cond2):fork2] Second-phase branch B step 1
- [ ] B5 [lane:B] [after:B4] Second-phase branch B complete
- [ ] C4 [lane:C] [after:A4] [when:else(cond2):fork2] Second-phase branch C step 1
- [ ] C5 [lane:C] [after:C4] Second-phase branch C complete
- [ ] A5 [lane:A] [after:A4,B5|C5] Converge after A4 and active branch (B5 or C5)
- [ ] A6 [lane:A] [after:A5] [ACCEPTANCE:MANDATORY] Happy-path mandatory acceptance
- [ ] D1 [lane:D] [after:A1] [parallel] Parallel lane D step 1 (runs concurrently with A)
- [ ] D2 [lane:D] [after:D1] Parallel lane D step 2
- [ ] D3 [lane:D] [after:D2] Parallel lane D step 3
- [ ] D4 [lane:D] [after:D3] [ACCEPTANCE:MANDATORY] Parallel lane D mandatory acceptance
- [ ] E1 [lane:E] [after:A4] [optional] Optional branch E step 1 (independent of D)
- [ ] E2 [lane:E] [after:E1] [ACCEPTANCE:OPTIONAL] Optional branch E acceptance

## Prove
Exact commands and expected output:
```bash
python3 -m unittest tests/test_kanban.py -v
```
Expected: All DAG topology, parallel execution, if/else, optional/mandatory acceptance, and process-audit QA tests pass.
