# Client deployment checklist

For free public-hosting alternatives, current provider limits, and the recommended Streamlit + Turso + GitHub Actions architecture, see [docs/free-public-hosting.md](docs/free-public-hosting.md).

## Recommended architecture

Run the included container on a managed host behind an HTTPS reverse proxy and authentication. Persist `/app/data` if scan history and paper outcomes must survive container replacement. Treat the dashboard as read-only research for clients; keep manual and live scan controls restricted to the operator whenever possible.

## Before a presentation

1. Start locally with `./start.sh` or launch the container.
2. Run `./healthcheck.sh` and confirm it reports the exact presentation URL.
3. Confirm the top badge says **LIVE MARKET DATA** or **SYNTHETIC DEMO DATA**, as intended.
4. Select the newest completed scan and review partial-data warnings.
5. Confirm the Executive Brief, Global Macro, Trade Ideas, and Stock Explorer pages render.
6. Never describe the evidence score as a win probability or the options pressure as complete institutional flow.

## Production controls

- Terminate TLS at the load balancer or reverse proxy.
- Require authentication; do not expose the raw Streamlit port to the public internet.
- Store `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, and optional `OPENAI_API_KEY` in the host's secret manager.
- Mount a persistent volume for `/app/data` and back it up.
- Monitor `/_stcore/health` and restart the container after repeated failures.
- Restrict outbound network access to required Alpaca and optional OpenAI endpoints.
- Review market-data redistribution rights before giving access to external clients.
- Keep synthetic and demo scans visibly labeled and separate from live scans.

## Container example

```bash
docker build -t market-radar .
docker run --name market-radar \
  -p 8502:8502 \
  -v market-radar-data:/app/data \
  --env-file .env \
  market-radar
```

This repository does not configure a public cloud account, DNS, TLS certificate, or identity provider. Those are deployment-specific infrastructure decisions and should be added deliberately.
