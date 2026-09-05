# Portfolio product status

## Implemented

- Local portfolios stay in the ignored SQLite database. The public entry point opens an empty guest portfolio in each Streamlit session. Guest holdings never enter the shared demo database or global Streamlit cache.
- Visitors can search companies, add or edit holdings and cash, import a validated JSON file, and download a portable backup. Import merges by ticker. Limit: 100 holdings and 250 KB per import.
- Valuation uses a dated broker reference or a real completed market close. It does not use synthetic scanner prices. Unknown screenshot dates must be confirmed before replacing the reference.
- Reports show concentration, currency quotation exposure, user-controlled position review limits, and conditional review actions with transparent scenario arithmetic. They are not suitability-based investment advice.
- Daily contribution is price change times current shares and saved FX. A whole-portfolio daily total is unavailable when coverage is incomplete or sessions differ. It excludes cash flows, dividends, fees and FX movement. This is not time-weighted or money-weighted performance.
- Screenshot gain percentages do not establish verified cost basis and are not used for tax or sale-gain estimates.
- Real US closes are fetched through Alpaca, with four workers, session deduplication, retries in the provider, and last-good-price retention. Foreign listings keep their reference values.
- The local scheduler refreshes portfolio prices on every tick, including when the broad scan already exists. The portfolio page also checks every 15 minutes while open and catches up on opening.

## Enable private daily updates

Set `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` in the local `.env` (never in chat or git), confirm screenshot price dates in the holding editor, and run `./start.sh`. Keep the computer awake for unattended local updates. Alpaca IEX is a US venue feed; this version does not promise consolidated US prices, automatic FX or European ETF coverage.

## Public guest release

Deploy `streamlit_app.py` as before. Visitors start on My Portfolio with an empty workspace. The market scanner remains a labelled synthetic demonstration. The guest portfolio supports actual user-entered reference values independently.

Public real-data display is enabled only when server-side Alpaca credentials are configured and `MARKET_RADAR_PUBLIC_DATA_LICENSED=1` is set after securing applicable display rights. This flag does not itself grant a data license. See [Alpaca's redistribution guidance](https://alpaca.markets/support/redistribute-alpaca-api).

Guest storage is temporary server memory, not a saved account. Reloading the page or losing the session can erase it. A JSON backup restores the portfolio. See [Streamlit's Session State lifecycle](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state).

## Still required for an account-based public product

1. Choose and configure an identity provider and durable database with ownership enforcement on every portfolio read and write. Do not use a user-supplied email or query parameter as authorization.
2. Agree market-data display rights and a provider for European listings and dated FX.
3. Run a hosted job independently of Streamlit sleep; persist daily snapshots and notify only users who opt in.
4. Add broker transactions, dividends, splits, deposits and withdrawals before claiming actual historical performance or tax cost basis.
5. Add goal, horizon and loss-tolerance inputs before more individualized allocation suggestions.

No credentials or hosting accounts are provisioned by the code change. The guest release is useful for portfolio review, but it is not a durable daily-tracking account service yet.
