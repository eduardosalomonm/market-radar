import unittest
from datetime import date

from test_pipeline import rising_bars

from market_radar.macro import MACRO_ASSETS, analyze_global_macro


class GlobalMacroTest(unittest.TestCase):
    def test_constructive_cross_asset_tape_is_explained_in_plain_language(self):
        bars = {
            "SPY": rising_bars(100, 0.0012),
            "EFA": rising_bars(100, 0.0010),
            "EEM": rising_bars(100, 0.0015),
            "HYG": rising_bars(100, 0.0004),
            "TLT": rising_bars(100, -0.0002),
            "UUP": rising_bars(100, -0.0001),
            "GLD": rising_bars(100, 0.0005),
            "USO": rising_bars(100, 0.0018),
            "DBC": rising_bars(100, 0.0015),
        }
        as_of = bars["SPY"][-1].session

        result = analyze_global_macro(bars, as_of)

        self.assertEqual(result["risk_label"], "Risk-on")
        self.assertEqual(result["growth_label"], "Growth assets strengthening")
        self.assertEqual(len(result["assets"]), len(MACRO_ASSETS))
        self.assertGreater(result["risk_score"], 65)
        self.assertTrue(any("global equity leader" in takeaway for takeaway in result["takeaways"]))

    def test_missing_assets_are_reported_without_invalidating_snapshot(self):
        spy = rising_bars(100, 0.0005)

        result = analyze_global_macro({"SPY": spy}, date(2026, 8, 28))

        self.assertIn("EFA", result["missing"])
        self.assertEqual([asset["ticker"] for asset in result["assets"]], ["SPY"])


if __name__ == "__main__":
    unittest.main()
