# Production readiness reinspection: 2026-11-07, HEAD 162837f

The goal comes from the Boss: once the demo run proves the app works, switching the config to the real account should be the only step left.

Today that is **not true.** This page merges three independent read-only audits:

- **Area A:** the switch from demo to the real account.
- **Area B:** the strategy lifecycle, end to end.
- **Area C:** unattended operation on the device.

The PM corrected items that had gone stale:

- The phone runs `162837f`.
- T055–T060 are done.
- The Boss decided T063 (option C).

## Blockers before real money (P0)

| Ticket | Gap |
|---|---|
| T070 | The armed entry accepts only `nightwatch_demo` + `ARM_DEMO`. Real is hard-refused in Python and Kotlin (G01). |
| T068 | Adoption can only be dry-run. Nothing writes `lot_annotations` for existing positions (G02). That covers the 202 SCHG + 7 UPRO real positions and any manual demo positions. |
| T069 | A vetoed save freezes `ath`, `bars` and `below_streak`. After any real all-time-high (ATH) day, later days look like a new ATH and repeat the SCHG sweeps. Buckets never expire (S1). |
| T071 | HALT and resume are split across homes. Telegram `/resume` cannot be reached while HALTed (G04). |
| T072 | Risk caps are shared by demo and real. The real cash reserve is $10, so a sweep would invest nearly all cash (X1/S2). **Boss decision on values.** |
| T076 | Real keys sit in a plaintext file on the device. The build is debug-signed and unminified (G03). **Boss decision on storage.** |
| T077 | The $10 remainder basis is unverified, and partial closes are on by default (G09). |
| (pilot) | No bounded real pilot is designed. The demo has not yet placed an order (G10). **Boss decision.** |

## Needed for months unattended (P1)

| Ticket | Gap |
|---|---|
| T073 | `schg_daily_values` is never written, so the budget is always 0.4 × current equity. |
| T074 | Under an order cap of 1, the SCHG sell that funds a UPRO buy uses the only send, and the buy starves. A shortfall blocks buys every session. |
| T075 | Missed alarms go unalerted, with no heartbeat. There is no PACKAGE_REPLACED/TIME_SET reschedule. Worker commands are not handled by Kotlin. |
| — | **G11/G12:** no fresh cash or eligibility check at send time. Quantity evidence after a send is thin. |
| — | **S9–S11:** sale proceeds are booked at the planned price, re-entry tails under $50 are lost, and recyclable cash is overstated after drops. |

## Hygiene (P2)

| Ticket | Gap |
|---|---|
| T078 | Event and log retention. |
| — | AGP/compileSdk mismatch (G17). |
| — | One-off market closures not covered by the rules calendar. |
| — | Count of real positions to adopt: 209, 221 or 230. Re-read the real book before T068 runs there. |

## Already in place

- **Gate 7:** a positive demo/real binding.
- **Armed refusals:** sessions refuse without live mode, the arm flag, risk limits or an order ceiling.
- **Crash recovery and reconcile:** crash recovery, durable fills, gate-11 persistence, the session-wide order ceiling, deadline-bounded waits and redaction all exist (T052, T055–T060, T063–T067).
- **Demo proof so far:** the 2026-11-06 demo session passed all 12 gates, made no trade by strategy, and the Telegram report arrived.

## Demo fidelity

The demo must run the same code path as real. The only differences should be:

- the home and arm flag (T070);
- environment-keyed config values (T072).

Manual SCHG positions on the demo, adopted through T068, then exercise the same adoption and ladder path the real book needs.
