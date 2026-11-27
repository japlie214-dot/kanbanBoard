---
id: C003
title: "QA re-review T019 after C002: PASS"
kind: qa
author: kb-qa
created_at: "2026-11-26T10:00:05Z"
updated_at: "2026-11-26T10:00:05Z"
tickets:
  - "snowball/security/T019"
projects:
  - "snowball"
epics:
  - "snowball/security"
ticket_titles_json: "{\"snowball/security/T019\": \"0.4.1: Validate narrowed executable release\"}"
attachments: []
---
## Initial Post (kb-qa · 2026-11-26T10:00:05Z)
## Ponytail Diff
- Remediation diff reviewed: tests/test_key_transactions.py only (17 insertions, 9 deletions). The adopt-gated child now completes imports and signals ready before the parent starts the timed migration lock, and a go signal gates adoption. The barrier deadline is 60 s. The finally block releases the child. The change is test-only and does not weaken the product assertions.
- Scope: docs/release-scope-0.4.1.md (line 8) now documents removal of sb export, sb play export and passphrase re-encryption, plus the historical board/, separate mcp/ and deferred native/t015 status (line 9). This covers the C002 P1-2 item.
- Working-tree drift remains: about 27 modified tracked files, deleted sbcore/cmd_export.py, and untracked board/, mcp/, native/, sbcore/duckdb_writer.py, sql/security/005_event_policy.sql and new tests. The scope doc and ticket explicitly cover these. Release packaging excludes them (see below).
- Product tooling matches the candidate-05 source snapshot: tools/plugin/entry.py and tools/plugin/smoke.py are byte-identical. seal.py.in differs only by the generated manifest placeholder.

## Testing Ladder
- unit: RUN. Full `pytest tests -q` with TEST_HTTPFS_PATH set to C:\Users\10102721\AppData\Local\Temp\claude\b18409981dd2ff2c\93a6dddc-d047-49f0-a48e-5d0a964f758d\scratchpad\duckdb-httpfs-extracted-01\httpfs.duckdb_extension. The extension SHA-256 was verified as 9B0B0202CFA34F94F12BD9B2698002735BBCD0C1BD5FDA2E85450583EFD18E94. Result: 2322 passed, 2 skipped, 700 warnings in 353.41 s, with no concurrent jobs. This matches the claimed figure. The previous C002 failure did not recur.
- integration: RUN (C002 pass, not repeated). tests/test_exe.py on candidate-05 was PASS in the earlier run at exe-proof-2 (log exe.out). Candidate ZIP is unchanged: 57,816,357 bytes, SHA-256 4DFB3F15A81E9237B4B2C0F9B2FB82F0D04677D79932AF8EE5EB2810C75D5859. The installed proof was not rerun after the test-only change. Its applicability rests on the unchanged ZIP and product sources above.
- component: RUN as part of the sealed-release smoke in the installed proof. Not separately rerun.
- e2e: n/a: no live Snowflake or Desktop UI access in QA scope.

## Positive + Pluto Witness
- Positive: runtime-0.4.1.7z SHA-256 0A4594BAF9AF3DAA5D43D1503711F0295A0D69EF30762DDD785F64288BA8A2E7 matches the fingerprint. The archive lists 5,171 entries with zero board/, mcp/, native/ or t015 paths.
- Outer snowball-plugin-0.4.1.zip has 15 entries and zero board/, mcp/, native/ or t015 paths (checked with System.IO.Compression).
- Negative witnesses (installed proof, C002 run): missing archive, edited archive, runtime tamper and interpreter bypass all refused. Release smoke exits 0 with the Snowflake connector Arrow assertion in smoke.py.

## Advisory Notes
- P2: dormant experimental evaluator code (sbcore/cmd_play.py _experimental_display) ships in the sealed runtime without a CLI entry point. Scope doc says it must not be presented as a supported reader. Consider removal in 0.4.2.
- P2: SQL 003 requires 005 applied first, or all security events fail to record. Confirm in the release checklist.
- P2: policy rows can downgrade alarms (IS_ALARM FALSE) for the five hardcoded kinds. Confirm admin intent.
- P2: output-cap and sealed-release tests skip unless TEST_HTTPFS_PATH is set. The release gate should require it.
- Limitations: security-event SQL checks are regex assertions on text, and procedures were not executed against Snowflake. Deferred T015 items (broader guarantees, trusted reader race) remain out of scope and are not failed here.
- Not rerun: installed acceptance after the test-only remediation. The sbcore/ sources were not snapshot-diffed against candidate-05.

## Verdict: PASS
Both C002 P1 items are resolved. Approve with the advisory notes above.
