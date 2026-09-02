from collections.abc import Mapping, Sequence
from datetime import date

from .models import DailyBar

MACRO_ASSETS = {
    "SPY": {"name": "United States", "lens": "U.S. large-cap equities", "group": "Global equities"},
    "EFA": {"name": "Developed markets", "lens": "Europe, Japan and developed Asia", "group": "Global equities"},
    "EEM": {"name": "Emerging markets", "lens": "Emerging-market equities", "group": "Global equities"},
    "HYG": {"name": "Credit appetite", "lens": "U.S. high-yield corporate bonds", "group": "Financial conditions"},
    "TLT": {"name": "Long-term rates", "lens": "Long-duration U.S. Treasuries", "group": "Financial conditions"},
    "UUP": {"name": "U.S. dollar", "lens": "Dollar versus major currencies", "group": "Currencies"},
    "GLD": {"name": "Gold", "lens": "Monetary and defensive demand", "group": "Real assets"},
    "USO": {"name": "Crude oil", "lens": "Oil-market price pressure", "group": "Real assets"},
    "DBC": {"name": "Broad commodities", "lens": "Diversified commodity basket", "group": "Real assets"},
}


def _ema(values: Sequence[float], period: int) -> float:
    alpha = 2.0 / (period + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _return(closes: Sequence[float], sessions: int) -> float:
    return closes[-1] / closes[-sessions - 1] - 1.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def analyze_global_macro(
    bars_by_symbol: Mapping[str, Sequence[DailyBar]],
    as_of: date,
) -> dict[str, object]:
    assets = []
    missing = []
    for ticker, metadata in MACRO_ASSETS.items():
        bars = sorted(
            (bar for bar in bars_by_symbol.get(ticker, []) if bar.session <= as_of), key=lambda bar: bar.session
        )
        if len(bars) < 64:
            missing.append(ticker)
            continue
        closes = [bar.close for bar in bars]
        ema50 = _ema(closes, 50)
        assets.append(
            {
                "ticker": ticker,
                **metadata,
                "close": round(closes[-1], 2),
                "return_1w": round(_return(closes, 5), 6),
                "return_1m": round(_return(closes, 20), 6),
                "return_3m": round(_return(closes, 63), 6),
                "above_ema50": closes[-1] > ema50,
                "ema50": round(ema50, 2),
            }
        )

    by_ticker = {asset["ticker"]: asset for asset in assets}

    def month_return(*tickers: str) -> float:
        return _mean([by_ticker[ticker]["return_1m"] for ticker in tickers if ticker in by_ticker])

    global_equities = month_return("SPY", "EFA", "EEM")
    credit = month_return("HYG")
    commodities = month_return("USO", "DBC")
    treasuries = month_return("TLT")
    dollar = month_return("UUP")
    risk_assets = [by_ticker[ticker] for ticker in ("SPY", "EFA", "EEM", "HYG") if ticker in by_ticker]
    breadth = 100.0 * _mean([1.0 if asset["above_ema50"] else 0.0 for asset in risk_assets]) if risk_assets else 0.0
    risk_composite = _mean([global_equities, credit])
    risk_score = round(_clamp(50.0 + risk_composite * 600.0 + (breadth - 50.0) * 0.25), 1)

    if risk_score >= 65:
        risk_label = "Risk-on"
        tone = "Constructive"
    elif risk_score <= 35:
        risk_label = "Defensive"
        tone = "Cautious"
    else:
        risk_label = "Balanced"
        tone = "Mixed"

    if global_equities > 0.01 and credit > -0.005:
        growth_label = "Growth assets strengthening"
    elif global_equities < -0.01 or credit < -0.01:
        growth_label = "Growth concerns rising"
    else:
        growth_label = "Growth signal mixed"

    if commodities > 0.03 and treasuries < 0:
        inflation_label = "Inflation pressure rising"
    elif commodities < -0.03 and treasuries > 0:
        inflation_label = "Disinflation impulse"
    else:
        inflation_label = "Inflation signal neutral"

    if dollar > 0.01:
        dollar_label = "Dollar strengthening"
    elif dollar < -0.01:
        dollar_label = "Dollar easing"
    else:
        dollar_label = "Dollar broadly stable"

    equity_assets = [asset for asset in assets if asset["ticker"] in {"SPY", "EFA", "EEM"}]
    leader = max(equity_assets, key=lambda asset: asset["return_1m"], default=None)
    laggard = min(equity_assets, key=lambda asset: asset["return_1m"], default=None)
    takeaways = []
    if leader and laggard:
        takeaways.append(
            f"The one-month global equity leader is {leader['name']} ({leader['return_1m']:+.1%}); "
            f"the laggard is {laggard['name']} ({laggard['return_1m']:+.1%})."
        )
    if "HYG" in by_ticker:
        takeaways.append(
            f"High-yield credit is {by_ticker['HYG']['return_1m']:+.1%} over one month, a market-based read on risk appetite."
        )
    if "UUP" in by_ticker and "DBC" in by_ticker:
        takeaways.append(
            f"The dollar proxy is {by_ticker['UUP']['return_1m']:+.1%} while broad commodities are "
            f"{by_ticker['DBC']['return_1m']:+.1%}, framing the inflation and global-liquidity backdrop."
        )

    return {
        "as_of": as_of.isoformat(),
        "tone": tone,
        "risk_label": risk_label,
        "risk_score": risk_score,
        "growth_label": growth_label,
        "inflation_label": inflation_label,
        "dollar_label": dollar_label,
        "global_equity_return_1m": round(global_equities, 6),
        "credit_return_1m": round(credit, 6),
        "commodity_return_1m": round(commodities, 6),
        "treasury_return_1m": round(treasuries, 6),
        "dollar_return_1m": round(dollar, 6),
        "risk_breadth": round(breadth, 1),
        "assets": assets,
        "takeaways": takeaways,
        "missing": missing,
        "method": "Market-implied cross-asset proxy; not an official economic forecast.",
    }
