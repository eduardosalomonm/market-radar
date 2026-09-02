import hashlib
import math
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone

from ..models import DailyBar, OptionContract


def _stable_number(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16)


class DemoProvider:
    name = "demo"
    stock_feed = "synthetic"
    option_feed = "indicative"

    def latest_completed_session(self, now: datetime) -> date:
        current = now.date()
        local_hour = now.hour + now.minute / 60.0
        if local_hour < 17.25:
            current -= timedelta(days=1)
        while current.weekday() >= 5:
            current -= timedelta(days=1)
        return current

    def get_daily_bars(self, symbols: Iterable[str], start: date, end: date) -> dict[str, list[DailyBar]]:
        del start
        result = {}
        sessions = []
        current = end - timedelta(days=420)
        while current <= end:
            if current.weekday() < 5:
                sessions.append(current)
            current += timedelta(days=1)
        sessions = sessions[-300:]
        for ticker in symbols:
            seed = _stable_number(ticker)
            drift = ((seed % 17) - 7) / 10000.0
            base = 40.0 + seed % 160
            bars = []
            previous = base
            for index, session in enumerate(sessions):
                cycle = math.sin(index / 11.0 + (seed % 31)) * 0.004
                shock = math.sin(index * 1.7 + (seed % 13)) * 0.002
                close = max(5.0, previous * (1.0 + drift + cycle + shock))
                open_price = previous * (1.0 + shock / 3.0)
                spread = close * (0.008 + (seed % 5) / 1000.0)
                high = max(open_price, close) + spread
                low = min(open_price, close) - spread
                volume = 600_000 + (seed % 4_000_000) + 200_000 * (1.0 + math.sin(index / 5.0))
                bars.append(DailyBar(session, open_price, high, low, close, volume))
                previous = close
            result[ticker] = bars
        return result

    def get_option_chain(self, symbol: str, as_of: date) -> list[OptionContract]:
        seed = _stable_number(symbol)
        bullish_bias = ((seed % 201) - 100) / 100.0
        timestamp = datetime.combine(as_of, time(20, 0), tzinfo=timezone.utc)
        contracts = []
        for index in range(30):
            is_call = index % 2 == 0
            contract_type = "call" if is_call else "put"
            delta = (0.25 + (index % 10) * 0.05) * (1 if is_call else -1)
            midpoint = 1.5 + (index % 7) * 0.35
            spread = midpoint * 0.12
            bid = midpoint - spread / 2.0
            ask = midpoint + spread / 2.0
            directional = bullish_bias * (1 if is_call else -1)
            contract_noise = math.sin(index * 1.37 + (seed % 19)) * 0.45
            aggressor = max(-1.0, min(1.0, directional + contract_noise))
            last_price = midpoint + aggressor * spread / 2.0
            size = 1 + (seed + index * 7) % 8
            expiration = as_of + timedelta(days=14 + (index % 4) * 7)
            contracts.append(
                OptionContract(
                    f"{symbol}-{contract_type}-{index}",
                    contract_type,
                    delta,
                    bid,
                    ask,
                    last_price,
                    size,
                    timestamp,
                    expiration,
                )
            )
        return contracts
