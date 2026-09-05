# Portfolio market evidence — v1

Implemented 2026-09-05. Real-data calculations stay unavailable until the appropriate feed and coverage exist.

## Shipped

- Six cards: dominant modeled risk contributor, capital-weighted EMA50 trend breadth, largest standalone options-priced movement, highest put-minus-call IV premium, verified earnings exposure and hybrid 30-day portfolio movement.
- Alpaca adjusted daily histories (550 calendar days, up to 252 aligned return observations, minimum 60) and a separate IV snapshot path that does not require a latest trade.
- Portfolio-wide US-symbol enrichment, four workers, provider retries, completed-session deduplication, saved inputs, formula version, per-symbol failures and last-good-data retention. Quote dates must match the requested completed session; the endpoint cannot backfill old option chains.
- Thirty-day ATM volatility through total-variance interpolation between bracketing expiries. No extrapolation. ATM contracts require absolute delta 0.4–0.6. Protection premium uses the closest call and put to absolute delta 0.25 within 0.2–0.3, at matching expiries; maturity interpolation is linear for skew.
- Reject missing/nonfinite IV, missing Greeks/timestamps, stale-session quotes, crossed/zero-bid/wide quotes and unsupported expiries. IV quotes need not have recent trades. Indicative-feed warning remains visible.
- Full-portfolio variance and hybrid movement require every holding's eligible aligned history; hybrid movement additionally requires IV for every holding. Missing European listings are not assumed riskless. FX is held constant, so this is not total EUR return risk.
- Reviewable holding-level tables, capital-versus-risk chart, exclusion counts and JSON evidence download.
- Optional reviewed earnings-calendar JSON stored with each private/guest portfolio. A source URL, verification in the past seven days and coverage through at least the next 30 days are required. Missing coverage stays unknown. This is a manual verification workflow, not automated source verification.

## Use

Configure private Alpaca credentials in `.env`, then run `./start.sh`. The portfolio page checks every 15 minutes while open; the local scheduler updates evidence independently while running. Public live display additionally requires approved display rights and the existing licensed-feed configuration. No broker orders are created.

The new cards appear below the portfolio-value overview. With no credentials, they explain missing inputs instead of displaying demo predictions.

## Still not included

Automatic verified earnings ingestion, European ETF and dated-FX histories, ETF constituent look-through, synchronized options trade-flow analysis, earnings-revision/fundamental feeds, actual investor return attribution and calibrated growth probabilities. These require additional sources or a transaction ledger. The research roadmap remains a proposal for those later stages.

## Interpretation

Options-priced movement is an approximate one-standard-deviation model scale, not an empirical probability band or a directional prediction. Skew reflects protection pricing, not proof of falling prices. Historical risk contributions use current weights; correlations can change. The hybrid estimate combines options IV with historical correlation and is explicitly not a fully option-implied portfolio distribution.

Sources and rationale: [options research](portfolio-options-research.md), [roadmap](portfolio-intelligence-roadmap.md), [Alpaca chain](https://docs.alpaca.markets/us/reference/optionchain).
