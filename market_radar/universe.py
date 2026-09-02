import csv
from collections.abc import Iterable
from pathlib import Path

from .models import UniverseMember


def load_universe(path, watchlist: Iterable[UniverseMember]) -> list[UniverseMember]:
    members = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = row["ticker"].strip().upper()
            if not ticker:
                continue
            members[ticker] = UniverseMember(
                ticker=ticker,
                name=row.get("name", ticker).strip() or ticker,
                sector=row.get("sector", "Unclassified").strip() or "Unclassified",
                sector_etf=row.get("sector_etf", "SPY").strip().upper() or "SPY",
                is_watchlist=False,
                industry=row.get("industry", "Unclassified").strip() or "Unclassified",
            )
    for item in watchlist:
        existing = members.get(item.ticker)
        if existing:
            members[item.ticker] = UniverseMember(
                existing.ticker,
                existing.name,
                existing.sector,
                existing.sector_etf,
                True,
                existing.industry,
            )
        else:
            members[item.ticker] = UniverseMember(
                item.ticker,
                item.name,
                item.sector,
                item.sector_etf,
                True,
                item.industry,
            )
    return sorted(members.values(), key=lambda member: member.ticker)
