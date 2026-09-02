# Free public hosting and live-data options

Research verified on 2026-09-02 against official provider documentation.

## Recommendation

Use **Streamlit Community Cloud + Turso + GitHub Actions** for the durable free version:

```text
Visitors
   |
   v
Streamlit Community Cloud  --->  Turso (saved scans, watchlist, outcomes)
                                      ^
                                      |
                         GitHub Actions at 17:15 America/New_York
                                      |
                                      v
                                 Alpaca API
```

- Streamlit serves the public, read-only dashboard from a stable `streamlit.app` URL.
- Turso replaces the machine-local SQLite file so history survives app sleep, rebuilds, and concurrent sessions.
- GitHub Actions runs the after-close scan independently of whether anyone has the dashboard open.
- Alpaca and database credentials stay in server-side secrets and never enter the repository or browser.

This is still an after-close product, not a tick-by-tick terminal. In this project, “live” should mean that the latest completed US session is fetched automatically and identified with its as-of time and feed.

## Options compared

| Route | Cost | Stable public URL | Scheduled scans | Durable history | Best use |
|---|---:|---|---|---|---|
| Streamlit Community Cloud only | $0 | Yes | Not reliable while sleeping | No guarantee from local SQLite | Public demo |
| Local Mac + Cloudflare Quick Tunnel | $0 | No; random temporary URL | Yes, while Mac is awake | Yes, on the Mac | Immediate private preview |
| Streamlit + Turso + GitHub Actions | $0 within provider limits | Yes | Yes, with small timing caveats | Yes | Recommended public MVP |
| Managed container + persistent disk | Usually paid | Yes | Yes | Yes | Client production |

### 1. Fastest public demo: Streamlit Community Cloud

Community Cloud is free, deploys directly from a GitHub repository, supports secrets, and assigns the app a public `streamlit.app` URL. Deploy the repository and choose `market_radar/dashboard.py` as the entry point after adding a cloud-compatible requirements file and configuration.

Important limitations:

- An app with no traffic for 12 hours goes to sleep.
- CPU, memory, and storage are bounded and can change over time.
- The app process is not a reliable scheduler.
- The repository is copied into a new Python environment during deployment, so a local SQLite file must not be treated as durable production storage.

Official references: [Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud), [deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [resource limits and hibernation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app), and [secrets](https://docs.streamlit.io/deploy/concepts/secrets).

### 2. Immediate live preview: Cloudflare Tunnel from the Mac

Running the existing app and scheduler locally preserves its current SQLite design. A Quick Tunnel can expose it temporarily:

```bash
./start.sh
cloudflared tunnel --url http://localhost:8502
```

This produces a random `trycloudflare.com` URL. The computer must remain awake, online, and running the service. Cloudflare describes Quick Tunnels as testing-only, without an SLA, with a 200-concurrent-request limit and no Server-Sent Events. A production tunnel can map a domain to the local service and add access controls, but a custom domain may introduce a cost.

Official references: [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/) and [Quick Tunnel limitations](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

Do not expose the current operator controls anonymously. A public build should be read-only, with scans, catalog refreshes, watchlist editing, and secret-bearing diagnostics behind authentication or removed from the public UI.

### 3. Recommended free public MVP

#### Streamlit Community Cloud

Deploy only the presentation layer. It should read the most recent completed scan from the remote database and clearly show:

- data as-of timestamp;
- `LIVE MARKET DATA` versus `SYNTHETIC DEMO DATA`;
- equities feed (`IEX` or full-market entitlement);
- options feed (`indicative` or `OPRA`);
- scan completeness and stale-data warnings.

#### Turso

Turso is SQLite-compatible and its current free plan includes 5 GB of storage, 500 million rows read, and 10 million rows written per month. That is ample for the expected daily scan, idea, watchlist, and outcome workload, but the application needs a repository adapter instead of assuming a writable local file.

Official references: [Turso pricing](https://turso.tech/pricing) and [usage limits](https://docs.turso.tech/help/usage-and-billing).

#### GitHub Actions

A scheduled workflow can run the scanner after market close, save the results to Turso, and update outcomes. Use an IANA timezone schedule for `America/New_York` and retain the app’s own completed-session/holiday check and deduplication.

GitHub states that standard hosted runners are free for public repositories; private repositories receive an account quota. Scheduled workflows can be delayed under load, and public-repository schedules are disabled after 60 days without repository activity. This is acceptable because the scanner already catches up the latest missed session and prevents duplicate scheduled scans.

Official references: [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) and [`schedule` behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Live-data reality

Alpaca Basic currently provides free US-equity real-time data from IEX rather than all US exchanges. For options, the free indicative feed uses modified quotes and its trades are delayed by 15 minutes; OPRA requires a subscription. The dashboard must keep these feed labels and warnings visible.

Official references: [Alpaca market-data plans](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api), [historical options feeds](https://docs.alpaca.markets/us/docs/historical-option-data), and [latest option quote feed](https://docs.alpaca.markets/us/v1.1/reference/optionlatestquotes).

The critical legal boundary is public redistribution. Alpaca's current customer agreement says market data may not be reproduced, distributed, sold, or commercially exploited without written consent from Alpaca. A public client-facing deployment therefore needs Alpaca confirmation or a redistribution-licensed feed before displaying its market data. Until then, the safest public version is the clearly labelled synthetic demo, or a restricted-access live version used only under the applicable data terms.

Official reference: [Alpaca disclosures and agreements](https://alpaca.markets/disclosures).

## Secrets and security

Use host-managed secrets for:

```text
ALPACA_API_KEY_ID
ALPACA_API_SECRET_KEY
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
OPENAI_API_KEY            # optional
```

Never commit `.env`, API keys, the production database, or generated logs. Public visitors should not be able to trigger live API scans, edit the shared watchlist, refresh the catalog, or inspect exception traces. Add rate limiting and basic abuse monitoring even when the host itself is free.

## Suggested rollout

1. Publish the synthetic demo on Streamlit Community Cloud to validate the public experience.
2. Make the public UI read-only and add a separate operator mode.
3. Move persistence behind a Turso repository adapter.
4. Add the after-close GitHub Actions workflow and verify catch-up/deduplication.
5. Add Alpaca secrets only to a restricted deployment while data-display rights are confirmed.
6. Enable the live public feed only after written redistribution approval or migration to a licensed public-display source.
