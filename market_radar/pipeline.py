import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from .analytics import build_trade_idea, classify_quadrant, compute_evidence_score, compute_option_pressure
from .macro import MACRO_ASSETS, analyze_global_macro
from .models import DailyBar, ScanResult, SymbolSignal, UniverseMember

FORMULA_VERSION = "market-radar-v4"


def _percentile(value: float, values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 50.0
    below = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    rank = (below + (equal - 1) / 2.0) / (len(values) - 1)
    return round(max(0.0, min(100.0, rank * 100.0)), 4)


def _axis(value: float, values: Sequence[float]) -> float:
    return 2.0 * _percentile(value, values) - 100.0


def _ema(values: Sequence[float], period: int) -> float:
    alpha = 2.0 / (period + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _atr(bars: Sequence[DailyBar], period: int = 14) -> float:
    true_ranges = []
    for previous, current in zip(bars[:-1], bars[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(true_ranges[-period:]) / min(period, len(true_ranges))


def _session_bars(bars: Iterable[DailyBar], as_of: date) -> list[DailyBar]:
    return sorted((bar for bar in bars if bar.session <= as_of), key=lambda bar: bar.session)


def _price_history(bars: Sequence[DailyBar], sessions: int = 126) -> list[dict[str, object]]:
    return [
        {
            "session": bar.session.isoformat(),
            "close": round(bar.close, 4),
            "volume": round(bar.volume, 2),
        }
        for bar in bars[-sessions:]
    ]


def _relative_history(
    stock_bars: Sequence[DailyBar],
    sector_bars: Sequence[DailyBar],
    spy_bars: Sequence[DailyBar],
    sessions: int = 63,
) -> list[dict[str, object]]:
    stock = {bar.session: bar.close for bar in stock_bars}
    sector = {bar.session: bar.close for bar in sector_bars}
    spy = {bar.session: bar.close for bar in spy_bars}
    common_sessions = sorted(set(stock) & set(sector) & set(spy))[-sessions:]
    if not common_sessions:
        return []
    first = common_sessions[0]
    bases = stock[first], sector[first], spy[first]
    if any(value == 0 for value in bases):
        return []
    return [
        {
            "session": session.isoformat(),
            "stock": round(stock[session] / bases[0] * 100.0, 4),
            "sector": round(sector[session] / bases[1] * 100.0, 4),
            "spy": round(spy[session] / bases[2] * 100.0, 4),
        }
        for session in common_sessions
    ]


def analyze_price_universe(
    bars_by_symbol: Mapping[str, Sequence[DailyBar]],
    universe: Sequence[UniverseMember],
    as_of: date,
) -> list[SymbolSignal]:
    prepared: dict[str, list[DailyBar]] = {
        ticker: _session_bars(bars, as_of) for ticker, bars in bars_by_symbol.items()
    }
    if len(prepared.get("SPY", [])) < 201:
        raise ValueError("SPY requires at least 201 completed daily bars")

    raw = []
    for member in universe:
        bars = prepared.get(member.ticker, [])
        sector_bars = prepared.get(member.sector_etf, [])
        spy_bars = prepared["SPY"]
        if len(bars) < 201 or len(sector_bars) < 21:
            continue
        closes = [bar.close for bar in bars]
        return_5d = closes[-1] / closes[-6] - 1.0
        return_20d = closes[-1] / closes[-21] - 1.0
        sector_5d = sector_bars[-1].close / sector_bars[-6].close - 1.0
        spy_20d = spy_bars[-1].close / spy_bars[-21].close - 1.0
        prior_volume = sum(bar.volume for bar in bars[-21:-1]) / 20.0
        volume_ratio = bars[-1].volume / prior_volume if prior_volume else 0.0
        raw.append(
            {
                "member": member,
                "bars": bars,
                "return_5d": return_5d,
                "return_20d": return_20d,
                "sector_relative_5d": return_5d - sector_5d,
                "spy_relative_20d": return_20d - spy_20d,
                "volume_ratio": volume_ratio,
                "dollar_turnover_5d": sum(bar.close * bar.volume for bar in bars[-5:]),
                "price_history": _price_history(bars),
                "relative_history": _relative_history(bars, sector_bars, spy_bars),
            }
        )

    sector_relatives = [item["sector_relative_5d"] for item in raw]
    spy_relatives = [item["spy_relative_20d"] for item in raw]
    volume_ratios = [item["volume_ratio"] for item in raw]
    signals = []
    for item in raw:
        member = item["member"]
        bars = item["bars"]
        closes = [bar.close for bar in bars]
        price_axis = 0.60 * _axis(item["sector_relative_5d"], sector_relatives) + 0.40 * _axis(
            item["spy_relative_20d"], spy_relatives
        )
        signals.append(
            SymbolSignal(
                ticker=member.ticker,
                name=member.name,
                sector=member.sector,
                sector_etf=member.sector_etf,
                as_of=as_of,
                close=round(bars[-1].close, 4),
                high=round(bars[-1].high, 4),
                low=round(bars[-1].low, 4),
                atr14=round(_atr(bars), 4),
                ema20=round(_ema(closes, 20), 4),
                ema50=round(_ema(closes, 50), 4),
                ema200=round(_ema(closes, 200), 4),
                return_5d=round(item["return_5d"], 6),
                return_20d=round(item["return_20d"], 6),
                sector_relative_5d=round(item["sector_relative_5d"], 6),
                spy_relative_20d=round(item["spy_relative_20d"], 6),
                price_axis=round(price_axis, 4),
                volume_ratio=round(item["volume_ratio"], 4),
                volume_percentile=_percentile(item["volume_ratio"], volume_ratios),
                trend_confirmation=0.0,
                swing_low_10d=round(min(bar.low for bar in bars[-10:]), 4),
                swing_high_10d=round(max(bar.high for bar in bars[-10:]), 4),
                dollar_turnover_5d=round(item["dollar_turnover_5d"], 2),
                price_history=item["price_history"],
                relative_history=item["relative_history"],
                industry=member.industry,
            )
        )
    return sorted(signals, key=lambda signal: signal.ticker)


def select_option_candidates(
    signals: Sequence[SymbolSignal],
    watchlist: set[str],
    per_side: int = 40,
    watchlist_limit: int = 40,
) -> list[str]:
    strongest = sorted(
        (signal for signal in signals if signal.price_axis >= 0), key=lambda s: s.price_axis, reverse=True
    )
    weakest = sorted((signal for signal in signals if signal.price_axis < 0), key=lambda s: s.price_axis)
    selected = {signal.ticker for signal in strongest[:per_side] + weakest[:per_side]}
    selected.update(sorted(watchlist)[:watchlist_limit])
    return sorted(selected, key=lambda ticker: (-next(s.price_axis for s in signals if s.ticker == ticker), ticker))


def _trend_confirmation(quadrant: str, signal: SymbolSignal, bars: Sequence[DailyBar]) -> float:
    if quadrant == "Contrarian Bid":
        upper_half = signal.close >= (signal.high + signal.low) / 2.0
        return 100.0 if len(bars) >= 2 and signal.close > bars[-2].close and upper_half else 0.0
    if quadrant == "Fear":
        return 100.0 if signal.close < signal.ema20 else 0.0
    if quadrant == "Chase":
        return 100.0 if signal.close > signal.ema20 > signal.ema50 else 0.0
    return 100.0 if signal.close > signal.ema20 else 0.0


def _market_regime(spy_bars: Sequence[DailyBar]) -> dict[str, object]:
    closes = [bar.close for bar in spy_bars]
    close = closes[-1]
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, 200)
    if close > ema50 > ema200:
        label = "Bullish trend"
    elif close < ema50 < ema200:
        label = "Bearish trend"
    else:
        label = "Mixed regime"
    returns = [closes[index] / closes[index - 1] - 1.0 for index in range(max(1, len(closes) - 20), len(closes))]
    realized = (sum(value * value for value in returns) / len(returns)) ** 0.5 * (252**0.5) if returns else 0.0
    return {
        "label": label,
        "spy_close": round(close, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "realized_vol_20d": round(realized, 4),
    }


def _sector_returns(
    bars_by_symbol: Mapping[str, Sequence[DailyBar]], sector_etfs: Sequence[str]
) -> dict[str, list[float]]:
    spy = list(bars_by_symbol.get("SPY", []))
    result = {}
    if len(spy) < 21:
        return result
    for ticker in sorted(set(sector_etfs)):
        bars = list(bars_by_symbol.get(ticker, []))
        if len(bars) < 21:
            continue
        weeks = []
        for offset in (20, 15, 10, 5):
            etf_return = bars[-offset + 4].close / bars[-offset].close - 1.0
            spy_return = spy[-offset + 4].close / spy[-offset].close - 1.0
            weeks.append(round(etf_return - spy_return, 6))
        result[ticker] = weeks
    return result


def run_scan(provider, universe: Sequence[UniverseMember], as_of: date, scan_type: str = "manual") -> ScanResult:
    started_at = datetime.now(timezone.utc)
    symbols = sorted(
        {member.ticker for member in universe} | {member.sector_etf for member in universe} | set(MACRO_ASSETS)
    )
    bars = provider.get_daily_bars(symbols, as_of - timedelta(days=400), as_of)
    signals = analyze_price_universe(bars, universe, as_of)
    by_ticker = {signal.ticker: signal for signal in signals}
    watchlist = {member.ticker for member in universe if member.is_watchlist}
    candidates = select_option_candidates(signals, watchlist)
    warnings: list[str] = []
    ideas = []

    pressures = {}
    failures = {}
    if candidates:
        with ThreadPoolExecutor(max_workers=min(5, len(candidates))) as executor:
            futures = {
                executor.submit(
                    lambda selected: compute_option_pressure(
                        provider.get_option_chain(selected, as_of), as_of, provider.option_feed
                    ),
                    ticker,
                ): ticker
                for ticker in candidates
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    pressures[ticker] = future.result()
                except Exception as exc:
                    failures[ticker] = exc

    for ticker in candidates:
        signal = by_ticker.get(ticker)
        if signal is None:
            continue
        if ticker in failures:
            exc = failures[ticker]
            warnings.append(f"{ticker}: option chain unavailable ({type(exc).__name__})")
            continue
        pressure = pressures[ticker]
        quadrant = classify_quadrant(signal.price_axis, pressure.axis)
        trend = _trend_confirmation(quadrant, signal, bars[ticker])
        score = compute_evidence_score(
            pressure.axis,
            pressure.valid_contracts,
            signal.price_axis,
            signal.volume_percentile,
            trend,
        )
        enriched = replace(
            signal,
            options_axis=pressure.axis,
            quadrant=quadrant,
            evidence_score=score,
            valid_contracts=pressure.valid_contracts,
            excluded_contracts=pressure.excluded_contracts,
            exclusions=pressure.exclusions,
            feed=pressure.feed,
            latest_trade_at=pressure.latest_trade_at,
            trend_confirmation=trend,
            warnings=["Indicative options feed: delayed trades and modified quotes"]
            if pressure.feed == "indicative"
            else [],
        )
        by_ticker[ticker] = enriched
        idea = build_trade_idea(
            ticker=ticker,
            quadrant=quadrant,
            evidence_score=score,
            scan_date=as_of,
            high=signal.high,
            low=signal.low,
            close=signal.close,
            atr=signal.atr14,
            swing_low=signal.swing_low_10d,
            swing_high=signal.swing_high_10d,
            technical_confirmed=trend == 100.0,
        )
        if idea:
            ideas.append(idea)

    config = {"formula_version": FORMULA_VERSION, "candidate_count": len(candidates), "scan_type": scan_type}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    market_regime = _market_regime(bars["SPY"])
    market_regime["global_macro"] = analyze_global_macro(bars, as_of)
    return ScanResult(
        as_of=as_of,
        scan_type=scan_type,
        status="partial" if warnings else "complete",
        provider=provider.name,
        stock_feed=provider.stock_feed,
        option_feed=provider.option_feed,
        config_hash=config_hash,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        signals=sorted(by_ticker.values(), key=lambda signal: signal.ticker),
        ideas=sorted(ideas, key=lambda idea: idea.evidence_score, reverse=True),
        warnings=warnings,
        market_regime=market_regime,
        sector_returns=_sector_returns(bars, [member.sector_etf for member in universe]),
    )
