"""Seed the shared, read-only market data behind the public showcase."""

from .models import PortfolioPosition, UniverseMember
from .pipeline import run_scan
from .portfolio_showcase import showcase_sessions
from .providers import DemoProvider

DEMO_FOLLOWED = {
    "PLTR": (18.0, 72.0, "AI platform adoption and durable government demand"),
    "NU": (60.0, 12.5, "Latin American digital banking growth"),
}


def ensure_public_demo(repo, catalog, universe) -> int:
    """Create the pinned demo scans once and return the current one's id.

    `universe` is called after the followed names are saved, so they are part of the scan.
    Scans are pinned to the example portfolio's date: the brief, portfolio and catalyst calendar agree.
    """
    by_ticker = {entry.ticker: entry for entry in catalog}
    entries = [by_ticker[ticker] for ticker in DEMO_FOLLOWED if ticker in by_ticker]
    for entry in entries:
        repo.upsert_watchlist(UniverseMember(entry.ticker, entry.name, entry.sector, entry.sector_etf, True, entry.industry))
    if not repo.list_positions():
        for entry in entries:
            shares, average_cost, thesis = DEMO_FOLLOWED[entry.ticker]
            repo.upsert_position(PortfolioPosition(
                ticker=entry.ticker, name=entry.name, sector=entry.sector, sector_etf=entry.sector_etf,
                industry=entry.industry, shares=shares, average_cost=average_cost, thesis=thesis,
            ))

    previous_session, session = showcase_sessions()
    for row in repo.list_scans():
        if row["provider"] == "demo" and row["as_of"] == session.isoformat() and repo.previous_scan(row["id"]):
            return row["id"]
    provider = DemoProvider()
    members = universe()
    repo.save_scan(run_scan(provider, members, previous_session, scan_type="public-demo"))
    return repo.save_scan(run_scan(provider, members, session, scan_type="public-demo"))
