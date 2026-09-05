# Portfolio intelligence: proposed next metrics

Research date: 2026-09-05. Proposal only; not implemented or a current portfolio forecast.

## Product boundary

Separate three questions: what changed (observed returns), what markets price (options uncertainty and protection costs), and what could happen (explicit scenarios). Do not present any of these as an assured growth forecast. See the companion options research for options-specific evidence and limitations.

## Priority 1: portfolio risk drivers

- **Risk contribution versus capital weight:** estimate a covariance matrix from aligned, corporate-action-adjusted daily returns in the reporting currency. For weight vector w and covariance matrix C, volatility is sqrt(w' C w); component contribution is w_i (Cw)_i / volatility. Show the lookback, observation count and estimation limitations. Historical relationships are not forecasts. Correlation, not just the number of stocks, determines diversification benefits. [CFA Institute](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-risk-return-part-1).
- **Hidden overlap:** combine direct ownership with dated ETF constituent weights. Display fund-data coverage and residual unknown exposure. FINRA specifically highlights correlated holdings and stock/fund overlap as concentration risks. [FINRA](https://www.finra.org/investors/insights/concentration-risk).
- **Earnings at risk:** sum portfolio weights of companies with verified earnings dates in the next 7/30 days, then show relevant options-implied move separately. Dates require provider provenance and tentative/confirmed status.
- **Trend breadth:** percentage of valued holdings above their EMA50/200, both capital-weighted and equal-weighted. This distinguishes broad strength from a large winner masking weakness. Proposed descriptive metric, not a calibrated return predictor.

## Priority 2: expectations and scenarios

- **30-day options-implied uncertainty:** translate single-name IV to approximate price moves, aggregate only with explicit dependence assumptions. Historical correlations plus options IV produce a hybrid model, not a fully option-implied portfolio distribution. Cboe's implied-correlation framework illustrates why component volatility alone is insufficient. [Cboe](https://www.cboe.com/us/indices/implied/).
- **Downside protection premium:** constant-maturity 25-delta put IV minus call IV; show change versus a saved baseline, not an unqualified fear signal. Hedging demand is not proof of a bearish directional bet.
- **Market sensitivity:** rolling beta and explanatory fit versus an appropriate benchmark; optional rate, dollar and sector scenarios. These are estimated associations, not causal or guaranteed impacts. Avoid redundant factors and overfitting small samples.
- **What-if contributions:** user-entered contribution amount and destination, recalculated capital concentration and estimated risk contribution. Do not invent an optimal portfolio without objectives and constraints.

## Priority 3: growth evidence and accountability

- **Business versus share-price growth:** earnings/revenue revisions, cash-flow quality and valuation changes, each with source date and coverage. Aggregation must handle losses and incomparable sector ratios. Present bull/base/bear assumptions and dividends, not a single implied growth probability.
- **Benchmark and return attribution:** actual transactions, dividends, fees, flows and dated FX are prerequisites for investor performance. Without them, use a clearly labelled static-current-holdings backtest, never 'your historical return'.
- **Forward validation:** freeze every outlook with date, horizon, data coverage and formula version; evaluate subsequent returns against an explicit baseline. Do not publish growth probabilities before calibration and out-of-sample validation.

## Presentation

At most six primary cards: trend breadth, options uncertainty, protection premium, dominant risk driver, earnings exposure and benchmark-relative performance. Each card: one number/status, one sentence, one change indicator, data timestamp and expandable method. Missing data stays unknown, never neutral or zero. Portfolio holdings remain private; data providers need symbols, not share counts or account values.

## Prerequisites

The current app has reference valuations and a limited latest-trade options snapshot model. It lacks the full saved volatility surface, synchronized trade/quote history, corporate-action-aware portfolio return ledger and ETF look-through data required for the proposed suite. First activate legitimate price/FX data access, then aligned history and dated options snapshots. Public display rights must be verified before enabling feeds for visitors.
