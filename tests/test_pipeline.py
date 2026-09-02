import math
import threading
import time
import unittest
from datetime import date, datetime, timedelta, timezone

from market_radar.models import DailyBar, OptionContract, UniverseMember
from market_radar.pipeline import analyze_price_universe, run_scan, select_option_candidates
from market_radar.providers import DemoProvider


def rising_bars(start, daily_change, volume=1_000_000, sessions=230):
    bars = []
    price = start
    session = date(2025, 10, 1)
    while len(bars) < sessions:
        if session.weekday() < 5:
            price *= 1 + daily_change
            bars.append(DailyBar(session, price * 0.995, price * 1.01, price * 0.99, price, volume))
        session += timedelta(days=1)
    return bars


def with_last_volume(bars, volume):
    last = bars[-1]
    return bars[:-1] + [DailyBar(last.session, last.open, last.high, last.low, last.close, volume)]


class FakeProvider:
    name = "fake"
    stock_feed = "fixture"
    option_feed = "indicative"

    def __init__(self, bars, failed_symbol=None):
        self.bars = bars
        self.failed_symbol = failed_symbol

    def get_daily_bars(self, symbols, start, end):
        del start, end
        return {symbol: self.bars[symbol] for symbol in symbols if symbol in self.bars}

    def get_option_chain(self, symbol, as_of):
        if symbol == self.failed_symbol:
            raise RuntimeError("fixture failure")
        timestamp = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=20)
        return [
            OptionContract(
                f"{symbol}-C-{index}",
                "call",
                0.50,
                9.0,
                10.0,
                10.0,
                1,
                timestamp,
                as_of + timedelta(days=21),
            )
            for index in range(25)
        ]


class ConcurrencyProvider(FakeProvider):
    def __init__(self, bars):
        super().__init__(bars)
        self.active = 0
        self.maximum_active = 0
        self.lock = threading.Lock()

    def get_option_chain(self, symbol, as_of):
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        time.sleep(0.02)
        try:
            return super().get_option_chain(symbol, as_of)
        finally:
            with self.lock:
                self.active -= 1


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.universe = [
            UniverseMember("AAA", "Alpha", "Technology", "XLK"),
            UniverseMember("BBB", "Beta", "Technology", "XLK"),
            UniverseMember("CCC", "Gamma", "Technology", "XLK", is_watchlist=True),
        ]
        self.bars = {
            "SPY": rising_bars(100, 0.0005),
            "XLK": rising_bars(100, 0.0007),
            "AAA": with_last_volume(rising_bars(100, 0.0030), 2_000_000),
            "BBB": with_last_volume(rising_bars(100, -0.0020), 500_000),
            "CCC": rising_bars(100, 0.0010),
        }
        self.as_of = self.bars["SPY"][-1].session

    def test_price_analysis_ranks_sector_and_market_relative_performance(self):
        signals = analyze_price_universe(self.bars, self.universe, self.as_of)
        by_ticker = {signal.ticker: signal for signal in signals}

        self.assertGreater(by_ticker["AAA"].price_axis, by_ticker["CCC"].price_axis)
        self.assertGreater(by_ticker["CCC"].price_axis, by_ticker["BBB"].price_axis)
        self.assertEqual(by_ticker["AAA"].volume_percentile, 100.0)
        self.assertEqual(by_ticker["BBB"].volume_percentile, 0.0)
        self.assertGreater(by_ticker["AAA"].ema20, by_ticker["AAA"].ema50)
        self.assertTrue(math.isfinite(by_ticker["AAA"].atr14))
        expected_turnover = sum(bar.close * bar.volume for bar in self.bars["AAA"][-5:])
        self.assertEqual(by_ticker["AAA"].dollar_turnover_5d, round(expected_turnover, 2))
        self.assertEqual(len(by_ticker["AAA"].price_history), 126)
        self.assertEqual(len(by_ticker["AAA"].relative_history), 63)
        self.assertEqual(by_ticker["AAA"].relative_history[0]["stock"], 100.0)
        self.assertEqual(by_ticker["AAA"].relative_history[0]["sector"], 100.0)
        self.assertEqual(by_ticker["AAA"].relative_history[0]["spy"], 100.0)

    def test_price_analysis_preserves_company_industry_metadata(self):
        member = UniverseMember("AAA", "Alpha Systems", "Technology", "XLK", industry="Application Software")

        signal = analyze_price_universe(self.bars, [member], self.as_of)[0]

        self.assertEqual(signal.name, "Alpha Systems")
        self.assertEqual(signal.industry, "Application Software")

    def test_candidate_selection_keeps_both_sides_and_watchlist(self):
        signals = analyze_price_universe(self.bars, self.universe, self.as_of)

        selected = select_option_candidates(signals, {"CCC"}, per_side=1, watchlist_limit=1)

        self.assertEqual(set(selected), {"AAA", "BBB", "CCC"})

    def test_scan_returns_partial_result_when_one_option_chain_fails(self):
        provider = FakeProvider(self.bars, failed_symbol="BBB")

        result = run_scan(provider, self.universe, self.as_of, scan_type="manual")

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.provider, "fake")
        self.assertEqual(len(result.signals), 3)
        self.assertEqual(
            {signal.ticker for signal in result.signals if signal.options_axis is not None}, {"AAA", "CCC"}
        )
        self.assertTrue(any("BBB" in warning for warning in result.warnings))
        self.assertTrue(any(idea.ticker == "AAA" for idea in result.ideas))

    def test_scan_bounds_parallel_option_requests_to_five(self):
        source = self.bars["AAA"]
        members = [UniverseMember(f"T{index:02d}", f"Ticker {index}", "Technology", "XLK") for index in range(12)]
        bars = {"SPY": self.bars["SPY"], "XLK": self.bars["XLK"]}
        bars.update({member.ticker: source for member in members})
        provider = ConcurrencyProvider(bars)

        run_scan(provider, members, self.as_of)

        self.assertGreater(provider.maximum_active, 1)
        self.assertLessEqual(provider.maximum_active, 5)

    def test_demo_scan_includes_a_global_cross_asset_snapshot(self):
        result = run_scan(DemoProvider(), self.universe, self.as_of)

        macro = result.market_regime["global_macro"]
        self.assertEqual(macro["as_of"], self.as_of.isoformat())
        self.assertEqual(len(macro["assets"]), 9)
        self.assertIn(macro["risk_label"], {"Risk-on", "Balanced", "Defensive"})


if __name__ == "__main__":
    unittest.main()
