import unittest
from dataclasses import replace
from datetime import timedelta

from test_pipeline import FakeProvider
from test_pipeline import PipelineTest as _PipelineFixture

from market_radar.daily_intelligence import build_daily_intelligence
from market_radar.models import PortfolioPosition
from market_radar.pipeline import run_scan


class DailyIntelligenceTest(unittest.TestCase):
    def setUp(self):
        fixture = _PipelineFixture()
        fixture.setUp()
        self.current = run_scan(FakeProvider(fixture.bars), fixture.universe, fixture.as_of)
        previous_signals = []
        for signal in self.current.signals:
            if signal.ticker == "AAA":
                previous_signals.append(
                    replace(signal, close=190.0, evidence_score=80.0, quadrant="Contrarian Bid")
                )
            else:
                previous_signals.append(replace(signal, close=signal.close * 1.01))
        previous_idea = replace(self.current.ideas[0], ticker="BBB", quadrant="Fear", direction="short")
        self.previous = replace(
            self.current,
            as_of=self.current.as_of - timedelta(days=1),
            signals=previous_signals,
            ideas=[previous_idea],
            market_regime={**self.current.market_regime, "label": "Bearish trend"},
        )

    def test_watchlist_pulse_explains_price_evidence_and_scan_status(self):
        intelligence = build_daily_intelligence(
            self.current,
            self.previous,
            ["AAA", "BBB", "MISSING"],
        )

        pulse = {row["ticker"]: row for row in intelligence["watchlist_pulse"]}
        self.assertAlmostEqual(pulse["AAA"]["price_change"], self.current.signals[0].close / 190.0 - 1.0)
        self.assertEqual(pulse["AAA"]["evidence_change"], 20.0)
        self.assertEqual(pulse["AAA"]["status"], "Qualified idea")
        self.assertEqual(pulse["MISSING"]["status"], "Awaiting next scan")

    def test_scan_comparison_names_new_removed_and_changed_signals(self):
        intelligence = build_daily_intelligence(self.current, self.previous, ["AAA"])
        changes = intelligence["changes"]

        self.assertEqual(changes["new_ideas"], ["AAA", "CCC"])
        self.assertEqual(changes["removed_ideas"], ["BBB"])
        self.assertEqual(changes["quadrant_changes"][0]["ticker"], "AAA")
        self.assertEqual(
            changes["market_regime"],
            f"Bearish trend → {self.current.market_regime['label']}",
        )
        self.assertTrue(any(item["ticker"] == "AAA" for item in changes["score_moves"]))

    def test_portfolio_update_values_positions_and_filters_low_noise_alerts(self):
        position = PortfolioPosition(
            ticker="AAA",
            name="Alpha",
            sector="Technology",
            sector_etf="XLK",
            shares=10,
            average_cost=180,
        )

        intelligence = build_daily_intelligence(self.current, self.previous, [], [position])
        portfolio = intelligence["portfolio"]

        self.assertEqual(portfolio["position_count"], 1)
        self.assertAlmostEqual(portfolio["market_value"], self.current.signals[0].close * 10)
        self.assertAlmostEqual(portfolio["daily_pnl"], (self.current.signals[0].close - 190) * 10)
        self.assertEqual(intelligence["alerts"][0]["ticker"], "AAA")
        self.assertIn("setup changed", intelligence["alerts"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
