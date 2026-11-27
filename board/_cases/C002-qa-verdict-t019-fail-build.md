---
id: C002
title: "QA verdict T019: FAIL (build)"
kind: qa
author: kb-qa
created_at: "2026-11-26T09:35:08Z"
updated_at: "2026-11-26T09:35:08Z"
tickets:
  - "snowball/security/T019"
projects:
  - "snowball"
epics:
  - "snowball/security"
ticket_titles_json: "{\"snowball/security/T019\": \"0.4.1: Validate narrowed executable release\"}"
attachments: []
---
## Initial Post (kb-qa · 2026-11-26T09:35:08Z)
## Ponytail Diff
- Reviewed raw `git diff` plus untracked files before worker notes. Release-relevant changes: tools/plugin/entry.py (extended-length site path), tools/plugin/seal.py.in (extended-length root for verification, reparse check kept), tools/plugin/smoke.py (asserts CAN_USE_ARROW_RESULT_FORMAT; uses duckdb_writer.connect), sbcore/duckdb_writer.py (fixed sealed httpfs path, autoinstall/autoload off, signature check kept), sbcore/ledger.py (connection closed on BaseException), sbcore/cmd_play.py (source path must equal managed path; locks config after view creation; `--save` re-opens saved file for profile), sql/security/003 + 005 (policy lookup overrides hardcoded alarm list when a row exists).
- Caller check: `_experimental_display` in cmd_play.py is not reachable from the CLI (no parser flags in sb.py); `getattr` defaults keep it dormant. Dead native-loading code is shipped in the runtime.
- Shape: minimal for the arrow/seal fixes. Not minimal: experimental evaluator code shipped in 0.4.1 despite the scope note excluding it.

## Testing Ladder
- unit: RUN. Full `pytest tests -q` with TEST_HTTPFS_PATH set to the approved extension (SHA-256 9B0B0202... verified). Result: 2321 passed, 2 skipped, 1 failed (tests/test_key_transactions.py::test_process_and_cached_thread_cannot_adopt_until_migration_finishes[True], "child did not reach barrier", tests/test_key_transactions.py:108, 10 s barrier deadline at line ~104). Run without concurrent jobs. Prior full run had a different key-transaction failure. Test passes in isolation (29/29 in test_key_transactions.py). Load-sensitive, not a product defect proven yet, but the Prove gate is not clean.
- integration: RUN. `tests/test_exe.py --build-dir candidate-05 --output-dir <new>` (exe-proof-2): PASS. Final line: "PASS: clean-profile install, smoke, bypasses, tamper, launcher pins and timings". Observed refusals: missing runtime archive, edited archive, bundled interpreter bypass, runtime tamper. Smoke exit 0 with "snowflake connector, boto3 s3, keyring, crypto imports ok". Ten warm config-show timings recorded (median 18.1 s, max 57.5 s under this machine's load; no budget violated).
- component: RUN as part of the sealed-release smoke (encrypted DuckDB, matplotlib png/svg/pdf). n/a for a separate harness.
- e2e: n/a: no live Snowflake or Desktop access in QA scope. Security SQL procedures 003/005 were not executed against Snowflake.

## Positive + Pluto Witness
- Positive: candidate-05 zip 57,816,357 bytes, SHA-256 4DFB3F15A81E9237B4B2C0F9B2FB82F0D04677D79932AF8EE5EB2810C75D5859 (matches handoff). Installed clean-profile smoke passes.
- Negative/witness: installed-copy refusals (archive missing, archive edited, runtime tamper, interpreter bypass) observed. Output-cap tests (tests/test_output_budget.py) and sealed-release tests SKIP unless TEST_HTTPFS_PATH is set (35 skipped without it). Release-sign-in gate test (tests/test_signin_clock.py::test_gate_timing) failed once under load (6.37 s); not failing in the final run.
- Security-event witnesses: tests/test_security_sql.py asserts SQL text by regex, not behavior. Weak witness, flagged below.

## Advisory Notes
- Scope drift (P1, see verdict): removal of `sb export` (sbcore/cmd_export.py deleted; sb.py h_export/parser removed; tests/test_export_removed.py added) is a user-visible CLI removal that is not in the ticket Scope/files list and not in docs/release-scope-0.4.1.md. Untracked board/, mcp/, native/ and new tests are also not reconciled to the ticket or release scope.
- Dead experimental code (P2): sbcore/cmd_play.py `_experimental_display` and native/t015 adapter ship in the sealed runtime without a CLI entry point.
- Deployment order (P2): 003 reads SBOX_DB.AI_SB.SECURITY_EVENT_POLICY. Applying 003 before 005 makes every event return "error: security event could not be recorded". README documents the order; confirm in the release checklist.
- Policy rows can downgrade alarms (IS_ALARM FALSE) for the five hardcoded kinds (sql/security/005_event_policy.sql seeds TRUE). Confirm this admin capability is intended.
- Test hygiene (P2): output-cap and sealed-release tests skip silently without TEST_HTTPFS_PATH; the release gate should require that variable so these cannot skip.
- Deferred and out of scope, not failed: broader T015 guarantees, trusted reader race guarantees.

## Findings
- P1-1 (Prove gate): tests/test_key_transactions.py:104-108 uses a 10 s barrier deadline for a child Python process. It failed in two of three full runs under load. Minimal fix: raise the deadline (for example to 60 s) or use an event-based handshake, then rerun the full regression with the approved extension and record a clean pass.
- P1-2 (scope drift): `sb export` removal (sbcore/cmd_export.py deleted, sb.py parser/handler removed) is not in the ticket Scope/files list or docs/release-scope-0.4.1.md. Minimal fix: either document the removal in the release scope and ticket, or restore the command and reject the removal test. Also reconcile the untracked board/, mcp/, native/ directories against the release scope.

## Verdict: FAIL
Reject to build with P1-1 and P1-2. Installed acceptance passed. Re-submit after the fixes and one clean full regression.
