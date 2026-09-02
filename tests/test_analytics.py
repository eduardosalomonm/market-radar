import unittest
from datetime import date, datetime, timezone

from market_radar.analytics import (
    build_trade_idea,
    classify_quadrant,
    compute_evidence_score,
    compute_option_pressure,
    evaluate_idea,
)
from market_radar.models import DailyBar, OptionContract, TradeIdea


class AnalyticsTest(unittest.TestCase):
    def test_classifies_all_four_price_and_options_quadrants(self):
        self.assertEqual(classify_quadrant(-10, 20), "Contrarian Bid")
        self.assertEqual(classify_quadrant(-10, -20), "Fear")
        self.assertEqual(classify_quadrant(10, 20), "Chase")
        self.assertEqual(classify_quadrant(10, -20), "Hedged Rally")

    def test_option_pressure_combines_contract_type_aggressor_and_premium(self):
        timestamp = datetime(2026, 8, 28, 19, 55, tzinfo=timezone.utc)
        contracts = [
            OptionContract("AAPL-C", "call", 0.50, 10.0, 12.0, 12.0, 2, timestamp, date(2026, 9, 18)),
            OptionContract("AAPL-P", "put", -0.50, 5.5, 7.0, 7.0, 1, timestamp, date(2026, 9, 18)),
        ]

        pressure = compute_option_pressure(contracts, date(2026, 8, 28), feed="indicative")

        self.assertAlmostEqual(pressure.axis, 54.84, places=2)
        self.assertEqual(pressure.valid_contracts, 2)
        self.assertEqual(pressure.excluded_contracts, 0)
        self.assertEqual(pressure.feed, "indicative")

    def test_option_pressure_excludes_crossed_wide_stale_and_out_of_window_contracts(self):
        fresh = datetime(2026, 8, 28, 19, 55, tzinfo=timezone.utc)
        stale = datetime(2026, 8, 27, 19, 55, tzinfo=timezone.utc)
        contracts = [
            OptionContract("GOOD", "call", 0.40, 9.0, 10.0, 10.0, 1, fresh, date(2026, 9, 18)),
            OptionContract("CROSSED", "call", 0.40, 11.0, 10.0, 10.0, 1, fresh, date(2026, 9, 18)),
            OptionContract("WIDE", "put", -0.40, 5.0, 10.0, 9.0, 1, fresh, date(2026, 9, 18)),
            OptionContract("STALE", "put", -0.40, 9.0, 10.0, 10.0, 1, stale, date(2026, 9, 18)),
            OptionContract("FAR", "call", 0.40, 9.0, 10.0, 10.0, 1, fresh, date(2026, 12, 18)),
        ]

        pressure = compute_option_pressure(contracts, date(2026, 8, 28), feed="indicative")

        self.assertEqual(pressure.valid_contracts, 1)
        self.assertEqual(pressure.excluded_contracts, 4)
        self.assertEqual(
            pressure.exclusions,
            {"crossed_quote": 1, "wide_spread": 1, "stale_trade": 1, "dte_window": 1},
        )

    def test_evidence_score_uses_the_published_weighting(self):
        score = compute_evidence_score(
            options_axis=80,
            valid_contracts=10,
            price_axis=-50,
            volume_percentile=60,
            trend_confirmation=100,
        )

        self.assertEqual(score, 67.0)

    def test_trade_plan_uses_conditional_trigger_structure_and_r_targets(self):
        idea = build_trade_idea(
            ticker="AAPL",
            quadrant="Chase",
            evidence_score=80,
            scan_date=date(2026, 8, 28),
            high=201,
            low=195,
            close=200,
            atr=4,
            swing_low=190,
            swing_high=205,
            technical_confirmed=True,
        )

        self.assertIsNotNone(idea)
        self.assertEqual(idea.direction, "long")
        self.assertAlmostEqual(idea.trigger, 201.4)
        self.assertAlmostEqual(idea.stop, 190.0)
        self.assertAlmostEqual(idea.target_1r, 212.8)
        self.assertAlmostEqual(idea.target_2r, 224.2)

    def test_hedged_rally_and_excessively_wide_risk_are_watch_only(self):
        common = dict(
            ticker="AAPL",
            evidence_score=90,
            scan_date=date(2026, 8, 28),
            high=201,
            low=195,
            close=200,
            atr=4,
            swing_low=180,
            swing_high=220,
            technical_confirmed=True,
        )
        self.assertIsNone(build_trade_idea(quadrant="Hedged Rally", **common))
        self.assertIsNone(build_trade_idea(quadrant="Chase", **common))

    def test_forward_log_uses_stop_first_when_stop_and_target_share_a_daily_bar(self):
        idea = TradeIdea(
            ticker="AAPL",
            quadrant="Chase",
            direction="long",
            evidence_score=80,
            scan_date=date(2026, 8, 28),
            trigger=100,
            stop=95,
            target_1r=105,
            target_2r=110,
            expires_after_sessions=5,
            max_holding_sessions=20,
        )
        bars = [
            DailyBar(date(2026, 8, 31), 99, 101, 98, 100, 1_000),
            DailyBar(date(2026, 9, 1), 100, 111, 94, 105, 1_200),
        ]

        outcome = evaluate_idea(idea, bars)

        self.assertEqual(outcome.status, "stopped")
        self.assertEqual(outcome.result_r, -1.0)
        self.assertEqual(outcome.triggered_on, date(2026, 8, 31))
        self.assertEqual(outcome.closed_on, date(2026, 9, 1))


if __name__ == "__main__":
    unittest.main()
