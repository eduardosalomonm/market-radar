import pytest

from market_radar.portfolio_intelligence import market_report
from market_radar.portfolio_showcase import TOTAL, populate_showcase
from market_radar.portfolio_tracker import portfolio_report
from market_radar.portfolio_view import SessionPortfolio


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
