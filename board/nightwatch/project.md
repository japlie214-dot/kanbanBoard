---
name: Nightwatch
state: active
summary: eToro auto-trader on Android (Chaquopy). Reach dry-run first light, then one armed daily session.
repo: repos/etoroNightwatch
---
# Nightwatch — plan

Next: keep T081 in verification. Offline Kotlin execution passed the JSON merge, malformed-input, allowlist and UTF-8 size boundaries using the exact production function on JVM with `org.json`, not the Android platform implementation. Independent local QA also confirmed committed WAL visibility without main database mutation, corrected Telegram URL validation and synthetic browser rendering at 400 px. Standard Gradle and actual phone wake/push remain unverified. The operator approved only SQLite-managed WAL/SHM activity for the existing demo database. No cloud rollout or device install is authorized or performed. T082 rule coverage remains incomplete. Leave Z10 armed in demo on Wi-Fi and power.

## Z10 evidence — 2026-11-18 local

Read-only device inspection confirmed the existing November 13 installation. All times below are UTC. No flags, alarm, APK, account or orders were changed by this inspection.

- **November 13, 20:05:** The alarm claimed the one-shot seed. `SEED_DEMO.done` reports 5 of 5 accepted at $11,000 each, buy complete and positions visible. Adoption deferred; the armed session failed gate 11 without HALT. These were setup orders, not strategy trades.
- **November 16, 20:10:** The alarm invoked adoption only; adoption remained pending. The armed session failed gate 3 without HALT.
- **November 17, 20:05:** Adoption-only retry planned and applied on its first attempt; `SEED_DEMO.adopt.done` reports `adopted`. At 20:30 the armed demo session finished, with all 12 gates passing. The read-only demo database shows zero strategy intents, zero orders and zero fills for that session.
- `ARM_DEMO` remains present. No seed, running, pending-adoption, failed-adoption or demo HALT marker remains. The next existing alarm is November 18 at 20:05 UTC (November 19 at 03:05 local, UTC+07).

## November 13 setup record (historical)

State left on the phone at 06:10 UTC 2026-11-13 (13:10 local), observed by the PM over adb:
- Installed build: commit `a9e4201` (T079 + T080), APK sha256 `6905D87CA348985C...`, installed 13:09 local. Pushed to `origin/main` at 14:07 local 2026-11-13 (`162837f..a9e4201`, Boss approved); local and remote are in sync.
- `files/nightwatch_demo/ARM_DEMO` present (since 6 Nov); `SEED_DEMO` = `5 11000` (8 bytes, set 13:10 local); no HALT file in either home.
- Session alarm present after the install: `origWhen 1794600300000` = 2026-11-13 20:05:00 UTC.
- Expected tonight (T080 Revision 2): buy 5 x 11,000 USD SCHG in demo, adoption refused for the missing end-of-day bar, status `bought_adoption_pending`, `SEED_DEMO.adopt` left; the session then fails gate 11 and aborts without HALT. Expected next trading day (Mon 2026-11-16 20:05 UTC): adoption applied, first managed session.
- Evidence to read: `SEED_DEMO.done`, `SEED_DEMO.adopt`, `SEED_DEMO.adopt.done` in the demo home; event log lines `DEMO_SEED_START`, `DEMO_SEED_RESULT`, `SESSION_RESULT`; the Boss's Telegram paste.
- Reach check at 13:14 local, on the Boss's instruction: the PM tapped the read-only "Plan adoption (demo)" button through adb. Result on screen and in the event log: `ADOPTION_RESULT trigger=manual status=refused`, "nothing to adopt: empty portfolio". That refusal comes after the portfolio read, so the app reached eToro with the demo home's read credentials, on mobile data, and **the demo account holds no positions** (seed baseline 0). No plan file written, database untouched, flags and alarm unchanged afterwards.
- **Risk seen in the event log:** sessions of 11 and 12 Nov failed at gate 3 (network): the phone could not resolve any host at 20:07 UTC, on battery, in doze. At 13:10 local today Wi-Fi was disconnected and the phone was on another network (mobile). If the network is down at 20:05 UTC the seed's baseline read fails, the flag is burned without buying, and the session fails gate 3. Then the seed needs a new flag at the next plug-in.
- Event log, 6 to 12 Nov: sessions 1, 2, 3 (6, 9, 10 Nov) executed armed with all gates passing; sessions 4, 5 (11, 12 Nov) `preflight_failed` at gate 3.

## Revised delivery requirement — Boss, 2026-11-13

Work strategy rules alongside the dashboard: every implemented strategy rule and safety gate must be visually reflected for monitoring. Deliver paired slices: rule behavior, persisted evaluation evidence, allowlisted export, dashboard display and independent verification. T081's account/session snapshot is only a foundation, not completion of this requirement. T082 records the coupled delivery intake; prepare exact child scopes only after source facts and gaps are verified.

For each rule show evaluated inputs, configured threshold/limit, verdict, reason, session and evaluation timestamp, plus intended action versus confirmed broker result. Show PASS/FAIL only from actual evaluation evidence. Distinguish not applicable, not evaluated, not implemented and unknown/stale; never infer a passing gate from an empty portfolio, absent event or no trade. Preserve rule/session history and visible data age; do not expose identifiers, credentials or raw broker payloads. Presentation must not enable remote order controls.

Coverage checking is incomplete. The 2026-11-13 bounded strategy precheck read the pinned specification and T070–T077 but reported a work-root reach block before reading Nightwatch source. It did not verify the implementation revision or rule coverage. No bypass or alternative worker retry is authorized by that report. T073/T074/T077 remain documented open concerns, not newly source-confirmed findings from this check. Resolve the worker's exact reach setup with the Boss before retrying if needed. Do not claim all strategy rules are complete.

On November 18 the T082 coverage precheck stopped after reporting an actual worker working-directory mismatch (HQ rather than the named Nightwatch root). Its partial source observations do not establish coverage; do not retry through another actor or tool until reach is clarified. T081's distinct dashboard-foundation precheck was completed and its design corrected for local implementation.

On November 13 at 16:49 local the PM entered wrap-up; no further feature build was started that day. The installed a9e4201 demo build and tonight's unattended setup remain unchanged. After the close, collect the Z10 evidence before claiming demo seed/adoption success. Next closed-market work prioritizes verified rule gaps and their dashboard views together, alongside completing lab acceptance; defer the separate USDJPY strategy until current strategy acceptance.

Earlier plan pointer: `handoff-2026-11-13.md` (day plan with fallbacks).

**Standing rule, Boss 2026-11-13: the PM works only while the US market is closed. Anything needing an open market is handed to the Z10 to probe and test by itself; the PM reads the evidence after the close.**

Previous Next line (stale): First armed DEMO session ran on the Z10 on 2026-11-06 (all 12 gates passed, no trade by strategy, Telegram report sent); see `handoff-2026-11-07.md`. Boss: push `d4937e7..5b5f246`, decide T063, then install a `5b5f246` build before Mon 2026-11-09 20:05 UTC.

**Update 2026-11-12 (PM, after the ecosystem review; the "Next" line above is stale).**
- Boss, 2026-11-12, on the sessions of 9, 10 and 11 November: "nothing never place any trade". Recorded as stated: no trade was placed. Whether each session ran, and on which build, is still not recorded here.
- Boss decision: **one dashboard, the cloud page.** The embedded phone dashboard (DESIGN §9.5, `web/app.py`) is not to be built.
- Boss decision: **the lab (`repos/etoro_trader`, board project `trader`) may replay the phone's strategy code as the single implementation.**
- The intended strategy is pinned in `strategy.md` beside this file (supplied by the Boss). It is the reference for tickets, the forward test and the lab replay.
- Review findings N1 to N7 are in `scratch/review-2026-11-12/REPORT-2-etoroNightwatch.md`. None is ticketed yet. Repo HEAD `2483696`, 3 commits unpushed, T079 work uncommitted.

**Single maintained plan.** Moved here from `repos/etoroNightwatch/doc/plan.md` on 2026-09-25 (boss order). Board tickets track execution; this file holds direction, sequence and decisions. Historical handoffs sit next to this file as `handoff-*.md` (archive, not current). Spec of record stays in the repo: `doc/DESIGN.md`, `doc/DESIGN_*.md`, `doc/API_CONTRACTS.md`, runbooks. Section references below to `HANDOFF_*.md` mean the `handoff-*.md` files here.

## 0. Update 2026-09-25 (PM)

- Repo moved to `hq/repos/etoroNightwatch`. `.venv` rebuilt (hygiene/T001); `etoro_trader` sibling copied to `hq/repos/etoro_trader` so the strategy parity oracle runs (hygiene/T003). Old `Documents\ClaudeFiles` copies deleted.
- Suite, both interpreters: **15 failed, 761 passed, 0 skipped** = 09-19 baseline. Same 15 (11 `test_market_bars.py`, 4 `test_probes_order_latency.py`).
- Repo `AGENTS.md`/`CLAUDE.md` deleted (boss order). Temp dirs ignored and cleared (hygiene/T002).
- **T6 (market/T002), resolved 2026-10-09:** demo API orders carry no take-profit (confirmed again by the T012 live probe), but the REAL account's hand-placed UPRO/SCHG positions do (219 of 221 at about 11x). Boss: clear the TP after every buy (S7, trunk/T012). Position `3587941667`, $10 SCHG, open, kept by boss; it is not in the `lots` table.
- New defects: market/T003 (post-fill portfolio lag), market/T004 (config path fixed at first import in a long-lived app process).
- Repo docs still cite `doc/plan.md` / `doc/HANDOFF_*.md` (DESIGN.md:3, :1494; code comments). Stale pointers; fix in S3 commit ticket.
- 2026-09-26 night: S1a (trunk/T001, fresh QA verified), S1b (trunk/T002), S2 green (**780 passed, 0 failed** on `.venv` and base 3.13.4), S3 committed in repo as `40fda33` docs, `81ad0ba` android-probe, `0eb8086` core. Not pushed. Repo refs repointed (hygiene/T004). Next: S4.
- 2026-10-02: eToro DEMO API reachable from this PC (PM shell): one read-only `get_balance()` via `.p1-test-tmp/api_probe.py`, 4.5 s, credit 100001.1, server Date header present. opencode workers cannot reach it (connect timeout, controlroom inbox). Real-API gate work from the PC must run in the PM shell, each call boss-approved.

## 1. Goal

The operator can let Nightwatch run one unattended daily trading session against the real eToro
account and afterwards prove, from persisted evidence, that it either traded as the strategy
intended or refused to trade for a named reason — with no position created that the operator
cannot account for.

Nothing in the repository currently achieves this: the session orchestration does not exist.

**Correction 2026-11-06:** That absence is historical: session orchestration now exists, including dry-run and armed DEMO execution (T015–T018, T030, T038, T042). This does not establish REAL-account readiness; the remaining gates are listed in the readiness audit below.

**Milestone before that (first light):** a *dry-run* session that decides, persists and reports
without ever arming — and that **visibly states arming would be refused** while the risk limits in
§11 are unset.

---

## 2. Current state — observed 2026-09-19

### 2.1 Fact — test suite is RED, on both interpreters

| Interpreter | Result |
|---|---|
| `AppData/Local/Programs/Python/Python313/python.exe` (3.13.4) | **15 failed, 761 passed** |
| `.venv/Scripts/python.exe` (3.13.4) | **15 failed, 761 passed** |

`WindowsApps/python.exe` (3.13.14) has no `pytest` installed and is **not** one of the two
configured interpreters — the second is `.venv`. Record that, so the next session does not
rediscover it.

`HANDOFF_2026-09-18.md` reported "132 tests passed" from a *focused subset* across the eToro
client/contract/close-status suites. That subset excludes `tests/test_market_bars.py` and
`tests/test_probes_order_latency.py`, which is exactly where the breakage is. **The standing rule
in §12.2 — full suite, both interpreters — was not followed, and would have caught this.**

Baseline drift: 712 passed (09-11) → 776 collected today. Test count grew; green did not.

### 2.2 Confirmed — 11 failures in `tests/test_market_bars.py` are **stale fixtures**

- **Symptom:** every bar seed/settle test raises
  `EtoroValidationError: no exact instrument found for symbol 'SPY'`.
- **Divergence point:** `app/src/main/python/nightwatch/etoro/client.py:1005` — the uncommitted
  hardening filters search rows to `row["internalSymbolFull"] == symbol` and raises when none match.
- **Mechanism:** the fake `_search_response` at `tests/test_market_bars.py:82` returns
  `{"instrumentId": 1001, "name": "SPY"}` — no `internalSymbolFull` at all, so the exact filter
  yields an empty list and every dependent test dies at the first HTTP call.
- **Confidence: high.** The error names the filter, the fixture visibly lacks the field, and the
  failure count (11) equals the number of tests routed through `_search_response`.
- **Verdict: product correct, fixture stale.** Exact-symbol filtering is the documented intent (the
  docstring cites `SPY.RTH`/`SPYD` contamination). Do **not** relax the client — that reintroduces a
  fuzzy-match position-identity risk. Test-side fix only.

### 2.3 Confirmed — the 4 probe failures are **NOT test-only**

Operator's correction, and inspection bears it out with a stronger finding than first recorded.

**The two layers, as actually built today:**

| Layer | Behaviour |
|---|---|
| `client.lookup_order(order_id=…)` — `client.py:1529-1548` | v2 `orders:lookup?orderId=` → **on 404, demo-only**, v1 `/trading/info/{demo/}orders/{orderId}`. The 404 is swallowed inside the client. |
| `probes/order_latency._poll_with_transitions` — `order_latency.py:148-168` | catches a 404 escaping `lookup_order` and flips `using_reference_id = True`, then polls v2 by `referenceId`. |

**The unresolved behaviour change:** because the client now absorbs the demo 404 internally, the
probe's `referenceId` leg is **effectively unreachable on demo** and still live on real. The probe
tests assert the pre-change world (a `referenceId` param that no longer appears), which is why they
fail — but the failure is reporting a genuine semantic shift, not a stale string.

**Two further defects found in the same code path:**

1. **`using_reference_id` is sticky.** It is a `nonlocal` flag that is never reset, so once flipped
   every subsequent poll in that leg uses a different route — and nothing records where the switch
   happened.
2. **The route is not attached to the measurement.** `StatusTransition` carries
   `elapsed_since_submission_s` and `raw_lookup_body` but **no route label**. The raw
   `response_capture` entries *do* already carry `path` and `params` (`client.py:329-332`), so the
   information exists — it is simply not bound to the transition that produces the number.

**Consequence — this is the operator's point, confirmed:** a T5 latency figure today cannot be
attributed to a route. A v2 hit, a v1 fallback hit and a referenceId hit are three different
round-trips with three different server paths, and the current trace cannot tell them apart.
**T5's number is ambiguous until this is fixed.**

- Confidence: **high** (read directly from `client.py:1529-1548` and `order_latency.py:148-168`).
- A third, cosmetic failure in this cluster: `expected 'o-open'` → `expected o-open`, because the
  09-18 work dropped `!r` quoting from parser errors. That one *is* test-only.

### 2.4 Fact — the critical path is still empty

- `engine/executor.py` — **18 lines, docstring only.** No `execute()`, no `recover_pending()`.
- `engine/session.py` — **24 lines, docstring only.** No `run_session()`.
- `engine/preflight.py` — 909 lines, but only gates 10 and 11 exist; **no `run_preflight()`
  orchestrator**. Ten gates are comments.
- Consequence, unchanged since 2026-09-06: `order_budget.py` (377 lines) and `reconcile.py`
  (724 lines) are fully written and **inert** — nothing calls them.

### 2.5 Fact — database is unmigrated

`data/nightwatch.db`: `schema_version` = 1; `lots` = 0 rows; `lot_annotations` **does not exist**.
Migrations 002–007 are on disk and unapplied. No downstream behaviour can be exercised against a
realistic 230-position book.

### 2.6 Fact — working tree is large and uncommitted

51 changed/untracked paths; **5,105 insertions / 351 deletions across 23 tracked files**, plus new
untracked files. Last commit `6e33267` (2026-09-06) — **~2 weeks of safety-critical uncommitted
work**, including the parser rewrite that caused both failure clusters above.

### 2.7 Fact — no daily loss guard is active

`max_daily_loss_usd = None`. Three further risk limits are unset (§11). **These are hard blockers
for arming** and must be surfaced by the dry-run, not merely documented here.

### 2.8 Housekeeping done (2026-09-19, non-product)

- Removed 8 empty `tmp*/` and `pytest-cache-files-*/` debris directories.
- Added `tmp*/`, `pytest-cache-files-*/`, `CLAUDE.md` to `.gitignore`.
- Marked the seven historical `HANDOFF_*.md` files superseded; corrected the 09-18 "132 passed".
- `AGENTS.md` and `CLAUDE.md` are byte-identical but for one word (line 258, "Codex"/"Claude");
  `AGENTS.md` is the one to commit.
- **Merged `doc/TODO.md` into this file and deleted it.**

---

## 3. DECISION — order lookup policy *(operator, 2026-09-19)*

Recorded here as the canonical statement. Settle this **before** touching the probe tests.

```
1. v2 by orderId          GET /api/v2/trading/info/{demo/}orders:lookup?orderId=…
2. v1 by orderId          GET /api/v1/trading/info/{demo/}orders/{orderId}
                          DEMO ONLY, read-only, only after step 1 returns 404
3. v2 by referenceId      GET /api/v2/trading/info/{demo/}orders:lookup?referenceId=…
                          ONLY if both 1 and 2 miss
```

**Binding consequences:**

- Step 3 is a **last resort**, not the first fallback. Today's probe reaches it on the *first* 404
  in the real environment — that is now wrong and must change.
- Step 2 is demo-only and **must never** be reachable with a real-environment config. Keep an
  explicit test asserting this.
- **No step may ever trigger a write or a resubmit.** GET only, exact ID only.
- The route escalation must **not** be sticky: each poll re-enters at step 1. A transient 404 must
  not permanently downgrade the leg.
- **Every observation must record which route produced it.** Latency attributed to an unlabelled
  route is not a measurement.

---

## 4. Direction check

**Destination right; sequencing was wrong, and has been for several sessions.**

- The last four sessions were organised around live market windows (T1–T7). Window work is
  calendar-constrained, so it always feels urgent.
- Meanwhile `run_preflight()`, `session.py` and `executor.py` have not moved since 2026-09-06.
  Two are still empty files.
- `order_budget.py` + `reconcile.py` = **1,101 lines of finished, tested, dead code.** That is the
  signature of building leaves before the trunk.

**Dependency truth, traced:** of seven window items only **two** feed the critical path — T5 yields
one number (B4's p95), T6 yields one boolean. B1/B3 and most of B2 are market-independent; they were
never blocked by the window, they were *displaced* by it.

### Alternative routes considered

| Route | Shape | Verdict |
|---|---|---|
| **A. Probe-first (status quo)** | Every session hostage to a 13:30–20:00 UTC window; three windows consumed, trunk unmoved | **Reject.** Empirically the slowest route; it is how we got here. |
| **B. Trunk-first against fixtures** | Decouples ~90 % of remaining work from the market calendar; B4 becomes a one-line drop-in | **Adopt.** |
| **C. Contract-drift first (C1–C6)** | Operator-requested and valuable, but C3 alone is M and it protects code that does not yet run | **Defer** — except **C2** (golden fixtures), nearly free and it supplies the fixtures route B needs. |
| **D. Narrow v1 to observe-and-report** | Session step [7] already defines a no-trade success path; reaches a demonstrable product with zero order risk | **Adopt as the milestone inside B.** Makes B3 optional for first light. |

---

## 5. Scope

**Required now:** S1–S6 below.
**Deferred:** armed execution (S7), C1/C3–C6, the sandbox, §10 cosmetics.
**Out of scope:** any real-money order beyond the single already-authorised $10 T6 probe; inventing
the operator-owned risk limits of §11.

---

## 6. Work plan

### S1a — Settle the lookup policy *(do this first; it is a product decision, not a test fix)*

- **WHAT** Implement §3's three-step order in the real code, de-stick the escalation, and label
  every observation with its route.
- **WHERE** `probes/order_latency.py:148-168` (`_poll_with_transitions`, `using_reference_id`);
  `probes/order_latency.py:72-76` (`StatusTransition`); `client.py:1529-1548` (the v1 fallback).
- **WHY** Without it T5's latency number cannot be attributed to a route, so the headline
  measurement this project has spent three windows chasing would be uninterpretable.
- **HOW** Add a route discriminator (e.g. `v2_order_id` / `v1_order_id_demo` / `v2_reference_id`) to
  `StatusTransition` and to each trace entry, set at the call site that actually produced the
  response. Reorder so `referenceId` is tried only after *both* ID routes miss. Reset the escalation
  per poll. `response_capture` already carries `path` and `params` (`client.py:329-332`) — prefer
  deriving the label there over a parallel flag that can drift.
- **WATCH** The client swallows the demo 404 internally, so the probe cannot see it; do not
  implement step 3 by catching an exception that will never arrive on demo. A sticky flag is what
  made this ambiguous — do not reintroduce one. Never let step 2 be reachable under a real config.
- **PROVE** Tests asserting: the exact three-route order; that step 2 is unreachable when
  `environment = "real"`; that a transient 404 does not permanently downgrade the leg; that every
  `StatusTransition` carries a route label; and that no route issues a write.

### S1b — Refresh the stale fixtures

- **WHAT** Fix the 11 market-bar failures and the one quoting assertion. Test-side only.
- **WHERE** `tests/test_market_bars.py:82`; the `expected 'o-open'` regex.
- **HOW** Emit `internalSymbolFull` matching the queried symbol in `_search_response`. Drop the
  quotes from the regex.
- **WATCH** The temptation to "fix" `client.py:1005`. The hardening is the safety property; the
  tests encode a pre-hardening world. Grep for other suites faking `market-data/search`.
- **PROVE** Confirm the S1 diff leaves `client.py:1005` untouched.

### S2 — Both full suites green

- **PROVE** Full suite, **both** interpreters (`Programs/Python313` and `.venv`), both numbers
  reported verbatim and unrounded. Target: **0 failed on each.** A focused subset is not evidence.

### S3 — Commit the recoverable tree

- **WHAT** Split 5,105 insertions into coherent commits.
- **WHY** Two weeks of unversioned safety-critical work is the largest recoverability risk.
- **HOW** Suggested seams: (a) parser/contract hardening + tests, (b) lookup policy + probe,
  (c) migrations 006/007 + repo, (d) order_budget/contracts, (e) android-probe, (f) docs.
- **WATCH** Exclude ignored `data/`, build output, `CLAUDE.md`. Include `AGENTS.md`.
- **PROVE** `git status --porcelain` shows only ignored paths; suite still green post-commit.

### S4 — Back up, migrate, adopt the database

- **WHAT** Back up via SQLite's backup API, apply 002–007, adopt the 230 live positions.
- **WATCH** Back up **first**. Do this before any T6-created position could enter the snapshot.
- **PROVE** `schema_version` = 7; `lot_annotations` exists; annotation counts, managed/excluded sets
  and foreign keys verified against the 230 known positions.

**Correction 2026-11-06:** Schema 7 and the 230-position count are historical targets. S4 remains pending for the REAL account, but its current target is migration 011 plus adoption of the freshly read real book and an account-bound marker (audit G02); do not assume the old position count or that the real database has already been migrated.

### S5 — `run_preflight()` + gates *(B1)*

- **WHAT** The orchestrator, then gates 1–9 and 12.
- **WHY** This single absence is why 1,101 lines of budget and reconcile code are inert.
- **HOW** Orchestrator first, wired to the two gates that already exist — that alone makes
  `reconcile.py` live and is independently verifiable. Then gates in dependency order.
- **WATCH** Per DESIGN §5 a failed gate holds the wake lock rather than returning.
- **PROVE** A gate failure aborts with the gate named and a `preflight_checks` row persisted;
  gates 10/11 unchanged (regression).

### S6 — Dry-run session, arming disabled *(first light)*

- **WHAT** `run_session()` steps [1]–[7] and [10]–[12], stopping cleanly at the arm gate.
- **WHY** Proves gates, bars, cone, ladder, persistence, notification and scheduling end-to-end
  with **zero** order risk.
- **HOW** The arm gate must evaluate, and report, **two** independent conditions: the operator's
  `is_armed` flag *and* the §11 risk-limit completeness check. Per operator direction, the dry run
  must **visibly report that arming would be refused** while any §11 limit is unset — naming which
  ones. A silent "not armed" is not acceptable output.
- **WATCH** Step [11] must reschedule *before* releasing — a crash there orphans the alarm.
  `create_session`'s UNIQUE constraint must make a double-fire a clean no-op, not an exception.
- **PROVE** Full session on a real trading date with `is_armed = false`: Telegram reports
  "would have done X" **and** the explicit arming-refused reason listing the missing limits; a
  `sessions` row and `decisions` rows persist; the next run is scheduled; the wake lock is released.
  Then kill the process mid-session and confirm a clean restart.

- **PLAN 2026-10-02 (PM, from jack inventory `jack-s6-inventory.out`):** all pieces exist as tested functions with no production caller; `engine/session.py` is a 24-line stub; `cli run` is not implemented. Tiingo and Telegram secrets are present on the PC (presence checked, values not read). Tickets, in order:
  1. trunk/T013: gates 2+3 (needed so preflight can pass at all).
  2. S6a: `run_session(dry_run)` skeleton, idempotent `create_session`, 12-gate list builder, `nightwatch run` CLI.
  3. S6b: fetch (Tiingo history + IEX, eToro rates/candles/portfolio), gate 10 rerun, `assemble_spy_signal`.
  4. S6c: phase A `decide`, arm gate with the 'would have done X' report, a portfolio snapshot taken after the unarmed stop (feeds T010), the Telegram report, and `next_run_at` persisted.
- **PM design calls (doc conflicts found by the inventory):**
  - Wake = T-45 (DESIGN_session §5 says 'T-15' then 'sleep until T-30', which is impossible; read as 15 min before T-30). Preflight runs at wake, then the session sleeps to T-30.
  - The adoption bootstrap [1b] is S4's job (real-account DB), not the PC dry run. Gate 11 on the demo account reports honestly.
  - An unarmed session still writes the snapshot, because it is read-only data.
  - On the desktop, `next_run_at` is computed and persisted, with no OS scheduler; Kotlin owns alarms.

### S7 — Armed execution *(only after S6)*

- **WHAT** B3 (the SCHG lot-selection executor) and B4, then arming.
- **BLOCKED BY** every §11 decision, without exception. These are **hard blockers**, not warnings.
- **HOW** HCBF descending `openRate`, tie-break `position_id`; sell-to-target with the 1.0 % buffer;
  iteration cap; minimum top-up floor (`DESIGN_session.md` §4.3/§4.6.1/§4.8). The spec is
  heterogeneity-aware (§4.9); the built code is size-agnostic — verified 09-11.

---

## 7. Sequence

```
S1a (lookup policy) ─┐
                     ├→ S2 (green ×2) → S3 (commit) → S4 (DB) → S5 (preflight) → S6 (dry run) → S7 (armed)
S1b (fixtures) ──────┘
                        T5 ──→ B4 p95 ┐
                        T6 ──→ TP decision ├→ inputs to S7 only
                        T7 ──→ P1 / C2    ┘
```

S1a before the probe tests are rewritten — otherwise they re-freeze the wrong semantics.
S2 → S3 is strict: never commit a red tree. S4 precedes any realistic verification.
T5/T6/T7 are opportunistic and block nothing before S7. C2 may run any time after S3.

---

## 8. Risks / unknowns

```
If cash_reserve_usd stays 0.0 and the sleeve has no prior-year SCHG values, the ladder treats ALL
broker available cash as sleeve cash. On 2026-10-09 (live demo, $100,001 cash, empty DB) it decided
136 x "open SCHG $666.66" (about $90,700) in one session: budget fell back to 40000 (0.4 x equity),
order_size = 40000/60, and everything above cash_target (8 x order_size) is swept into SCHG.
On the real account this would sweep cash the boss keeps for other assets.
Mitigation: boss sets cash_reserve_usd (sleeve size) and confirms the budget fallback. Before S7, the
executor must enforce max_notional_per_session_usd (5000) against the intents; gate 12 checks the
caps in preflight only.
Trigger: any decision whose summed intents exceed max_notional_per_session_usd.
```

```
If the network's ISP DNS blocks eToro (observed 2026-10-09 on the PC: public-api.etoro.com
and www.etoro.com resolve to internetpositif3.firstmedia.com 202.137.1.74, FirstMedia
"Internet Positif"), every session fails at gate 3/6 and no order can be placed or closed.
Mitigation: boss-controlled VPN or DNS on the PC and on the Android device; gate 3 already fails closed.
Trigger: EtoroTimeoutError / ConnectTimeout on the first eToro call; nslookup shows internetpositif.
```

```
If the probe tests are rewritten before §3's policy is implemented,
they will re-freeze the accidental semantics the 09-18 change introduced,
so S1a precedes S1b's probe half. Trigger: any probe-test edit with no route label in the diff.
```
```
If the route escalation stays sticky or unlabelled,
T5's p95 mixes three different server round-trips into one number and B4 is seeded with a fiction,
so every StatusTransition must carry its route. Trigger: a T5 result with any unlabelled transition.
```
```
If client.py:1005's exact-symbol filter is relaxed to green the bar tests,
fuzzy search rows can select the wrong instrument,
so verify client.py:1005 is untouched in the S1 diff.
```
```
If S3 commits before S2 is green,
a broken baseline becomes the project's history and bisects are useless,
so S3 is gated on two green runs. Trigger to stop: any non-zero failure count.
```
```
If arming is enabled while any §11 limit is unset,
the account runs with no daily loss guard at all,
so §11 blocks S7 absolutely and S6 must report the refusal visibly.
```

**Open unknowns:** the unexplained fee discrepancy (121 trades, `-126.01`; accepted consciously,
off the critical path); the `migrations_run` marker blocking on-device adoption bootstrap; whether
a `PARTIALLY_FILLED` body can be provoked at all (report unobserved rather than fabricate).

---

## 9. Item catalogue — merged from `doc/TODO.md`

Sizes: **S** ≈ under an hour · **M** ≈ a session · **L** ≈ multiple sessions.

### 9.1 Market-window items (T-series) — opportunistic, block nothing before S7

| # | Item | Size |
|---|---|---|
| **T1** | ✅ Device config restored to `"real"`; on-device MD5 `f6aaeb1acb95f3659e866f31fc90ed37` (2026-09-18 16:28 UTC), app force-stopped. | S |
| **T2** | ✅ Demo book verified flat. Close order `382344827` returned `FILLED` after 641.5 ms; independent portfolio read showed 0 positions. | S |
| **T3** | ✅ Updated probe APK built and installed 16:28 UTC. T5 harness not rerun on this build. | S |
| **T4** | ✅ UPRO rates-freeze re-poll: quote age 20.1–29.5 min (mean 24.7), worse than 09-11's mean 23.1. Stale-quote problem persists. | S |
| **T5** | ⚠️ **Incomplete, and now also blocked on S1a.** The 16:16 UTC $50 SCHG open `382257359` filled; v2 returned 404 and the demo v1 fallback returned the legacy `statusID`/`positions` shape. Fill latency 1.371 s is **timestamp-derived**, not a terminal-status transition. The partial-close leg was never exercised. Before resuming: complete S1a, then stage `device_config_before_restore_demo.toml`, verify MD5 `5f0411892139abf50fd7fe3b79814896`, rerun one demo cycle. Never replay an order whose result is unresolved. | M |
| **T6** | ✅ **Done 2026-09-25 (market/T002): API orders get `takeProfitRate 0.0`, `isNoTakeProfit true`.** Original: **The $10 take-profit probe.** One $10 SCHG order, read the position back: `takeProfitRate ≈ openRate × 11`, or `isNoTakeProfit: true`? Settles whether API orders inherit the broker's 11× default (229/230 hand-placed carry one). **Do not guess the suppression field** — candidates `isNoTakeProfit` / `takeProfitRate: null` / `takeProfitPercentage: 0`. **One real $10 probe authorised; not run. One-time gate only, never repeat.** | S |
| **T7** | **Capture the live payload gaps.** Provoke a rejected order on **demo** (sub-minimum size); preserve any `PARTIALLY_FILLED` body; capture a portfolio with a non-empty `orders` array; capture `/market-data/search` exact + fuzzy. Report unreproducible shapes as unobserved rather than fabricating a fixture. | S |

**Fee audit (from the T4 run, read-only):** 121 closed trades, `sum_fees=-506.41` vs `-380.40`
expected (diff `-126.01`); `sum_net_profit=339.21` vs `327.25` (diff `+11.96`). No dividend- or
account-charge-shaped field in the 121 payloads. Unexplained; raw payloads under
`data/probe_2026-09-18/live_probe/`.

### 9.2 Parser / hygiene (P-series) — absorbed into S1–S4

| # | Item | Maps to |
|---|---|---|
| **P1** | Finish the parser audit against `data/probe_2026-09-11/`. Cleared 09-11: `_parse_position`, `_parse_trade_history_entry`, `_parse_candle`, rates, eligibility, instruments, portfolio envelope. **Still unverified: `search_instrument`, `compute_available_cash` per-order fields, rejected/partial bodies** (needs T7). Four parsers were wrong; assume nothing. | after T7 |
| **P2** | Commit the working tree. | **S3** |
| **P3** | Apply migrations 002–007 and adopt the 230 live positions. | **S4** |

---

## 10. Contract-drift detection + Telegram alerting — deferred behind S6, except C2

Operator request, designed not built. Requirements established 09-11; build agent stopped for budget.

| # | Item | Size |
|---|---|---|
| **C1** | Decide the contract representation — per-endpoint required-field-path set vs typed schema. Constraint: adding a parser must *force* declaring its contract, or this rots. Write the decision down before coding. | S |
| **C2** | **Seed golden fixtures** from `data/probe_2026-09-11/` (14 endpoint payloads + order-lookup and close bodies). First ground truth this project has had. **Pull forward — may run any time after S3.** | S |
| **C3** | The checker. Must distinguish *field missing* / *wrong type* / *right type, unexpected shape*. **Must catch both drift from a known-good contract AND a shape that was never right** — all four 09-11 defects were wrong from the start, so a pure "diff against last week" design would have blessed every one. | M |
| **C4** | Per-call-site severity. A violation while placing an order is position-identity-critical and must fail closed; one while reading a quote is advisory. Follow `_parse_order_result`'s existing required-vs-optional precedent. | S |
| **C5** | Telegram alerting + dedup. eToro *adding* a field is not a breakage; a field vanishing or changing type is. Without dedup one break fires ~230 messages. Respect "disabled when secrets absent never raises". | M |
| **C6** | Tests that mutate a golden payload (remove a field, change a type) and assert detection *and* the alert. Then state plainly which of the four 09-11 defects this design would NOT have caught. | S |

---

## 11. Decisions the operator still owes — HARD BLOCKERS for arming

Carried from `HANDOFF_2026-09-07.md` §5; none resolved.

**Operator decided 2026-10-02 (chat):** `max_daily_loss_usd = 500`, `max_notional_per_session_usd = 5000` (confirmed as intended), `max_open_lots = 100` (strategy `MAX_LOTS = 60` stays the tighter bound; this is the backstop), lot-size check **dropped** (no replacement). In config and gate 12 since 2026-10-02 (trunk/T009). **Revised same day after consultant review:** the daily loss guard is **not a halt**. Purpose = catch the app, not the market. Loss is reported every session in $ and %, and $500 is a loud **alert** threshold (trading continues; the operator decides on HALT). **2026-10-07:** loss scope = all UPRO + SCHG positions (hand-placed included), position P&L only (no cash, so deposits/withdrawals/other assets excluded); alerts = A (daily P&L ≤ −$500) + C (market-unexplained loss, default $50, to confirm; C sets HALT, boss 2026-10-07; HALT cleared only by boss via Telegram `/resume <reason>` (trunk/T019); PM never clears HALT); detail in trunk/T010. Halts come only from integrity violations: caps, reconciliation, prices, cash mismatch. trunk/T010. Per operator direction 2026-09-19, these
block S7 absolutely, and **S6's dry run must name the unset ones in its report**.

- **Resolved 2026-10-10:** `config.toml` [risk] sets `max_notional_per_session_usd = 5000.0`, `max_daily_loss_usd = 500.0` (alert A), `max_unexplained_loss_usd = 50.0` (alert C, HALT) and `max_open_lots = 1000` (boss 2026-10-10, was 100; 221 held). Gap: notional and open-lots are **not enforced against intents** (gate 12 marks them evaluated_elsewhere). S7 must enforce them at submission.
  **Correction 2026-11-06:** The unenforced-cap gap is historical: T026 submission controls enforce buy-notional and prospective open-lot caps before buys, wired into armed sessions by T030. The buy cap includes unresolved buy reservations; sells do not count toward buy notional. This is not the session-wide buy+close order ceiling still required by audit G08.
- **The `lot_annotations` units question** — worse under mixed lot sizing: "amount ≠ $500 means
  something is wrong" was a free check and is now gone.

Not arming blockers, but still owed:

- **The `migrations_run` marker** — blocks the on-device adoption bootstrap.
- **Take-profit — RESOLVED 2026-10-09 (see the T6 line at the top and trunk/T012).** History follows. Take-profit suppression — DISPUTED 2026-10-02. Earlier marked "settled 2026-09-25 by T6: API orders carry no TP". Precheck found the code (preflight.py:1076-1080) and DESIGN.md:978-982 still call it unresolved, and DESIGN.md:1503 says the T6 probe was not run. Open: does eToro add its default TP to API-opened positions? Gate 12 reports TPs and never fails on them (trunk/T009). **Operator stated 2026-10-02 (chat): eToro DOES add its automatic take-profit to orders the app places.** Treat it as fact: every app-opened lot carries a broker TP (live evidence: multiple 11.00, i.e. +1000%). Consequence: a TP fill closes a lot outside the app, and gate 11 then hard-fails ('DB lot with no broker position') until a human reconciles. Open for S7: suppress the TP on open (field unknown; position 3550406905 shows `isNoTakeProfit: true` is reachable), or accept it and teach reconciliation to recognise a TP close. **Operator decided 2026-10-02: remove the take-profit when the app opens a position** (trunk/T012).

---

## 12. Deferred, low-stakes, and standing rules

### 12.1 Low-stakes

- `strategy/min_allocation.py:261` — *"Affords N of 60 ladder rungs"* describes a uniform book that
  is not the operator's. Wrong number, display-only, never gates an order. Fix the claim.
- Stale docstrings: `order_budget.py:18-20` calls the book bimodal; it is trimodal.
  `DESIGN_session.md` §4.4's *reason* for rejecting a total-cost-basis sort ("every one opens at
  exactly $50") is now false — the decision stands, the justification must be re-derived.
- `max_lots = 60` is permanently slack under $1,000 lots (dollar ceiling binds at ~30). Record that
  the "both 60s are the same 60" invariant is dead.
- Move `MAX_TICK_DEVIATION_PCT`, `LEVERAGED_TICK_DEVIATION_PCT`, `MIN_PLAUSIBLE_PRICE`,
  `LEVERAGED_SYMBOLS`, `STALE_REFERENCE_TRADING_DAYS` from `market/bars.py` into `RiskConfig`.
  **Fifth session deferring this.** Either do it or strike it from `DESIGN.md` §6.C.
- Warm `exchange_calendars` at wake-service start — 13–19 s cold start per fresh process.
- Per-session telemetry logging `(actual_cash_delta - target)/target`.
- The sandbox (`DESIGN_sandbox.md`) — still design-only.

### 12.2 Standing rules

1. **A parse miss must never produce a plausible value.** Raise, or be visibly absent. The whole
   lesson of 09-11 — five instances in one day.
2. **Run the full suite on both interpreters and report both numbers.** The two are
   `AppData/Local/Programs/Python/Python313/python.exe` and `.venv/Scripts/python.exe` (both
   3.13.4); `WindowsApps/python.exe` has no pytest and is not one of them. Current baseline is
   **RED: 15 failed, 761 passed on both** (2026-09-19). The 09-11 figure of 712 is historical.
   Never round up to a number a document claims, and never accept a focused subset as evidence —
   the 09-18 "132 passed" subset is exactly what let these 15 failures through.
3. **A failure to measure must be reported as loudly as a failure.** A clean run that measured
   nothing is the failure mode this project keeps reinventing. **A measurement that cannot name its
   route counts as a failure to measure** (§3).
4. **Read the book; do not trust a write's return value.** On 09-11 two closes executed server-side
   while the client reported neither.
5. **E2 / real-money orders are never authorised by default** — only by the operator, per instance.

---

## 13. Status

```
[x] S1a lookup policy          — done 2026-09-26 (trunk/T001)
[x] S1b stale fixtures         — done 2026-09-26 (trunk/T002)
[x] S2  both suites green      — 780 passed, 0 failed, both interpreters (2026-09-26)
[x] S3  commit the tree        — 40fda33, 81ad0ba, 0eb8086 (local, not pushed)
[ ] S4  back up, migrate, adopt— blocked on S3
Correction 2026-11-06: S3 is complete, so it no longer blocks S4. REAL-account backup/migrate-to-011/adopt plus an account-bound marker remains pending (audit G02).
[x] S5  run_preflight + gates  — S5a orchestrator, gates 1, 4 (2026-10-01), 5-9 and 12 (2026-10-02) done (trunk/T003-T009; 6-8 live-proven on DEMO from PC); gates 2, 3 built 2026-10-02 (trunk/T013; PC-proven, Z10 device data pending). **All 12 gates built.**
[x] S6  dry run, arming off    — live end to end on DEMO 2026-10-09 (trunk/T015-T018, T021); P&L alerts + HALT (T010, T022), /resume (T019), cash reserve (T023). T022/T023 await a market-hours demo run.
[ ] S7  armed execution        — planning 2026-10-10 (jack-S7 inventory, consultant review); executor not built, session refuses armed configs
Correction 2026-11-06: Armed DEMO execution is built: buys/recovery (T028/T029), session wiring (T030), UPRO closes/two-phase wiring (T036/T038), and SCHG partial closes/session wiring (T041/T042). S7 acceptance is not established: T039 live acceptance and Z10 armed demo proof remain pending; REAL readiness remains gated by the audit below.
[-] T5  close-latency probe    — timestamp-derived only; S1a done, needs device + demo config (see market/T001 gaps)
[x] T6  $10 take-profit probe  — done 2026-09-25, no TP on API orders (market/T002)
[ ] T7  payload gaps           — not run
[x] C2  golden fixtures        — covered 2026-10-08: tests/fixtures/etoro_contracts/ holds 15 sanitized payloads + mutation tests (test_etoro_contracts.py). Raw 09-11 captures under data/ (gitignored) are not on this PC; tests/test_etoro_client.py:514 reads one (suite passes, so it skips or is guarded; unchecked)
[x] housekeeping               — debris removed, .gitignore extended, TODO.md merged (2026-09-19)
[x] hygiene T001–T003          — venv rebuilt, tmp dirs ignored, parity oracle restored (2026-09-25)
```

## S7 plan — approved by the boss 2026-10-10 (consultant review: scratchpad consult-S7.out, jack inventory jack-S7.out)

**Boss decisions 2026-10-10:**
- **A. Cap.** `max_notional_per_session_usd` (5000) counts **buy notional only** per session. Sells do not count. When the ladder wants more, execute **whole buy intents in ladder order** until the cap, drop the rest with a report line, and re-decide next session. Unresolved (in-flight) buys count against the cap across restarts.
- **B. TP removal failure.** The fill is always recorded. If the TP is still present after a bounded retry window, **set HALT and alert**. Never auto-sell.
  **Correction 2026-11-06:** The TP-failure HALT rule above is historical, not the current behavior: T044 makes a failed TP clear veto the final strategy-state save. The fill remains recorded; failure is reported, with no automatic sale or retry. Operator-authorized retry (T049) remains parked pending approval; do not infer HALT from TP-clear failure alone.
- **C. Adopted UPRO `entry_reference_spy`.** Use the SPY close on the position's open date from price history. Where history is missing, armed operation stays blocked until it is resolved.

**Bug found 2026-10-10 (boss question):** `strategy/ladder.py:800` `new_ath_bar = ath > (state.ath or 0.0)`. On a first run (`state.ath` None), any SPY ATH counts as a new ATH, so the ladder sweeps all spare cash into SCHG ("cash to core", `:909–917`). That caused the 2026-10-09 demo's 136 × SCHG. Fix in bootstrap: seed `state.ath` from history on the first run, and do not treat the first bar as a new ATH.

**Order:**
1. S7-0 policy (A/B/C above; single execution owner; state applied from observed fills only).
2. S7-1 order hygiene: non-empty request_id on buy/close; close polling + response-loss recovery via the close route.
3. S7-4 bookkeeping: execution-event ledger (partial closes, so T022 integrity does not false-HALT on app closes); adopted UPRO reference (C); first-run bootstrap (ATH seed bug, adoption).
4. S7-2 submission controls: buy-notional cap with reservations, prospective open lots, cash/eligibility, deadline.
5. S7-3a narrow buy executor: one demo SCHG buy at the minimum, one-order ceiling, fill → annotate → clear TP → verify → state → post-execution snapshot; restart proves zero duplicate submissions.
6. S7-3b closes + two-phase (sells → reread → buys; one day advancement).
7. S7-5 real TP contract (docs blocked by ISP DNS; boss screenshot or DoH).
8. S7-6 acceptance by cases on demo (buy, full close, partial close, sell-funded buy, crash recovery, TP failure), then a real pilot with explicit boss limits.

## Where we stopped (2026-10-10, Saturday)
- **S7 done so far:**
  - T024 order hygiene;
  - T026 submission limits + `max_open_lots` 1000;
  - T027 adopted UPRO reference (decision C);
  - T025 first-run ATH fix (verify: needs a demo run).

  All committed locally in the repo (a112885, 7a61a56, f47b49c, 8a681ba). **Not pushed.**
- **Waiting for market hours (Mon 13:30 UTC):** one demo dry run on a fresh temp DB (`.p1-test-tmp/s6c_live.py`; it needs `doh_pin` while the ISP DNS block lasts). It proves:
  - T022: first run "interval: no baseline"; a seeded prev gives complete, $0.00;
  - T023: sleeve = available − 5000;
  - T025: no cash-to-core SCHG sweep.
- **Next ticket: S7-3a narrow buy executor.** One demo SCHG buy at the minimum, a one-order ceiling, then:
  1. Intent;
  2. buy, poll;
  3. Order + fill;
  4. annotation;
  5. clear TP + read-back;
  6. state for what filled;
  7. post-execution snapshot;
  8. restart recovery with zero resubmits.

  A jack code-fact inventory was dispatched 2026-10-10 (copied to `hq/scratch/nightwatch/jack-S73a.out` with `consult-S7.out` and `jack-S7.out`). The live proof needs one boss-approved demo order.
- **Blocked:**
  - Partial-close ledger (S7-4): needs one boss-approved demo partial close to observe how eToro reports it.
  - Real TP path (S7-5): api-portal.etoro.com is DNS-blocked here; the boss's screenshot or Windows DoH is needed.
- **Open friction:** controlroom inbox, the deny-bash word filter and the dispatch export timeout.

## Boss 2026-10-16
Boss approved one DEMO SCHG buy for the first armed executor run (S7-3a acceptance, via T028/T030, order about $633 at the ladder order size, one-order ceiling, TP cleared right after). Runs once T028-T030 are built; provider login (token_revoked) must be fixed first.

## Real-account TP path confirmed 2026-10-16
eToro docs (api-portal.etoro.com, read in the browser after the boss enabled DNS-over-HTTPS): real = `PATCH /api/v2/trading/positions/{positionId}`, demo = `PATCH /api/v2/trading/demo/positions/{positionId}`; same description, options `clearTakeProfit`/`clearStopLoss`, default 60/60s quota, asynchronous. S7-5 = lift the real-path refusal in `EtoroClient.clear_take_profit` (demo-only today), test offline, then prove on real only with boss go.

## Where we stopped (2026-10-16, end of day)
- T028 (executor core, 7604e2d) and T029 (crash recovery, df3ec7a) done, committed locally in the NIGHTWATCH repo, NOT pushed. Pushed through 8a681ba. Both suites 1171 passed.
- Built by Claude Haiku 5.5 medium subagents because opencode workers are down (provider 401 token_revoked). opencode.json unchanged. Boss will re-login to the OpenAI provider another time.
- Next: write T030 (session wiring: recover_unfinished before gate 11, apply limits, execute_buys with deadline close minus 5 min, narrow state-save rule, HALT on tp_failed, post-execution snapshot, arming_refusals incl. max_orders_per_session), precheck, build, verify. Then announce and run the single approved DEMO SCHG buy (about $633) in market hours, DoH on.
- Open: abandoned intents reserve cap only for their own date (late fill adopted by reconcile); clear command and cross-date reservation are future items. S7-4 partial close needs a boss-approved demo partial close. S7-5 lifts real TP refusal.
- Awaiting boss: push approval for T028/T029 commits; opencode re-login.

## Where we stopped (2026-10-23, overnight PM)
- Boss 2026-10-23: CH Fun only (CR retired), no opencode, demo account use is free, full auto.
- `hq/repos/etoroNightwatch` is now a real git repo: history fetched from the CR clone (HEAD df3ec7a), 41 missing tracked files restored, origin = GitHub, `.venv` rebuilt (Python 3.13). `data/nightwatch.db` moved over, plus the one test fixture `data/probe_2026-09-11/order_latency_run2`. Commit branch override `repos/etoroNightwatch: main` in `hq/config/commit-branches.json`.
- T030 committed `55da9bb` (not pushed). Suite: 1221 passed, full (2026-10-24, after MANAGER restored the 1296 missing tracked files in `hq/repos/etoro_trader`).
- **Live demo blocked from this PC:** system DNS returns the Kominfo sinkhole (even via 1.1.1.1). DoH gives the real Cloudflare IPs, but TLS with SNI `public-api.etoro.com` times out while TLS without SNI works, so the block is SNI/DPI. A dry run fails at gate 3. No VPN/SNI evasion attempted. No Android device attached (`adb devices` empty). Needed: a device with Private DNS on, or a network without the filter.
- T031 blocked (classifier denied removing the real-account TP refusal); its partial edits stay only in the retired CR tree.
- Next once eToro is reachable: dry run on a scratch DB copy, then the armed DEMO run (`mode="live"`, `NIGHTWATCH_ARM`) in market hours. Offline: S7-3b (closes + two-phase) design ticket.

## eToro reachable again (2026-10-24)
- Read-only demo `get_balance()` OK in 3.3 s (available_cash 100001.52) through the app client.
- Recipe: Fortinet SSL VPN up (route works with real SNI); resolve `*.etoro.com` via DoH (ISP DNS returns `trustpositif.moratelindo.io` sinkhole); run with HTTP(S)_PROXY unset (the shell's local proxy 127.0.0.1:8790 breaks it). Launchers: PM scratchpad `nw_doh_run.py` / `nw_doh_balance.py`. Should become a repo dev tool (ticket).
- Saturday: market closed. Close experiment A and the armed demo run need US market hours (Mon 2026-10-26, 13:30–20:00 UTC).

## 2026-10-24 build day
- Done and committed on `main` (not pushed): T034 `22fa718` (migration 009: per-phase decisions plus close-observation ledger), T035 `cc1437a` (UPRO buys, explicit bucket_id), T036 `ef30b78` (UPRO full-close executor, strict absence read, never resends), T037 tool `943afc7` (demo close experiment). Suite 1345 passed on both interpreters; independent QA PASS on all four.
- `data/nightwatch.db` backed up as `data/nightwatch.db.bak-pre009-2026-10-24` before its first run under 009.
- **Monday 2026-10-26 runbook (US session 13:30–20:00 UTC):**
  1. Fortinet VPN up; confirm with `nw_doh_balance.py` (DoH, proxy env unset).
  2. `tools/demo_close_experiment.py --steps 1,2,3,4,5 --dry-plan`, then the live run through the same DoH/no-proxy launcher. Fixtures go to `tests/fixtures/etoro_contracts/`; check leftovers are empty.
  3. Close T037 on the observed evidence; decide whether partial closes (G) and close reference recovery are viable.
- Next tickets: E (two-phase session wiring: UPRO closes → strict fresh portfolio → cash reread → phase B → buys; SCHG sells refused; T036 low findings), F (demo acceptance cases), and a repo dev tool for the DoH/no-proxy launcher.

## T038 done (2026-10-26) — commit 34e9e3e on main, not pushed
- Armed session: gate 11 recovers closes then buys; UPRO full closes run first, then pre-close-eligible buys sized against re-read cash. SCHG sells and any unsupported intent refuse the whole session before any order.
- Migration 010: `sale_effects` (one row per position, upserted until confirmed, credited exactly once on confirmed_full_close) and `bucket_fill_applications` (one per reentry fill intent).
- Decision: buys that only the sale's proceeds could fund wait for the next session (no second decide).
- Armed requires fixed exit mode; trail_state is not persisted.
- Suite 1406 passed on both interpreters; parity passes (not skipped). QA PASS after one retry-lockout fix.
- Known limits carried: gate 11 does not verify quantities after partial closes; partial SCHG fill recyclable-cash earmark gap.
- Next: T037 live demo run (Mon 13:30-20:00 UTC, VPN + DoH launcher), then F (demo acceptance).

## T040 + T039 done (2026-10-26) — commits 27bf51f, T039 on main, not pushed
- T040: phone alarm runs the real session as a dry run only (android_entry.run_session_dry). Z10 device proof (alarms, kill/restart, overlap, Doze) still pending; power gating, Kotlin HALT link and market-aware alarm scheduling are known gaps.
- T039: tools/demo_acceptance.py. Live run is PM-run after T037 in market hours, via the proxy route (keep HTTP(S)_PROXY; the Fortinet VPN is not needed).
- T039 accepted LOW sanitizer residuals: a token 4x percent-encoded inside a URL path, fullwidth-colon labels, a label and its value split across separate JSON fields. Evidence stays local and is never attached raw.
- Suite: 1518 passed on both interpreters.

## Overnight 2026-10-30/31 (PM full auto)
- Done and committed on `main`:
  - T031 `0c807e4` and T037 `001e2be`, both pushed;
  - lock-test deflake `6f94702`;
  - G: T041 `6f674f2` (SCHG partial-close executor, migration 011), T043 `97b852e` (interval evidence and modelled-subset residual), T042 `a8e45da` (armed session runs SCHG sells);
  - T044 `808c2d9` (a failed TP clear vetoes the final save; automatic retry deferred);
  - Android: T045 `25e332f` (market-aware alarms, HALT latch) and T046 `e15e1d8` (battery gate, 33 JVM tests).
  
  Everything after `001e2be` is NOT pushed.
- T047 (a network failure before any order ends the session cleanly; precise send-risk evidence) is built, 1810 passed on both interpreters, and is in QA.
- T037 live findings (Boss accepted):
  - lookup by our referenceId returns 404;
  - a partial close returns two position IDs: the original keeps its ID and the other is the closed slice;
  - portfolio and lookups lag fills by seconds to minutes.
- T039 live acceptance has NOT passed:
  - Run 1 was killed at 16:36 UTC by a builder's blanket `taskkill` on python.exe. Builders are now told never to kill processes they did not start.
  - Run 2 passed preflight at 16:37, slept until close-30, then hit an eToro network SSL EOF at 19:30 and the session escaped with an exception. The run DB has 0 intents, orders and decisions, so nothing was sent; the account was flat before the run. eToro was still unreachable at 19:37.
  - T047 fixes the escaped exception. Rerun T039 on the next trading day, with T047 committed.
- Z10:
  - The offline build failed because Gradle had pruned the Chaquopy 3.13 runtime from its cache; earlier builds ran online.
  - The Boss approved online Gradle. The APK now builds and includes T045+T046.
  - Device proof (install, dry session, alarms, HALT, power) is still pending: the phone was unplugged.
- Deferred follow-ups:
  - operator-authorized retry of failed TP clears, with ownership binding, per-run dedupe and a durable budget;
  - inner eToro/Tiingo retries are not bound by the close-25 cutoff;
  - the broker's $10 remainder-gate basis is unverified;
  - AGP 8.9 is tested only through compileSdk 35, while the app targets 36.
- Next: QA and commit T047. Then, with the Boss, push, do the Z10 device proof, and rerun T039 in market hours.
- Update 2026-10-31 early: T047 `8174e66` (a network failure before any order ends the session cleanly; DB-derived send risk) and T048 `d4937e7` (every outcome, HALT reason and notification redacted; alerts driven by structured flags) are done and committed. Suite 1861 passed on both interpreters. The APK has been rebuilt with all of tonight's code. Not pushed.
- T049 (operator-authorized retry of failed TP clears) is written and prechecked, with the fixes amended in. It is parked in backlog: it NEEDS BOSS APPROVAL because it adds a Telegram command that authorizes broker writes.
- Waiting on the Boss: push `001e2be..d4937e7` (8 commits); Z10 device proof with the rebuilt APK; T039 rerun in market hours; approve or reject T049.

## Market-open runbook (written 2026-11-06, market closed, Z10 unplugged)
**Correction 2026-11-06:** The earlier fixed 20:00 UTC close and d4937e7-based no-rebuild assumption are superseded by the calendar-derived times and HEAD provenance checks below. Historical run times elsewhere remain historical.
Do in this order on the next trading day. Read that trading date's close from the exchange calendar (21:00 UTC during EST on a regular full session; early closes differ); session wakes at close-55, orders cutoff close-25.
1. Preflight, before close-60 (20:00 UTC for a regular EST session): run `git -C repos/etoroNightwatch status`; it must be clean. Record the current HEAD used for this run. Keep HTTP(S)_PROXY set; VPN is not needed. Run the `nw_doh_balance.py` and `nw_portfolio.py` scratch scripts with `PYTHONPATH=app/src/main/python` and check the demo account is reachable and flat.
2. Run `tools/demo_acceptance.py --dry-plan --config <demo cfg>`. It makes no network calls and every refusal check must pass.
3. Start the live T039 run before close-60 in the background. Never taskkill python. Builders must not run at the same time as it.
4. After the run, check the evidence bundle: exit code, intents and orders in the run DB, and redacted alerts. If any position is left over, close it with `nw_close3.py` and record that.
5. Z10, any time the phone is plugged in: verify the APK build provenance includes the recorded current HEAD; if stale or unverified, rebuild from that clean HEAD before installing with `adb install -r`. Confirm the installed APK is that build before the dry session, alarm at close-55, HALT latch, battery gate and kill/restart checks. A prior build at `d4937e7` is not evidence that the installed APK includes HEAD.
6. Pass: move T039 to done with a note and update T040 with the device-proof result. Fail: open a ticket with the evidence summary and never attach raw evidence.
## Real-account readiness audit (2026-11-06, Sol high, static at 21c06ba)
- Built, so not to be reopened:
  - notional and open-lot caps before buys;
  - real/demo routing with gate-7 evidence;
  - real TP PATCH;
  - market alarms and the power gate (device-unverified).
- P0 before any REAL run:
  - G01: Android REAL armed entry (T054 is demo only).
  - G02: S4 backup/migrate-to-011/adopt the real book, plus an account-bound marker.
  - G03: secure real credential provisioning and a hardened build.
  - G04: one Telegram/Kotlin HALT-resume path that stays reachable while halted.
  - G05: crash recovery before the gate-5 unfinished-session refusal.
  - G06: durable fill finalization (intent resolved before annotation; no further sends on missing identity).
  - G07: gate-11 reconciliation adoptions persisted.
  - G08: a session-wide buy+close order ceiling for the pilot.
  - G09: the $10 remainder basis, or fence partial closes.
  - G10: Z10 armed demo acceptance, then a bounded real pilot.
- P1 before unattended daily:
  - G11: pending-slot reservation, fresh eligibility and cash at send.
  - G12: quantity integrity and durable post-send evidence.
  - G13: strategy-state progress under capped execution; budget history wiring.
  - G14: T052 plus deadline terminology.
  - G15: redact FCM, snapshot and client-fallback logs.
  - G16: `/positions` on `lot_annotations`, next-run report at close-55, heartbeat, drift notifier.
- P2:
  - G17: AGP/compileSdk;
  - G18: stale board claims (lines 29, 429, 487, 253-256, 500, and the runbook's 20:00 UTC).
- Order: G18, G03+G15, G02, G05→G06→G07, G04+G08, G11+G12+G14, G09, G01, G10, G13+G16, G17.
- Today's armed demo run on Z10 (T054) knowingly carries the G05/G06/G08 risks. Demo only.