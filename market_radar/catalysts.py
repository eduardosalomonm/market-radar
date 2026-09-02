import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Catalyst:
    date: date
    time_et: str
    title: str
    category: str
    importance: str
    scope: str
    tickers: tuple[str, ...]
    source: str
    source_url: str

    @property
    def days_away_label(self) -> str:
        return self.date.strftime("%b %-d")


def load_catalysts(
    path,
    as_of: date,
    days: int = 35,
    tickers: Optional[set[str]] = None,
) -> list[Catalyst]:
    source = Path(path)
    if not source.exists():
        return []
    upper_bound = as_of + timedelta(days=days)
    requested = {ticker.upper() for ticker in tickers} if tickers else set()
    catalysts = []
    for item in json.loads(source.read_text(encoding="utf-8")):
        event_date = date.fromisoformat(item["date"])
        event_tickers = tuple(ticker.upper() for ticker in item.get("tickers", []))
        if not (as_of < event_date <= upper_bound):
            continue
        if item.get("scope") == "company" and requested and not (requested & set(event_tickers)):
            continue
        catalysts.append(
            Catalyst(
                date=event_date,
                time_et=item.get("time_et", "TBD"),
                title=item["title"],
                category=item.get("category", "Other"),
                importance=item.get("importance", "Medium"),
                scope=item.get("scope", "macro"),
                tickers=event_tickers,
                source=item.get("source", ""),
                source_url=item.get("source_url", ""),
            )
        )
    return sorted(catalysts, key=lambda item: (item.date, item.time_et, item.title))
