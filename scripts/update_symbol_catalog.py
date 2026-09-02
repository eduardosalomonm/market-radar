import argparse
import csv
import io
import urllib.request
from datetime import date
from pathlib import Path

NASDAQ_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SOURCE = "Nasdaq Trader Symbol Directory"

EXCHANGES = {
    "Q": "NASDAQ Global Select",
    "G": "NASDAQ Global Market",
    "S": "NASDAQ Capital Market",
    "A": "NYSE American",
    "N": "NYSE",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}

EXCLUDED_NAME_PARTS = (
    " warrant",
    " right",
    " unit",
    " preferred",
    "% note",
    " notes due",
    " subordinated note",
    " bond",
    " debt securities",
)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "MarketRadar/0.1 personal research"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_pipe_table(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("File Creation Time")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|"))


def is_company(row: dict[str, str], ticker_field: str) -> bool:
    ticker = row.get(ticker_field, "").strip()
    name = row.get("Security Name", "").casefold()
    return bool(
        ticker
        and row.get("Test Issue", "N") == "N"
        and row.get("ETF", "N") == "N"
        and not any(part in name for part in EXCLUDED_NAME_PARTS)
    )


def load_aliases(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["ticker"].upper(): row for row in csv.DictReader(handle)}


def build_rows(nasdaq_text: str, other_text: str, aliases: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in parse_pipe_table(nasdaq_text):
        if not is_company(row, "Symbol"):
            continue
        ticker = row["Symbol"].strip().upper()
        rows[ticker] = {
            "ticker": ticker,
            "name": row["Security Name"].strip(),
            "exchange": EXCHANGES.get(row.get("Market Category", ""), "NASDAQ"),
        }
    for row in parse_pipe_table(other_text):
        if not is_company(row, "ACT Symbol"):
            continue
        ticker = row["ACT Symbol"].strip().upper()
        rows[ticker] = {
            "ticker": ticker,
            "name": row["Security Name"].strip(),
            "exchange": EXCHANGES.get(row.get("Exchange", ""), "US exchange"),
        }

    result = []
    for ticker, row in rows.items():
        override = aliases.get(ticker, {})
        result.append(
            {
                **row,
                "name": override.get("name") or row["name"],
                "sector": override.get("sector", "Unclassified"),
                "industry": override.get("industry", "Unclassified"),
                "sector_etf": override.get("sector_etf", "SPY"),
                "aliases": override.get("aliases", ""),
                "source": SOURCE,
                "as_of": date.today().isoformat(),
            }
        )
    return sorted(result, key=lambda item: item["ticker"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the searchable US company catalog")
    parser.add_argument("--output", type=Path, default=Path("data/symbol_catalog.csv"))
    parser.add_argument("--aliases", type=Path, default=Path("data/company_aliases.csv"))
    args = parser.parse_args()
    rows = build_rows(fetch_text(NASDAQ_LISTED), fetch_text(OTHER_LISTED), load_aliases(args.aliases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "name",
                "exchange",
                "sector",
                "industry",
                "sector_etf",
                "aliases",
                "source",
                "as_of",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows):,} searchable companies to {args.output}")


if __name__ == "__main__":
    main()
