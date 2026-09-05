"""Reproducible portfolio market evidence. No synthetic fallback or growth odds."""

import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

VERSION = "portfolio-market-v1"
NY = ZoneInfo("America/New_York")


def option_evidence(snapshots, session):
    """Interpolate total variance to 30 days; no extrapolation or probability claim."""
    excluded = Counter()
    valid = []
    for item in snapshots:
        try:
            iv, delta, bid, ask = (float(item[k]) for k in ("iv", "delta", "bid", "ask"))
            stamp = datetime.fromisoformat(item["quote_at"].replace("Z", "+00:00"))
            days = (date.fromisoformat(item["expiration"]) - session).days
            if not all(math.isfinite(x) for x in (iv, delta, bid, ask)) or not 0 < iv <= 5 or abs(delta) > 1:
                reason = "invalid_iv_or_greeks"
            elif stamp.tzinfo is None or stamp.astimezone(NY).date() != session:
                reason = "quote_not_in_session"
            elif bid <= 0 or ask < bid or (ask - bid) / ((ask + bid) / 2) > .25:
                reason = "quote_quality"
            elif not 7 <= days <= 45:
                reason = "expiration"
            elif item["type"] not in {"put", "call"} or (item["type"] == "put") != (delta < 0):
                reason = "invalid_type"
            else:
                valid.append(dict(item, iv=iv, delta=delta, days=days))
                continue
            excluded[reason] += 1
        except (KeyError, TypeError, ValueError, AttributeError):
            excluded["missing_or_invalid_fields"] += 1
    expiries = {}
    for days in sorted({i["days"] for i in valid}):
        chain = [i for i in valid if i["days"] == days]
        atm = [i for i in chain if .4 <= abs(i["delta"]) <= .6]
        calls = sorted([i for i in chain if i["type"] == "call" and .2 <= i["delta"] <= .3], key=lambda i: abs(i["delta"] - .25))
        puts = sorted([i for i in chain if i["type"] == "put" and -.3 <= i["delta"] <= -.2], key=lambda i: abs(i["delta"] + .25))
        if atm:
            expiries[days] = {"iv": float(np.mean([i["iv"] for i in atm])),
                              "skew": (puts[0]["iv"] - calls[0]["iv"]) * 100 if puts and calls else None}
    lower = max((d for d in expiries if d <= 30), default=None)
    upper = min((d for d in expiries if d >= 30), default=None)
    result = {"iv30": None, "move30": None, "skew_points": None, "valid": len(valid),
              "excluded": dict(excluded), "expiries": expiries, "session": session.isoformat(), "version": VERSION}
    if lower is not None and upper is not None:
        alpha = (30 - lower) / (upper - lower) if lower != upper else 0
        variance = ((1 - alpha) * expiries[lower]["iv"] ** 2 * lower + alpha * expiries[upper]["iv"] ** 2 * upper) / 365
        result.update(move30=math.sqrt(variance), iv30=math.sqrt(variance * 365 / 30))
        a, b = expiries[lower]["skew"], expiries[upper]["skew"]
        if a is not None and b is not None:
            result["skew_points"] = (1 - alpha) * a + alpha * b
    return result


def refresh_intelligence(provider, repository, positions, now=None):
    if provider.name == "demo":
        raise ValueError("Real provider required")
    now = now or datetime.now(timezone.utc)
    session = provider.latest_completed_session(now)
    cached = repository.cache_get("portfolio_market_evidence") or {"symbols": {}}
    symbols = dict(cached.get("symbols", {}))
    wanted = sorted({p.ticker for p in positions if p.quote_currency == "USD"} | {"SPY"})[:101]
    errors = {}

    def fetch(ticker):
        previous = symbols.get(ticker, {})
        output = dict(previous)
        failures = []
        if previous.get("history_session") != session.isoformat():
            try:
                bars = provider.get_portfolio_history(ticker, session - timedelta(days=550), session)
                bars = sorted([b for b in bars if b.session <= session], key=lambda b: b.session)
                if len(bars) < 61 or bars[-1].session != session or any(not math.isfinite(b.close) or b.close <= 0 for b in bars):
                    raise ValueError("Insufficient adjusted history")
                output.update(history=[{"date": b.session.isoformat(), "close": b.close} for b in bars], history_session=session.isoformat())
            except Exception:
                failures.append("history")
        if previous.get("option_session") != session.isoformat():
            try:
                # Endpoint is latest-only, not an as-of backfill. Quote-session filtering is mandatory.
                raw = provider.get_portfolio_options(ticker, session)
                evidence = option_evidence(raw, session)
                output.update(options=evidence, raw_options=raw, option_session=session.isoformat())
                repository.cache_put(f"portfolio-options:{VERSION}:{provider.name}:{provider.option_feed}:{ticker}:{session}",
                                     {"raw": raw, "evidence": evidence, "retrieved_at": now.isoformat()})
            except Exception:
                failures.append("options")
        return output, failures

    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(fetch, ticker): ticker for ticker in wanted}
        for future in as_completed(tasks):
            ticker = tasks[future]
            try:
                symbols[ticker], failures = future.result()
                if failures:
                    errors[ticker] = failures
            except Exception:
                errors[ticker] = ["unavailable"]
    result = {"symbols": symbols, "session": session.isoformat(), "checked_at": now.isoformat(),
              "source": f"{provider.name}/{provider.stock_feed}", "feed": provider.option_feed,
              "version": VERSION, "errors": errors}
    repository.cache_put("portfolio_market_evidence", result)
    return result


def market_report(valuation, evidence):
    """Current-weight, constant-FX historical model. Never actual investor returns."""
    rows = valuation["rows"]
    total = valuation["total"] or 0
    session = evidence.get("session")
    histories, option_rows, trend_rows = {}, [], []
    for row in rows:
        source = evidence.get("symbols", {}).get(row["ticker"], {})
        if row["currency"] != "USD" or row["value"] is None or row.get("as_of") != session:
            continue
        if source.get("history_session") == session and session:
            series = pd.Series({b["date"]: b["close"] for b in source.get("history", [])}, dtype=float).sort_index()
            if len(series) >= 61 and (series > 0).all() and np.isfinite(series).all():
                histories[row["ticker"]] = series
                trend_rows.append({"ticker": row["ticker"], "weight": row["weight"],
                                   "above50": bool(series.iloc[-1] > series.ewm(span=50, adjust=False).mean().iloc[-1])})
        options = source.get("options", {})
        if options.get("session") == session and options.get("move30") is not None:
            option_rows.append({"ticker": row["ticker"], "weight": row["weight"],
                                "move_pct": options["move30"] * 100, "movement_value": row["value"] * options["move30"],
                                "skew_points": options.get("skew_points"), "iv": options["iv30"]})
    covered = sum(r["weight"] for r in trend_rows)
    result = {"options": sorted(option_rows, key=lambda r: r["movement_value"], reverse=True),
              "option_coverage": sum(r["weight"] for r in option_rows), "history_coverage": covered,
              "trend_breadth": sum(r["weight"] for r in trend_rows if r["above50"]) / covered if covered else None,
              "risk": [], "annual_vol": None, "hybrid_move": None, "observations": 0}
    # No renormalized partial-portfolio risk marketed as whole-portfolio risk.
    if not rows or not valuation["complete"] or len(histories) != len(rows) or total <= 0:
        return result
    levels = pd.DataFrame(histories).dropna().tail(253)
    returns = levels.pct_change(fill_method=None).dropna()
    result["observations"] = len(returns)
    if len(returns) < 60:
        return result
    weights = np.array([next(r["weight"] for r in rows if r["ticker"] == t) for t in returns.columns])
    covariance = returns.cov().to_numpy() * 252
    variance = float(weights @ covariance @ weights)
    if variance <= 0 or not math.isfinite(variance):
        return result
    result["annual_vol"] = math.sqrt(variance)
    shares = weights * (covariance @ weights) / variance
    result["risk"] = sorted([{"ticker": t, "capital_weight": float(w), "risk_share": float(r)}
                             for t, w, r in zip(returns.columns, weights, shares)], key=lambda r: r["risk_share"], reverse=True)
    if len(option_rows) == len(rows):
        vols = np.array([next(r["iv"] for r in option_rows if r["ticker"] == t) for t in returns.columns])
        hybrid = float((weights * vols) @ returns.corr().to_numpy() @ (weights * vols))
        if math.isfinite(hybrid) and hybrid >= 0:
            result["hybrid_move"] = total * math.sqrt(hybrid * 30 / 365)
    return result


def earnings_exposure(rows, records, as_of):
    """Only explicitly verified, current calendar records establish coverage."""
    covered, events = set(), {}
    for item in records:
        try:
            checked = date.fromisoformat(item["verified_on"])
            until = date.fromisoformat(item["coverage_through"])
            if not item.get("source_url", "").startswith("https://") or not 0 <= (as_of - checked).days <= 7 or until < as_of + timedelta(days=30):
                continue
            ticker = item["ticker"]
            covered.add(ticker)
            if item.get("earnings_date"):
                event = date.fromisoformat(item["earnings_date"])
                if 0 <= (event - as_of).days <= 30:
                    events[ticker] = {"ticker": ticker, "date": event.isoformat(), "source": item["source_url"]}
        except (KeyError, TypeError, ValueError):
            continue
    return {"coverage": sum(r["weight"] for r in rows if r["ticker"] in covered),
            "weight30": sum(r["weight"] for r in rows if r["ticker"] in events),
            "weight7": sum(r["weight"] for r in rows if r["ticker"] in events and (date.fromisoformat(events[r["ticker"]]["date"]) - as_of).days <= 7),
            "events": list(events.values())}
