"""Portfolio valuation and review rules; independent of synthetic scanner signals."""

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .models import CashBalance, PortfolioPosition

MAX_HOLDINGS = 100
CURRENCIES = {"USD", "EUR", "GBP"}


def number(value, label, minimum=0):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(value) or value < minimum or value > 1e12:
        raise ValueError(f"{label} is outside the supported range")
    return value


def export_portfolio(positions, cash, currency):
    return json.dumps({
        "version": 1, "base_currency": currency,
        "positions": [asdict(p) for p in positions],
        "cash": [asdict(c) for c in cash],
    }, default=lambda value: value.isoformat(), indent=2, allow_nan=False)


def import_portfolio(raw):
    """Validate the entire document before a caller writes anything."""
    if len(raw) > 250_000:
        raise ValueError("Portfolio file must be under 250 KB")
    try:
        data = json.loads(raw)
        if data.get("version") != 1 or data.get("base_currency") not in CURRENCIES:
            raise ValueError("Use a version 1 portfolio with EUR, USD or GBP as base currency")
        rows = data["positions"]
        if not isinstance(rows, list) or len(rows) > MAX_HOLDINGS:
            raise ValueError("A portfolio supports up to 100 holdings")
        positions = []
        seen = set()
        for row in rows:
            ticker = str(row["ticker"]).strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", ticker) or ticker in seen:
                raise ValueError("Tickers must be valid and unique")
            seen.add(ticker)
            currency = row.get("quote_currency", "USD")
            if currency not in CURRENCIES:
                raise ValueError("Quote currency must be USD, EUR or GBP")
            values = {key: str(row.get(key, default))[:300] for key, default in (
                ("name", ticker), ("sector", "Unclassified"), ("sector_etf", "SPY"),
                ("industry", "Unclassified"), ("thesis", ""), ("reference_source", "User import"),
            )}
            for key in ("average_cost", "reference_price", "reference_value_base"):
                values[key] = number(row[key], key) if row.get(key) is not None else None
            for key in ("created_at", "updated_at", "reference_price_at"):
                values[key] = datetime.fromisoformat(row[key]) if row.get(key) else None
            rate = number(row.get("fx_to_base", 1), "FX rate", 0.000001)
            if currency == data["base_currency"] and rate != 1:
                raise ValueError("FX must equal 1 when quote and base currencies match")
            positions.append(PortfolioPosition(
                ticker=ticker, shares=number(row["shares"], "Shares", 0.000001),
                quote_currency=currency, fx_to_base=rate, **values,
            ))
        cash = []
        seen_cash = set()
        for row in data.get("cash", []):
            currency = row["currency"]
            if currency not in CURRENCIES or currency in seen_cash:
                raise ValueError("Cash currencies must be valid and unique")
            seen_cash.add(currency)
            rate = number(row.get("fx_to_base", 1), "Cash FX", 0.000001)
            if currency == data["base_currency"] and rate != 1:
                raise ValueError("Base currency cash FX must equal 1")
            cash.append(CashBalance(currency, number(row["amount"], "Cash"), rate))
        return positions, cash, data["base_currency"]
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid portfolio file. Use the downloadable example or backup format.") from exc


def refresh_prices(provider, repository, positions, now=None):
    """Fetch only US holdings, bounded to four workers. Never request shares or cost data."""
    if provider.name == "demo":
        raise ValueError("Synthetic providers cannot update personal portfolios")
    now = now or datetime.now(timezone.utc)
    session = provider.latest_completed_session(now)
    existing = repository.cache_get("portfolio_closes") or {"symbols": {}}
    symbols = dict(existing.get("symbols", {}))
    wanted = sorted({p.ticker for p in positions if p.quote_currency == "USD"} | {"SPY"})
    wanted = [ticker for ticker in wanted if symbols.get(ticker, {}).get("as_of") != session.isoformat()]
    errors = []

    def fetch(ticker):
        bars = provider.get_daily_bars([ticker], session - timedelta(days=16), session).get(ticker, [])
        bars = sorted((b for b in bars if b.session <= session), key=lambda b: b.session)
        if len(bars) < 2 or bars[-1].session != session:
            raise ValueError("No current completed close")
        if any(not math.isfinite(b.close) or b.close <= 0 for b in bars):
            raise ValueError("Invalid closing prices")
        return {"as_of": session.isoformat(), "close": bars[-1].close,
                "previous_close": bars[-2].close, "previous_as_of": bars[-2].session.isoformat(),
                "currency": "USD", "source": f"{provider.name} / {provider.stock_feed}",
                "fetched_at": now.isoformat()}

    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(fetch, ticker): ticker for ticker in wanted[:MAX_HOLDINGS + 1]}
        for task in as_completed(tasks):
            ticker = tasks[task]
            try:
                symbols[ticker] = task.result()
            except Exception:
                errors.append(ticker)
    result = {"symbols": symbols, "session": session.isoformat(), "errors": sorted(errors),
              "checked_at": now.isoformat()}
    repository.cache_put("portfolio_closes", result)
    return result


def portfolio_report(positions, cash, currency, prices=None, max_weight=0.25):
    prices = prices or {}
    quotes = prices.get("symbols", {})
    rows, actions = [], []
    for p in positions:
        quote = quotes.get(p.ticker)
        # Unsupported currencies and undated screenshots require explicit confirmation.
        if quote and (quote.get("currency") != p.quote_currency or (
            p.reference_price is not None and (p.reference_price_at is None
            or quote["as_of"] < p.reference_price_at.date().isoformat())
        )):
            quote = None
        value = p.reference_value_base
        price = p.reference_price
        source = p.reference_source or "Manual reference"
        as_of = p.reference_price_at.date().isoformat() if p.reference_price_at else None
        movement = None
        if quote:
            price, source, as_of = quote["close"], quote["source"], quote["as_of"]
            value = price * p.shares * p.fx_to_base
            if as_of == prices.get("session"):
                movement = (price - quote["previous_close"]) * p.shares * p.fx_to_base
        elif value is None and price is not None:
            value = price * p.shares * p.fx_to_base
        # Screenshot percentage gains do not establish historical purchase FX or tax cost.
        inferred_cost = "screenshot" in p.reference_source.lower()
        pnl = ((price - p.average_cost) * p.shares * p.fx_to_base
               if price is not None and p.average_cost is not None and not inferred_cost else None)
        rows.append({"ticker": p.ticker, "name": p.name, "sector": p.sector,
                     "shares": p.shares, "currency": p.quote_currency, "price": price,
                     "value": value, "daily_change": movement, "pnl": pnl,
                     "source": source, "as_of": as_of, "thesis": p.thesis,
                     "fx": p.fx_to_base, "previous_as_of": quote.get("previous_as_of") if quote else None})
    cash_value = sum(c.amount * c.fx_to_base for c in cash)
    invested = sum(r["value"] or 0 for r in rows)
    total = invested + cash_value
    for row in rows:
        row["weight"] = (row["value"] or 0) / total if total else 0
    rows.sort(key=lambda r: r["value"] or 0, reverse=True)
    complete = bool(rows) and all(r["value"] is not None for r in rows)
    daily_rows = [r for r in rows if r["daily_change"] is not None]
    daily_complete = complete and len(daily_rows) == len(rows) and len({r["previous_as_of"] for r in rows}) == 1
    daily = sum(r["daily_change"] for r in daily_rows) if daily_complete else None
    sectors, currencies = {}, {}
    for row in rows:
        sectors[row["sector"]] = sectors.get(row["sector"], 0) + (row["value"] or 0)
        currencies[row["currency"]] = currencies.get(row["currency"], 0) + (row["value"] or 0)
    if rows and complete and rows[0]["weight"] > max_weight:
        largest = rows[0]
        excess = largest["value"] - total * max_weight
        actions.append({"title": f"Review {largest['ticker']} concentration",
                        "why": f"It is {largest['weight']:.1%} of your portfolio, above your {max_weight:.0%} review limit.",
                        "action": "Consider directing new contributions elsewhere, or review a gradual reduction after considering tax and your thesis.",
                        "scenario": f"At unchanged prices, shifting {currency} {excess:,.2f} to cash would reach that limit."})
    if currencies.get("USD", 0) and currency != "USD" and total:
        actions.append({"title": "Understand your dollar exposure",
                        "why": f"USD-quoted holdings represent {currencies['USD'] / total:.1%} of the valued portfolio.",
                        "action": "Review this alongside your spending currency. Quotation currency is not the same as company revenue exposure.",
                        "scenario": f"If USD fell 10% against {currency} with stock prices unchanged, those holdings would lose about {currency} {currencies['USD'] * .1:,.0f}."})
    if rows:
        actions.append({"title": "Keep a reason for every holding",
                        "why": f"{sum(not r['thesis'].strip() for r in rows)} holdings have no saved investment thesis.",
                        "action": "Write why you own each company and what evidence would make you reconsider it.", "scenario": ""})
    allocation_weights = [(r["value"] or 0) / invested for r in rows] if invested else []
    concentration = sum(w * w for w in allocation_weights)
    largest = rows[0] if rows else None
    diagnostics = {
        "effective_holdings": 1 / concentration if concentration else None,
        "cash_weight": cash_value / total if total else None,
        "over_limit": sum(r["weight"] > max_weight for r in rows),
        "largest_drop_20": largest["value"] * .2 if largest and complete else None,
        "new_cash_to_limit": max(0, largest["value"] / max_weight - total) if largest and complete else None,
        "usd_drop_10": currencies.get("USD", 0) * .1 if complete and currency != "USD" else None,
    }
    return {"rows": rows, "total": total if rows or cash else None, "invested": invested,
            "diagnostics": diagnostics,
            "cash": cash_value, "complete": complete, "daily": daily,
            "daily_coverage": len(daily_rows), "sectors": sectors, "currencies": currencies,
            "actions": actions, "top_three": sum(r["weight"] for r in rows[:3])}
