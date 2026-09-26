import json
from datetime import date

import pytest

from market_radar.portfolio_journal import (
    add_review,
    dump_journal,
    import_journal,
    load_journal,
    merge_journal,
    record_decision,
    review_journal,
)

TODAY = date(2026, 9, 26)


def report(price=100.0, as_of="2026-09-25", complete=True):
    return {"complete": complete, "total": 1000, "cash": 0, "rows": [
        {"ticker": "AAA", "price": price, "as_of": as_of, "currency": "USD", "weight": .6, "value": 600}]}


def decision(**changes):
    entry = record_decision(report(), "AAA", "Hold", "Margins expanding", "Two weak quarters", date(2026, 12, 1), TODAY)
    return dict(entry, **changes)


def test_decision_freezes_snapshot():
    entry = decision()
    assert (entry["price"], entry["price_as_of"], entry["weight"], entry["currency"]) == (100.0, "2026-09-25", .6, "USD")
    assert entry["decided_on"] == "2026-09-26" and entry["reviews"] == []


@pytest.mark.parametrize("ticker, review_on", [("ZZZ", date(2026, 12, 1)), ("AAA", TODAY), ("AAA", date(2029, 1, 1))])
def test_invalid_decisions_rejected(ticker, review_on):
    with pytest.raises(ValueError):
        record_decision(report(), ticker, "Hold", "Reason", "", review_on, TODAY)
    with pytest.raises(ValueError):
        record_decision(report(), "AAA", "Hold", "  ", "", date(2026, 12, 1), TODAY)


def test_due_first_and_price_change_needs_newer_price():
    later = decision(review_on="2026-12-01")
    due = decision(id="abc123", review_on="2026-09-20", decided_on="2026-09-01", price=80.0, price_as_of="2026-09-01")
    result = review_journal([later, due], report(), TODAY)
    assert [r["id"] for r in result] == ["abc123", later["id"]]
    assert result[0]["due"] and result[0]["price_change"] == pytest.approx(.25)
    assert result[1]["price_change"] is None  # same price date: no observation yet


def test_review_is_append_only_and_clears_due():
    entry = decision(review_on="2026-09-20", decided_on="2026-09-01")
    reviewed = add_review(entry, "Still valid", "Thesis intact", TODAY)
    assert reviewed["reason"] == entry["reason"] and entry["reviews"] == []
    assert not review_journal([reviewed], report(), TODAY)[0]["due"]


def test_sold_holding_and_other_currency_have_no_change():
    entry = decision(price_as_of="2026-09-01")
    gone = review_journal([entry], {"complete": True, "rows": []}, TODAY)[0]
    assert not gone["held"] and gone["price_change"] is None
    assert review_journal([dict(entry, currency="EUR")], report(), TODAY)[0]["price_change"] is None


def test_storage_round_trip_skips_damaged_entries():
    good = decision()
    raw = json.dumps([good, {"ticker": "<script>", "action": "Hold"}, dict(good, id="ff", action="YOLO")])
    assert load_journal(raw) == [good]
    assert load_journal("not json") == [] and load_journal(None) == []
    assert load_journal(dump_journal([good])) == [good]


def test_backup_import_is_validated_and_merged_by_id():
    good = decision()
    assert import_journal(json.dumps({"version": 1, "journal": [good]})) == [good]
    assert import_journal(json.dumps({"version": 1})) == []
    with pytest.raises(ValueError):
        import_journal(json.dumps({"journal": [dict(good, review_on="2026-01-01")]}))
    assert merge_journal([good], [good, dict(good, id="bb")]) == [good, dict(good, id="bb")]
