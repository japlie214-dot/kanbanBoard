<!-- Pinned 2026-11-12 on the Boss's instruction. Text as supplied by the Boss; only the source links at the bottom were made relative to this file. This is the intended strategy, the reference for tickets, the forward test and the lab replay. -->

# Nightwatch — the intended trading strategy

**Keep SCHG as the long-term core. Buy UPRO during unusually sharp SPY declines. Sell profitable UPRO during unusually strong rebounds. Recycle proceeds under controlled rules.**

This describes the strategy we intended, including approved corrections. It is **not a claim that every feature is implemented or live-proven**.

## 1. Three instruments, three roles

| Instrument | Role |
|---|---|
| **SPY** | Signal only. Determines momentum, all-time high, drawdown, and deployment tier. Never traded. |
| **SCHG** | Long-term core. Receives eligible surplus cash and supplies limited funding for UPRO entries. |
| **UPRO** | Tactical exposure. Bought through the normal ladder or deferred re-entry buckets. |

Nightwatch manages **SCHG and UPRO only**. Other account holdings remain untouched.

UPRO has embedded leveraged exposure. Orders themselves use **broker leverage 1**, never margin leverage or shorts.

## 2. Manage a sleeve, not the entire account

You withhold cash through an absolute USD reserve:

```text
sleeve_cash = max(0, broker_available_cash − cash_reserve_usd)

sleeve_equity =
    sleeve_cash
    + current SCHG market value
    + current UPRO market value
```

All strategy calculations use these sleeve values.

- Other instruments do not enter sleeve equity.
- Reserved cash cannot fund strategy orders.
- A zero reserve exposes all available broker cash to the strategy.
- Deposits above the reserve become available automatically.
- To exclude a deposit, increase the reserve.

This is deliberately an **exclusion model**, not a fixed allocation that needs constant manual resizing.

## 3. SPY signal: five-day return versus its own volatility

For each trading day:

```text
r5[t] = SPY_close[t] / SPY_close[t−5] − 1

cone_5_z[t] =
    r5[t] / population_standard_deviation(
        the latest 260 five-day returns
    )
```

Important details:

- This is **not mean-centered**. We divide the return by its standard deviation without subtracting its mean.
- A valid signal needs **265 daily closes**.
- The daily live decision uses a validated provisional close near session end.
- Historical prices must share a consistent adjustment basis.

Default thresholds:

```text
Buy condition:  cone_5_z < −2
Sell condition: cone_5_z > +3
```

Both comparisons are strict. Exactly −2 or +3 does not trigger.

The signal comes from **SPY**, not UPRO’s own return.

## 4. Annual UPRO budget and order size

The normal annual rule:

```text
annual_UPRO_budget =
    floor(
        0.40 × previous_calendar_year_mean_SCHG_market_value / 20
    ) × 20
```

The budget is rounded down to a multiple of $20.

At bootstrap, or when prior-year SCHG history is unavailable:

```text
annual_UPRO_budget =
    floor(0.40 × current_sleeve_equity / 20) × 20
```

Missing rollover history must produce a visible warning, not a crash or silent substitution.

Then:

```text
normal_order_size = max(annual_UPRO_budget / 60, $50)

cash_target = 8 × normal_order_size
```

**$50 is the intended strategy floor.** Some early design tables say $10; later decisions distinguish the broker minimum from our chosen strategy minimum.

Additional rules:

- The annual budget normally stays fixed during the year.
- A mid-year deposit increases available cash, not automatically the established annual budget.
- An explicit budget override replaces the automatic value and recomputes sizing.
- The UPRO budget constrains **deployed cost basis**, not current market value.
- “40% budget” does **not** mean continuously rebalance UPRO to 40% of equity.

## 5. Drawdown ladder

Calculate SPY drawdown from its running historical closing ATH:

```text
drawdown = SPY_close / SPY_ATH − 1
```

Deeper drawdowns unlock larger **cumulative** portions of the UPRO budget:

| Tier | SPY drawdown | Cumulative budget cap |
|---|---|---:|
| 0 | Less than 10% below ATH | 10.0706% |
| 1 | 10% to less than 15% below ATH | 22.1553% |
| 2 | 15% to less than 20% below ATH | 36.6569% |
| 3 | 20% to less than 25% below ATH | 54.0588% |
| 4 | 25% to less than 35% below ATH | 74.9412% |
| 5 | 35% or more below ATH | 100% |

Exactly −10%, −15%, −20%, −25%, or −35% enters the deeper tier.

These are **not amounts to buy immediately**. They are ceilings. The negative signal must still trigger individual entries.

## 6. Normal UPRO entry — the “catapult” book

When `cone_5_z < −2`, attempt **one normal-sized UPRO buy per trading day**.

Default dwell is one qualifying day. A longer configured dwell would require consecutive qualifying days.

Every entry must pass:

1. **Total UPRO ceiling:** existing cost basis across both books plus the new buy cannot exceed the annual budget.
2. **Tier ceiling:** the normal ladder’s counted deployment must fit the current cumulative tier cap.
3. **Cash:** sufficient sleeve cash must exist.
4. **SCHG core protection:** sufficient SCHG value must remain above its protected floor.
5. **Lot count:** fewer than 60 open UPRO lots.
6. **Execution controls:** broker eligibility, order minimums, submission limits, and deadline.

Tier accounting uses each normal lot’s **SPY entry reference relative to today’s ATH**. It does not blindly trust a permanently stamped tier.

**Subtle but intended:** the normal-entry gate checks SCHG headroom even when cash is available. An all-cash sleeve is not equivalent to an initialized SCHG core.

## 7. SCHG core protection and funding

Protected SCHG floor:

```text
SCHG_core_floor = 0.50 × sleeve_equity

sellable_SCHG =
    max(0, SCHG_market_value − SCHG_core_floor)
```

The floor limits strategy-driven SCHG sales. It is **not a promise that market movements cannot push SCHG below 50%**.

SCHG is sold only to support a qualifying normal ladder buy and replenish cash toward the cash target.

### Which SCHG positions sell first?

**Highest entry price per share first.**

```text
Sort:
    broker openRate descending
    position_id ascending for ties
```

Not highest total dollar investment. Not FIFO. Not lowest current value.

Execution policy:

- Close whole lots while needed.
- Partially close the final lot for the remaining shortfall.
- Avoid leaving a broker-invalid tiny remainder.
- Reread actual settled cash.
- Make only bounded top-up attempts if still short.

The intended remainder rule uses $10, but its exact broker basis remained a live-verification concern.

The purpose is to sell higher-cost shares first while preserving lower-cost core positions longer.

## 8. UPRO exits — sell strength, but only profitable lots

Default exit mode is **fixed**:

```text
If cone_5_z > +3:
    close each eligible profitable UPRO lot
```

A lot qualifies when:

```text
current_UPRO_price × remaining_units > remaining_cost_basis
```

Rules:

- Applies to both normal and re-entry UPRO books.
- Close qualifying lots fully.
- Process older entries first.
- Keep losing lots open.
- No percentage profit target.
- No routine strategy stop-loss.
- No forced liquidation because a lot is old.

This profitability test is price-versus-cost based. It does not guarantee positive net profit after all carrying charges.

A 5% trailing-exit alternative exists in the strategy design/code, but **fixed mode is the intended armed mode**.

## 9. Classify UPRO sale proceeds

A same-day batch of UPRO sales takes one of two routes.

### A. SPY ATH advanced since at least one sold lot entered

Compare today’s SPY ATH with each sold lot’s recorded entry ATH.

If the ATH advanced, place the sale batch’s proceeds into a **deferred re-entry bucket**.

This does **not** require SPY to set a fresh ATH on the sale day itself.

### B. No qualifying ATH advancement

Add the proceeds to **recyclable cash**.

That earmark can be consumed by later normal UPRO buys. Eligible remaining recyclable cash can return to SCHG on a future new-ATH day.

**Do not redeploy sale proceeds into SCHG on the same UPRO sale day.**

## 10. Deferred re-entry — three descending-price tranches

Split a qualifying sale batch into three equal dollar tranches, rounded down to cents.

Initial reference:

```text
last_reference_SPY = SPY close on the sale date
```

A tranche becomes eligible when:

- It is a later trading day than the sale.
- SPY closes **below the bucket’s last reference**.
- Cash, total UPRO budget, and lot-count limits permit the buy.

After a fill:

```text
last_reference_SPY = SPY close on that tranche’s entry day
```

Therefore each later tranche requires another lower SPY reference.

Further rules:

- No `cone_5_z < −2` requirement for bucket entries.
- At most **one bucket tranche across all buckets per day**.
- A normal ladder buy and one bucket entry can both occur that day.
- Re-entry lots use a separate book for tier accounting.
- Both books still share the total UPRO budget and 60-lot ceiling.
- Each bucket expires after **20 trading bars**.
- Expiry cancels remaining planned entries; it does not force a trade or close existing positions.

A pending bucket is strategy bookkeeping, **not a broker-held cash reservation**.

## 11. Buy SCHG on genuine new SPY ATHs

SCHG accumulation is event-driven, not a daily recurring purchase.

On a **genuine increase in SPY ATH**, with no same-day UPRO sale batch:

```text
tier_0_reserve = annual_UPRO_budget × 0.10070574586703619

available_for_SCHG =
    max(0, sleeve_cash − cash_target − tier_0_reserve)
```

If recyclable cash is positive, the sweep is additionally limited by:

```text
max(0, recyclable_cash − tier_0_reserve)
```

Create SCHG buy intents in normal-order-sized chunks, with a possible smaller final intent subject to execution minimums.

**Bootstrap rule:** first launch seeds the known ATH. It must not manufacture a “new ATH” and sweep cash.

Consequently:

- An empty demo account does not automatically become SCHG on startup.
- Initial manual SCHG purchases and adoption are separate setup operations.
- Strategy SCHG accumulation happens on later qualifying ATH advances.

## 12. Daily operating sequence

Run once per NYSE trading day, using the exchange calendar for holidays, DST, and early closes.

Intended operational timing:

- Wake around **55 minutes before market close**.
- Run preflight and recovery.
- Decide around **30 minutes before close**.
- Stop new submissions by **25 minutes before close**.

The logical sequence:

1. Recover unresolved prior orders without duplicate submissions.
2. Reconcile broker positions with persisted strategy annotations.
3. Fetch and validate history and current prices.
4. Derive SPY signal, ATH, drawdown, tier, and budget.
5. Determine exits and funding actions.
6. Execute permitted sells.
7. Reread portfolio and available cash.
8. Execute permitted buys against observed cash.
9. Persist confirmed fills and their strategy effects.
10. Save market-state progress without inventing trade effects.
11. Report actions, skips, failures, and next run.
12. Schedule the next session.

The original design discussed broader two-pass re-decision. The approved narrower execution approach **does not create fresh buys solely because a same-session sale released cash**. Such opportunities can wait until the next session.

## 13. Safety rules around the strategy

These constrain execution; they do not replace the investment rules.

- Only SCHG and UPRO may be traded.
- Explicit arming and positive account-environment verification.
- No order based on stale, missing, or inconsistent data.
- Tiingo history and validated live data; do not trust the known-stale eToro rates feed.
- Broker positions are the source of ownership truth.
- Preserve entry metadata, book, bucket, and position identity across restarts.
- Never assume a submitted order filled.
- Never blindly resend an order with an uncertain outcome.
- Clear broker take-profit after buys and verify the result.
- A failed TP clear does not authorize an automatic sale.

Recorded risk settings include:

| Control | Intended behavior |
|---|---|
| **$5,000 buy notional per session** | Execute whole buy intents in order until the cap. Report skipped remainder. Sells do not consume this cap. |
| **Unresolved buys** | Continue reserving applicable buy capacity across recovery. |
| **60 UPRO lots** | Strategy limit. |
| **1,000 managed open lots** | Separate operational backstop. |
| **Daily P&L ≤ −$500** | Loud alert, **not an automatic market-loss halt**. |
| **Market-unexplained loss threshold, recorded as $50** | Integrity alarm and HALT, not an ordinary drawdown stop. |

HALT is for integrity failures and operator intervention—not an invented rule to exit whenever markets fall.

## What this strategy deliberately accepts

- UPRO losses can remain open for a long time.
- Embedded leverage creates substantial drawdown and path-dependence risk.
- A profitable-price exit can still have carrying-cost drag.
- Cash can sit idle while no entry or ATH event qualifies.
- SCHG’s 50% floor limits selling; it does not continually rebalance the portfolio.
- “60 ladder slots” does not guarantee all 60 can be funded.
- No rule guarantees profit or prevents large losses.

**In short:** SCHG is the compounding core, SPY is the timing signal, UPRO is the controlled dip-and-rebound engine. Sale proceeds either recycle normally or re-enter through three progressively lower SPY references.

Sources: [strategy design](../../repos/etoroNightwatch/doc/DESIGN.md) (line 255), [ladder rules](../../repos/etoroNightwatch/app/src/main/python/nightwatch/strategy/ladder.py) (line 483), [SCHG lot-selection policy](../../repos/etoroNightwatch/doc/DESIGN_session.md) (line 487), and [recorded operator decisions](project.md) (line 505).
