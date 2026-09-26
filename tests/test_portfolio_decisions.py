from datetime import date

import pytest

from market_radar.portfolio_decisions import contribution_scenario, review_priority


def report():
    return {"complete": True, "total": 1000, "cash": 100, "rows": [
        {"ticker": "AAA", "value": 600, "weight": .6, "as_of": "2026-09-04"},
        {"ticker": "BBB", "value": 300, "weight": .3, "as_of": "2026-09-04"}]}


def test_cash_dilutes_concentration_without_changing_holdings():
    source = report()
    result = contribution_scenario(source, 1000, "Cash")
    assert result["largest_after"] == .3
    assert result["cash_after"] == .55
    assert source == report()
    assert sum(r["After"] for r in result["rows"]) + result["cash_after"] == 1


def test_buying_largest_increases_concentration():
    assert contribution_scenario(report(), 1000, "AAA")["largest_after"] == .8
    assert contribution_scenario(report(), 0, "Cash")["largest_after"] == .6


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_invalid_amount_rejected(amount):
    with pytest.raises(ValueError):
        contribution_scenario(report(), amount, "Cash")


def test_missing_values_and_unknown_destination_rejected():
    with pytest.raises(ValueError):
        contribution_scenario(dict(report(), complete=False), 100, "Cash")
    with pytest.raises(ValueError):
        contribution_scenario(report(), 100, "UNKNOWN")


def test_freshness_precedes_allocation_advice_and_demo_is_explicit():
    assert review_priority(report(), date(2026, 9, 26))[0] == "Refresh your prices first"
    assert review_priority(report(), date(2026, 9, 5))[0] == "Review AAA concentration"
    assert review_priority(report(), date(2026, 9, 26), synthetic=True)[0] == "Illustrative review"
    assert review_priority(report(), date(2026, 9, 5), due=["BBB"])[0] == "Revisit your BBB decision"
    assert review_priority(report(), date(2026, 9, 26), due=["BBB"])[0] == "Revisit your BBB decision"


def test_room_before_limit_for_holding_and_cash():
    # BBB: (300 + a) / (1000 + a) = .4 -> a = 166.67
    assert contribution_scenario(report(), 0, "BBB", .4)["room"] == pytest.approx(1000 / 6)
    assert contribution_scenario(report(), 0, "AAA", .4)["room"] == 0
    # Cash needed for AAA to fall to 40%: 600 / .4 - 1000
    assert contribution_scenario(report(), 0, "Cash", .4)["room"] == pytest.approx(500)
