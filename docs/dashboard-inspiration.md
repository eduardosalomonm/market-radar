# Dashboard inspiration and proposed roadmap

Research date: 2026-09-01

This note uses first-party product and institutional sources. It separates useful interaction patterns from features that would add data, licensing, or operational complexity.

## Patterns worth borrowing

### 1. Search-first navigation

Koyfin treats its command bar as a fast route to securities and charts, borrowing the shortcut-navigation model of professional terminals. Its watchlists can also be embedded in dashboards, grouped, sorted, annotated, and configured with reusable column views. Market Radar should adopt the search-first principle without trying to become a general terminal. [Koyfin getting started](https://www.koyfin.com/help/topic/getting-started/) · [Koyfin watchlists](https://www.koyfin.com/features/watchlists/)

TradingView's watchlist flow begins with symbol search, then exposes last price, price change, volume, company detail, notes, alerts, earnings, dividends, and news. Its advanced view supports grouping by sector and summary statistics. This suggests that Market Radar's watchlist should become a compact monitoring surface rather than only an input list. [TradingView watchlists](https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/) · [TradingView advanced watchlist](https://www.tradingview.com/support/solutions/43000771546-watchlist-advanced-view-mode/)

### 2. Overview first, drill-down second

TradingView distinguishes heatmaps for fast anomaly detection from screeners for detailed filtering. Its heatmap uses cell size for importance and color for change, supports sector grouping, and lets users drill into a sector or symbol. Market Radar could use the same information hierarchy with size representing index weight or options premium and color representing relative performance or evidence. [TradingView heatmaps](https://www.tradingview.com/support/solutions/43000766446-tradingview-heatmaps-from-global-trends-to-details/)

Koyfin dashboards combine resizable watchlists, charts, economic series, and news in one workspace. Market Radar should keep a curated layout for clients, but the underlying idea—one question per widget—is useful. [Koyfin dashboards](https://www.koyfin.com/help/mydashboards-myd/)

### 3. Put catalysts beside signals

TradingView's economic calendar emphasizes time, country, importance, actual, forecast, and prior values, with filters by country, category, importance, date, and time zone. The FRED API exposes economic series, release dates, update timestamps, and vintage dates; ALFRED makes revisions observable. A small "next market catalysts" rail would add context without pretending the calendar predicts direction. [TradingView economic calendar](https://www.tradingview.com/support/solutions/43000759911-economic-calendar-track-all-major-market-events/) · [FRED API](https://fred.stlouisfed.org/docs/api/fred/overview.html)

### 4. Combine market-implied and official macro evidence

The IMF DataMapper presents official indicators as a map, time series, and ranking table and supports comparisons across countries, regions, and analytical groups. Market Radar already has a daily cross-asset lens; a country-comparison view could complement it with slower-moving official data and explicit publication dates. [IMF DataMapper](https://www.imf.org/external/datamapper/datasets) · [IMF DataMapper guide](https://www.imf.org/-/media/Files/OAP/oap-home/2021/datamapperhelp-en.ashx)

### 5. Use primary company disclosures for fundamental context

The SEC's public `data.sec.gov` APIs expose company submission history and XBRL company facts without API authentication, and the filing feeds update shortly after dissemination. A restrained company snapshot could show revenue, earnings, cash, debt, and the latest filing date directly from filings rather than from unsourced summaries. Any implementation must follow SEC fair-access guidance and handle company-specific XBRL taxonomy differences. [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) · [SEC developer resources](https://www.sec.gov/about/developer-resources)

### 6. Make outputs client-ready

Koyfin's reports emphasize benchmark comparison, performance, risk, exposure, holdings, reusable templates, and custom methodology or market-outlook pages. Market Radar could produce a one-click dated PDF brief containing the market posture, top three conditional ideas, risk disclosures, and paper-results summary. [Koyfin reports](https://www.koyfin.com/features/reports/)

## Proposed roadmap for approval

Implementation status (2026-09-01): Watchlist Daily Pulse, What Changed, source-linked Catalyst Rail, equal-size/data-depth
Market Driver Heatmap, client brief PDF, and the expanded provider-backed symbol catalog are now implemented. Market-cap
weighting remains intentionally absent until a licensed fundamentals contract exists.

| Priority | Proposal | Client value | Complexity / caveat |
|---|---|---|---|
| 1 | **Watchlist Daily Pulse**: price, 1-day change, evidence change, quadrant, scan status, notes, and sortable columns | Turns the watchlist into the daily starting point | Requires saving prior-scan comparisons; modest |
| 2 | **What Changed Since Yesterday**: regime changes, new/removed ideas, score jumps, and sector rotation | Answers the most natural client question immediately | Deterministic diff model; modest |
| 3 | **Catalyst Rail**: upcoming high-impact macro releases and earnings dates beside each idea | Makes conditional plans easier to interpret and discuss | Needs source/licensing decision; FRED covers official U.S. releases but not consensus estimates |
| 4 | **Market Driver Heatmap**: sector-grouped tiles sized by importance and colored by relative performance or evidence | Highly visual presentation surface with useful drill-down | Market-cap sizing needs a fundamentals source |
| 5 | **Fundamental Snapshot**: latest SEC-reported revenue, earnings, cash, debt, and filing date | Adds business context to technical/options evidence | XBRL normalization requires careful mappings and freshness labels |
| 6 | **Global Economy Map**: growth, inflation, debt, and policy-rate comparisons with official-source dates | Strong client storytelling for the world-economy layer | Slow-moving data; country coverage and vintages vary |
| 7 | **Client Brief PDF**: dated, branded one-page summary with methodology and disclosures | Makes the tool useful in meetings and follow-ups | Needs visual template and PDF QA |
| 8 | **Provider-backed U.S. symbol directory**: search all active Alpaca U.S. equities by company or ticker | Removes the current S&P 500 search boundary | Requires Alpaca credentials and metadata caching; the assets endpoint is the provider's master list. [Alpaca assets](https://docs.alpaca.markets/us/docs/working-with-assets) |

## Recommended sequence

Approve **1 and 2 together** first. They deepen the existing deterministic dataset, require no new paid data source, and make the dashboard more habit-forming. Then choose between **3** (better daily decision context) and **5** (better company-level conviction). Build **4** after a reliable importance metric is available. Treat **6–8** as separate data-product decisions rather than visual-only enhancements.
