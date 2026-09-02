#!/usr/bin/env python3
import argparse
import csv
from datetime import date
from pathlib import Path

SECTOR_ETFS = {
    "Communication Services": ("XLC", "Communication Services Select Sector SPDR Fund"),
    "Consumer Discretionary": ("XLY", "Consumer Discretionary Select Sector SPDR Fund"),
    "Consumer Staples": ("XLP", "Consumer Staples Select Sector SPDR Fund"),
    "Energy": ("XLE", "Energy Select Sector SPDR Fund"),
    "Financials": ("XLF", "Financial Select Sector SPDR Fund"),
    "Health Care": ("XLV", "Health Care Select Sector SPDR Fund"),
    "Industrials": ("XLI", "Industrial Select Sector SPDR Fund"),
    "Materials": ("XLB", "Materials Select Sector SPDR Fund"),
    "Real Estate": ("XLRE", "Real Estate Select Sector SPDR Fund"),
    "Information Technology": ("XLK", "Technology Select Sector SPDR Fund"),
    "Utilities": ("XLU", "Utilities Select Sector SPDR Fund"),
}


def update_universe(source: Path, destination: Path, as_of: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        constituents = list(csv.DictReader(handle))

    fields = ["ticker", "name", "sector", "industry", "sector_etf", "source", "as_of"]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in constituents:
            sector = row["GICS Sector"]
            writer.writerow(
                {
                    "ticker": row["Symbol"],
                    "name": row["Security"],
                    "sector": sector,
                    "industry": row["GICS Sub-Industry"],
                    "sector_etf": SECTOR_ETFS[sector][0],
                    "source": "datasets/s-and-p-500-companies",
                    "as_of": as_of,
                }
            )
        for sector, (ticker, name) in SECTOR_ETFS.items():
            writer.writerow(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": sector,
                    "industry": "Sector ETF",
                    "sector_etf": ticker,
                    "source": "State Street Select Sector SPDR",
                    "as_of": as_of,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the editable Market Radar universe seed.")
    parser.add_argument("source", type=Path, help="S&P 500 CSV with GICS Sector and GICS Sub-Industry columns")
    parser.add_argument("destination", type=Path, help="Output universe.csv path")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    update_universe(args.source, args.destination, args.as_of)


if __name__ == "__main__":
    main()
