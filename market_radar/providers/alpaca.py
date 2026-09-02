import re
import time as time_module
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ..models import DailyBar, OptionContract

OCC_PATTERN = re.compile(r"^([A-Z.]+)(\d{6})([CP])(\d{8})$")


def _value(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class AlpacaProvider:
    name = "alpaca"
    stock_feed = "iex"
    option_feed = "indicative"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        stock_client=None,
        option_client=None,
        sleeper=time_module.sleep,
        maximum_attempts: int = 3,
    ):
        self.sleeper = sleeper
        self.maximum_attempts = maximum_attempts
        self._sdk = None
        if stock_client is None or option_client is None:
            try:
                from alpaca.data.enums import DataFeed, OptionsFeed
                from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
                from alpaca.data.requests import OptionChainRequest, StockBarsRequest
                from alpaca.data.timeframe import TimeFrame
            except ImportError as exc:
                raise RuntimeError("alpaca-py is required for live scans; install the project dependencies") from exc
            if not api_key or not secret_key:
                raise ValueError("ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY are required for live scans")
            stock_client = StockHistoricalDataClient(api_key, secret_key)
            option_client = OptionHistoricalDataClient(api_key, secret_key)
            self._sdk = {
                "DataFeed": DataFeed,
                "OptionsFeed": OptionsFeed,
                "OptionChainRequest": OptionChainRequest,
                "StockBarsRequest": StockBarsRequest,
                "TimeFrame": TimeFrame,
            }
        self.stock_client = stock_client
        self.option_client = option_client

    def _retry(self, operation):
        delay = 1.0
        for attempt in range(self.maximum_attempts):
            try:
                return operation()
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                retriable = status == 429 or (isinstance(status, int) and status >= 500)
                if not retriable or attempt + 1 >= self.maximum_attempts:
                    raise
                self.sleeper(delay)
                delay *= 2.0
        raise RuntimeError("unreachable")

    def _stock_request(self, symbols: Iterable[str], start: date, end: date):
        if self._sdk is None:
            return {"symbols": list(symbols), "start": start, "end": end, "feed": "iex"}
        return self._sdk["StockBarsRequest"](
            symbol_or_symbols=list(symbols),
            timeframe=self._sdk["TimeFrame"].Day,
            start=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
            end=datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
            feed=self._sdk["DataFeed"].IEX,
        )

    def get_daily_bars(self, symbols: Iterable[str], start: date, end: date):
        symbol_list = list(symbols)
        response = self._retry(lambda: self.stock_client.get_stock_bars(self._stock_request(symbol_list, start, end)))
        data = _value(response, "data", response)
        result = {}
        for ticker in symbol_list:
            normalized = []
            for bar in data.get(ticker, []):
                timestamp = _value(bar, "timestamp")
                session = (
                    timestamp.date() if isinstance(timestamp, datetime) else date.fromisoformat(str(timestamp)[:10])
                )
                normalized.append(
                    DailyBar(
                        session,
                        float(_value(bar, "open")),
                        float(_value(bar, "high")),
                        float(_value(bar, "low")),
                        float(_value(bar, "close")),
                        float(_value(bar, "volume")),
                    )
                )
            result[ticker] = sorted(normalized, key=lambda item: item.session)
        return result

    def _option_request(self, symbol: str, as_of: date):
        if self._sdk is None:
            return {
                "underlying_symbol": symbol,
                "feed": "indicative",
                "expiration_date_gte": as_of + timedelta(days=7),
                "expiration_date_lte": as_of + timedelta(days=45),
            }
        return self._sdk["OptionChainRequest"](
            underlying_symbol=symbol,
            feed=self._sdk["OptionsFeed"].INDICATIVE,
            expiration_date_gte=as_of + timedelta(days=7),
            expiration_date_lte=as_of + timedelta(days=45),
        )

    @staticmethod
    def _contract_identity(symbol: str):
        match = OCC_PATTERN.match(symbol.replace(" ", ""))
        if not match:
            raise ValueError(f"Unsupported OCC option symbol: {symbol}")
        expiration = datetime.strptime(match.group(2), "%y%m%d").date()
        contract_type = "call" if match.group(3) == "C" else "put"
        return contract_type, expiration

    def get_option_chain(self, symbol: str, as_of: date):
        response = self._retry(lambda: self.option_client.get_option_chain(self._option_request(symbol, as_of)))
        data = _value(response, "data", response)
        contracts = []
        for option_symbol, snapshot in data.items():
            try:
                contract_type, expiration = self._contract_identity(option_symbol)
                trade = _value(snapshot, "latest_trade")
                quote = _value(snapshot, "latest_quote")
                greeks = _value(snapshot, "greeks")
                if trade is None or quote is None or greeks is None:
                    continue
                contracts.append(
                    OptionContract(
                        option_symbol,
                        contract_type,
                        float(_value(greeks, "delta", 0.0)),
                        float(_value(quote, "bid_price", 0.0)),
                        float(_value(quote, "ask_price", 0.0)),
                        float(_value(trade, "price", 0.0)),
                        int(_value(trade, "size", 0)),
                        _value(trade, "timestamp"),
                        expiration,
                    )
                )
            except (TypeError, ValueError):
                continue
        return contracts

    def latest_completed_session(self, now: datetime) -> date:
        from zoneinfo import ZoneInfo

        local = now.astimezone(ZoneInfo("America/New_York"))
        end = local.date() if (local.hour, local.minute) >= (17, 15) else local.date() - timedelta(days=1)
        bars = self.get_daily_bars(["SPY"], end - timedelta(days=14), end).get("SPY", [])
        if not bars:
            raise RuntimeError("Alpaca returned no completed SPY session in the last 14 days")
        return bars[-1].session
