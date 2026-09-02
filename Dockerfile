FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY market_radar ./market_radar
COPY data ./data
COPY .streamlit ./.streamlit

RUN python -m pip install --no-cache-dir .

ENV MARKET_RADAR_ADDRESS=0.0.0.0
ENV MARKET_RADAR_PORT=8502
EXPOSE 8502

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8502/_stcore/health', timeout=3)"

CMD ["bash", "-lc", "market-radar bootstrap && exec market-radar serve --address 0.0.0.0 --port 8502"]
