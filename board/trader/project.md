---
name: "eToro Trader Lab"
state: active
summary: "Strategy lab: test any strategy on real, alternative-history and null markets, and watch it trade on a dashboard."
repo: "repos/etoro_trader"
---
# eToro Trader Lab: plan

Next: T009 mandate headline, followed by T010 repository hygiene. T001–T008 are accepted and committed locally. T008 (`4098ef7` on main) passed 379 tests and the end-to-end custom-settings and strategy-error browser checks; the default replay matched the pre-change equity hash and all 131 orders. T007 (`9d8592a` on main) passed the independent fan-chart journey and PM native saved-run deletion check, including 1,575 px page height with 443 orders. T008–T010 designs were corrected after precheck. T005 remains accepted (`c83f6de` on main). T005 passed independent socket HTTP, restart, cancellation, determinism and concurrency checks; PM reran 123 tests and the 104-file import check successfully. QA measured 8.563 seconds/path for ten synthetic std_band_ladder paths and worst health latency 0.371 seconds; builder's different run measured 18.1 to 21.5 seconds/path, so use strategy-specific timing rather than a universal estimate. The full T007 browser journey reserves at least 30 minutes. Wrap up at 16:45 local and stop at 17:00; PM works only while the US market is closed. The `etoro_trader` clone still has **no git remote configured**, so its commits cannot be pushed until the Boss names a remote. Nightwatch main was pushed through a9e4201. The full day plan remains `../nightwatch/handoff-2026-11-13.md`.

Earlier: T001 is ready (2026-11-13; fact-checked by the PM against `8505b62` after the precheck agent stalled with no output). T002 has full Design and Plan; its precheck was still running on 2026-11-13 and it moves to ready only after T001 is done (same file). Boss still owes decisions 1 and 2. No builder has been dispatched.

Created 2026-11-12 after the ecosystem review. The review is the source for every claim here: `scratch/review-2026-11-12/REPORT-1-etoro_trader.md` (findings F1 to F7, UI specification in its section 8).

## Goal

The README's prime directive: a tool to try any trading strategy in a realistically simulated market, with results that can be trusted. The Boss's request of 2026-11-12 adds the surface: a dashboard showing the strategy in action, the portfolio and the history, in the style of the reference video, with synthetic market data built the way the video builds it.

## Reality on 2026-11-12 (HEAD `e392be2`, branch `main`)

- The engine works: 23 strategies, 12 indicators, mandate gates, 128 of 128 tests pass.
- The lab page is one replay screen. It keeps no runs (the server deletes them at start), opens on an almost empty chart and offers only the `std_band_*` family at a fixed 10,000 dollars.
- Real-market data needs Snowflake credentials. The synthetic market is GARCH, which the project's own measurements say cannot test dip-buying.
- The 2026-08-24 plan (`doc/architecture_plan_v0.2.0.md`) that would fix this was not built.
- The replay endpoint can read any `.json` file on the machine and the server listens on all interfaces.
- 12 uncommitted paths have sat in the checkout since October, including the untracked strategy file that Nightwatch was ported from.

## Scope

In: the lab web server and page, the market-data sources for the lab, strategy discovery, the mandate headline, repository hygiene.

Out: strategy research and new strategies; the `ai/` training pipeline; the six legacy strategies and `/api/run` (kept as they are until the Boss decides); anything in `repos/etoroNightwatch`; any live or demo broker connection.

## Acceptance for the project

1. A new strategy appears in the lab after adding one file.
2. A run can be found again after a restart.
3. One screen shows growth of 1 dollar, positions and order history at a chosen date.
4. One action runs a strategy over N alternative histories built from real data and reports median, worst, best and how often it beat the benchmark.
5. Every result names the kind of market that produced it.
6. The server exposes nothing outside its own files and is reachable only from this machine.

## Phases and tickets (epic `lab`)

| Phase | Tickets | Depends on |
|---|---|---|
| 1. Safe and persistent | T001 server exposure, T002 run store | none |
| 2. Trustworthy market | T003 local real data, T004 block bootstrap | Boss decision 1; T004 needs T003 |
| 3. See it in action | T006 dashboard, T005 many-paths job, T007 fan chart | T002; T007 needs T005 and T006 |
| 4. Any strategy | T008 auto-discovery and run settings | none; touches the registry Nightwatch's parity test imports |
| 5. Honest verdict and tidy | T009 mandate headline, T010 documents and stray files | Boss decisions 2 and 3 |

T001 and T002 can start first and in parallel only if their edits to `web/server.py` are sequenced: T001 first, then T002. T006 and T005 both touch `web/server.py` too; one writer at a time on that file.

All ten tickets are in backlog with Outcome, Scope, Acceptance and Prove. Design, Plan, Ripple effects and Watch are still to be written by the PM and prechecked before any ticket moves to ready.

## Bootstrap realism result, 2026-11-13 (T004)

Real cache 2010-01-04..2026-08-21, 4,184 SPY rows.

- **The ticket's generic test** (5-day return after a daily fall beyond 2 sigma of the last 60 days): real SPY lift is **-0.07 percentage points** (162 events, t -0.27). No rebound by that definition in this history, so T004's three gates are "not applicable". The August plan's +0.72 pp (t 2.86) is not reproduced here; its definition and period are not recorded.
- **PM check with the strategy's own buy signal** (`cone_5_z < -2`: 5-day return divided by the standard deviation of the last 260 five-day returns), scratch script, not committed:

| Market | Lift 5 days after signal | Lift 20 days after signal |
|---|---|---|
| Real SPY (118 events) | +0.52 pp | +1.34 pp |
| Bootstrap, 1-month blocks (100 paths) | +0.69 pp | +0.83 pp |
| Bootstrap, 6-month blocks (100 paths) | +0.87 pp | +1.44 pp |
| Bootstrap, 3-year blocks (100 paths) | +0.70 pp | +1.37 pp |
| GARCH (30 paths) | +0.37 pp, not distinguishable from zero | +0.79 pp, not distinguishable from zero |

Reading: on the signal the phone actually trades, real history shows a rebound, the 6-month and 3-year bootstraps keep it at about the real size over 20 days (ratios 1.07 and 1.02), the 1-month bootstrap loses about a third of it, and GARCH shows none that can be told from noise. The real-history t values are inflated by overlapping windows and are not quoted as evidence.

**DECIDED by the Boss, 2026-11-13: the strategy-signal measure is accepted as the bootstrap's gate.** "Alt. histories" ships in the dashboard (T007) with 6-month blocks as the default and 1-month blocks labelled as weaker. Still owed: the measure exists only as a PM scratch script; it must be added to `scripts/study_bootstrap_rebound.py` with a test so the gate is reproducible (follow-up to T004, not yet ticketed), and its numbers have not been checked by independent QA.

## Decisions needed from the Boss

1. **Real-data source. ANSWERED 2026-11-13 by the Boss: "the lab may even use the available credential data".** The lab's own loader may use the Snowflake connection; the PM and workers still never open or print the credential files. Original question: May the lab use a local, credential-free daily price file, and which public source may the one-off fetch script download from? (T003, blocks T004.)
2. **Mandate. DECIDED by the Boss, 2026-11-13: headline only.** No absolute-loss gate. T009's design is for this option. Original question: Change only the headline (recommended) or add an absolute-loss gate? (T009.)
3. **Pending work in the checkout.** Boss, 2026-11-12: "forget about the uncommitted paths if not needed". PM check the same day: they **are needed**, so nothing was discarded. Nightwatch's parity test imports the untracked `std_band_ladder_cash_recycle.py` and the modified `std_band_ladder_martingale.py`; the registry edit registers that strategy; the `web/` and `replay_runner.py` edits are the lab as it runs today. All 128 tests pass on this exact tree (scratch copy, 2026-11-12). **DONE 2026-11-12: committed unchanged to `main` as baseline `8505b62` on the Boss's go-ahead; tree clean; not pushed.** Original question: commit, branch or discard the 12 uncommitted paths. Builders should not start in a dirty tree, and the cash-recycle strategy file should be under version control. (T010 and every other ticket.)
4. **Commit branch. DECIDED 2026-11-12 by the Boss: `main`.** Override added to `config/commit-branches.json`.

**Decided 2026-11-12 by the Boss: the lab may replay Nightwatch's production strategy code as the single implementation** (review N3 and N4 in `scratch/review-2026-11-12/REPORT-2-etoroNightwatch.md`). The intended strategy is pinned at `board/nightwatch/strategy.md`. Not ticketed yet; it needs a design pass on how the lab imports `nightwatch.strategy.ladder` without the two repositories depending on each other's internals.

Also open, not blocking: retire or keep the old "Strategy VCR" page once the dashboard exists; retire or port the six legacy strategies.

## Risks and unknowns

- The block bootstrap's realism gate (rebound statistic near real SPY) is unproven until real data is available. If it fails, phase 2 needs a redesign before phase 3's fan chart means anything.
- Tapes are about 20 MB for 5 years. The run store and the many-paths job must not multiply that.
- The open chart bug from `doc/HANDOFF_2026-08-28.md` section 1 was neither reproduced nor disproved. The new dashboard replaces that chart code; if the old page is kept, the bug stays open.
- Review prototypes in `scratch/review-etoro-trader-20261112` are throwaway references, not designs to copy.

## Ideas kept, not ticketed

A no-code rule builder for simple timing rules (moving average, buffer band, buy the crash, volatility gate), a crash-replay library, price history back to 2000 with synthesized leveraged funds, a same-average-exposure benchmark. The last three are phases 3, 4 and 6 of the August plan.
