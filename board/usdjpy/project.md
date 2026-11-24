---
name: "USDJPY strategy — deferred"
state: paused
summary: "Saved video strategy for a separate trading pocket and budget, after the current strategy is fully implemented."
repo: "repos/etoro_trader"
---
# USDJPY strategy

Next: Do not dispatch work yet. Resume only after the current strategy is fully implemented and accepted; finishing the lab UI alone does not satisfy that condition.

## Saved reference

https://www.youtube.com/watch?v=5JrP-Abm0bg

Saved at the Boss's request on 2026-11-13. The video has not been fetched or reviewed; its title, rules and performance are not verified.

## Confirmed intent

- Implement this strategy after the current strategy is fully implemented.
- Use a different trading pocket and a separate budget from the current strategy.
- Investigate USDJPY on eToro. The Boss believes eToro supports it; availability and account-specific terms remain unverified.

## Boundaries and open decisions

Budget amount, risk limits, leverage, margin, fees/overnight financing, instrument type and account eligibility are undecided. Do not share the current strategy's capital or silently reallocate it. A pocket must have separate accounting and explicit capital/risk limits; broker-level segregation is not assumed.

The repository link is an intake association with the existing lab, not a decision about deployment architecture. No new codebase or live-trading authorization is implied.

## First future step

`strategy/T001.md` holds the deferred intake. When sequencing permits, review the source, specify reproducible rules, verify the broker contract, and propose implementation, testing and separate-budget controls for approval. No orders, fund allocation or external service actions are authorized by this saved reference.
