import unittest

from market_radar.models import SymbolSignal
from market_radar.stock_profile import build_stock_profile


class StockProfileTest(unittest.TestCase):
    def test_builds_six_decision_kpis_and_two_explanatory_charts(self):
        signal = SymbolSignal(
            ticker="PLTR",
            name="Palantir Technologies",
            sector="Information Technology",
            sector_etf="XLK",
            as_of=__import__("datetime").date(2026, 8, 31),
            close=120.0,
            high=122.0,
            low=117.0,
            atr14=4.8,
            ema20=115.0,
            ema50=110.0,
            ema200=90.0,
            return_5d=0.06,
            return_20d=0.14,
            sector_relative_5d=0.03,
            spy_relative_20d=0.10,
            price_axis=75.0,
            volume_ratio=1.3,
            volume_percentile=80.0,
            trend_confirmation=100.0,
            swing_low_10d=105.0,
            swing_high_10d=122.0,
            dollar_turnover_5d=12_500_000_000,
            price_history=[
                {"session": f"2026-08-{day:02d}", "close": 90.0 + day, "volume": 1_000_000 + day * 1000}
                for day in range(1, 21)
            ],
            relative_history=[
                {
                    "session": f"2026-08-{day:02d}",
                    "stock": 100.0 + day,
                    "sector": 100.0 + day * 0.5,
                    "spy": 100.0 + day * 0.25,
                }
                for day in range(1, 21)
            ],
        )

        profile = build_stock_profile(signal)

        self.assertEqual(len(profile.kpis), 6)
        self.assertEqual(profile.trend_label, "Strong uptrend")
        self.assertIn("above its 20-, 50-, and 200-session averages", profile.trend_explanation)
        self.assertEqual(len(profile.price_figure.data), 4)
        self.assertEqual(len(profile.relative_figure.data), 3)
        self.assertEqual(profile.relative_figure.layout.yaxis.title.text, "Growth of 100")


if __name__ == "__main__":
    unittest.main()
