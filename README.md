# FolioShift

**What changed. What matters.** Personal portfolio intelligence after the close.

**Public showcase:** [market-radar-insights.streamlit.app](https://market-radar-insights.streamlit.app/)

FolioShift turns a portfolio and watchlist into a low-noise daily update. It scans a dated S&P 500 universe plus the eleven Select Sector SPDR ETFs, compares price movement with an approximation of options pressure, connects the global market backdrop to the user's exposures, and forward-tracks every frozen conditional idea.

It never connects to a brokerage, sends an order, or sizes a position. The evidence score is a reproducible ranking heuristic—not a probability, return forecast, or financial recommendation.

## Quick start

macOS or Linux with Python 3.9 or newer:

```bash
cd /path/to/market-radar
./start.sh
```

The first launch creates `.venv`, installs dependencies, copies `.env.example` to `.env`, creates a presentation-ready demo scan when the database is empty, and starts the dashboard at `http://127.0.0.1:8502`.

Keep that terminal window open while using or presenting the dashboard. From another terminal, verify availability with:

```bash
./healthcheck.sh
```

If the page is not reachable, restart `./start.sh` and use the exact URL printed by the launcher. The port can be changed with `MARKET_RADAR_PORT` in `.env`.

To run the deterministic workflow before opening the dashboard:

```bash
.venv/bin/market-radar demo
.venv/bin/market-radar serve
```

`folioshift` is also installed as a friendlier command name; `market-radar` remains available for compatibility.

Saved scans, ideas, outcomes, holdings, and watchlist entries are stored in `data/market_radar.db`.

The company search is broader than the nightly base scan. It merges the dated S&P 500 seed with a local catalog of
roughly 6,000 Nasdaq-, NYSE-, NYSE American-, Arca-, Cboe-, and IEX-listed operating-company securities. Search by
official name, familiar alias, or ticker; for example, `Palantir`, `PLTR`, `Nu Bank`, `Nubank`, and `NU` all resolve.
Adding a company to the portfolio or watchlist includes it in the next price scan and prioritizes it for options enrichment. Portfolio shares and average cost are entered manually; FolioShift does not request brokerage access.

## Live Alpaca setup

Add personal market-data credentials to `.env`:

```dotenv
ALPACA_API_KEY_ID=your-key-id
ALPACA_API_SECRET_KEY=your-secret-key
```

Then run:

```bash
.venv/bin/market-radar scan
```

Or restart `./start.sh`. With credentials present, the launcher also starts the after-close scheduler. It checks every fifteen minutes, identifies the latest completed SPY session from Alpaca, saves at most one scheduled scan per session, and catches up the most recent missed session after restart.

Alpaca's free `indicative` options feed is delayed and uses modified quotes. Its chain snapshot supplies the latest trade, quote, and Greeks for each contract. FolioShift therefore labels options pressure as an approximation rather than full options flow. See the [official Alpaca option-chain documentation](https://docs.alpaca.markets/us/reference/optionchain).

“Live” in this version means a fresh completed-session scan after the U.S. close, not streaming quotes. Keep `start.sh` running: at 17:15 America/New_York the scheduler discovers the latest completed session, catches up a missed session after restart, and refreshes the followed universe before every scan so newly added holdings are included. The current price shown is always the saved close and is dated in the interface.

## Commands

```bash
market-radar demo [--as-of YYYY-MM-DD]
market-radar scan [--as-of YYYY-MM-DD]
market-radar bootstrap [--as-of YYYY-MM-DD]
market-radar serve [--port 8502] [--address 127.0.0.1]
market-radar scheduler [--interval 900]
```

Every command accepts `--database /path/to/file.db` and `--universe /path/to/universe.csv`.

## What the scanner calculates

```text
S&P 500 + sector ETFs + portfolio + watchlist
→ 260+ completed daily bars
→ cross-asset world lens: U.S. / developed / emerging equities, credit, rates, dollar, gold, oil, commodities
→ 5-day sector-relative and 20-day SPY-relative performance
→ ATR, EMA20/50/200, volume ratio, market regime, sector rotation
→ trailing five-session dollar turnover (sum of closing price × shares traded)
→ top 40 positive + top 40 negative price axes + up to 40 watchlist names
→ 7–45 DTE indicative option-chain snapshots
→ inferred aggressor × premium notional
→ four quadrants + transparent evidence rank
→ conditional trigger / invalidation / 1R / 2R plan
→ immutable scheduled idea + conservative forward outcome
```

## Client presentation experience

The default dashboard is designed for financially literate non-specialists:

- **Daily Brief** leads with portfolio value, daily P&L, and only the followed-name changes that crossed a materiality threshold.
- **What Changed** compares the selected scan with the last earlier completed session: new and removed ideas, setup changes, meaningful evidence moves, regime, and sector leadership.
- **Global Macro** explains daily market-implied risk appetite, growth, inflation, and dollar signals across nine liquid proxies.
- **Opportunity Map** adds a sector-grouped market-driver heatmap before the price-versus-options scatterplot.
- **Trade Ideas** gives company name, GICS industry, a short deterministic rationale, and every conditional trade level.
- **Stock Explorer** defaults to the 100 companies with the highest trailing five-session dollar turnover, supports
  searching every price-scanned company, and clearly distinguishes price-only names from options-enriched names.
  Each stock has a six-KPI summary, a six-month price/EMA/volume chart, a three-month comparison against its sector ETF
  and SPY, and a plain-language trend/participation reading. Formula-level evidence stays collapsed unless
  **Professional detail** is enabled.
- **My Portfolio** stores shares, optional average cost and a one-line thesis; it shows P&L, concentration, market context, and the watchlist Daily Pulse.
- **Catalyst Rail** places source-linked official releases beside the market story and affected ideas.
- **Client Brief PDF** downloads a dated one-page summary built only from the selected saved scan.
- **Method & Data** shows feed identity, limitations, formula definitions, and immutable scan history.

Synthetic demo data is labeled prominently. Live scans retain the indicative-options warning beside evidence scores.

### World-economy boundary

The daily macro layer is market-implied rather than a claim about official economic releases. It uses SPY, EFA, EEM, HYG, TLT, UUP, GLD, USO, and DBC to read global equity breadth, credit appetite, long rates, the dollar, and real assets together. A dated IMF World Economic Outlook snapshot provides a slower-moving official growth and inflation reference with a direct source link.

### Catalysts and earnings

`data/catalysts.json` is the explicit, auditable event contract. The included macro dates link to official BLS, Federal
Reserve, BEA, and Census schedules. Company events use the same file with `"scope": "company"` and a `tickers` list,
so verified earnings dates from a licensed source can be added without changing dashboard code. The project does not
invent earnings dates or show unsourced consensus estimates.

### Price axis

The −100…+100 price axis is 60% five-session sector-relative percentile and 40% twenty-session SPY-relative percentile.

### Options axis

For contracts with 7–45 DTE, absolute delta 0.20–0.80, a same-session trade, a non-crossed quote, and spread no wider than 25% of midpoint:

1. Locate the latest trade between bid and ask to estimate aggressor direction.
2. Weight it by `trade price × size × 100`.
3. Treat bought calls and sold puts as bullish; bought puts and sold calls as bearish.
4. Divide net bullish premium by total included premium and scale to −100…+100.

The dashboard shows valid and excluded contract counts, exclusion reasons, last update time, and feed identity beside the result.

### Quadrants and evidence score

| Price | Options | Quadrant | Automated interpretation |
|---|---|---|---|
| Down | Bullish | Contrarian Bid | Conditional long reversal |
| Down | Bearish | Fear | Conditional short continuation |
| Up | Bullish | Chase | Conditional long momentum |
| Up | Bearish | Hedged Rally | Watch-only; puts may be hedges |

The evidence score weights options magnitude 35%, contract coverage 20%, price displacement 20%, volume percentile 15%, and bucket-specific trend confirmation 10%. Ideas require a score of at least 65 and technical confirmation.

Long triggers sit 0.1 ATR above the scan-day high; short triggers sit 0.1 ATR below its low. Invalidation must be beyond both 1.5 ATR and ten-session structure. Plans wider than 3 ATR are rejected. Untriggered ideas expire after five sessions and triggered ideas time-exit after twenty.

## Paper outcomes

Only scheduled ideas enter the forward log. Each idea is immutable. Subsequent daily bars classify it as pending, expired, open, stopped, target 1R, target 2R, or time exit. When a stop and target fall inside the same daily bar, the result is conservatively recorded stop-first.

## Optional AI narrative

Set `OPENAI_API_KEY` to enable the dashboard's optional prose brief. The implementation sends only saved deterministic evidence to the Responses API, requests Structured Outputs, disables storage with `store: false`, and provides no tools. The returned prose cannot modify signals, ranks, or trade levels. Any API or schema failure falls back to a deterministic template. See the [official OpenAI Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

## Container and client deployment

### Free public showcase

`streamlit_app.py` is a deployment-safe entry point for Streamlit Community Cloud. It automatically creates a
deterministic demo snapshot on ephemeral storage, seeds a fictional Palantir/Nu Holdings portfolio and watchlist, hides scan controls,
and prevents public visitors from changing shared data. No credentials are required.

1. Push this project to a GitHub repository without `.env` or `data/*.db` files.
2. In Streamlit Community Cloud, create an app from that repository.
3. Set the main file path to `streamlit_app.py` and deploy.

The public showcase intentionally contains synthetic data and is not a safe place for personal holdings. A real multi-user product needs authentication, a persistent per-user database (for example Postgres), a separate scheduled worker, encrypted secrets, and an email or push provider; Streamlit Community Cloud plus a shared SQLite file is only a showcase. See
[docs/free-public-hosting.md](docs/free-public-hosting.md) before adding live data or client access.

### Container deployment

For a reproducible presentation container:

```bash
docker build -t market-radar .
docker run --rm -p 8502:8502 market-radar
```

Open `http://127.0.0.1:8502`. For external clients, deploy the container behind HTTPS and authentication rather than exposing a developer laptop or raw Streamlit port. Keep Alpaca and OpenAI credentials in server-side environment variables. See [DEPLOYMENT.md](DEPLOYMENT.md) for the production checklist.

## Universe and provenance

`data/universe.csv` contains 503 constituent securities plus eleven sector ETFs as of 2026-08-30. Constituent names, GICS sectors, and GICS sub-industries come from the public [`datasets/s-and-p-500-companies`](https://github.com/datasets/s-and-p-500-companies) dataset; each row carries its source and as-of date. Watchlist additions—including editable company and industry labels—are stored separately in SQLite. `scripts/update_universe.py` rebuilds the seed from an updated source CSV.

`data/symbol_catalog.csv` is a separate search-and-discovery index generated from the official Nasdaq Trader symbol
directory plus reviewed aliases in `data/company_aliases.csv`. It intentionally does not expand the scheduled options
workload until a company is added to the watchlist. Refresh it with:

```bash
.venv/bin/python scripts/update_symbol_catalog.py
```

The public symbol files carry Nasdaq's usage terms. Confirm redistribution rights before shipping the generated catalog
inside a commercial client deployment.

## Development and verification

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
```

The test suite covers the published formulas, option filtering, all four quadrants, trade-plan risk rules, conservative outcomes, provider normalization and retries, complete/partial scans, SQLite round-trips, scheduled idempotency, exports, optional AI fallback, and Streamlit smoke rendering.

The live Alpaca adapter is fixture-tested without transmitting credentials. A real live scan requires your own API access and remains subject to Alpaca entitlements and rate limits.
