import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from market_radar.providers import AlpacaProvider, CachedProvider, DemoProvider
from market_radar.repository import Repository


class RetriableError(RuntimeError):
    status_code = 429


class FakeStockClient:
    def __init__(self, response, fail_once=False):
        self.response = response
        self.fail_once = fail_once
        self.calls = 0

    def get_stock_bars(self, request):
        del request
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise RetriableError("rate limited")
        return self.response


class FakeOptionClient:
    def __init__(self, response):
        self.response = response

    def get_option_chain(self, request):
        del request
        return self.response


class ProviderTest(unittest.TestCase):
    def test_demo_prices_are_consistent_across_overlapping_windows(self):
        provider = DemoProvider()
        earlier = provider.get_daily_bars(["PLTR"], date(2026, 8, 1), date(2026, 8, 27))["PLTR"]
        later = provider.get_daily_bars(["PLTR"], date(2026, 8, 20), date(2026, 8, 28))["PLTR"]
        self.assertEqual([bar for bar in earlier if bar.session >= date(2026, 8, 20)], later[:-1])
        self.assertNotEqual(later[-1].close, later[-2].close)

    def test_demo_provider_is_repeatable_and_has_valid_after_close_data(self):
        provider = DemoProvider()
        as_of = date(2026, 8, 28)

        first = provider.get_daily_bars(["AAPL", "SPY"], date(2025, 8, 1), as_of)
        second = provider.get_daily_bars(["AAPL", "SPY"], date(2025, 8, 1), as_of)
        chain = provider.get_option_chain("AAPL", as_of)

        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first["AAPL"]), 250)
        self.assertEqual(first["AAPL"][-1].session, as_of)
        self.assertGreaterEqual(len(chain), 20)
        self.assertTrue(all(contract.trade_timestamp.date() == as_of for contract in chain))

    def test_alpaca_provider_normalizes_sdk_bar_and_option_shapes(self):
        bar = SimpleNamespace(
            timestamp=datetime(2026, 8, 28, tzinfo=timezone.utc),
            open=100,
            high=105,
            low=99,
            close=104,
            volume=12345,
        )
        stock_response = SimpleNamespace(data={"AAPL": [bar]})
        trade = SimpleNamespace(price=3.2, size=4, timestamp=datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc))
        quote = SimpleNamespace(bid_price=3.0, ask_price=3.4)
        snapshot = SimpleNamespace(latest_trade=trade, latest_quote=quote, greeks=SimpleNamespace(delta=0.45))
        option_response = {"AAPL260918C00150000": snapshot}
        provider = AlpacaProvider(
            stock_client=FakeStockClient(stock_response),
            option_client=FakeOptionClient(option_response),
            sleeper=lambda _: None,
        )

        bars = provider.get_daily_bars(["AAPL"], date(2026, 8, 1), date(2026, 8, 28))
        chain = provider.get_option_chain("AAPL", date(2026, 8, 28))

        self.assertEqual(bars["AAPL"][0].close, 104)
        self.assertEqual(chain[0].contract_type, "call")
        self.assertEqual(chain[0].expiration, date(2026, 9, 18))
        self.assertEqual(chain[0].last_size, 4)

    def test_alpaca_provider_retries_rate_limits_at_the_system_boundary(self):
        response = SimpleNamespace(data={"AAPL": []})
        client = FakeStockClient(response, fail_once=True)
        waits = []
        provider = AlpacaProvider(stock_client=client, option_client=FakeOptionClient({}), sleeper=waits.append)

        provider.get_daily_bars(["AAPL"], date(2026, 8, 1), date(2026, 8, 28))

        self.assertEqual(client.calls, 2)
        self.assertEqual(waits, [1.0])

    def test_cached_provider_reuses_after_close_source_values(self):
        class CountingDemo(DemoProvider):
            def __init__(self):
                self.bar_calls = 0
                self.chain_calls = 0

            def get_daily_bars(self, symbols, start, end):
                self.bar_calls += 1
                return super().get_daily_bars(symbols, start, end)

            def get_option_chain(self, symbol, as_of):
                self.chain_calls += 1
                return super().get_option_chain(symbol, as_of)

        with TemporaryDirectory() as directory:
            inner = CountingDemo()
            provider = CachedProvider(inner, Repository(Path(directory) / "radar.db"))
            as_of = date(2026, 8, 28)
            first_bars = provider.get_daily_bars(["AAPL"], date(2025, 8, 1), as_of)
            second_bars = provider.get_daily_bars(["AAPL"], date(2025, 8, 1), as_of)
            first_chain = provider.get_option_chain("AAPL", as_of)
            second_chain = provider.get_option_chain("AAPL", as_of)

        self.assertEqual(first_bars, second_bars)
        self.assertEqual(first_chain, second_chain)
        self.assertEqual(inner.bar_calls, 1)
        self.assertEqual(inner.chain_calls, 1)


if __name__ == "__main__":
    unittest.main()
