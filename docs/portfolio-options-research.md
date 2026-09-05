# Portfolio options research

Research date: 2026-09-05. Product research, not a forecast or trading recommendation.

## Main conclusion

Options are most useful here for **how much movement is priced, how expensive downside protection is, and where portfolio risk sits**. They do not establish that a portfolio is expected to grow. Cboe explicitly describes implied volatility as non-directional; OCC's education material likewise explains that higher volatility means larger potential fluctuations in either direction. [Cboe volatility guide](https://www.cboe.com/tradable_products/cboe_minis/vix_mini_vix/), [OCC options pricing](https://prd-web.optionseducation.org/optionsoverview/options-pricing)

Option-implied probabilities are pricing, or risk-neutral, probabilities. They incorporate compensation for risk and are not actual-world event frequencies. A displayed “70% chance of profit” would therefore require a separately validated forecasting model, not merely delta or a fitted options distribution. [Federal Reserve research](https://www.federalreserve.gov/econres/ifdp/files/ifdp1294.pdf)

## Prioritized metrics

The formulas and UI recommendations below are proposed implementation choices, not metrics promised by the cited providers.

| Priority | Plain-language card | Deterministic implementation | Important boundary |
| --- | --- | --- | --- |
| 1 | Movement priced for the next month | Use liquid near-ATM IV at a consistent horizon; approximate fractional one-standard-deviation movement as IV × sqrt(calendar days / 365). Show holding value × movement in reporting currency. | Illustrative model band, not a guaranteed range or growth target. Do not claim empirical 68% coverage without testing. |
| 1 | Which holdings could move my portfolio most? | Rank holding value × horizon-adjusted IV as standalone movement exposures. | These exposures cannot be added as a portfolio volatility estimate. |
| 2 | Portfolio movement range | Combine consistent-horizon IVs with a historical return correlation matrix: sqrt(wᵀ D R D w). Label “hybrid estimate”; disclose lookback, coverage and constant-FX assumption. | Historical correlation is not implied correlation and can change sharply in stress. Require aligned sufficient history; omit rather than silently set missing correlations to zero. |
| 2 | Downside protection premium | At the same expiration compare 25-delta put IV against 25-delta call IV; show difference in volatility points and its own saved history. | A richer put is insurance pricing, not proof the stock will fall. This is single-stock skew, not the Cboe SKEW index. |
| 2 | Nervousness rising or easing | Compare today's constant-horizon ATM IV with 5/20-session changes and realized volatility over a disclosed window. | IV-minus-realized-volatility is a descriptive gap, not risk-free opportunity or exact variance risk premium. Save daily observations first. |
| 3 | Near-term event risk | Compare short- and medium-maturity IV and join an independently verified earnings calendar. | Current 7–45-day filter cannot produce a 90-day term comparison. Do not infer an earnings date from an IV spike. |
| 3 | Portfolio options tone | Weight eligible holding-level experimental pressure by portfolio value; show bullish, bearish and uncovered exposure separately. | Keep experimental and subordinate to data quality. Not institutional money flow, buying intent, or probability of growth. |

Cboe describes skew as variation in implied volatility across strikes; OCC describes event anticipation as one reason IV can rise. These support the interpretation of protection pricing and event sensitivity, not a reliable directional prediction. [Cboe skew explainer](https://www.cboe.com/insights/posts/dawn-of-a-new-era-brings-on-the-existence-of-skew/), [OCC option price behavior](https://www.optionseducation.org/referencelibrary/faq/option-price-behavior)

## Why not lead with put/call ratios or latest-trade pressure?

Put/call volume can be distorted by mechanical early-exercise activity. A put also can protect an existing long position, while a call can be sold as part of a covered position or spread. Do not translate raw contract counts directly into bullish/bearish forecasts. [Cboe early-exercise and put/call research](https://www.cboe.com/insights/posts/how-early-exercise-order-flow-impacts-equity-option-put-call-ratios), [Cboe options facts](https://optionsfacts.cboe.com/)

Alpaca's snapshot is the latest trade and latest quote for each contract, not every trade in a session. These observations can occur at different times. **Inference:** comparing an earlier trade with a later quote cannot reliably recover its contemporaneous aggressor; modified quotes compound that limitation. Even contemporaneous quote-rule signing has errors documented in research hosted by Cboe. A sum of one latest trade per contract is therefore neither daily traded premium nor institutional flow. [Alpaca chain](https://docs.alpaca.markets/us/reference/optionchain), [Cboe-hosted research on trade signing](https://cdn.cboe.com/resources/education/research_publications/Retail_Profitability.pdf)

For defensible aggressor estimation, acquire trade history plus contemporaneous quotes, reject excessive timestamp mismatches, filter conditions and account for multi-leg ambiguity. Do not imply that tighter filters make intent observable.

## Feed and schema requirements

Alpaca's chain supports latest trade/quote, IV and Greeks; the free indicative feed has delayed trades and modified quotes. The endpoint is useful for prototyping but results must retain the indicative label. Public display rights need separate confirmation before deployment. [Alpaca chain documentation](https://docs.alpaca.markets/us/reference/optionchain), [Alpaca Python historical options API](https://alpaca.markets/sdks/python/api_reference/data/option/historical.html)

Current code audit supplied by the parent task: `OptionContract` stores delta, bid/ask, latest trade price/size/time and expiry, but not explicit strike, IV or quote timestamp. The strongest/weakest/watchlist 7–45 DTE enrichment also does not automatically cover every portfolio holding.

Before implementation:

- Store explicit strike, IV, quote timestamp, underlying spot and timestamp, feed, retrieval time, bid/ask sizes where provided, and model/source identifiers. Retain raw source snapshots for reproducibility.
- Enrich all eligible portfolio holdings within limits; report portfolio-value coverage, not only contract coverage. Keep uncovered European ETFs and missing quotes visible.
- Select consistent expiries, validate IV and quotes, exclude crossed/stale/very wide markets; separate contract-quality checks for IV metrics from trade-freshness checks used for pressure.
- Interpolate **total variance** for a constant maturity when bracketing expirations exist; do not silently compare differing expiry horizons.
- Start storing daily IV/skew immediately; suppress historical percentiles until enough real observations exist.
- For a portfolio band, add adjusted return histories and currency methodology. Report FX sensitivity separately if FX covariance is unavailable.
- Use no “dealer gamma wall,” “max pain target,” or institution-intent claim from snapshots. Open interest alone does not reveal dealer ownership or hedging direction.

## Recommended first release

Three visible cards: **Options-priced movement**, **Largest movement contributor**, **Downside protection premium**. One expandable holding table with source/expiry/coverage. Add a hybrid portfolio range only after historical correlations and coverage checks exist. Keep any options-tone indicator explicitly experimental and never label it “expected portfolio growth.”
