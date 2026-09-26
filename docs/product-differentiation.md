# Product direction: evidence into decisions

## Positioning hypothesis

FolioShift should answer: what deserves my attention, why, and what changes if I act?
Do not compete on the number of charts or imply that options predict positive returns.

## Implemented in this review

- A leading review priority checks incomplete, undated, future-dated and stale valuations before concentration.
- Synthetic examples remain explicitly illustrative.
- A contribution preview compares cash or existing holdings at fixed prices and FX.
- Before/after capital concentration, threshold breaches and cash share are visible; allocations and JSON export sit behind details.
- Limit headroom: how much a chosen holding can receive before crossing the review limit, or how much new cash brings the largest holding back to it.
- Decision journal: record action, reason, "I'd reconsider if" trigger and review date with a frozen price/weight snapshot. Due decisions lead the review card; reviews append a verdict without editing the original. Entries travel in the portfolio backup (guests have no persistent storage). The example portfolio ships two fictional entries reviewed at its fixed date.
- Scenarios never update holdings or submit orders. No return, tax or transaction-cost forecasts.

## Next priorities (not implemented here)

1. Reliable daily valuations and event coverage, with per-source dates and missing-data visibility. Synthetic examples are not live evidence.
2. A short daily change brief: portfolio impact, cause, uncertainty, and the evidence that would change the conclusion.
3. Decision journal follow-ups: reminders outside the app (email/calendar file) and a personal hit-rate summary once enough reviews exist.
4. ETF look-through and correlated-exposure analysis, distinguishing capital allocation from modeled risk.
5. Persistent authenticated accounts before promising cross-device private portfolio storage; guest sessions remain temporary.

Validate whether users find a useful review faster and return to check a saved decision. Do not claim improved investment returns without evidence.

## Reference boundaries

- Sharesight already offers contribution analysis: https://help.sharesight.com/contribution-analysis-report/
- Parqet already offers industry/country allocation: https://parqet.com/en/blog/industry-country-allocation
- Card hierarchy reference: https://ui.shadcn.com/docs/components/base/card

Preserve the existing FolioShift cards and colors. These references informed hierarchy and product positioning; no new UI dependency was introduced.
