from datetime import date

from test_cli_scheduler import UNIVERSE_CSV

from market_radar.catalog import CompanyCatalogEntry
from market_radar.public_demo import ensure_public_demo
from market_radar.repository import Repository
from market_radar.universe import load_universe


def test_public_demo_is_seeded_once_on_the_pinned_example_session(tmp_path):
    universe_path = tmp_path / "universe.csv"
    universe_path.write_text(UNIVERSE_CSV, encoding="utf-8")
    repo = Repository(tmp_path / "demo.db")
    catalog = [
        CompanyCatalogEntry("PLTR", "Palantir Technologies", "NASDAQ", "Information Technology", "Application Software", "XLK"),
        CompanyCatalogEntry("NU", "Nu Holdings Ltd.", "NYSE", "Financials", "Financial Services", "XLF"),
    ]

    def universe():
        return load_universe(universe_path, repo.list_followed_members())

    first = ensure_public_demo(repo, catalog, universe)
    second = ensure_public_demo(repo, catalog, universe)

    assert first == second
    assert [row["as_of"] for row in repo.list_scans()] == ["2026-09-04", "2026-09-03"]
    scan = repo.get_scan(first)
    assert scan.as_of == date(2026, 9, 4)
    assert {"PLTR", "NU"} <= {signal.ticker for signal in scan.signals}
    assert [item.ticker for item in repo.list_watchlist()] == ["NU", "PLTR"]
    assert [p.ticker for p in repo.list_positions()] == ["NU", "PLTR"]
