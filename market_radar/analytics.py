from collections.abc import Iterable
from datetime import date
from typing import Optional
from zoneinfo import ZoneInfo

from .models import DailyBar, IdeaOutcome, OptionContract, OptionPressure, TradeIdea

NEW_YORK = ZoneInfo("America/New_York")


def classify_quadrant(price_axis: float, options_axis: float) -> str:
    if price_axis < 0 and options_axis >= 0:
        return "Contrarian Bid"
    if price_axis < 0 and options_axis < 0:
        return "Fear"
    if price_axis >= 0 and options_axis >= 0:
        return "Chase"
    return "Hedged Rally"


def _exclude(exclusions, reason: str) -> None:
    exclusions[reason] = exclusions.get(reason, 0) + 1


def compute_option_pressure(
    contracts: Iterable[OptionContract],
    as_of: date,
    feed: str,
    minimum_dte: int = 7,
    maximum_dte: int = 45,
    minimum_abs_delta: float = 0.20,
    maximum_abs_delta: float = 0.80,
    maximum_spread_fraction: float = 0.25,
) -> OptionPressure:
    bullish_premium = 0.0
    total_premium = 0.0
    valid = 0
    excluded = 0
    exclusions = {}
    latest = None

    for contract in contracts:
        dte = (contract.expiration - as_of).days
        if not minimum_dte <= dte <= maximum_dte:
            _exclude(exclusions, "dte_window")
            excluded += 1
            continue
        if not minimum_abs_delta <= abs(contract.delta) <= maximum_abs_delta:
            _exclude(exclusions, "delta_window")
            excluded += 1
            continue
        if contract.ask < contract.bid:
            _exclude(exclusions, "crossed_quote")
            excluded += 1
            continue
        midpoint = (contract.bid + contract.ask) / 2.0
        spread = contract.ask - contract.bid
        if midpoint <= 0 or spread <= 0:
            _exclude(exclusions, "invalid_quote")
            excluded += 1
            continue
        if spread / midpoint > maximum_spread_fraction:
            _exclude(exclusions, "wide_spread")
            excluded += 1
            continue
        if contract.trade_timestamp.astimezone(NEW_YORK).date() != as_of:
            _exclude(exclusions, "stale_trade")
            excluded += 1
            continue
        if contract.last_price <= 0 or contract.last_size <= 0:
            _exclude(exclusions, "invalid_trade")
            excluded += 1
            continue

        aggressor = max(-1.0, min(1.0, (contract.last_price - midpoint) / (spread / 2.0)))
        type_sign = 1.0 if contract.contract_type.lower() == "call" else -1.0
        premium = contract.last_price * contract.last_size * 100.0
        bullish_premium += type_sign * aggressor * premium
        total_premium += abs(premium)
        valid += 1
        latest = max(latest, contract.trade_timestamp) if latest else contract.trade_timestamp

    axis = 0.0 if total_premium == 0 else 100.0 * bullish_premium / total_premium
    return OptionPressure(
        axis=round(max(-100.0, min(100.0, axis)), 4),
        bullish_premium=round(bullish_premium, 2),
        total_premium=round(total_premium, 2),
        valid_contracts=valid,
        excluded_contracts=excluded,
        exclusions=exclusions,
        feed=feed,
        latest_trade_at=latest,
    )


def compute_evidence_score(
    options_axis: float,
    valid_contracts: int,
    price_axis: float,
    volume_percentile: float,
    trend_confirmation: float,
) -> float:
    coverage = min(max(valid_contracts, 0) / 20.0, 1.0) * 100.0
    score = (
        0.35 * min(abs(options_axis), 100.0)
        + 0.20 * coverage
        + 0.20 * min(abs(price_axis), 100.0)
        + 0.15 * min(max(volume_percentile, 0.0), 100.0)
        + 0.10 * min(max(trend_confirmation, 0.0), 100.0)
    )
    return round(score, 1)


def build_trade_idea(
    ticker: str,
    quadrant: str,
    evidence_score: float,
    scan_date: date,
    high: float,
    low: float,
    close: float,
    atr: float,
    swing_low: float,
    swing_high: float,
    technical_confirmed: bool,
) -> Optional[TradeIdea]:
    del close
    if evidence_score < 65 or not technical_confirmed or atr <= 0 or quadrant == "Hedged Rally":
        return None

    if quadrant in {"Contrarian Bid", "Chase"}:
        direction = "long"
        trigger = high + 0.1 * atr
        stop = min(swing_low, trigger - 1.5 * atr)
        risk = trigger - stop
        if risk <= 0 or risk > 3.0 * atr:
            return None
        target_1r = trigger + risk
        target_2r = trigger + 2.0 * risk
    elif quadrant == "Fear":
        direction = "short"
        trigger = low - 0.1 * atr
        stop = max(swing_high, trigger + 1.5 * atr)
        risk = stop - trigger
        if risk <= 0 or risk > 3.0 * atr:
            return None
        target_1r = trigger - risk
        target_2r = trigger - 2.0 * risk
    else:
        return None

    return TradeIdea(
        ticker=ticker,
        quadrant=quadrant,
        direction=direction,
        evidence_score=evidence_score,
        scan_date=scan_date,
        trigger=round(trigger, 4),
        stop=round(stop, 4),
        target_1r=round(target_1r, 4),
        target_2r=round(target_2r, 4),
    )


def evaluate_idea(idea: TradeIdea, bars: Iterable[DailyBar]) -> IdeaOutcome:
    observed: list[DailyBar] = sorted(
        (bar for bar in bars if bar.session > idea.scan_date), key=lambda bar: bar.session
    )
    triggered_on = None
    holding = 0

    for index, bar in enumerate(observed):
        if triggered_on is None:
            if index >= idea.expires_after_sessions:
                return IdeaOutcome(idea.ticker, "expired", 0.0, None, observed[index - 1].session, index, idea.id)
            triggered = bar.high >= idea.trigger if idea.direction == "long" else bar.low <= idea.trigger
            if not triggered:
                continue
            triggered_on = bar.session

        holding += 1
        if idea.direction == "long":
            stopped = bar.low <= idea.stop
            hit_2r = bar.high >= idea.target_2r
            hit_1r = bar.high >= idea.target_1r
        else:
            stopped = bar.high >= idea.stop
            hit_2r = bar.low <= idea.target_2r
            hit_1r = bar.low <= idea.target_1r

        if stopped:
            return IdeaOutcome(idea.ticker, "stopped", -1.0, triggered_on, bar.session, len(observed), idea.id)
        if hit_2r:
            return IdeaOutcome(idea.ticker, "target_2r", 2.0, triggered_on, bar.session, len(observed), idea.id)
        if hit_1r:
            return IdeaOutcome(idea.ticker, "target_1r", 1.0, triggered_on, bar.session, len(observed), idea.id)
        if holding >= idea.max_holding_sessions:
            risk = abs(idea.trigger - idea.stop)
            signed_move = bar.close - idea.trigger if idea.direction == "long" else idea.trigger - bar.close
            return IdeaOutcome(
                idea.ticker,
                "time_exit",
                round(signed_move / risk, 4),
                triggered_on,
                bar.session,
                len(observed),
                idea.id,
            )

    if triggered_on:
        return IdeaOutcome(idea.ticker, "open", None, triggered_on, None, len(observed), idea.id)
    if len(observed) >= idea.expires_after_sessions:
        return IdeaOutcome(
            idea.ticker,
            "expired",
            0.0,
            None,
            observed[idea.expires_after_sessions - 1].session,
            len(observed),
            idea.id,
        )
    return IdeaOutcome(idea.ticker, "pending", None, None, None, len(observed), idea.id)
