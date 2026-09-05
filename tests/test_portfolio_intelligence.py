from datetime import date, datetime, timedelta

import numpy as np
import pytest

from market_radar.models import DailyBar, PortfolioPosition
from market_radar.portfolio_intelligence import earnings_exposure, market_report, option_evidence, refresh_intelligence
from market_radar.portfolio_tracker import portfolio_report
from market_radar.repository import Repository

SESSION = date(2026, 9, 4)


def chain(days=30, iv=.4):
    return [{"symbol": f"fixture-{kind}-{delta}", "type": kind, "expiration": (SESSION + timedelta(days=days)).isoformat(),
             "iv": vol, "delta": delta, "bid": 2, "ask": 2.1, "quote_at": "2026-09-04T19:59:00Z"}
            for kind, delta, vol in [("call", .5, iv), ("put", -.5, iv), ("call", .25, iv), ("put", -.25, iv + .1)]]


def test_option_variance_interpolation_and_protection_premium():
    result = option_evidence(chain(20, .3) + chain(40, .5), SESSION)
    assert result["move30"] == pytest.approx(np.sqrt((.3**2 * 20 + .5**2 * 40) / 2 / 365))
    assert result["skew_points"] == pytest.approx(10)
    assert result["valid"] == 8
    assert option_evidence(chain(20), SESSION)["move30"] is None


@pytest.mark.parametrize("change,reason", [({"quote_at": "2026-09-03T20:00:00Z"}, "quote_not_in_session"),
                                            ({"ask": 1}, "quote_quality"), ({"iv": float("nan")}, "invalid_iv_or_greeks"),
                                            ({"quote_at": None}, "missing_or_invalid_fields")])
def test_option_exclusions(change, reason):
    items = chain()
    items[0].update(change)
    assert option_evidence(items, SESSION)["excluded"][reason] == 1


def positions():
    return [PortfolioPosition(t, t, "Technology", "XLK", 10, quote_currency="USD", reference_price=100,
                              reference_value_base=1000, reference_price_at=datetime(2026, 9, 4)) for t in ("AAA", "BBB")]


class Provider:
    name, stock_feed, option_feed = "alpaca", "iex", "indicative"
    calls = 0

    def latest_completed_session(self, now):
        return SESSION

    def get_portfolio_history(self, ticker, start, end):
        self.calls += 1
        rng = np.random.default_rng(2 if ticker == "AAA" else 3)
        prices = 100 * np.exp(np.cumsum(rng.normal(0, .02, 260)))
        return [DailyBar(SESSION - timedelta(days=259-i), p, p, p, float(p), 1000) for i, p in enumerate(prices)]

    def get_portfolio_options(self, ticker, session):
        self.calls += 1
        return chain()


def test_full_refresh_database_restart_and_risk(tmp_path):
    repo = Repository(tmp_path / "evidence.db")
    provider = Provider()
    evidence = refresh_intelligence(provider, repo, positions())
    assert provider.calls == 6
    restarted = Repository(tmp_path / "evidence.db")
    refresh_intelligence(provider, restarted, positions())
    assert provider.calls == 6
    result = market_report(portfolio_report(positions(), [], "USD"), evidence)
    assert len(result["risk"]) == 2
    assert sum(r["risk_share"] for r in result["risk"]) == pytest.approx(1)
    assert result["hybrid_move"] > 0
    assert result["option_coverage"] == 1
    assert result["observations"] == 252


def test_partial_refresh_preserves_success_and_no_full_portfolio_range(tmp_path):
    class Partial(Provider):
        def get_portfolio_history(self, ticker, start, end):
            if ticker == "BBB":
                raise RuntimeError("offline")
            return super().get_portfolio_history(ticker, start, end)
    repo = Repository(tmp_path / "partial.db")
    evidence = refresh_intelligence(Partial(), repo, positions())
    assert evidence["errors"]["BBB"] == ["history"]
    result = market_report(portfolio_report(positions(), [], "EUR"), evidence)
    assert result["history_coverage"] == .5
    assert result["hybrid_move"] is None
    assert result["risk"] == []


def test_verified_earnings_coverage_and_duplicate_events():
    rows = [{"ticker": "AAA", "weight": .6}, {"ticker": "BBB", "weight": .4}]
    record = {"ticker": "AAA", "verified_on": "2026-09-04", "coverage_through": "2026-10-10",
              "earnings_date": "2026-09-08", "source_url": "https://example.com/ir"}
    result = earnings_exposure(rows, [record, record], SESSION)
    assert result["weight7"] == .6
    assert result["coverage"] == .6
    assert len(result["events"]) == 1
    assert earnings_exposure(rows, [dict(record, verified_on="2026-08-01")], SESSION)["coverage"] == 0


def test_demo_evidence_is_rejected(tmp_path):
    provider = Provider()
    provider.name = "demo"
    with pytest.raises(ValueError):
        refresh_intelligence(provider, Repository(tmp_path / "demo.db"), positions())


def test_stale_symbol_is_not_used_as_current_evidence(tmp_path):
    evidence = refresh_intelligence(Provider(), Repository(tmp_path / "stale.db"), positions())
    evidence["session"] = "2026-09-08"
    result = market_report(portfolio_report(positions(), [], "USD"), evidence)
    assert result["history_coverage"] == 0
    assert result["option_coverage"] == 0
