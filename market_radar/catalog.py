import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .universe import load_universe


@dataclass(frozen=True)
class CompanyCatalogEntry:
    ticker: str
    name: str
    exchange: str
    sector: str = "Unclassified"
    industry: str = "Unclassified"
    sector_etf: str = "SPY"
    aliases: tuple[str, ...] = ()
    source: str = ""

    @property
    def search_label(self) -> str:
        alias = f" ({', '.join(self.aliases)})" if self.aliases else ""
        return f"{self.name}{alias} — {self.ticker} · {self.exchange}"


def _aliases(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def load_company_catalog(universe_path, catalog_path) -> list[CompanyCatalogEntry]:
    entries: dict[str, CompanyCatalogEntry] = {}
    for member in load_universe(universe_path, []):
        if member.industry == "Sector ETF":
            continue
        entries[member.ticker] = CompanyCatalogEntry(
            ticker=member.ticker,
            name=member.name,
            exchange="S&P 500",
            sector=member.sector,
            industry=member.industry,
            sector_etf=member.sector_etf,
            source="dated S&P 500 seed",
        )

    path = Path(catalog_path)
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                ticker = row.get("ticker", "").strip().upper()
                if not ticker:
                    continue
                existing = entries.get(ticker)
                entries[ticker] = CompanyCatalogEntry(
                    ticker=ticker,
                    name=(existing.name if existing else (row.get("name") or ticker)).strip(),
                    exchange=(row.get("exchange") or (existing.exchange if existing else "US listing")).strip(),
                    sector=(existing.sector if existing else (row.get("sector") or "Unclassified")).strip(),
                    industry=(existing.industry if existing else (row.get("industry") or "Unclassified")).strip(),
                    sector_etf=(existing.sector_etf if existing else (row.get("sector_etf") or "SPY")).strip(),
                    aliases=_aliases(row.get("aliases", "")),
                    source=(
                        f"{existing.source}; {row.get('source')}"
                        if existing and row.get("source")
                        else (row.get("source") or (existing.source if existing else ""))
                    ).strip(),
                )
    return sorted(entries.values(), key=lambda item: (item.name.casefold(), item.ticker))


def _searchable(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def search_company_catalog(
    catalog: list[CompanyCatalogEntry], query: str, limit: int = 25
) -> list[CompanyCatalogEntry]:
    needle = _searchable(query)
    if not needle:
        return []

    ranked = []
    for entry in catalog:
        ticker = _searchable(entry.ticker)
        name = _searchable(entry.name)
        aliases = [_searchable(alias) for alias in entry.aliases]
        if needle == ticker:
            rank = (0, len(entry.name), entry.name.casefold())
        elif name.startswith(needle):
            rank = (1, len(entry.name), entry.name.casefold())
        elif any(alias.startswith(needle) for alias in aliases):
            rank = (2, len(entry.name), entry.name.casefold())
        elif needle in name or needle in ticker or any(needle in alias for alias in aliases):
            rank = (3, len(entry.name), entry.name.casefold())
        else:
            continue
        ranked.append((rank, entry))
    return [entry for _, entry in sorted(ranked, key=lambda item: item[0])[:limit]]
