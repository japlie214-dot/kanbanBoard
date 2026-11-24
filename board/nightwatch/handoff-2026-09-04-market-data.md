> **Historical handoff — superseded by `doc/plan.md` (2026-09-19). Do not treat as current.**

# etoroNightwatch — Handoff: market-data redesign session

**Date:** 2026-09-04
**From:** market-data integrity session (empirical verification against live APIs and a real device)
**To:** whoever builds `market/`, `etoro/client.py`'s position parsing, and preflight gates 9–10 next

**Read [`doc/DESIGN_market_data.md`](DESIGN_market_data.md) in full before writing any code
touching prices or positions. It is the spec of record for this area now — ~1150 lines, design
agreed but not yet built, and it supersedes DESIGN.md §3, §4.2, and §6.G. This document is the map
of what changed, what was proven, and what's left; DESIGN_market_data.md is the contract for how
to build it.** `doc/HANDOFF.md` from the prior session is still current for everything outside
market data (Android platform, Telegram, Cloudflare, strategy port) — nothing in this document
supersedes it except where noted.

---

## 1. Read this first — the one-line decision and why it matters

**Stop accumulating price history on the phone. Fetch a full ~265-bar window fresh every session,
use it, discard it.** The SQLite store keeps everything else (sessions, intents, orders, buckets,
strategy state, audit) but no price series. Positions move the same way: eToro is authoritative for
the financial facts of a position, and the local store keeps only a `lot_annotations` sidecar of
split-invariant strategy metadata, keyed on eToro's `position_id`.

This isn't a simplification for its own sake — it **dissolves** missing-day detection, split
rebuilds, dividend adjustment-epoch contamination, and provisional-bar poisoning, making each one
inexpressible rather than mitigated. DESIGN_market_data.md §0–§3 has the full reasoning; §1
specifically walks through why the old bad-tick guard was answering two unrelated questions with
one number, and why that conflation is dangerous rather than just imprecise (a split would have
been misread as a valid crash signal and triggered a maximum-conviction buy under the old design's
own logic if the deviation band had been "fixed" without also fixing the history).

Two of this session's findings are **not optional reading** — they describe live bugs that would
otherwise poison a trade or silently corrupt data with no error raised anywhere:

- **§4 below / DESIGN_market_data.md §2.9, §2.11 — eToro's rates endpoint is frozen for UPRO**,
  serving a stale prior-close as if it were live, with no price-based signature to catch it.
- **§5 below / DESIGN_market_data.md §4.2, §10.7 — `_parse_position` reads fields that don't
  exist**, silently nulling out symbol and mark-to-market on every real position.

---

## 2. What changed since HANDOFF.md — and one decision that supersedes the design doc's own text

HANDOFF.md's build table (§4) listed step 6 ("market calendar + bar store + seeding + provisional/
settle") as done and step 5 (eToro client) as done. Both remain true as far as they went, but this
session found the underlying architecture for step 6 was structurally wrong (§1 above) and found a
real bug inside step 5's client (§5 below). Concretely:

- The `bars` table, `is_provisional`, `settle_bar()`/`settle_previous()`, and the whole
  provisional/settle mechanism praised in HANDOFF.md §4 as "subtle — read it twice" are now
  **dropped entirely** (DESIGN_market_data.md §3.2, §7). They existed to manage a problem
  (accumulated, retroactively-adjusted history) that the new architecture no longer has.
- `lots` is replaced by `lot_annotations` (DESIGN_market_data.md §4.4).
- Both tracked **High** risks in DESIGN.md §12 (unchecked rate staleness; undetected missing days)
  are addressed by gates 9–10 as specified in DESIGN_market_data.md §6 — see that document's header
  block for the exact cross-reference. DESIGN.md §12 now carries a pointer note to this effect; it
  was not otherwise edited this session.
- The Medium risk in DESIGN.md §12 about the `clientPortfolio` envelope being unverified against a
  non-empty portfolio is **closed** — a live 227-position probe confirmed the envelope unwrap is
  correct (DESIGN_market_data.md §10.8).

**Operator decision made this session, now recorded in DESIGN_market_data.md §4.7:** quarantining
these positions (visible but untouchable) was offered and **declined**. The executor gets
access to **all** SCHG and UPRO
positions in the live account — 202 SCHG + 7 UPRO, not just app-created ones. They are to be
**adopted** into the sidecar, not quarantined away from the app's reach. This means:

- `entry_spy_ath` / `entry_spy_close` / `entry_spy_drawdown` / `entry_tier` are **derived** from
  `openDateTime` plus Tiingo SPY history for adopted positions — legitimate here specifically
  because these positions predate the app, so nothing was ever stamped and nothing is being
  overwritten. (Contrast DESIGN_market_data.md §4.3, which forbids re-deriving these fields for
  app-created positions because the stamped value was a provisional T-30 close, not the official
  close the re-derivation would produce — that prohibition does not apply here since there is no
  stamped value to contradict.)
- `book` is **assigned**, defaulting to `catapult` unless the operator says otherwise.
- `bucket_id` stays `NULL` — there is no originating sale for an adopted position.
- Keep an `origin` column (`app` | `adopted`) on `lot_annotations` as **provenance**, not as an
  access gate. Derived annotations must stay distinguishable from stamped ones, but both are fully
  live to the executor once adopted.
- The 18 positions across 5 other instruments stay excluded, by instrument filter — this decision
  only widens the managed set to all SCHG/UPRO, not to the whole account.

This is **already recorded** in DESIGN_market_data.md §4.7 (the migration subsection), with the
`origin` column added to the §4.4 DDL and a note in §4.5 that gate 11 invariant 1 is satisfied
for pre-existing positions by that migration. No reconciliation is outstanding.

What *is* outstanding is smaller and listed in §10.x of the design doc: where the 202 SCHG
positions originated (they look systematic — mostly ~$10 each over roughly two years), whether
`catapult` is the right default book for all of them, and whether the resulting increase in
sleeve size is intended (it feeds budget and order sizing).

Two other operator decisions, smaller:

- The T-30 trigger (moved from T-10 in the prior session) stays as is — the ~18s Chaquopy import
  cost measured this session is immaterial against the ~20-minute warm-up buffer it buys.
- `android-probe-deps/` is kept as a standing dependency-regression harness rather than deleted
  after use; cleanup is deferred, not forgotten.

---

## 3. What is now proven, layer by layer

Same convention as HANDOFF.md §1: everything below was watched happening on real infrastructure
this session, not inferred. Full detail and exact numbers are in DESIGN_market_data.md at the
section cited — this table is a map, not a substitute.

| Layer | Status | Where |
|---|---|---|
| Splits are scheduled, not tail risk (UPRO 5 splits, SCHG 2, both on a ~2–3yr cadence, UPRO overdue) | ✅ confirmed | §2.1 |
| Dividend adjustment epochs would silently poison any accumulated store (~0.32%/quarter on SPY) | ✅ confirmed via `activity_server`'s own bug as a worked example | §2.2 |
| Trading calendar: exactly 2 wrong dates out of 4,748 checked, both ad hoc funeral closures no algorithm can derive | ✅ confirmed | §2.3 |
| Yahoo/yfinance is not usable on-device in any form (curl_cffi impossible on Chaquopy; plain requests/httpx both defeated by anti-bot TLS fingerprinting, HTTP 429 observed) | ✅ confirmed | §2.4 |
| Chaquopy build-time dependency resolution: httpx, numpy, pandas, lxml, exchange_calendars all resolve; curl_cffi and yfinance≥0.2.58 do not | ✅ confirmed (build-time only — see gotchas) | §2.5 |
| `exchange_calendars` 4.11.1 (what Chaquopy resolves) behaviourally identical to 4.13.2 for XNYS, 3,186 sessions, zero differing dates | ✅ confirmed | §2.6 |
| Tiingo carries all four needed fields (`close`/`adjClose`/`splitFactor`/`divCash`) free-tier, for all 3 symbols; verified against the SCHG split | ✅ confirmed | §2.7 |
| The dev PC cannot reach eToro at all — Kominfo DNS sinkhole; **all eToro work must run on-device** | ✅ confirmed, same finding as HANDOFF.md §2 but now hitting market-data probes specifically | §2.8 |
| eToro's rates endpoint serves a frozen stale price for UPRO with no price-based tell | ✅ confirmed, live and demo, market open | §2.9 — see §4 below |
| No eToro streaming/push feed exists (ws.etoro.com is the marketing CDN; three other hosts reset TLS post-ClientHello) | ✅ confirmed, with a stated caveat on WAF-vs-SNI | §2.10 |
| eToro's candles endpoint is unaffected by the rates freeze, at every granularity down to one minute | ✅ confirmed | §2.11 — see §4 below |
| eToro candles are split-adjusted but NOT proven dividend-adjusted (open) and NOT official NYSE closes (~0.1% variable-sign venue difference) | ✅ confirmed (adjustment), ✅ confirmed (not official) | §10.1, §2.11(C) |
| `_parse_position` reads four fields that don't exist on a live position | ✅ confirmed against 227 real positions | §4.2, §10.7 — see §5 below |
| eToro retroactively rewrites both `units` and `openRate` on a split while preserving `amount` exactly | ✅ confirmed, 15 pre-split SCHG positions across the 2024-10-11 4:1 | §4.6 |
| `clientPortfolio` envelope unwrap is correct | ✅ confirmed against 227 positions, closes a DESIGN.md §12 Medium risk | §10.8 |
| Chaquopy runtime imports (numpy/pandas/exchange_calendars/httpx actually importing and running on-device) | ❌ still unverified — the probe hung | §10.3 — see gotchas |
| Whether eToro's trade history endpoint is windowed | ❌ still open | §10.5 |

---

## 4. The UPRO rates-freeze finding — read before touching the provisional-close code path

`GET /api/v1/market-data/instruments/rates` served UPRO at `date=2026-09-03T19:59:54.8409896Z`,
`lastExecution=153.67` — byte-identical across 5+ polls spanning ~40 minutes, on **both** demo and
live accounts, while SPY and SCHG in the same batch requests ticked forward to the second each
time. Quantified against Tiingo: the frozen quote was 153.67 against a true concurrent price of
151.665 — a **+1.322% (+$2.00/share) pricing error**, and the error scales with the day's move
times leverage (a mild −0.42% SPY day already produced this; DESIGN_market_data.md §2.9 projects
roughly 9% on a −3% SPY day and roughly 36% on a 2020-03-16-scale day). The error is **always
adverse**: the frozen prior close sits above the true price on a down day, which is exactly when
the cone strategy wants to buy — so a bad tick here doesn't just corrupt the signal, it oversizes a
buy at the worst possible moment, one-directionally, worse the more attractive the trade looks.

**eToro's own app and its own candles endpoint both show the correct live price at the same
instant** — confirmed by screenshot and by direct probe respectively. So this is not an outage, not
demo-only, not an entitlement/eligibility issue (`allowOpenPosition: true` confirmed for UPRO on
both accounts). **It is confined to one endpoint.** The workaround already exists inside the same
API: candles at any granularity down to `OneMinute` are current and self-timestamped, and
DESIGN_market_data.md §3.1 specifies Tiingo IEX `tngoLast` as primary provisional-close source with
eToro candles as fallback/cross-check, **never the rates endpoint**, for exactly this reason.

This is worth reporting to eToro (DESIGN_market_data.md §10.6(b)) — it's an unusually well-evidenced
report, since the vendor's own app and own candles endpoint contradict their own rates endpoint on
the same instrument at the same moment. That's a judgment call for the operator, not resolved here.

---

## 5. The `_parse_position` bug — a code fix, not a design question

`app/src/main/python/nightwatch/etoro/client.py:441` reads `currentRate`, `invested`,
`unrealizedPL`, and `symbol` off each broker position. **None of these four keys exist** in the
live payload — confirmed against a real 227-position portfolio, not inferred. Every `Position`
parsed from a live portfolio today silently carries `current_price=None`, `invested=None`,
`unrealized_pnl=None`, `symbol=None`, while `position_id`, `units`, `entry_price`, `leverage`,
`is_buy`, and `open_date` populate correctly because those map to fields that genuinely exist.

**There is no symbol string anywhere on a broker position.** Matching must key on `instrumentID`
through the `instruments` table, never a string comparison — this touches every place existing
design text says "symbol match" (gate 11 invariant 4, the sidecar re-link key). Mark-to-market must
be **computed**, not read: `current_price` and `unrealized_pnl` are genuinely absent as keys, not
sometimes-null, and the fix is to reuse the price already fetched for the signal (§3 of the design
doc) against `amount` as cost basis.

This bug was invisible to every prior probe because they all ran against a demo account holding
zero positions — the same "check that passes because nothing happened" pattern flagged in
HANDOFF.md §7 rule 1 and DESIGN.md §12. It took a genuinely populated live payload to surface it.
Confirmed correct at the same time: `amount == units × openRate` holds 227/227, live account.

Full field mapping and the fix direction are in DESIGN_market_data.md §4.2 and §10.7.

---

## 6. Sources — what to reach for and what to leave alone

| Purpose | Source | Notes |
|---|---|---|
| ~265-bar adjusted history, daily | **Tiingo** `adjClose` | `close`, `splitFactor`, `divCash` all free-tier; verified against the SCHG split |
| Today's provisional close | **Tiingo IEX** `tngoLast` (primary) | Keeps the whole window in one vendor's convention, seam-free (§8 of the design doc) |
| Provisional-close fallback / eToro internal cross-check | eToro candles, `OneDay` or latest `OneMinute` | Self-timestamped at the bar level; unaffected by the rates freeze |
| Never for the provisional close, or for anything price-critical | eToro `rates` endpoint | Frozen for UPRO, §4 above |
| Trading calendar | `exchange_calendars` 4.11.1 | Do not call `.is_session()` — raises `DateOutOfBounds` under desktop pandas 3.0.5; use `.sessions`/`.adhoc_holidays` membership |
| Desktop-only research/backtest history | yfinance | Never on device — see §2.4 of the design doc |
| Execution | eToro | Orders and fills only; this session changes only where the app reads the number that decides whether/how much to buy |

---

## 7. Open items, in priority order

1. **Reconcile DESIGN_market_data.md §4 with the "adopt, don't quarantine" decision** (§2 above).
   The design doc's prose and its `lot_annotations` DDL (§4.4) both predate this decision and need
   an `origin` column plus the derivation rule for adopted positions.
2. **Fix `_parse_position`** (§5 above, `client.py:441`). Blocks anything that reads `symbol`,
   `current_price`, `invested`, or `unrealized_pnl` off a live position.
3. **Build gate 10's freshness check** (DESIGN_market_data.md §6). This is called out in the design
   doc itself as the single highest-value fix in the whole redesign — it would have caught the UPRO
   freeze outright, and every session run before it lands is exposed to that exact failure mode.
4. **Re-run the Chaquopy runtime-import probe** (§10.3 of the design doc) — it hung last time; see
   gotchas below for the fix before re-attempting.
5. **Trade-history windowing** (§10.5 of the design doc) — now answerable against the real account,
   unlike when it was first raised.
6. **Report the UPRO rates bug to eToro** — operator judgment call, not an engineering task
   (§10.6(b) of the design doc).

---

## 8. Gotchas — carried forward and new this session

These cost real time. Read before repeating the mistake.

- **The dev PC cannot reach eToro at all.** Same Kominfo DNS sinkhole as HANDOFF.md §2, but this
  session hit it specifically while trying to probe market data: `public-api.etoro.com` resolves to
  `202.137.1.74` (a sinkhole that drops packets) from the dev machine, presenting as a bare
  12-second TCP timeout with zero diagnostic hint. The z10's Private DNS fix resolves it correctly.
  **All nine other data-provider hostnames evaluated this session resolve fine from the dev PC** —
  eToro is specifically blocklisted, not caught by a generic redirect. Every eToro-touching probe,
  forward test, or integration test must run on-device.
- **Credential handling pattern that works, reused from the prior session:** load credentials on
  the PC, pipe a curl config to the device's `curl --config -` over stdin via `adb shell`. The key
  never touches device disk, shell history, or argv.
- **The Chaquopy runtime-import probe hung** — CPU frozen at ~18s, process sleeping, zero Python
  output in logcat. Cause: a network call issued with no timeout, combined with unflushed stdout
  hiding whatever had already run. Fix before re-attempting: explicit per-call timeout on every
  network operation, and flush stdout after every print.
- **`exchange_calendars.is_session()` raises `DateOutOfBounds` for every date, including ordinary
  trading days, under pandas 3.0.5** (the desktop venv's version). Use `.sessions` /
  `.adhoc_holidays` membership instead — both authoritative, both work identically on desktop
  pandas 3.0.5 and the device's pandas 2.1.3.
- **`exchange_calendars`' default calendar range ends 2027-09-03.** Construct with explicit bounds
  if a session ever needs dates beyond that.
- **Chaquopy dependency resolution succeeding at build time is not proof it works at runtime.**
  `numpy` 1.26.2 / `pandas` 2.1.3 / `exchange_calendars` 4.11.1 / `httpx` 0.27.2 all resolved
  cleanly in `installDebugPythonRequirements`, but no device was connected for that pass — this is
  exactly the gap item 4 in §7 above exists to close.
- **`yfinance` versioning is a dead end for on-device use, not a temporary gap.** `≥0.2.58` hard-
  requires `curl_cffi`, which needs `cffi>=2.0.0` with no compatible wheel in Chaquopy's index —
  confirmed by an actual failed pip resolution, not read from a changelog. `0.2.57` does install but
  relies on plain `requests`, the exact mechanism Yahoo's anti-bot fingerprinting was already
  defeating (`httpx` doesn't dodge this either — it presents the same Python TLS fingerprint).
  Pinning `0.2.57` would mean deliberately shipping the broken fetch path with no upgrade route.
- **Subagent failure mode, carried forward from HANDOFF.md §7 rule 1 in spirit:** a check that
  passes because nothing happened is not a pass. This session's clearest instance:
  `_parse_position`'s bug was invisible through every prior demo-account probe (0 positions, 0
  parse attempts, 0 chance to be wrong) and only surfaced against a genuinely populated live
  portfolio. Before trusting a green result on anything touching positions or prices, confirm the
  test actually exercised a non-trivial case.

---

## 9. Where things live (market-data-specific; see HANDOFF.md §8 for everything else)

- `doc/DESIGN_market_data.md` — the spec of record for this area, design agreed, not yet built.
- `doc/DESIGN.md` §3, §4.2, §6.G, §12 — superseded in the specific places DESIGN_market_data.md's
  own header names; DESIGN.md was not otherwise edited this session.
- `app/src/main/python/nightwatch/etoro/client.py:441` — `_parse_position`, the bug in §5 above.
- `app/src/main/python/nightwatch/etoro/client.py:663` — `get_rates`, already parses eToro's
  timestamp into `Rate.timestamp`; currently dropped by `write_provisional`, which never reads it.
- `app/src/main/python/nightwatch/etoro/client.py:725` — `get_eligibility`, already implements the
  `allowOpenPosition` check correctly; confirmed this session for SPY/UPRO/SCHG.
- `market/bars.py:550-573` — `missing_trading_days()`, promoted from dead diagnostic to gate 10's
  window-completeness check (DESIGN_market_data.md §6).
- `market/calendar.py` — sound; kept as a cross-check, not the authority (its two known misses are
  the funeral closures no algorithm can derive).
- `android-probe-deps/` — kept as a standing dependency-regression harness, cleanup deferred.
- `scratchpad/z10_probe.py` (this session's probe host, not committed to the repo under that
  path — check the session's own scratchpad location if picking this up cold) — the working example
  of the credential-piping pattern above.

---

## 10. One thing to say to the user, if you're a fresh agent picking this up

HANDOFF.md §9 already asks whether the strategy variant itself is still wanted — that question is
unchanged and still open. Add one more: the "adopt, don't quarantine" decision in §2 above hands
the executor control over 209 real positions (202 SCHG + 7 UPRO) that predate this app and were
never intended to be machine-managed. Confirm the operator still wants that scope before step 6 of
DESIGN_market_data.md §12's build sequence lands. The decision is recorded and its tradeoff is
stated honestly in §4.7 — but it is also the newest and least-tested part of the design.
Everything else in this handoff was verified against live data; this one has been exercised
against nothing. It is worth a second explicit yes before code makes it real.
