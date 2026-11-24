> **SUPERSEDED — see `doc/plan.md` (2026-09-19) for current state, priority and status.**
> The `HANDOFF_*.md` files are a dated archive, newest first: 09-18, 09-11, 09-07, 09-06,
> 09-05_evening, 09-05, 09-04_market_data. Read them as history. Only `doc/plan.md` is maintained as current.

# etoroNightwatch — Handoff to the build phase

**Date:** 2026-09-04
**From:** design + infrastructure + Android-platform-proof session
**To:** whoever builds the real trading app next (a fresh agent or a future session)

**Read `doc/DESIGN.md` in full before writing any code. It is the spec of record — 1219 lines,
all of it earned the hard way (see below). This document is the map of what's already true and
what to do next; DESIGN.md is the contract for how to build it.**

---

## 1. What is actually proven right now — read this before assuming anything is still a risk

Everything below was verified on real infrastructure and real hardware this session, not
inferred from documentation. Where the design says "unverified," believe it; where it says
"confirmed," it means someone watched it happen and checked the evidence.

| Layer | Status | Evidence |
|---|---|---|
| Telegram outbound/inbound | ✅ proven | `telegram-test` CLI passed; real sends confirmed |
| Firebase + Cloudflare Worker (FCM send path) | ✅ proven | OAuth token minted from the real service account, FCM HTTP v1 accepted an authenticated send |
| Cloudflare Pages + server-side token proxy | ✅ proven | Deployed; Cloudflare Access confirmed protecting `/api/*`, not just the HTML |
| Android toolchain (JDK 17, SDK, Chaquopy 17.0.0) | ✅ proven | Real builds, real APKs |
| Chaquopy on API 36 + numpy/pandas for arm64-v8a | ✅ proven | Real `.so` files unzipped and confirmed inside the APK, not just "pip didn't error" |
| `setAlarmClock()` accuracy | ✅ proven | Fired **2 seconds** after its scheduled time from **genuine deep Doze** (`isDeviceIdleMode=true`) — this is the single most important data point in the whole project |
| Boot survival | ✅ proven | The device rebooted unprompted overnight; `BootReceiver` re-armed the alarm and ran a full check battery, unassisted |
| FCM delivery, remote command loop | ✅ proven | `ping`/`status`/`selftest` driven from a laptop via `POST /command` → HMAC’d FCM → phone executes → pushes to `/snapshot` → read back remotely, phone never touched |
| OriginOS 6 battery/hibernation controls | ✅ confirmed present and set | Alarm & pengingat, Izinkan penggunaan daya di latar belakang, Mulai otomatis, Jeda aktivitas dinonaktifkan — all located and configured on the physical device |
| App standby bucket | ✅ best possible | `unknown(5)` = **EXEMPTED** every wake observed |
| Clock skew | ✅ proven | ~800–1100 ms vs the Worker's `Date` header, gate threshold is 60,000 ms |
| tzdata, both runtimes | ✅ proven | Kotlin `java.time` and Python `zoneinfo` both resolve EST/EDT correctly on-device |
| **eToro API reachability from the device** | ✅ proven, with a real finding attached | See §2 below — do not skip this |

**The forward test and the strategy port itself are NOT yet built.** Everything above is
platform and infrastructure proof. None of it is the trading logic.

---

## 2. The Kominfo/DNS finding — this is not optional reading

`public-api.etoro.com` did not resolve correctly on **either** the corporate Wi-Fi **or** the
phone's mobile data connection. Both networks returned a TLS certificate for
`stopmalware.moratelindo.io` / `trustpositif.moratelindo.io` — Indonesia's Kominfo/Trust Positif
ISP-level content filtering, not a corporate policy. It reproduced on two independently-operated
networks, which is strong evidence it is nationwide, not one operator's choice.

**Fix, confirmed working:** device-wide Private DNS set to `one.one.one.one` (Cloudflare
DNS-over-TLS) — Settings → Connections → More connection settings → Private DNS. This must be
set on **any** device this app ever runs on in Indonesia, and it is now item 6 in the design's
device-setup checklist (`doc/DESIGN.md` §7.4b). **The failure mode if it's ever lost is silent
and specific**: DNS resolves, TLS completes a handshake, and the only symptom is a certificate
naming `moratelindo.io` on eToro's hostname specifically — not a generic network error. Preflight
and the Telegram alert text should distinguish this exact signature from an ordinary outage; see
§7.4b for the precise ask.

### 2a. A second Kominfo DNS block, found doing steps 5–6

Steps 5 and 6 (§4 table) ran live against the eToro demo API on 2026-09-04. One new finding
along the way, same family as above: `builders.etoro.com` is DNS-blocked by Kominfo the same way
`public-api.etoro.com` was — the in-session `WebFetch` tool failed with `ECONNREFUSED` against
it, but server-side `WebSearch` worked fine, since it doesn't route through the blocked
resolver. If a future session needs to consult eToro's builder docs and `WebFetch` refuses to
connect, that's this block, not a broken URL — reach for `WebSearch` instead of concluding the
page doesn't exist.

---

## 3. Assumption from kickoff — now settled

The user said the eToro **demo** credentials would be in `config/.secrets.env`
(`ETORO_DEMO_PRIVATE_KEY`, `ETORO_PUBLIC_KEY`) by the time this handoff was picked up; as of the
design session those variable names existed in the file but were **blank**. **This is now
resolved**: the credentials were populated and steps 5–6 ran live against them successfully
(§2a). Auth is trivial once the naming is right (DESIGN §1.1): the "private key" in the brief is
the **user key**, sent as `x-user-key`; the short public key is sent as `x-api-key`. No signing,
no nonce, no JWT — secret handling, not auth mechanics, was ever the hard part here.

---

## 4. The build order, restated with what's actually left

`doc/DESIGN.md` §11 has the authoritative table. Steps 0–4 are done (this session). What's left:

| Step | What | Notes |
|---|---|---|
| **5** | eToro client: auth, rate limiting, retries, all read endpoints, typed models | **Done, live-verified 2026-09-04** against the demo API. Auth confirmed: `x-user-key` = the "private key" in the brief, `x-api-key` = the short public key. See §2a below. |
| 6 | Market calendar + bar store + seeding (400 daily bars) + provisional/settle | **Done, live-verified 2026-09-04.** §4.2's provisional-close mechanism is subtle — read it twice. `market/bars.py`'s live-rate staleness check is still a stub pending step 9's preflight (DESIGN §5 gate 10, §12) — do not read its absence as a step-6 gap. |
| 7 | Strategy port with the four approved bug fixes | See §5 below — do not skip the bug analysis. **`strategy/cone.py` must read bars with `settled_only=True`.** If it ever reads a provisional bar as settled, the ≥265-bar SPY history the cone signal depends on is silently poisoned — not yet verifiable since the module is still a stub, but this is a required check before step 7 is called done. |
| **8** | Forward-test harness + fake eToro broker | See §6 below — this is the user's explicit new ask |
| 9 | Session engine: preflight, executor, idempotency, reconciliation, sleeve accounting | §5 (preflight), §4.5 (sleeve) |
| 10 | Full integration: Telegram inbound, snapshot push, live web app | Reuses the exact plumbing already proven on the probe |
| 11 | Demo end-to-end **on the phone** | Multiple consecutive sessions, on battery. **Acceptance criterion (operator decision 2026-09-04, DESIGN §11/§12):** at least one session must run while the demo account genuinely holds a non-empty position, with `get_portfolio()`'s `clientPortfolio` envelope handling confirmed correct against it — every prior probe passed against 0 positions, which is the "check that passes because nothing happened" pattern (§7 rule 1 below), not proof the parsing is right. The manual trade controls spec'd in DESIGN §9.7 are the intended way to get a real position onto the demo account for this. |
| 12 | Go live | Real keys, `NIGHTWATCH_ARM`, a generous `cash_reserve_usd` so only a small sleeve is initially exposed |

**No real-money credential is used before step 12. This is non-negotiable and is stated in the
design as a hard boundary, not a suggestion.**

---

## 5. Building the real app "like it will be on live" — what that actually means

The user's instruction: build the real app now, targeted at demo, but architected exactly as it
will run in production — not a simplified version to be rewritten later. Concretely:

- Use the **real Android + Chaquopy target** (`com.nightwatch.etoro`), not a desktop-only stub —
  but the Python package under `app/src/main/python/nightwatch/` must still run unmodified on
  desktop CPython, because the forward test (step 8) runs there. This dual-target constraint
  already shaped every module in the existing scaffold; keep it.
- Wire the **full safety architecture from §6** from day one: structural leverage/short
  prevention (hardcoded `max_leverage = 1`, never a config value), the symbol allowlist limiting
  closes to positions in our own `lots` table, sleeve accounting (§4.5) so the app never reasons
  about whole-account cash, bad-tick and bad-data guards, and the two-key arming gate
  (`mode=="live"` AND `NIGHTWATCH_ARM`). None of this is "add later" scaffolding — it has to be
  there before step 5's first live call, because retrofitting safety checks around code that
  didn't have them is how bugs hide.
- **Port the strategy with all four approved fixes, not the original buggy version.** This is
  the single most important correctness requirement in the whole project:
  1. **`_buy_if_allowed` was defined twice** in the source (`etoro_trader`); the dead copy was
     the one that stamped `entry_spy_ath`, so `new_ath_sale` was always `False` and **deferred
     re-entry could never fire at all.** Merge the two into one method: G-F ceiling check → the
     parent gate → stamp `entry_spy_ath`/`entry_spy_close`/`entry_spy_drawdown` → decrement
     `_recyclable_cash`.
  2. **`_process_reentry_buckets` duplicated buckets** on a fill bar. Rewrite as a single pass:
     drop expired, fill at most one, then filter.
  3. **`_reconcile_lots` fabricated lots** for unknown broker positions, losing book/vintage/ATH
     metadata — fine for a backtest, wrong for an app that restarts. Load persisted lot rows and
     match by `position_id`; an unmatched position in a **managed** symbol is a hard preflight
     failure, never something to paper over (§1.4, §5, §6.D).
  4. **`_ensure_budget` raised** on the first bar of a new calendar year with no prior-year SCHG
     history. Fall back to `core_fraction × current sleeve equity` with a loud Telegram warning.
  `CASH_BAND_FRACTION` and `MARTINGALE_RATIO` are dropped entirely (both provably inert in the
  source — see §1.4 for the exact reasoning); the six tier caps are hardcoded constants.
- **`WARMUP_BARS = 0` in live config**, but `_bars` must be persisted in `strategy_state` and
  ≥265 SPY daily bars must be seeded, or the cone signal is `None` forever. This is explained at
  length in DESIGN §1.4 — it trips people up because the naive fix (just set warmup to 0) creates
  a worse bug (permanent warmup) if `_bars` isn't also persisted.
- **Sleeve, not account -- and, since 2026-09-04, by exclusion, not inclusion (operator
  decision, DESIGN §4.5).** `cash_reserve_usd` is an absolute figure in config -- the cash the
  operator withholds for their own use. `sleeve_cash = max(0, broker_available_cash -
  cash_reserve_usd)`, where `broker_available_cash` keeps eToro's documented formula
  (`credit − Σ pending order amounts`, never `totalBalance`); `sleeve_equity` counts only the
  app's own UPRO/SCHG lots. Every strategy read of cash or equity means the sleeve. Getting this
  wrong computes the SCHG core floor against a far larger number than the app actually manages
  and permanently blocks buys. The trade-off exclusion buys: the sleeve now grows with the
  account instead of being pinned to a fixed figure, but any deposit above the reserve is
  immediately tradable -- see DESIGN §12.

---

## 6. The simulation/forward-test ask — build a fake eToro, not a shortcut

The user's explicit ask: don't just backtest against clean historical prices — **replicate the
eToro API's actual behavior** for the simulation, so the exact same session/executor/preflight
code that will run live also runs the forward test unmodified. This is already partially
specified in `doc/DESIGN.md` §10; the build must take it seriously rather than build a
simplified stand-in.

The fake broker (`forward_test/fake_broker.py` per the existing layout) must reproduce, not
abstract away:

- **Async accept-then-fill.** A submitted order returns 200 immediately; the fill (or rejection,
  or partial fill) happens on a subsequent poll of `orders:lookup`, exactly like the real API.
  Code that assumes a synchronous fill will pass the fake broker and fail on eToro.
- **The full order status lifecycle** — 1 Received, 2 Placed, 3 Filled, 4 Rejected,
  5 PartiallyFilled, 6 PendingCancel, 7 Canceled, 8 Expired, **11 WaitingForMarket** (queued, not
  filled — a real and currently unverified-in-production behavior near the close).
- **USD-denominated opens, unit-denominated closes.** Buys specify `amount`; closes specify
  `UnitsToDeduct` (`null` = full close). The fake broker must enforce this asymmetry, not paper
  over it with a single internal representation.
- **Per-instrument minimums from a fake `eligibility` endpoint**, not a hardcoded constant — the
  real strategy's `order_size` can fall below `minPositionExposure`, and that must be a detectable
  failure in simulation too.
- **`x-request-id` / `referenceId` idempotency**, so the forward test can exercise the exact
  crash-recovery path (kill mid-order, restart, recover by `referenceId` rather than re-sending)
  that's listed as acceptance criterion 5 in DESIGN §10.
- **Injectable failures** — timeout after submit, outright rejection, partial fill — so the nine
  (soon ten, see below) acceptance criteria in §10 can actually be exercised deliberately, not
  hoped for.

**Compare results against `etoro_trader`'s own replay output for the same historical inputs.**
This is acceptance criterion 2 in DESIGN §10, and it needs one careful qualification: the ported
strategy is **not** bit-for-bit identical to what's on disk in `etoro_trader` — it has the four
bug fixes applied. Every divergence from `etoro_trader`'s replay must be traced to a specific,
named fix; an unexplained divergence is a bug in the port, not a discrepancy to shrug off. The
`etoro_trader` repo itself is not committed to git and has no study results for this exact
strategy variant — treat its replay output as a reference for mechanism parity, not as proof the
strategy is profitable.

**New: watch the forward test run live from the web app** (`doc/DESIGN.md` §9.6, added this
session). The forward-test runner pushes progressive snapshots to the same Worker `/snapshot`
endpoint the phone uses, tagged `mode: "simulation"`, and the existing Pages UI renders a
visibly distinct "simulation running" view — same components, unmistakably labelled so it's
never confused with a live account. Roughly one push per simulated trading day is the right
cadence: fast enough to watch, not so fast it floods the Worker's free-tier write budget over a
multi-year run.

**T-10 vs T-30 provisional-close divergence** is acceptance criterion 9 in §10 — replay the
strategy using provisional closes sampled at both offsets against the official close series and
report the actual divergence in `cone_5_z` and in resulting trade decisions. The live app trades
at T-30 (moved from the original T-10 for a larger error margin); this criterion quantifies what
that margin costs in signal fidelity, so it's a number instead of an assumption.

---

## 7. Standing rules for whoever builds this — earned the hard way this session

These aren't style preferences. Each one corresponds to a real bug found in this exact codebase
this session, caught only because someone checked the evidence instead of trusting a green
result.

1. **A check that passes because nothing happened is not a pass.** This session hit that
   pattern at least four times: a redaction test on an empty log file, `0`-byte HTTP responses
   read as "no leak," a Worker test suite that passed against a KV binding name that didn't
   match production, and `getPriority()` never even appearing in a log because a notification
   payload silently prevented the handler from running at all. Before trusting a green result,
   confirm something actually happened.
2. **FCM messages must be data-only, never carry a `notification` block.** A message with both
   gets rendered by the FCM SDK itself when the app is backgrounded, and `onMessageReceived` is
   never called. This was found empirically — three pushes displayed as notifications while the
   app's own event log recorded nothing. The fix, and the reasoning, is in
   `cloud/worker/src/fcm.js` — do not revert it to "look more standard."
3. **HMAC an optional argument, don't leave it unsigned alongside a signed command.** The
   `schedule` command's ISO-8601 time argument is folded into the HMAC message itself
   (`command:counter:arg`), not appended unsigned — otherwise the command name and counter would
   be authenticated but the argument could be tampered with independently.
4. **Never widen the remote command surface to include anything that can move money.** §8.3 (new
   this session) makes "everything should be remotely operable" an explicit design principle,
   because the phone lives away from the user most of the time — but arming live trading,
   changing `cash_reserve_usd`, or any other config write stay local-only by design (§6.E).
   This tension is intentional and stated in the design; do not silently resolve it by expanding
   what Telegram or the Worker's `/command` route can do. The manual trade controls spec'd in
   DESIGN §9.7 are the concrete test of this rule: they exist only on the on-device UI and the
   LAN-only embedded dashboard, never on the Pages web app, the Worker, or Telegram, and still
   require `NIGHTWATCH_ARM` in live mode like any other order.
5. **Verify claims about delivery, not just acceptance.** An FCM message ID or an HTTP 200 from
   a send endpoint proves the message was *accepted*, not that it was *delivered* — FCM queues
   for offline devices. This distinction mattered concretely this session.
6. **Prefer Sonnet for subagent work** unless a task genuinely needs Opus-level judgment (novel
   design decisions, safety-relevant tradeoffs). Running several Opus subagents in parallel hit
   a session rate limit mid-task earlier this session and lost in-flight work.
7. **Read the actual device/API facts before designing around assumed ones.** This project
   corrected its target OS twice (Windows → Android, then Android 15/Funtouch → Android
   16/OriginOS 6) and found the Kominfo DNS block empirically rather than from documentation.
   When a device-specific or vendor-specific behavior matters, verify it against the real thing
   before writing code that depends on it.

---

## 8. Where things live

- `doc/DESIGN.md` — the spec of record, 1219 lines, all sections cross-referenced and internally
  consistent as of this commit.
- `doc/RUNBOOK_INFRA.md` — step-by-step Firebase/Cloudflare/Telegram/Android-toolchain setup,
  with 🖱️ YOU / ⚙️ REPO markers, and Part G.7 recording the exact working toolchain version
  combination (Chaquopy 17.0.0, AGP 8.9.0, Gradle 8.11.1, Kotlin 2.0.21, JDK 17).
- `app/src/main/python/nightwatch/` — the real app's Python package (config, db, host
  abstraction, logging with third-party-logger redaction). Stubs exist for `etoro/`, `market/`,
  `strategy/`, `engine/`, `notify/`, `web/` with `TODO(step N)` comments naming exactly what
  belongs there — start here for steps 5–10.
- `android-probe/` — the throwaway proof APK (v3 installed and tested on the physical device; v4
  built and pushed to the repo but **not yet installed**, since installing over the armed alarm
  would have cleared it before tonight's test). Do not confuse this with the real app; it is
  disposable, though its Kotlin patterns (alarm scheduling, FCM handling, command verification)
  are the proven template for the real app's Android side.
- `cloud/worker/` — the Cloudflare Worker, deployed and live at
  `https://etoro-nightwatch-worker.japlie214.workers.dev`, 57 tests passing.
- `cloud/pages/` — the static web app + server-side proxy, deployed behind Cloudflare Access.
- `secrets/` — gitignored. Contains the GitHub PAT, Firebase service-account JSON, and the
  Worker's `PHONE_PUSH_SECRET`/`WEB_READ_TOKEN`/`COMMAND_HMAC_SECRET` values as plain text files
  (the same values set via `wrangler secret put`, kept locally since Cloudflare secrets can't be
  read back). `config/.secrets.env` holds the eToro and Telegram credentials.

---

## 9. One thing to say to the user, if you're a fresh agent picking this up

Ask them, don't assume: is the strategy variant being built here still what they want? It has no
study results in `etoro_trader` and the source file isn't even committed to git there — this
project executes it faithfully but has never validated that it's a good strategy. That's a
separate, legitimate piece of work (a proper study run in `etoro_trader`) that nobody has done
yet, and it's worth surfacing again now that real building is starting.
