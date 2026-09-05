"""Fixed fictional public example. Never derived from a user's portfolio."""

import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from .models import CashBalance, PortfolioPosition
from .portfolio_intelligence import VERSION, option_evidence

SESSION = date(2026, 9, 4)
TOTAL = 62384.71


def populate_showcase(repo):
    rng = np.random.default_rng(62384)
    days = pd.bdate_range(end=SESSION, periods=260)
    common = rng.normal(.0003, .009, len(days))
    specs = [
        ("NVDA", "NVIDIA", "Information Technology", "XLK", 18000, .58),
        ("MSFT", "Microsoft", "Information Technology", "XLK", 11500, .29),
        ("AAPL", "Apple", "Information Technology", "XLK", 8200, .31),
        ("JPM", "JPMorgan Chase", "Financials", "XLF", 6500, .25),
        ("COST", "Costco", "Consumer Staples", "XLP", 5200, .24),
        ("XOM", "Exxon Mobil", "Energy", "XLE", 4000, .30),
        ("JNJ", "Johnson & Johnson", "Health Care", "XLV", 3000, .20),
        ("DIS", "Walt Disney", "Communication Services", "XLC", 2500, .36),
    ]
    symbols, closes = {}, {}
    for index, (ticker, name, sector, etf, value, iv) in enumerate(specs):
        returns = common * (.7 + index / 15) + rng.normal(.0002, iv / math.sqrt(252) * .65, len(days))
        returns[-1] = [.018, .007, -.004, .003, .002, -.011, .001, -.006][index]
        history = (100 + index * 23) * np.exp(np.cumsum(returns))
        price = float(history[-1])
        shares = value / (.92 * price)
        repo.upsert_position(PortfolioPosition(ticker, name, sector, etf, shares,
                             quote_currency="USD", fx_to_base=.92, reference_price=price,
                             reference_value_base=value, reference_price_at=datetime(2026, 9, 4),
                             reference_source="Synthetic showcase — fictional prices and holdings",
                             thesis="Example thesis: review business execution, valuation and concentration."))
        raw = [{"symbol": f"SYNTHETIC-{ticker}-{kind}-{delta}", "type": kind,
                "expiration": (SESSION + timedelta(days=30)).isoformat(), "strike": price,
                "iv": vol, "delta": delta, "bid": 2, "ask": 2.1, "quote_at": "2026-09-04T19:59:00Z"}
               for kind, delta, vol in [("call", .5, iv), ("put", -.5, iv),
                                        ("call", .25, iv), ("put", -.25, iv + .025 + index * .008)]]
        symbols[ticker] = {"history_session": SESSION.isoformat(), "option_session": SESSION.isoformat(),
                           "history": [{"date": day.date().isoformat(), "close": float(p)} for day, p in zip(days, history)],
                           "raw_options": raw, "options": option_evidence(raw, SESSION)}
        closes[ticker] = {"as_of": SESSION.isoformat(), "close": price, "previous_close": float(history[-2]),
                          "previous_as_of": days[-2].date().isoformat(), "currency": "USD", "source": "Synthetic showcase"}
    repo.set_setting("portfolio_base_currency", "EUR")
    repo.set_setting("synthetic_showcase", "1")
    repo.upsert_cash_balance(CashBalance("EUR", TOTAL - sum(s[4] for s in specs)))
    repo.cache_put("portfolio_closes", {"session": SESSION.isoformat(), "symbols": closes, "errors": [], "synthetic": True})
    repo.cache_put("portfolio_market_evidence", {"symbols": symbols, "session": SESSION.isoformat(),
                   "source": "Seeded synthetic fixture — not market observations", "feed": "synthetic", "version": VERSION,
                   "synthetic": True, "errors": {}})
    repo.cache_put("synthetic_earnings", {"coverage": sum(s[4] for s in specs) / TOTAL,
                   "weight30": (11500 + 5200 + 2500) / TOTAL, "weight7": 5200 / TOTAL,
                   "events": [{"ticker": "COST", "date": "2026-09-09"},
                              {"ticker": "MSFT", "date": "2026-09-18"}, {"ticker": "DIS", "date": "2026-09-28"}]})
