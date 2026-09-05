import hashlib
import json
from datetime import date, datetime

from ..models import DailyBar, OptionContract


class CachedProvider:
    """Persistent cache for immutable, after-close provider-boundary responses."""

    def __init__(self, provider, repository):
        self.provider = provider
        self.repository = repository
        self.name = provider.name
        self.stock_feed = provider.stock_feed
        self.option_feed = provider.option_feed

    def _key(self, operation: str, payload) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"{self.name}:{operation}:{digest}"

    def latest_completed_session(self, now: datetime) -> date:
        return self.provider.latest_completed_session(now)

    def get_portfolio_history(self, symbol, start, end):
        return self.provider.get_portfolio_history(symbol, start, end)

    def get_portfolio_options(self, symbol, as_of):
        return self.provider.get_portfolio_options(symbol, as_of)

    def get_daily_bars(self, symbols, start: date, end: date):
        symbol_list = sorted(set(symbols))
        key = self._key(
            "daily-bars",
            {"symbols": symbol_list, "start": start.isoformat(), "end": end.isoformat(), "feed": self.stock_feed},
        )
        cached = self.repository.cache_get(key)
        if cached is not None:
            return {
                ticker: [
                    DailyBar(
                        date.fromisoformat(item["session"]),
                        item["open"],
                        item["high"],
                        item["low"],
                        item["close"],
                        item["volume"],
                    )
                    for item in values
                ]
                for ticker, values in cached.items()
            }
        result = self.provider.get_daily_bars(symbol_list, start, end)
        self.repository.cache_put(
            key,
            {ticker: [bar.to_dict() for bar in bars] for ticker, bars in result.items()},
        )
        return result

    def get_option_chain(self, symbol: str, as_of: date):
        key = self._key(
            "option-chain",
            {"symbol": symbol, "as_of": as_of.isoformat(), "feed": self.option_feed},
        )
        cached = self.repository.cache_get(key)
        if cached is not None:
            return [
                OptionContract(
                    item["symbol"],
                    item["contract_type"],
                    item["delta"],
                    item["bid"],
                    item["ask"],
                    item["last_price"],
                    item["last_size"],
                    datetime.fromisoformat(item["trade_timestamp"]),
                    date.fromisoformat(item["expiration"]),
                )
                for item in cached
            ]
        result = self.provider.get_option_chain(symbol, as_of)
        self.repository.cache_put(
            key,
            [
                {
                    "symbol": item.symbol,
                    "contract_type": item.contract_type,
                    "delta": item.delta,
                    "bid": item.bid,
                    "ask": item.ask,
                    "last_price": item.last_price,
                    "last_size": item.last_size,
                    "trade_timestamp": item.trade_timestamp.isoformat(),
                    "expiration": item.expiration.isoformat(),
                }
                for item in result
            ],
        )
        return result
