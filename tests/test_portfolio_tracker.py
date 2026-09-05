from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from market_radar.models import CashBalance, DailyBar, PortfolioPosition
from market_radar.portfolio_tracker import export_portfolio, import_portfolio, portfolio_report, refresh_prices
from market_radar.portfolio_view import SessionPortfolio


def holding(**kwargs):
    return replace(PortfolioPosition("AAA", "Alpha", "Technology", "XLK", 10,
                                     quote_currency="USD", fx_to_base=.8,
                                     reference_price=100, reference_value_base=800), **kwargs)


def test_import_roundtrip_and_invalid_documents():
    p = holding()
    encoded = export_portfolio([p], [CashBalance("EUR", 10)], "EUR")
    positions, cash, base = import_portfolio(encoded)
    assert positions == [p]
    assert cash[0].amount == 10
    assert base == "EUR"
    with pytest.raises(ValueError):
        import_portfolio(export_portfolio([p, p], [], "EUR"))
    with pytest.raises(ValueError):
        import_portfolio('{"version":1,"base_currency":"EUR","positions":[{"ticker":"AAA","shares":NaN}]}')
    with pytest.raises(ValueError):
        import_portfolio(export_portfolio([replace(p, quote_currency="EUR")], [], "EUR"))


def test_guest_sessions_cannot_read_each_others_positions_or_quotes():
    first, second = SessionPortfolio({}), SessionPortfolio({})
    first.upsert_position(holding())
    first.cache_put("portfolio_closes", {"private": 1})
    assert second.list_positions() == []
    assert second.cache_get("portfolio_closes") is None


def test_unknown_or_future_snapshot_dates_do_not_get_overwritten():
    quotes = {"session": "2026-09-04", "symbols": {"AAA": {
        "as_of": "2026-09-04", "close": 90, "previous_close": 95,
        "previous_as_of": "2026-09-03", "currency": "USD", "source": "alpaca / iex"}}}
    for p in (holding(), holding(reference_price_at=datetime(2026, 9, 5))):
        report = portfolio_report([p], [], "EUR", quotes)
        assert report["total"] == 800
        assert report["daily"] is None
    report = portfolio_report([holding(reference_price_at=datetime(2026, 9, 3))], [], "EUR", quotes)
    assert report["total"] == 720
    assert report["daily"] == -40


def test_partial_data_is_not_total_daily_performance():
    quotes = {"session": "2026-09-04", "symbols": {"AAA": {
        "as_of": "2026-09-04", "close": 90, "previous_close": 95,
        "previous_as_of": "2026-09-03", "currency": "USD", "source": "alpaca / iex"}}}
    first = holding(reference_price_at=datetime(2026, 9, 3))
    missing = holding(ticker="BBB", reference_price=None, reference_value_base=None)
    report = portfolio_report([first, missing], [], "EUR", quotes)
    assert report["daily"] is None
    assert report["daily_coverage"] == 1
    assert not report["complete"]


def test_screenshot_inferred_cost_is_not_presented_as_verified_gain():
    p = holding(average_cost=10, reference_source="Revolut screenshot")
    report = portfolio_report([p], [CashBalance("EUR", 200)], "EUR")
    assert report["rows"][0]["pnl"] is None
    assert report["total"] == 1000
    assert report["actions"][0]["title"] == "Review AAA concentration"


def test_refresh_is_deduplicated_and_retains_last_good_quotes():
    class Provider:
        name, stock_feed = "alpaca", "iex"
        calls = []

        def latest_completed_session(self, now):
            return date(2026, 9, 4)

        def get_daily_bars(self, symbols, start, end):
            self.calls.extend(symbols)
            if symbols == ["BAD"]:
                raise RuntimeError("fixture failure")
            return {symbols[0]: [DailyBar(date(2026, 9, day), 100, 101, 99, 100, 1000) for day in (3, 4)]}

    provider, repo = Provider(), SessionPortfolio({})
    repo.cache_put("portfolio_closes", {"symbols": {"BAD": {"as_of": "2026-09-03", "close": 50}}})
    positions = [holding(), holding(ticker="BAD"), holding(ticker="EURO", quote_currency="EUR")]
    first = refresh_prices(provider, repo, positions, datetime.now(timezone.utc))
    assert first["errors"] == ["BAD"]
    assert first["symbols"]["BAD"]["close"] == 50
    provider.calls.clear()
    refresh_prices(provider, repo, positions)
    assert provider.calls == ["BAD"]
