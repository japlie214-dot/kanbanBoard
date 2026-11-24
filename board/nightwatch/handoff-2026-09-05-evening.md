> **Historical handoff — superseded by `doc/plan.md` (2026-09-19). Do not treat as current.**

# etoroNightwatch — Handoff: the day the code met live data

**Date:** 2026-09-05 (Saturday, US market closed)
**From:** a session that ran the probe on the physical device four times, settled the fee
question, built the window assembly, and found two bugs in it within minutes of its first
contact with a real payload.
**To:** whoever builds the gates, the strategy modules, or runs the migration.

Supersedes nothing in `HANDOFF_2026-09-05.md` except where stated; that document remains the map
of the parser-bug pattern. Read `FINDINGS_fees_2026-09-05.md` and
`FINDINGS_window_live_2026-09-05.md` in full before touching `market/` or any P&L surface.

---

## 1. The one lesson worth carrying forward

`get_trade_history` had a guard written specifically to handle a bare-list payload, and the guard
**could not fire** — `data.get(...)` was evaluated before its own `isinstance` fallback. It also
had a test named *"matching the live probe exactly"* that wrapped its rows in the wrong envelope.
**The code and the test encoded the same wrong assumption, agreed with each other, and the suite
stayed green.** Only a real payload broke the tie.

That is now **five** parser bugs of one family in three days. And within an hour of `window.py`
first meeting live data, it produced two more bugs of a different family. The rule this project
has earned: **a green suite is evidence about your fixtures, not about eToro.**

---

## 2. Status — what is proven, and by what

| Item | Status | Evidence |
|---|---|---|
| Chaquopy runtime on the z10 (numpy 1.26.2, pandas 2.1.3, exchange_calendars 4.11.1, httpx 0.27.2) | ✅ **proven on-device** | probe section A, ran and computed |
| SPY resolves on eToro; candle fallback exists for it | ✅ proven live (was unknown) | section F |
| Window completeness vs the real XNYS calendar | ✅ 276 sessions, exact match, none missing/unexpected | section F |
| A real `cone_5_z` end to end | ✅ 0.2426, ATH 777.88, dd −0.99%, tier 0 | section F |
| `cone_5_z` matches the backtested signal | ✅ verified algebraically vs `expected_move_cone(center_mode="close")` | this session |
| Fee model | ✅ settled across all 120 closed trades | `FINDINGS_fees_2026-09-05.md` |
| Sleeve arithmetic (SCHG $44,866.97, UPRO $4,046.98, equity $50,178.53) | ✅ re-measured live, matches §10.11 exactly | section D |
| Five eToro parser bugs | ✅ fixed, tested | `etoro/client.py` |
| **ATH is a 276-bar high, not all-time** | ✅ **FIXED** (2026-09-05, superseded twice — see §3) | `market/window.py`'s fetch now covers full history from `FULL_HISTORY_START_DATE` ("2010-01-01"); the rolling ATH is the full-history ATH by construction, every session |
| **`adjClose` vs raw `close` bases mixed incoherently** | ✅ **FIXED** | `market/window.py`'s `_spy_context_with_provisional` (raw `close` for ATH/drawdown/tier, `adj_close` for `cone_5_z`) and `market/adopt.py`'s `SpyContext`/`build_spy_context_index` (raw `close` throughout) — matches §4's table exactly |
| Gates 1–9, 11, 12 + `run_preflight` | ❌ comment-only stubs | `engine/preflight.py` |
| Gate 10 items 2, 4, 5 | ❌ unbuilt (item 2 now unblocked) | |
| `strategy/ladder.py`, `state.py`, `engine/session.py` | ❌ stubs | |
| Adoption migration run against the live account | ❌ never run (DCA stopped, so unblocked) | |
| Forward-test harness / fake broker | ❌ unbuilt | |
| UPRO rates-freeze re-poll | ❌ needs an open market — **Friday 2026-09-11** | |
| Everything else in `window.py` / `cone.py` against live data | ⚠️ section F is the ONLY live exercise; the rest is fakes | |

Tests: **495 passed** (from 392 at session start). **Update, 2026-09-05 (later the same day):
509 passed** — verified by running the suite after the window/basis/floor fixes below landed.

---

## 3. BUG 1 — the ATH window. Fix this first.

`market/window.py:417-431` takes `max(adj_close)` over the fetched window (276 bars ≈ 13 months).
The strategy it was ported from accumulates a running max over its **whole** dataset.

The error runs in the dangerous direction: a peak that ages out of the window makes drawdown read
shallower, the tier read lower, and `TIER_CAPS` (cumulative budget ceilings) permit **less**
capital precisely in the prolonged drawdowns the deep tiers exist for.

**Decided 2026-09-05: use a 39-month (819-bar) window.** ~~**SUPERSEDED, 2026-09-05, a few
hours after this was written (§7):** the operator aborted the 39-month window and replaced it
with full history fetched from `FULL_HISTORY_START_DATE` ("2010-01-01"), because Tiingo's real
free-tier ceiling is **1 GB/month bandwidth** (also 1000 req/day, 50/hour, 500 symbols/month),
and full history costs ~43 MB/month ≈ 4.2% of that ceiling — there was never a bandwidth reason
to accept a rolling window's blind spot at all. The measurement table below is unchanged and
remains real, measured evidence for why a *short* window (276/504 bars) was wrong; only the
*conclusion drawn from it* (819 bars vs. full history) changed, not the data itself.~~
Measured on 4,184 SPY bars (2010–2026):

| window | months | bytes/fetch | dd understated | tier differs | max gap |
|---|---|---|---|---|---|
| 276 | 13 | 94 KB | 5.93% | 1.60% | 10.04 pp |
| 504 | 24 | 171 KB | 0.22% | 0.00% | 0.21 pp |
| **819** | **39** | **278 KB** | **0.00%** | **0.00%** | **0.00** |
| 4184 | all | 1.42 MB | 0.00% | 0.00% | 0.00 |

39 months reproduces the full-history ATH exactly, at one fifth the bandwidth.

**A second, independent reason for 39 months — positions open above the rolling ATH.** The
operator asked for this explicitly, and it turned out to matter more than the ATH accuracy did:

| window | SCHG positions opened before the window starts | stranded cost basis |
|---|---|---|
| 13 mo | **72 of 202** | $5,220 |
| 24 mo | 4 | $40 |
| **39 mo** | **0** | **$0** |

The adoption migration reconstructs `entry_spy_ath` / `entry_tier` from SPY context *at each
position's open date*. With a 13-month window that is impossible for **36% of the SCHG book** —
the migration would have mis-tiered or failed on 72 positions. At 39 months coverage is complete
with 456 days of margin (oldest position 731 d, window 1,187 d). **A 13-month window is
insufficient for the migration itself, independent of the ATH question.**

**Do NOT fix this by persisting a running ATH across sessions.** That reintroduces the accumulated
state `DESIGN_market_data.md` §2.2 exists to prevent, and a stored ATH from an older
dividend-adjustment epoch would be in stale units. Extend the single fetch — one fetch is still
one epoch.

**Update, 2026-09-05 (later the same day): a narrow, rigorous exception is now designed (not
built) in `doc/DESIGN_ath_staircase.md`.** This prohibition still stands as the default — do not
persist a running ATH over adjusted prices. The staircase design is a different, more specific
thing: a monotone list of raw-`close` new-highs only, argued to be legitimate precisely because
(a) raw `close` is never retroactively revised the way `adjClose` is, and (b) a max over
*closed* history is a re-derivable, verifiable cache, not drifting accumulated state — see that
document's §3 for the full argument and §5 for how it stays checked against a fresh fetch. It is
explicitly gated behind a bandwidth trigger (its §7: build only if Tiingo's free tier drops below
~215 MB/month) that is nowhere near firing today (~43 MB/month, ~4.2% of the current 1 GB
ceiling) — it is insurance, not a pending change to this prohibition.

**Known limit of the measurement:** the dataset starts in 2010, so it cannot test 2008 (peak
Oct 2007, not regained until roughly Mar 2013 — about 65 months) or 2000–2002. A 39-month window
would have understated drawdown through 2011–2013. If a 2008-scale event is in scope, only full
history is safe. Stated, accepted limit — not an oversight.

### 3a. What happens when a position sits ABOVE the rolling ATH

**Operator question, 2026-09-05:** *"what if the positions now become above the rolling ATH? How
should the app handle it? should we just lump it to tier 1?"*

The right answer depends on **which** of three cases you are in, and only two of them need a
policy at all. 39 months is a reprieve, not a permanent fix — SCHG is a long-hold core book, so
today's positions age past *any* fixed window eventually.

**Update, 2026-09-05 (later the same day): the premise changed, the guards stay.** With the
39-month window superseded by full history from 2010 (§7), the live app's rolling ATH *is* the
full-history ATH every session, so Case 2 (a stamped `entry_spy_ath` exceeding the rolling ATH)
and Case 3 (a position predating the fetched window) are no longer *expected* paths under
ordinary operation — a real SCHG/UPRO position cannot predate 2010. Both are **retained
deliberately, as invariant guards, not deleted**: the §3a ATH floor (Case 2, below) is free and
monotone-correct even when it rarely engages, and the Case-3 HALT still protects against a
corrupted `openDateTime`, a future narrowing of the fetch window, or any other anomaly that could
otherwise silently assign a fabricated tier. Both are now **implemented**: the floor in
`market/window.py`'s `_spy_context_with_provisional` (`current_ath = max(rolling_window_ath,
max(entry_spy_ath for every OPEN lot))`), and the halt in `market/adopt.py`'s
`build_adoption_plan`, whose own in-code comment (2026-09-05) records this same near-unreachable
-guard framing.

**Case 1 — a position ages past the window after the app bought it. NOT A PROBLEM.**
`DESIGN_market_data.md` §4.3 requires `entry_spy_ath`/`entry_spy_close`/`entry_spy_drawdown`/
`entry_tier` to be **stamped at entry and never re-derived** (the stamped value is the provisional
T-30 close; re-deriving from official closes would silently shift a *discrete* field). Those
values live in `lot_annotations` permanently. The fetch window is irrelevant to them. This is
precisely what "stamp at entry, keep forever" buys, and it means the window question does **not**
recur for app-created positions.

**Case 2 — a stamped `entry_spy_ath` EXCEEDS the current rolling ATH. Real, and cheap to fix.**
Once an entry peak ages out of the window, a lot can carry a stamped ATH higher than the app
currently believes the ATH to be, and any logic comparing the two is incoherent.

**Decision: floor the current ATH with the open lots' own stamped values.**

```
current_ath = max(rolling_window_ath, max(entry_spy_ath for every OPEN lot))
```

This is not the accumulated price history §2.2 forbids — it is derived from the sidecar the app
already maintains and already trusts. It is also monotone-correct: an ATH is a running max that
by definition never decreases, and we *know* SPY traded at each stamped level because we bought
there. So the floor can only move the ATH **toward** truth, never away from it. Cost: nothing —
no extra fetch, no extra state, no new failure mode. Caveat: stamped values came from provisional
T-30 closes and may sit ~0.1% off the official ATH; since this is only a floor, the error is
small and one-directional.

**Case 3 — a position being ADOPTED whose `open_date` predates the fetched window.** Zero of the
209 fall here at 39 months (§3), but it recurs if the migration is delayed, re-run later, or the
window is ever shortened.

**Decision: HALT loudly; do not silently assign a tier.** A guessed tier that is indistinguishable
from a measured one is this project's exact pathology — a plausible number sitting beside a real
one and being trusted by association. `market/adopt.py` is already atomic and all-or-nothing, so
it must refuse the whole backfill and name the offending positions rather than fabricate context
for them.

**If the operator chooses to override and lump anyway, the tier should be 0, not 1.** A position
opened above every price in the window was, by definition, bought at a **high** — its drawdown at
entry was ~0, which *is* tier 0. Assigning tier 1 would assert a −10%-to−15% entry drawdown that
the available data actively contradicts. (Recorded as a disagreement with the operator's initial
suggestion of tier 1, with the reasoning, so it can be overruled deliberately rather than by
default.)

**Whichever is chosen, the annotation must carry its own provenance** — e.g.
`entry_context_source IN ('derived', 'assumed_out_of_window')`. The tier value matters less than
the ability to tell a reconstructed lot from a measured one later. §4.7 already accepts that
adopted lots use reconstructed rather than stamped context; a lot with *no* recoverable context at
all is a third category and must not be silently folded into the second.

**Unresolved, and it gates how much any of this matters:** `strategy/ladder.py` is a stub, so the
*direction* of harm from a wrong `entry_tier` cannot be determined yet. §4.7 says only that "the
ladder's exit logic will make sell decisions about these positions using reconstructed context."
Whoever builds `ladder.py` should revisit this section and state plainly whether a too-shallow or
too-deep `entry_tier` is the more dangerous error — the answer may change the Case-3 default.

**ANSWERED, 2026-09-05, by the session that built `strategy/ladder.py`/`strategy/state.py`.**
Tracing the mechanism first: `entry_tier` — the discrete, stamped field — is not read by any
trading decision in this port, and it never was in the source either: the source's own `LadderLot`
dataclass (`std_band_ladder.py`) has no `entry_tier` field at all. Sell decisions
(`_sell_profitable_lots`) are governed purely by profitability and the `cone_z` sell-threshold
crossing — no tier of any kind enters an exit decision, in the source or in this port. The one
tier-shaped quantity that gates a decision at all is used only for the BUY budget gate
(`_deployed_amount`), and it is recomputed every bar from the *continuous* `entry_reference_spy`
against the *live* ATH — never from the discrete stamped `entry_tier`. `entry_tier` is exactly as
inert here as `entry_spy_close` is: reporting/provenance metadata, nothing more.

Restated in terms of the field that actually is load-bearing (a lot's effective entry drawdown, as
recomputed live against today's ATH — the same direction `entry_tier` itself points, since deeper
drawdown means a higher tier number both ways): a lot whose effective entry looks artificially
SHALLOWER than truth gets counted against the live UPRO budget cap at MORE (shallower) current
drawdown levels than it truly should — the strategy sees more of its tier-0/1 budget as already
consumed than is real, and permits FEWER new buys at those levels. This is self-favouring in the
same sense `DESIGN.md` §4.2a already uses that word: it costs opportunity, never principal — the
strategy never buys or holds more UPRO than the calibrated schedule intends, only less. A lot
whose effective entry looks artificially DEEPER than truth escapes that same budget count at
intermediate current-tier levels where, correctly measured, it should still be counted — the
strategy under-counts its own deployed capital and permits MORE new buys than the tier-cap schedule
(`DESIGN.md` §1.4's table, calibrated against the real 2022 −47.15% drawdown) was designed to
allow, at a shallower drawdown than the schedule was calibrated for. Only the second direction lets
the strategy commit MORE real capital than intended.

**Answer: a too-DEEP `entry_tier` (or the effective-entry value behind it read as deeper than
truth) is the dangerous error — it lets the strategy over-commit real capital sooner and in
greater size than its own calibrated schedule allows. A too-SHALLOW `entry_tier` is the safe-side
error — it only ever makes the strategy MORE conservative, never less.** This CONFIRMS, rather
than reverses, this section's existing Case-3 default of preferring tier 0 over tier 1 when data
is missing for an out-of-window position — "when in doubt, assign the shallowest plausible tier"
was already the right instinct; this is the mechanism-level reasoning that was missing to justify
it. See `strategy/ladder.py`'s module docstring and `_deployed_amount`'s docstring for the code
this traces, and `strategy/ladder.py`'s own note on why the `new_ath_sale` bucket-vs-cash
classification (the other place a stamped ATH-shaped value is read) does not change this
conclusion — it gates which pool proceeds land in, not how much new UPRO exposure gets opened.

---

## 4. BUG 2 — which price basis. Decided; not yet implemented.

Tiingo returns **both** `close` and `adjClose`. `window.py` uses `adjClose` everywhere; section
F's cross-check used raw `close`. Measured on the live payload:

- oldest bar (2025-08-01): `close` 621.72, `adjClose` 614.92, **eToro 620.83**
- adjustment gap: **1.0932% at the oldest bar, 0.0000% at the latest**
- 4 ex-dividend days in 276 bars (`divCash` $1.80–$1.99; SPY pays quarterly)
- Tiingo raw vs eToro across 272 common dates: mean **0.128%**, max **0.640%**, signed deviation
  decaying monotonically toward the present (+0.153% → +0.007% by quarter)

**eToro's candles track Tiingo's RAW close, not `adjClose`.**

**Decision (operator, 2026-09-05): mixing bases is fine and intended — adjusted for *returns*,
raw for *levels*.** The operator's standing principle, first applied to the T-30 provisional-close
question (§4.2a), is that each decision is judged on its own error profile rather than forced into
one uniform rule.

| use | basis | why |
|---|---|---|
| `cone_5_z` | **`adjClose`** | it is a *return* z-score; on raw close the four annual dividends inject ~0.27% fake down-moves into the 260-return window that are not losses |
| ATH / drawdown / tier | **raw `close`** | drives real buy decisions, is compared against traded prices, matches eToro |
| any eToro cross-check | **raw `close`** | like with like — 0.128% instead of ~1% |

**Why raw wins for levels:** no bid, ask, or execution ever happens at `adjClose`. It is a
synthetic back-adjusted series. `minPositionExposure`, position `amount`, `openRate` and eToro's
rates endpoint are all in actual traded prices.

**Consequence for gate 10:** `provisional_close_deviation_pct = 0.0075` (0.75%). An
`adjClose`-vs-eToro comparison at the window edge diverges **1.09%** and breaches it. Today's bar
is safe either way (adjustment is 0.0000% at the present edge), which is exactly why the gate has
never tripped and nobody noticed. The gate must compare like with like. Also: the measured max
raw-vs-eToro deviation of **0.640%** sits uncomfortably close to the 0.75% tolerance, and §10.4
says that tolerance must be set from an observed distribution rather than guessed — §4 here is the
first real distribution available.

---

## 5. Decisions closed this session — do not re-litigate

| decision | rationale |
|---|---|
| `cash_reserve_usd` stays **0.0** | explicit; the entire cash balance is tradable. **Removed from the go-live blocker list.** |
| `min_order_size` stays **50** | operator demand. The live broker floor `minPositionExposure` is **$10 for both SCHG and UPRO** — the old "$50, live-verified" claim was wrong. 50 is a *choice*, not a broker constraint. Do not "correct" it to 10. |
| recurring SCHG DCA | **confirmed stopped** → migration unblocked |
| core floor vs deposits | a deposit of D raises the floor by 0.5D and shrinks SCHG sell headroom by the same. Operator: *"no problem."* Accepted. |
| T-30 timing | **stays**, though its original reason (the rejected Windows host's S4 latency) is gone |
| `cone_5_z` at T-30 | **keeps the provisional close** — its errors are self-favouring |
| SCHG ATH test | **uses the previous day's SETTLED bar**, inside the existing session. **No second schedule** (proposed and rejected: battery, another surface for vivo's background killer, two sessions spending one cash sleeve). 40.2% of intraday ATH touches fail to close at an ATH. |
| drawdown tiers at T-30 | keep the provisional close — 1.27% of bars sit near a tier boundary vs 17.90% near the ATH boundary, 14× less exposure |
| ATH-inclusivity in the backfill | **inclusive** |
| `cone_center_mode` | accepts only `"close"`; `"mid"` (unimplemented, silently computed `"close"`) and `"ema"` both rejected |
| instrument 4375 (≈ MINT) | out of scope; operator notes dividends offset its ~3.3%/yr carry |

---

## 6. TODO — in priority order

**Blocking correctness — items 1-4 below are DONE as of 2026-09-05 (later the same day this
handoff was written); kept here, marked, rather than deleted, per this project's audit-trail
practice:**

1. ~~**Fix the ATH window to 39 months / 819 bars** (§3).~~ **DONE — superseded, not merely
   fixed as specified.** The operator replaced the 39-month window with full history from 2010
   (§7) before this item was ever built against 819 bars; `market/window.py`'s fetch now covers
   full available history every session, so the ATH is the true all-time high by construction,
   and the migration-stranding concern is moot (full history's 2010 floor covers the same ground
   the 39-month table already showed was sufficient).
2. ~~**Implement §3a's ATH floor**~~ **DONE.** `market/window.py`'s
   `_spy_context_with_provisional` implements `current_ath = max(rolling_window_ath,
   max(entry_spy_ath of every open lot))` (`open_lot_entry_spy_ath` is now a required, no-default
   parameter, after a "silently never engaged" defect in an earlier defaulted-empty version was
   found and fixed). `entry_context_source` provenance (`'derived'` / `'assumed_out_of_window'`)
   is live in `lot_annotations` via migration 005, and `market/adopt.py`'s `build_adoption_plan`
   HALTs (an `UnresolvedPosition` that `run_adoption_backfill` turns into an `AdoptionError`)
   rather than guessing a tier for an out-of-window position — see §3a's update above.
3. ~~**Implement the basis split**~~ **DONE.** `market/window.py` uses `adj_close` for
   `cone_5_z` and raw `close` for ATH/drawdown/tier; `market/adopt.py`'s `SpyContext` and
   `build_spy_context_index` use raw `close` throughout — matches §4's table exactly, audited in
   both modules.
4. ~~**Re-set `provisional_close_deviation_pct`**~~ **DONE.** `config.py`'s
   `MarketDataConfig.provisional_close_deviation_pct` is now **0.010** (1.0%), calibrated from
   the measured 272-date Tiingo-raw-vs-eToro distribution (mean 0.128%, max 0.640%) — **this
   value is operator-accepted; do not change it.** `max_rate_age_minutes` and
   `rate_vs_candle_deviation_pct` remain provisional placeholders (see `config.py`'s own updated
   docstring) — still open, not part of this DONE set.

**The product**

4. `strategy/ladder.py`, `strategy/state.py`, `engine/session.py` — the strategy itself is still
   stubs. Everything built so far only makes its *inputs* trustworthy.
5. Gates 1–9, 11, 12 and the `run_preflight` orchestration. `engine/preflight.py`'s TODO block is
   the map. Gate 11 needs `engine/reconcile.py` (unbuilt).
6. Gate 10 items 2, 4, 5. Item 2 is now unblocked — `validate_window_completeness` exists and
   passed live.
7. The forward-test harness and fake broker — also the only thing that can measure §7's open
   questions.

**Operations**

8. Run the adoption migration against the live account — the ATH window prerequisite (§3) is now
   **satisfied** (items 1-4 above are DONE), but the migration itself has **not** been run against
   the live account as of this writing. Still open. Re-measure immediately before writing.
9. **Friday 2026-09-11:** the UPRO rates-freeze re-poll (§10.6(a)) — the only remaining item that
   genuinely needs an open market.
10. Send or hold the eToro bug report (`doc/etoroTicket.md`) — awaiting operator review.
11. Decide whether SCHG's **0.320%/yr** carrying cost belongs on a P&L surface. Modelled nowhere.

**Cleanup**

12. Step 3's "drop `bars`" was deliberately skipped. The superseded accumulation path still
    exists; the new path never touches it, so they coexist without interacting.
13. `engine/session.py`'s step [5] comment is stale against §3.1's actual sequence.
14. Identify instrument 4375 definitively (operator believes MINT; unverified).

---

## 7. Open questions

- **Should the strategy rebalance toward the core floor?** Unspecified anywhere. Carried forward
  unchanged for three handoffs now.
- ~~**Is a 39-month ATH window enough?**~~ **CLOSED, 2026-09-05, superseded same day.** The
  operator aborted the 39-month/819-bar window a few hours after this handoff was written and
  replaced it with full history from `FULL_HISTORY_START_DATE` ("2010-01-01") -- bandwidth
  measurements (§3's own table) showed full history costs ~43 MB/month, ~4.2% of Tiingo's real 1
  GB/month ceiling (DESIGN_market_data.md §10.4), so there was no longer a bandwidth reason to
  accept a rolling window's blind spot at all. The live app's rolling-window ATH now **is** the
  full-history ATH, by construction, every session -- this question does not recur for the live
  app. It is **not** fully closed in the abstract: the fetch still starts at 2010 (the ETF-inception
  floor for UPRO/SCHG), so a 2008-scale event (peak Oct 2007, not regained until ~Mar 2013) or
  1999-2002 would still be invisible to it, exactly as a 39-month window would have been. That
  residual limit is accepted with eyes open, same as before -- it is just a much smaller one now
  (missing 2008-2009 rather than missing the last three years).
- **T-10 vs T-30 divergence** — decision made (T-30 stays), but the forward-test replay is still
  worth running as a measurement.
- **Does the disclosed `$0.15 transactionFee` ever hit cash?** Needs a live order; deferred to
  deployment by the operator, who also decided demo fees may be assumed equal to real.

---

## 8. Gotchas

- **The dev PC cannot reach eToro at all** (Kominfo DNS sinkhole). Everything eToro-touching runs
  on-device. `builders.etoro.com` needs WebSearch, not WebFetch.
- **`exchange_calendars` differs by platform**: desktop 4.13.2, Android 4.11.1 (Chaquopy's index
  tops out at a numpy 1.26.2 wheel; 4.12+ needs ≥1.26.4). Code must work on both.
- **PowerShell 5.1's `Set-Content -Encoding utf8` writes a BOM**, and `tomllib` rejects it with a
  useless `Invalid statement (at line 1, column 1)`. Bit us once while pushing config to the device.
- **Git Bash mangles `/data/local/tmp` paths** into Windows paths for adb. Use `MSYS_NO_PATHCONV=1`,
  or `adb exec-out run-as ... cat` per file.
- **Comments do not survive `.pyc` compilation** — verifying an APK by grepping bytecode for a
  comment always fails. Grep for an error *string* instead.
- **An identical APK byte size does not mean the build did nothing.** Unzip
  `assets/chaquopy/app.imy` and check the packaged `.pyc`.
- **Section C's `missing_from_payload` has a high false-positive rate** — it counts fallback
  alternatives in `or`-chains as required. `_parse_candle` was flagged for six missing keys and is
  entirely correct. `unused_in_payload` is the trustworthy half. Section F's `diff_required_keys`
  fixes this properly; section C still has the old behaviour.
- **`pulled_probe_output/` and `_device_config_tmp/` are gitignored** — live account data and
  credentials. This session's payloads exist on the operator's disk only.
