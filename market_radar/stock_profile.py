from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .models import SymbolSignal


@dataclass(frozen=True)
class ProfileKPI:
    label: str
    value: str
    delta: Optional[str]
    help: str


@dataclass(frozen=True)
class StockProfile:
    kpis: tuple[ProfileKPI, ...]
    trend_label: str
    trend_explanation: str
    participation_label: str
    participation_explanation: str
    price_figure: go.Figure
    relative_figure: go.Figure


def _compact_dollars(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def _trend(signal: SymbolSignal) -> tuple[str, str]:
    if signal.close > signal.ema20 > signal.ema50 > signal.ema200:
        return "Strong uptrend", "Price is above its 20-, 50-, and 200-session averages, in bullish order."
    if signal.close > signal.ema20 and signal.close > signal.ema50:
        return "Uptrend", "Price is above its short- and medium-term averages, but the long-term stack is mixed."
    if signal.close < signal.ema20 < signal.ema50 < signal.ema200:
        return "Strong downtrend", "Price is below its 20-, 50-, and 200-session averages, in bearish order."
    if signal.close < signal.ema20 and signal.close < signal.ema50:
        return "Downtrend", "Price is below its short- and medium-term averages; recovery still needs confirmation."
    return "Mixed trend", "Price and moving averages are not aligned, so the trend signal is inconclusive."


def _participation(signal: SymbolSignal) -> tuple[str, str]:
    if signal.volume_ratio >= 1.25:
        return "High participation", f"Latest volume was {signal.volume_ratio:.2f}x its 20-session norm."
    if signal.volume_ratio <= 0.75:
        return "Quiet participation", f"Latest volume was only {signal.volume_ratio:.2f}x its 20-session norm."
    return "Normal participation", f"Latest volume was {signal.volume_ratio:.2f}x its 20-session norm."


def _price_figure(signal: SymbolSignal) -> go.Figure:
    history = pd.DataFrame(signal.price_history)
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.76, 0.24],
    )
    if history.empty:
        figure.add_annotation(text="Run a new scan to save chart history", showarrow=False)
    else:
        history["session"] = pd.to_datetime(history["session"])
        history["ema20"] = history["close"].ewm(span=20, adjust=False).mean()
        history["ema50"] = history["close"].ewm(span=50, adjust=False).mean()
        figure.add_trace(
            go.Scatter(
                x=history["session"],
                y=history["close"],
                name="Close",
                line={"color": "#73A7FF", "width": 2.5},
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=history["session"],
                y=history["ema20"],
                name="EMA 20",
                line={"color": "#4DD4AC", "width": 1.5},
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=history["session"],
                y=history["ema50"],
                name="EMA 50",
                line={"color": "#F4C95D", "width": 1.5},
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Bar(
                x=history["session"],
                y=history["volume"],
                name="Volume",
                marker_color="rgba(135, 151, 177, 0.45)",
            ),
            row=2,
            col=1,
        )
    figure.update_yaxes(title_text="Price (USD)", row=1, col=1)
    figure.update_yaxes(title_text="Volume", showticklabels=False, row=2, col=1)
    figure.update_layout(
        title="Six-month price, trend and participation",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=470,
        margin={"l": 8, "r": 8, "t": 58, "b": 8},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0},
    )
    return figure


def _relative_figure(signal: SymbolSignal) -> go.Figure:
    history = pd.DataFrame(signal.relative_history)
    figure = go.Figure()
    if history.empty:
        figure.add_annotation(text="Run a new scan to save benchmark history", showarrow=False)
    else:
        history["session"] = pd.to_datetime(history["session"])
        series = (
            (signal.ticker, "stock", "#73A7FF", 3.0),
            (signal.sector_etf, "sector", "#4DD4AC", 2.0),
            ("SPY", "spy", "#A9B4C7", 1.8),
        )
        for label, column, color, width in series:
            figure.add_trace(
                go.Scatter(
                    x=history["session"],
                    y=history[column],
                    name=label,
                    line={"color": color, "width": width},
                )
            )
    figure.add_hline(y=100, line_dash="dot", line_color="rgba(169,180,199,0.45)")
    figure.update_layout(
        title=f"Three-month performance vs {signal.sector_etf} and SPY",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=360,
        margin={"l": 8, "r": 8, "t": 58, "b": 8},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.10, "x": 0},
        yaxis={"title": "Growth of 100"},
    )
    return figure


def build_stock_profile(signal: SymbolSignal) -> StockProfile:
    trend_label, trend_explanation = _trend(signal)
    participation_label, participation_explanation = _participation(signal)
    atr_percent = signal.atr14 / signal.close if signal.close else 0.0
    kpis = (
        ProfileKPI(
            "Latest saved price",
            f"${signal.close:,.2f}",
            f"{signal.return_5d:+.1%} · 5 sessions",
            "Closing price from the selected saved market session.",
        ),
        ProfileKPI("One-month move", f"{signal.return_20d:+.1%}", None, "Return over 20 sessions."),
        ProfileKPI(
            "Vs sector · 5D",
            f"{signal.sector_relative_5d:+.1%}",
            None,
            f"Five-session return minus {signal.sector_etf} return.",
        ),
        ProfileKPI(
            "Vs S&P 500 · 20D",
            f"{signal.spy_relative_20d:+.1%}",
            None,
            "Twenty-session return minus SPY return.",
        ),
        ProfileKPI(
            "Typical daily move",
            f"{atr_percent:.1%}",
            None,
            "ATR as a percentage of price; a practical volatility measure.",
        ),
        ProfileKPI(
            "Five-session turnover",
            _compact_dollars(signal.dollar_turnover_5d) if signal.dollar_turnover_5d else "Not saved",
            None,
            "Approximate liquidity: sum of daily close multiplied by shares traded.",
        ),
    )
    return StockProfile(
        kpis=kpis,
        trend_label=trend_label,
        trend_explanation=trend_explanation,
        participation_label=participation_label,
        participation_explanation=participation_explanation,
        price_figure=_price_figure(signal),
        relative_figure=_relative_figure(signal),
    )
