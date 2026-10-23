from datetime import date

import pytest

from market_radar.catalysts import load_catalysts
from market_radar.cli import PROJECT_ROOT
from market_radar.portfolio_intelligence import market_report
from market_radar.portfolio_showcase import SESSION, TOTAL, populate_showcase, showcase_sessions
from market_radar.portfolio_tracker import portfolio_report
from market_radar.portfolio_view import SessionPortfolio, example_brief


def test_synthetic_showcase_is_complete_repeatable_and_isolated():
    visitor = SessionPortfolio({})
    demo = SessionPortfolio({})
    populate_showcase(demo)
    report = portfolio_report(demo.list_positions(), demo.list_cash_balances(), "EUR", demo.cache_get("portfolio_closes"))
    assert report["total"] == pytest.approx(TOTAL)
    assert report["daily"] is not None
    assert len(report["rows"]) == 8
    market = market_report(report, demo.cache_get("portfolio_market_evidence"))
    assert len(market["risk"]) == 8
    assert len(market["options"]) == 8
    assert market["hybrid_move"] > 0
    assert market["trend_breadth"] is not None
    assert all(row["skew_points"] is not None for row in market["options"])
    assert visitor.list_positions() == []
    assert visitor.cache_get("portfolio_market_evidence") is None
    second = SessionPortfolio({})
    populate_showcase(second)
    assert demo.cache_get("portfolio_market_evidence") == second.cache_get("portfolio_market_evidence")
    assert demo.cache_get("portfolio_market_evidence")["synthetic"] is True


def test_public_scan_sessions_are_pinned_to_the_example_date():
    previous, current = showcase_sessions()
    assert current == SESSION == date(2026, 9, 4)
    assert previous == date(2026, 9, 3)
    assert showcase_sessions() == (previous, current)


def test_catalyst_calendar_is_not_empty_at_the_pinned_session():
    events = load_catalysts(PROJECT_ROOT / "data" / "catalysts.json", SESSION, days=35)
    assert events


def test_example_brief_matches_my_portfolio_calculations():
    brief = example_brief()
    demo = SessionPortfolio({})
    populate_showcase(demo)
    report = portfolio_report(demo.list_positions(), demo.list_cash_balances(), "EUR", demo.cache_get("portfolio_closes"))
    assert brief["currency"] == "EUR"
    assert brief["session"] == SESSION
    assert brief["total"] == pytest.approx(TOTAL)
    assert brief["daily"] == pytest.approx(report["daily"])
    assert brief["daily_return"] == pytest.approx(report["daily"] / (TOTAL - report["daily"]))
    assert brief["largest"]["ticker"] == "NVDA"
    assert brief["over_limit"] == 1
    assert [item["ticker"] for item in brief["due"]] == ["NVDA"]
    changes = [abs(item["change"]) for item in brief["movers"]]
    assert len(changes) == 3 and changes == sorted(changes, reverse=True)
    assert example_brief(limit=.5)["over_limit"] == 0
