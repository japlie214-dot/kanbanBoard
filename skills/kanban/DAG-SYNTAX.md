# DAG Branching Syntax (Disclosed Reference)

Use only when a ticket genuinely has a contingency fork, parallel workstream, or optional polish:
- `[START]` — entry node.
- `[after:A1]` or `[after:A1,B1]` — prerequisite join; `[after:B1|B2]` — XOR fallback join; `[after:T1,O2?]` — optional join.
- `[when:if(cond):fork1]` / `[when:else(cond):fork1]` — conditional fork.
- `[parallel]` — independent lane safe for concurrent execution.
- `[optional]` / `[ACCEPTANCE:OPTIONAL]` — skippable via `skip_nodes`.
- `[ACCEPTANCE:MANDATORY]` — required terminal checkpoint.
