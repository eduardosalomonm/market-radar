import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from market_radar.ai import generate_daily_brief
from market_radar.catalog import CompanyCatalogEntry, load_company_catalog, search_company_catalog
from market_radar.catalysts import load_catalysts
from market_radar.cli import DEFAULT_DATABASE, DEFAULT_UNIVERSE, PROJECT_ROOT, _load_env
from market_radar.client_report import build_client_brief_pdf
from market_radar.daily_intelligence import build_daily_intelligence
from market_radar.exports import export_outcomes_json
from market_radar.models import PortfolioPosition, UniverseMember
from market_radar.pipeline import run_scan
from market_radar.presentation import (
    QUADRANT_EXPLANATIONS,
    evidence_components,
    evidence_label,
    executive_brief,
    recommendation_reason,
)
from market_radar.providers import AlpacaProvider, CachedProvider, DemoProvider
from market_radar.repository import Repository
from market_radar.stock_profile import build_stock_profile
from market_radar.universe import load_universe

NEW_YORK = ZoneInfo("America/New_York")
PUBLIC_DEMO = os.getenv("MARKET_RADAR_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}
DATABASE = Path(os.getenv("MARKET_RADAR_DATABASE", str(DEFAULT_DATABASE)))
UNIVERSE_PATH = Path(os.getenv("MARKET_RADAR_UNIVERSE", str(DEFAULT_UNIVERSE)))
GLOBAL_OUTLOOK_PATH = PROJECT_ROOT / "data" / "global_outlook.json"
SYMBOL_CATALOG_PATH = Path(
    os.getenv("MARKET_RADAR_SYMBOL_CATALOG", str(PROJECT_ROOT / "data" / "symbol_catalog.csv"))
)
CATALYSTS_PATH = Path(os.getenv("MARKET_RADAR_CATALYSTS", str(PROJECT_ROOT / "data" / "catalysts.json")))
SECTORS = {
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}
QUADRANT_COLORS = {
    "Contrarian Bid": "#39d98a",
    "Fear": "#ff6b6b",
    "Chase": "#60a5fa",
    "Hedged Rally": "#f6c453",
}
PAGES = [
    "1 · Executive Brief",
    "2 · Global Macro",
    "3 · Opportunity Map",
    "4 · Trade Ideas",
    "5 · Stock Explorer",
    "6 · Watchlist",
    "7 · Paper Results",
    "Method & Data",
]
PAGE_DESCRIPTIONS = {
    "1 · Executive Brief": "What changed, what matters to your holdings, and the few items worth attention.",
    "2 · Global Macro": "How equities, rates, credit, the dollar and commodities fit together.",
    "3 · Opportunity Map": "Where price strength and options positioning agree—or diverge.",
    "4 · Trade Ideas": "Ranked setups with a plain-English thesis, trigger, risk and targets.",
    "5 · Stock Explorer": "A focused company view with current saved price, trend and relative strength.",
    "6 · Watchlist": "Track your holdings and watchlist, with a personalized after-close update.",
    "7 · Paper Results": "Forward outcomes from frozen ideas; never rewritten with hindsight.",
    "Method & Data": "Formulas, data health, limitations and the audit trail behind every score.",
}
PAGE_LABELS = {
    "1 · Executive Brief": "Daily Brief",
    "2 · Global Macro": "Global Economy",
    "3 · Opportunity Map": "Market Map",
    "4 · Trade Ideas": "Trade Ideas",
    "5 · Stock Explorer": "Stock Explorer",
    "6 · Watchlist": "My Portfolio",
    "7 · Paper Results": "Paper Results",
    "Method & Data": "Method & Data",
}

st.set_page_config(page_title="FolioShift", page_icon="◒", layout="wide")
st.markdown(
    """
    <style>
    .stApp {background: radial-gradient(circle at 18% -8%, #16283a 0%, #0b111b 40%, #070b11 100%);}
    [data-testid="stMetric"] {background: rgba(20,30,48,.76); border: 1px solid #26354f; border-radius: 14px; padding: 14px;}
    [data-testid="stSidebar"] {background: #090e18; border-right: 1px solid #22304a;}
    .radar-kicker {letter-spacing:.16em; text-transform:uppercase; color:#78f0c4; font-size:.75rem; font-weight:700;}
    .radar-card {background:rgba(16,24,39,.8);border:1px solid #26354f;border-radius:14px;padding:18px;margin:.5rem 0 1rem;}
    .radar-muted {color:#94a3b8;}
    .radar-eyebrow {color:#78f0c4;font-size:.78rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;}
    .radar-reason {font-size:1.02rem;line-height:1.55;color:#dbe7f7;margin:.45rem 0 .2rem;}
    .radar-pill {display:inline-block;background:#17243a;border:1px solid #314561;border-radius:999px;padding:3px 9px;margin:2px 4px 2px 0;color:#b9c9df;font-size:.76rem;}
    .radar-hero {background:linear-gradient(135deg,rgba(24,70,77,.9),rgba(18,29,48,.94));border:1px solid #2d6c68;border-radius:18px;padding:24px 26px;margin:.4rem 0 1.2rem;box-shadow:0 18px 50px rgba(0,0,0,.2);}
    .radar-hero h2 {font-size:1.65rem;margin:.25rem 0 .5rem;color:#f3f7ff;}
    .radar-hero p {font-size:1.02rem;line-height:1.55;color:#c9d7ec;margin:0;}
    .radar-status {display:inline-block;border-radius:999px;background:#132c2c;border:1px solid #2d6c68;padding:4px 10px;color:#8ff4d0;font-size:.72rem;font-weight:700;letter-spacing:.08em;}
    .radar-section-note {color:#a9b7ca;font-size:.92rem;line-height:1.55;}
    .radar-nav-spacer {height:.5rem;}
    div[data-testid="stAlert"] {border-radius:12px;}
    [data-testid="stPopover"] > button {min-height:46px;justify-content:space-between;border-color:#38537a;}
    [data-testid="stRadio"] label {min-height:44px;align-items:center;}
    [data-testid="stMainBlockContainer"] {max-width:1280px;padding-top:4.5rem;padding-bottom:4rem;}
    @media (max-width: 768px) {
      [data-testid="stMainBlockContainer"] {padding:4.25rem 1rem 3rem;}
      h1 {font-size:2rem !important;line-height:1.12 !important;}
      h2 {font-size:1.45rem !important;line-height:1.2 !important;}
      h3 {font-size:1.2rem !important;line-height:1.25 !important;}
      .radar-hero {padding:18px 18px;margin:.25rem 0 1rem;border-radius:16px;}
      .radar-hero h2 {font-size:1.38rem !important;}
      .radar-hero p,.radar-reason {font-size:.95rem;line-height:1.5;}
      .radar-card {padding:15px;margin:.4rem 0 .8rem;}
      [data-testid="stMetric"] {padding:12px;}
      [data-testid="stMetricValue"] {font-size:1.65rem;}
      div.stButton > button, div.stDownloadButton > button {min-height:44px;width:100%;}
      [data-testid="stSelectbox"] [data-baseweb="select"] {min-height:44px;}
      [data-testid="stDataFrame"] {max-width:100%;overflow-x:auto;}
      .js-plotly-plot {max-width:100%;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def repository():
    return Repository(DATABASE)


repo = repository()
_load_env(PROJECT_ROOT / ".env")


def universe():
    return load_universe(UNIVERSE_PATH, repo.list_followed_members())


@st.cache_data
def load_global_outlook():
    return json.loads(GLOBAL_OUTLOOK_PATH.read_text(encoding="utf-8"))


@st.cache_data
def company_catalog():
    return load_company_catalog(UNIVERSE_PATH, SYMBOL_CATALOG_PATH)


@st.cache_resource
def bootstrap_public_demo():
    """Create one safe, deterministic snapshot for ephemeral public hosting."""
    catalog_by_ticker = {entry.ticker: entry for entry in company_catalog()}
    for ticker in ("PLTR", "NU"):
        entry = catalog_by_ticker.get(ticker)
        if entry:
            repo.upsert_watchlist(
                UniverseMember(
                    entry.ticker,
                    entry.name,
                    entry.sector,
                    entry.sector_etf,
                    True,
                    entry.industry,
                )
            )

    if not repo.list_positions():
        demo_positions = {
            "PLTR": (18.0, 72.0, "AI platform adoption and durable government demand"),
            "NU": (60.0, 12.5, "Latin American digital banking growth"),
        }
        for ticker, (shares, average_cost, thesis) in demo_positions.items():
            entry = catalog_by_ticker.get(ticker)
            if entry:
                repo.upsert_position(
                    PortfolioPosition(
                        ticker=entry.ticker,
                        name=entry.name,
                        sector=entry.sector,
                        sector_etf=entry.sector_etf,
                        industry=entry.industry,
                        shares=shares,
                        average_cost=average_cost,
                        thesis=thesis,
                    )
                )

    existing = repo.latest_scan()
    if existing:
        return existing.id

    provider = DemoProvider()
    session = provider.latest_completed_session(datetime.now(NEW_YORK))
    previous_session = session - timedelta(days=1)
    while previous_session.weekday() >= 5:
        previous_session -= timedelta(days=1)
    repo.save_scan(run_scan(provider, universe(), previous_session, scan_type="public-demo"))
    result = run_scan(provider, universe(), session, scan_type="public-demo")
    return repo.save_scan(result)


def save_scan(provider, label):
    session = provider.latest_completed_session(datetime.now(NEW_YORK))
    with st.spinner(f"Running {label.lower()} scan for {session.isoformat()}…"):
        result = run_scan(provider, universe(), session, scan_type="manual")
        scan_id = repo.save_scan(result)
    st.session_state["selected_scan_id"] = scan_id
    st.success(f"Saved scan {scan_id}: {len(result.signals)} symbols and {len(result.ideas)} conditional ideas.")
    st.rerun()


st.sidebar.markdown('<div class="radar-kicker">Data & settings</div>', unsafe_allow_html=True)
st.sidebar.title("FolioShift")
st.sidebar.caption("Personal portfolio intelligence")
professional_detail = st.sidebar.toggle(
    "Professional detail",
    value=False,
    help="Show formula-level evidence and data diagnostics. The default client view keeps the story simple.",
)
st.sidebar.divider()
if PUBLIC_DEMO:
    st.sidebar.info("Public showcase · deterministic demo data · read-only")
else:
    if st.sidebar.button("Run demo scan", width="stretch"):
        save_scan(DemoProvider(), "Demo")
    if os.getenv("ALPACA_API_KEY_ID") and os.getenv("ALPACA_API_SECRET_KEY"):
        if st.sidebar.button("Run live Alpaca scan", type="primary", width="stretch"):
            live = AlpacaProvider(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"))
            save_scan(CachedProvider(live, repo), "Live Alpaca")
    else:
        st.sidebar.caption("Add Alpaca credentials to `.env` to enable live scans.")

if PUBLIC_DEMO:
    with st.spinner("Preparing the public market showcase…"):
        bootstrap_public_demo()

scan_rows = repo.list_scans()
if not scan_rows:
    st.title("FolioShift")
    st.caption("What changed. What matters.")
    st.info(
        "No saved scan yet. Choose **Run demo scan** to generate a deterministic local example without credentials."
    )
    st.stop()

scan_options = {row["id"]: f"{row['as_of']} · {row['provider'].title()} · #{row['id']}" for row in scan_rows}
default_id = st.session_state.get("selected_scan_id", scan_rows[0]["id"])
if default_id not in scan_options:
    default_id = scan_rows[0]["id"]
selected_id = st.sidebar.selectbox(
    "Saved scan",
    list(scan_options),
    index=list(scan_options).index(default_id),
    format_func=scan_options.get,
)
st.session_state["selected_scan_id"] = selected_id
scan = repo.get_scan(selected_id)
previous_scan = repo.previous_scan(selected_id)
enriched = [signal for signal in scan.signals if signal.options_axis is not None]
ranked_signals = sorted(enriched, key=lambda signal: signal.evidence_score or 0, reverse=True)
universe_lookup = {member.ticker: member for member in universe()}
watchlist_entries = repo.list_watchlist()
portfolio_positions = repo.list_positions()
daily_intelligence = build_daily_intelligence(
    scan,
    previous_scan,
    [item.ticker for item in watchlist_entries],
    portfolio_positions,
)
upcoming_catalysts = load_catalysts(
    CATALYSTS_PATH,
    scan.as_of,
    days=35,
    tickers={item.ticker for item in scan.ideas}
    | {item.ticker for item in watchlist_entries}
    | {item.ticker for item in portfolio_positions},
)
macro = scan.market_regime.get("global_macro", {})
outlook = load_global_outlook()
brief = executive_brief(scan)


def display_industry(signal):
    saved_industry = getattr(signal, "industry", "Unclassified")
    if saved_industry and saved_industry != "Unclassified":
        return saved_industry
    member = universe_lookup.get(signal.ticker)
    return getattr(member, "industry", "Unclassified") if member else "Unclassified"


def compact_dollars(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


st.markdown('<div class="radar-nav-spacer" aria-hidden="true"></div>', unsafe_allow_html=True)
st.title("FolioShift")
st.caption("What changed. What matters. · Personal portfolio intelligence after the close.")
with st.popover("Menu", use_container_width=True):
    view = st.radio(
        "Sections",
        PAGES,
        key="active_dashboard_view",
        format_func=PAGE_LABELS.get,
        label_visibility="collapsed",
    )
st.caption(f"Current: {PAGE_LABELS[view]} · {PAGE_DESCRIPTIONS[view]}")

mode_label = "SYNTHETIC DEMO DATA" if scan.provider == "demo" else "LIVE MARKET DATA"
st.markdown(f'<span class="radar-status">{mode_label}</span>', unsafe_allow_html=True)
st.caption(
    f"Viewing scan #{scan.id} · market session {scan.as_of.isoformat()} · {scan.status} · "
    f"{scan.provider} / {scan.option_feed} options feed"
)
with st.expander("New here? Read this 30-second guide"):
    st.markdown(
        """
        1. **Executive Brief** explains the market story, global backdrop and most important opportunities in plain language.
        2. **Global Macro** reads equities, credit, rates, the dollar and commodities together.
        3. **Trade Ideas** lists only setups that passed the 65-point evidence threshold and technical checks.
        4. A plan is **conditional**: nothing happens unless price reaches the trigger. The invalidation is the planned exit
           if the setup fails; 1R and 2R are one and two times the amount risked.

        Higher evidence means more of this scanner's inputs agree. It does **not** mean a higher guaranteed win rate.
        """
    )
if scan.option_feed == "indicative" and view in {"3 · Opportunity Map", "4 · Trade Ideas", "5 · Stock Explorer"}:
    st.warning(
        "Indicative options feed: trades are delayed and quotes are modified. Pressure is an approximation, not full market flow."
    )
if scan.warnings:
    with st.expander(f"{len(scan.warnings)} partial-data warning(s)"):
        for warning in scan.warnings:
            st.write(f"• {warning}")


def metric_row():
    regime = scan.market_regime
    columns = st.columns(5)
    columns[0].metric(
        "Market regime",
        regime.get("label", "Unknown").replace(" regime", ""),
        help="A simple SPY trend label based on its moving averages.",
    )
    columns[1].metric("SPY close", f"${regime.get('spy_close', 0):,.2f}", help="SPY close for this saved session.")
    columns[2].metric("Stocks scanned", f"{len(scan.signals):,}", help="Symbols with enough daily price history.")
    columns[3].metric(
        "Options checked",
        f"{len(enriched):,}",
        help="Finalists that received an options-chain pressure reading.",
    )
    columns[4].metric(
        "Trade ideas",
        f"{len(scan.ideas):,}",
        help="Conditional plans that passed both evidence and risk-width rules.",
    )


def scatter_chart():
    figure = go.Figure()
    for x0, x1, y0, y1, color in [
        (-100, 0, 0, 100, QUADRANT_COLORS["Contrarian Bid"]),
        (0, 100, 0, 100, QUADRANT_COLORS["Chase"]),
        (-100, 0, -100, 0, QUADRANT_COLORS["Fear"]),
        (0, 100, -100, 0, QUADRANT_COLORS["Hedged Rally"]),
    ]:
        figure.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=color,
            opacity=0.07,
            line_width=0,
            layer="below",
        )
    label_tickers = {signal.ticker for signal in ranked_signals[:12]}
    for quadrant, color in QUADRANT_COLORS.items():
        rows = [signal for signal in enriched if signal.quadrant == quadrant]
        if not rows:
            continue
        figure.add_trace(
            go.Scatter(
                x=[row.price_axis for row in rows],
                y=[row.options_axis for row in rows],
                mode="markers+text",
                name=quadrant,
                text=[row.ticker if row.ticker in label_tickers else "" for row in rows],
                textposition="top center",
                marker={
                    "size": [9 + (row.evidence_score or 0) / 6 for row in rows],
                    "color": color,
                    "line": {"width": 1, "color": "#d9e6ff"},
                    "opacity": 0.82,
                },
                customdata=[
                    [row.ticker, row.sector, row.evidence_score, row.valid_contracts, row.volume_ratio] for row in rows
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Relative price %{x:.1f}"
                    "<br>Estimated options sentiment %{y:.1f}"
                    "<br>Evidence %{customdata[2]:.1f}<br>Contracts %{customdata[3]}<br>Volume ratio %{customdata[4]:.2f}<extra></extra>"
                ),
            )
        )
    figure.add_hline(y=0, line_color="#52627d", line_width=1)
    figure.add_vline(x=0, line_color="#52627d", line_width=1)
    for label, x, y in [
        ("CONTRARIAN BID", -76, 92),
        ("CHASE", 76, 92),
        ("FEAR", -76, -92),
        ("HEDGED RALLY", 76, -92),
    ]:
        figure.add_annotation(x=x, y=y, text=label, showarrow=False, font={"size": 11, "color": "#8da2bd"})
    figure.update_layout(
        title="How price movement and options sentiment line up",
        xaxis_title="Relative price · lagging ← 0 → leading",
        yaxis_title="Estimated options sentiment · bearish ↓ 0 ↑ bullish",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,11,18,.5)",
        legend_orientation="h",
        margin={"l": 30, "r": 20, "t": 65, "b": 35},
        height=570,
    )
    figure.update_xaxes(range=[-105, 105])
    figure.update_yaxes(range=[-105, 105])
    return figure


def heatmap_chart():
    tickers = sorted(scan.sector_returns)
    z = [[100 * value for value in scan.sector_returns[ticker]] for ticker in tickers]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=["Week −4", "Week −3", "Week −2", "Latest week"],
            y=tickers,
            colorscale=[[0, "#7f1d1d"], [0.5, "#172033"], [1, "#047857"]],
            zmid=0,
            text=[[f"{value:+.1f}%" for value in row] for row in z],
            texttemplate="%{text}",
            colorbar={"title": "vs SPY"},
            hovertemplate="%{y} · %{x}<br>%{z:+.2f}% vs SPY<extra></extra>",
        )
    )
    figure.update_layout(
        title="Four-week sector rotation",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin={"l": 25, "r": 20, "t": 60, "b": 25},
    )
    return figure


def macro_returns_chart():
    assets = macro.get("assets", [])
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            name="1 month",
            x=[asset["name"] for asset in assets],
            y=[100 * asset["return_1m"] for asset in assets],
            marker_color=["#4ade80" if asset["return_1m"] >= 0 else "#fb7185" for asset in assets],
            hovertemplate="%{x}<br>1 month %{y:+.2f}%<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            name="3 months",
            x=[asset["name"] for asset in assets],
            y=[100 * asset["return_3m"] for asset in assets],
            mode="markers",
            marker={"size": 10, "color": "#93c5fd", "symbol": "diamond"},
            hovertemplate="%{x}<br>3 months %{y:+.2f}%<extra></extra>",
        )
    )
    figure.add_hline(y=0, line_color="#52627d", line_width=1)
    figure.update_layout(
        title="Cross-asset performance",
        yaxis_title="Return (%)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,11,18,.35)",
        legend_orientation="h",
        height=470,
        margin={"l": 25, "r": 20, "t": 65, "b": 90},
    )
    return figure


def risk_gauge_chart():
    score = macro.get("risk_score", 50)
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 34}},
            title={"text": "Cross-asset risk appetite"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#7da8ee"},
                "steps": [
                    {"range": [0, 35], "color": "#4a2028"},
                    {"range": [35, 65], "color": "#3c3b28"},
                    {"range": [65, 100], "color": "#173f35"},
                ],
                "threshold": {"line": {"color": "#f3f7ff", "width": 2}, "value": score},
            },
        )
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=310,
        margin={"l": 25, "r": 25, "t": 55, "b": 20},
    )
    return figure


def opportunity_mix_chart():
    counts = {quadrant: sum(signal.quadrant == quadrant for signal in enriched) for quadrant in QUADRANT_COLORS}
    figure = go.Figure(
        go.Pie(
            labels=list(counts),
            values=list(counts.values()),
            hole=0.62,
            marker={"colors": [QUADRANT_COLORS[label] for label in counts]},
            textinfo="label+value",
            hovertemplate="%{label}<br>%{value} options-enriched stocks<extra></extra>",
        )
    )
    figure.update_layout(
        title="Opportunity mix",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin={"l": 10, "r": 10, "t": 60, "b": 15},
        showlegend=False,
    )
    return figure


def market_driver_heatmap(color_by: str, size_by: str):
    if not enriched:
        return go.Figure()
    color_values = {
        "Relative price": lambda signal: signal.price_axis,
        "Options pressure": lambda signal: signal.options_axis or 0,
        "Evidence score": lambda signal: signal.evidence_score or 0,
    }
    size_values = {
        "Equal size": lambda signal: 1,
        "Usable option contracts": lambda signal: max(signal.valid_contracts, 1),
    }
    frame = pd.DataFrame(
        [
            {
                "sector": signal.sector,
                "ticker": signal.ticker,
                "company": signal.name,
                "color": color_values[color_by](signal),
                "size": size_values[size_by](signal),
                "quadrant": signal.quadrant,
                "price_axis": signal.price_axis,
                "options_axis": signal.options_axis,
                "evidence": signal.evidence_score,
                "contracts": signal.valid_contracts,
            }
            for signal in enriched
        ]
    )
    midpoint = 65 if color_by == "Evidence score" else 0
    figure = px.treemap(
        frame,
        path=[px.Constant("Options-enriched universe"), "sector", "ticker"],
        values="size",
        color="color",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=midpoint,
        hover_data={
            "company": True,
            "quadrant": True,
            "price_axis": ":+.1f",
            "options_axis": ":+.1f",
            "evidence": ":.1f",
            "contracts": True,
            "size": False,
            "color": False,
        },
    )
    figure.update_traces(textinfo="label")
    figure.update_layout(
        title=f"Market drivers · color by {color_by.lower()} · {size_by.lower()}",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 8, "r": 8, "t": 60, "b": 8},
        height=600,
        coloraxis_colorbar={"title": color_by},
    )
    return figure


def render_daily_changes():
    changes = daily_intelligence["changes"]
    if previous_scan is None:
        st.info("A prior completed session is needed before daily changes can be calculated.")
        return
    st.caption(f"Compared with {previous_scan.as_of.isoformat()} · same {scan.provider} data mode")
    columns = st.columns(4)
    columns[0].metric("New ideas", len(changes["new_ideas"]))
    columns[1].metric("Ideas removed", len(changes["removed_ideas"]))
    columns[2].metric("Setup changes", len(changes["quadrant_changes"]))
    columns[3].metric("Score moves ≥ 5", len(changes["score_moves"]))
    for item in changes["summary"]:
        st.write(f"• {item}")
    with st.expander("See the names behind the changes"):
        if changes["new_ideas"]:
            st.write(f"**New qualified ideas:** {', '.join(changes['new_ideas'])}")
        if changes["removed_ideas"]:
            st.write(f"**No longer qualified:** {', '.join(changes['removed_ideas'])}")
        if changes["quadrant_changes"]:
            st.dataframe(pd.DataFrame(changes["quadrant_changes"]), hide_index=True, width="stretch")
        if changes["score_moves"]:
            st.dataframe(pd.DataFrame(changes["score_moves"]), hide_index=True, width="stretch")


def render_personal_update(compact: bool = False):
    portfolio = daily_intelligence["portfolio"]
    alerts = daily_intelligence["alerts"]
    if not portfolio["position_count"]:
        st.info("Add holdings in My Portfolio to turn this market brief into your personal after-close update.")
        return

    metrics = st.columns(4)
    metrics[0].metric(
        "Portfolio value",
        f"${portfolio['market_value']:,.0f}" if portfolio["market_value"] is not None else "Awaiting scan",
        help="Saved closing prices × shares. This is not an intraday brokerage balance.",
    )
    metrics[1].metric(
        "Session P&L",
        f"${portfolio['daily_pnl']:+,.0f}" if portfolio["daily_pnl"] is not None else "Need 2 scans",
        delta=f"{portfolio['daily_return']:+.2%}" if portfolio["daily_return"] is not None else None,
    )
    metrics[2].metric(
        "Unrealized P&L",
        f"${portfolio['unrealized_pnl']:+,.0f}" if portfolio["unrealized_pnl"] is not None else "Add cost basis",
        help="Uses the optional average cost you entered; it does not include fees or taxes.",
    )
    metrics[3].metric("Material changes", len(alerts), help=daily_intelligence["alert_policy"])

    if alerts:
        st.markdown("**Worth your attention**")
        for alert in alerts[: 3 if compact else None]:
            icon = "●" if alert["severity"] == "high" else "○"
            st.write(f"{icon} **{alert['ticker']} · {alert['name']}** — {alert['reason']}.")
    else:
        st.success("No material followed-name change today. Quiet is a valid result; no action is suggested.")
    st.caption(daily_intelligence["alert_policy"])

    if not compact and portfolio["macro_notes"]:
        st.markdown("**How today's backdrop connects to your holdings**")
        for note in portfolio["macro_notes"]:
            st.write(f"• {note}")


def render_catalyst_rail(limit: int = 6):
    if not upcoming_catalysts:
        st.info("No verified catalyst is configured in the next 35 days.")
        return
    for catalyst in upcoming_catalysts[:limit]:
        with st.container(border=True):
            date_column, event_column = st.columns([0.2, 0.8])
            date_column.markdown(f"**{catalyst.date.strftime('%b %d')}**")
            date_column.caption(f"{catalyst.time_et} ET")
            event_column.markdown(f"**{catalyst.title}**")
            event_column.caption(f"{catalyst.category} · {catalyst.importance} importance · {catalyst.source}")
            if catalyst.source_url:
                event_column.markdown(f"[Official schedule]({catalyst.source_url})")


def render_official_outlook():
    st.markdown(f"#### Official world outlook · {outlook['as_of']}")
    st.caption("A slow-moving economic forecast reference beside the dashboard's daily market-implied signals.")
    columns = st.columns(len(outlook["metrics"]))
    for column, metric in zip(columns, outlook["metrics"]):
        column.metric(metric["label"], metric["value"])
        column.caption(metric["context"])
    st.markdown(f"**{outlook['title']}**")
    st.write(outlook["summary"])
    st.markdown(f"[Read the {outlook['source']}]({outlook['source_url']})")
    st.caption(outlook["source_note"])


def ideas_frame():
    signal_by_ticker = {signal.ticker: signal for signal in scan.signals}
    return pd.DataFrame(
        [
            {
                "Ticker": idea.ticker,
                "Company": signal_by_ticker[idea.ticker].name,
                "Industry": display_industry(signal_by_ticker[idea.ticker]),
                "Setup": idea.quadrant,
                "Direction": idea.direction.upper(),
                "Evidence": idea.evidence_score,
                "Why it surfaced": recommendation_reason(signal_by_ticker[idea.ticker], idea),
                "Trigger": idea.trigger,
                "Invalidation": idea.stop,
                "Target 1R": idea.target_1r,
                "Target 2R": idea.target_2r,
                "Expires": f"{idea.expires_after_sessions} sessions",
            }
            for idea in scan.ideas
        ]
    )


if view == "1 · Executive Brief":
    st.markdown(
        f"""
        <div class="radar-hero">
          <div class="radar-eyebrow">Your after-close signal</div>
          <h2>{brief["posture"]}</h2>
          <p>FolioShift filters the market down to the changes that affect your holdings and watchlist, then shows the
          evidence, the risk and what would invalidate the idea.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    headline_metrics = st.columns(4)
    headline_metrics[0].metric(
        "U.S. market trend",
        brief["market_label"].replace(" trend", "").replace(" regime", ""),
    )
    headline_metrics[1].metric(
        "Global risk appetite",
        f"{macro.get('risk_score', 50):.0f}/100",
        help="A market-implied score from global equities, high-yield credit and trend breadth.",
    )
    headline_metrics[2].metric("Qualified ideas", brief["idea_count"])
    headline_metrics[3].metric("Ideas ≥ 80 evidence", brief["high_evidence_count"])
    client_pdf = build_client_brief_pdf(scan, daily_intelligence, upcoming_catalysts)
    st.download_button(
        "Download client brief PDF",
        data=client_pdf,
        file_name=f"folioshift-client-brief-{scan.as_of.isoformat()}.pdf",
        mime="application/pdf",
        help="A dated executive brief built only from saved deterministic evidence and verified catalyst dates.",
    )

    st.subheader("Your portfolio today")
    render_personal_update(compact=True)

    story, risk = st.columns([1.35, 0.65])
    with story:
        st.subheader("The market story in one minute")
        for takeaway in brief["takeaways"]:
            st.write(f"• {takeaway}")
    with risk:
        st.subheader("What could go wrong")
        for item in brief["risks"]:
            st.write(f"• {item}")

    st.subheader("What changed since the prior session")
    render_daily_changes()

    st.subheader("Highest-ranked conditional opportunities")
    st.caption("These plans still require price confirmation at the activation trigger; they are not immediate orders.")
    signal_by_ticker = {signal.ticker: signal for signal in scan.signals}
    top_ideas = sorted(scan.ideas, key=lambda idea: idea.evidence_score, reverse=True)[:3]
    if top_ideas:
        columns = st.columns(len(top_ideas))
        for column, idea in zip(columns, top_ideas):
            signal = signal_by_ticker[idea.ticker]
            with column.container(border=True):
                st.markdown(f"### {idea.ticker} · {signal.name}")
                st.caption(f"{display_industry(signal)} · {idea.quadrant} · {idea.direction.upper()}")
                st.metric("Evidence", f"{idea.evidence_score:.1f}/100")
                if scan.option_feed == "indicative":
                    st.caption("Indicative options snapshot · approximation")
                st.write(recommendation_reason(signal, idea))
                st.caption(f"Activate at USD {idea.trigger:,.2f} · Invalidate at USD {idea.stop:,.2f}")
    else:
        st.info("No setup passed the evidence, confirmation and risk-width rules in this scan.")

    st.subheader("Upcoming verified catalysts")
    st.caption(
        "Official macro release dates that may change rates, volatility, or the market backdrop. "
        "The calendar provides context; it does not predict direction."
    )
    render_catalyst_rail()

    with st.container(border=True):
        render_official_outlook()
        st.markdown("**Main forecast risks**")
        for item in outlook["risks"]:
            st.write(f"• {item}")

    if professional_detail:
        with st.expander("Optional narrative engine and detailed daily brief"):
            daily = generate_daily_brief(scan)
            st.markdown(f"**{daily['headline']}**")
            st.write(daily["summary"])
            for leader in daily["leaders"]:
                st.write(f"• {leader}")
            if os.getenv("OPENAI_API_KEY") and st.button("Generate optional AI narrative"):
                st.session_state[f"ai_brief_{scan.id}"] = generate_daily_brief(
                    scan,
                    api_key=os.getenv("OPENAI_API_KEY"),
                )
            if st.session_state.get(f"ai_brief_{scan.id}"):
                st.json(st.session_state[f"ai_brief_{scan.id}"])

elif view == "2 · Global Macro":
    st.markdown(
        f"""
        <div class="radar-hero">
          <div class="radar-eyebrow">Market-implied world economy</div>
          <h2>{macro.get("risk_label", "Cross-asset snapshot unavailable")} · {macro.get("tone", "Unknown")} tone</h2>
          <p>Global equities, credit, long rates, the dollar and real assets are read together. This is a daily market
          lens—not a replacement for official GDP, inflation or policy statistics.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not macro.get("assets"):
        st.info("This older scan has no global macro snapshot. Run a new demo or live scan to populate it.")
    else:
        macro_metrics = st.columns(4)
        macro_metrics[0].metric("Risk posture", macro["risk_label"], f"{macro['risk_score']:.0f}/100")
        macro_metrics[1].metric(
            "Growth signal",
            {
                "Growth assets strengthening": "Strengthening",
                "Growth concerns rising": "Concerns",
                "Growth signal mixed": "Mixed",
            }.get(macro["growth_label"], macro["growth_label"]),
        )
        macro_metrics[2].metric(
            "Inflation signal",
            {
                "Inflation pressure rising": "Rising",
                "Disinflation impulse": "Disinflation",
                "Inflation signal neutral": "Neutral",
            }.get(macro["inflation_label"], macro["inflation_label"]),
        )
        macro_metrics[3].metric(
            "Dollar signal",
            {
                "Dollar strengthening": "Strengthening",
                "Dollar easing": "Easing",
                "Dollar broadly stable": "Stable",
            }.get(macro["dollar_label"], macro["dollar_label"]),
        )
        gauge, returns = st.columns([0.35, 0.65])
        with gauge:
            st.plotly_chart(risk_gauge_chart(), use_container_width=True)
            st.caption(f"{macro['risk_breadth']:.0f}% of tracked risk assets are above their 50-session trend.")
        with returns:
            st.plotly_chart(macro_returns_chart(), use_container_width=True)

        takeaways, table = st.columns([0.43, 0.57])
        with takeaways:
            st.subheader("What markets are saying")
            for takeaway in macro["takeaways"]:
                st.write(f"• {takeaway}")
            st.caption(macro["method"])
        with table:
            st.subheader("Cross-asset dashboard")
            macro_frame = pd.DataFrame(
                [
                    {
                        "Lens": asset["name"],
                        "What it represents": asset["lens"],
                        "1 week": f"{asset['return_1w']:+.1%}",
                        "1 month": f"{asset['return_1m']:+.1%}",
                        "3 months": f"{asset['return_3m']:+.1%}",
                        "Trend": "Above 50-day" if asset["above_ema50"] else "Below 50-day",
                    }
                    for asset in macro["assets"]
                ]
            )
            st.dataframe(macro_frame, hide_index=True, width="stretch")

    st.divider()
    render_official_outlook()
    with st.expander("Key official-outlook risks"):
        for item in outlook["risks"]:
            st.write(f"• {item}")
    with st.expander("Why these market proxies are used"):
        st.markdown(
            """
            - **SPY, EFA and EEM** compare U.S., developed ex-U.S. and emerging-market equity behavior.
            - **HYG** is a liquid read on non-investment-grade corporate credit appetite.
            - **TLT** reflects long-duration U.S. Treasury prices; it moves inversely to long yields, all else equal.
            - **UUP** represents the U.S. dollar versus major currencies.
            - **GLD, USO and DBC** frame gold, crude oil and broad commodity pressure.

            Product definitions: [EFA](https://www.ishares.com/us/products/239623/ishares-msci-eafe-etf),
            [EEM](https://www.ishares.com/us/products/239637/ishares-msci-emerging-markets-etf),
            [HYG](https://www.ishares.com/us/products/239565/ishares-iboxx-high-yield-corporate-bond-etf),
            [TLT](https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf),
            [USO](https://www.uscfinvestments.com/uso), and
            [Invesco commodity funds](https://www.invesco.com/us/en/solutions/invesco-etfs/commodity-investing.html).
            """
        )

elif view == "3 · Opportunity Map":
    metric_row()
    st.subheader("Market Driver Heatmap")
    st.caption(
        "A fast sector-grouped view of the options-enriched universe. Equal-size tiles avoid implying market-cap "
        "weight that is not in the current data contract; switch size to usable contracts to emphasize data depth."
    )
    heatmap_color, heatmap_size = st.columns(2)
    driver_color = heatmap_color.selectbox(
        "Color tiles by",
        ["Relative price", "Options pressure", "Evidence score"],
    )
    driver_size = heatmap_size.selectbox(
        "Size tiles by",
        ["Equal size", "Usable option contracts"],
    )
    st.plotly_chart(market_driver_heatmap(driver_color, driver_size), use_container_width=True)
    st.divider()
    st.subheader("Where price and options activity agree—or conflict")
    st.markdown(
        """
        **How to read this chart**

        - **Each dot is one stock.** Its position compares two different signals.
        - **Left ↔ right is relative price, not a return percentage.** It blends five-session performance versus the
          stock's sector with twenty-session performance versus the S&P 500. Leaders move right; laggards move left.
        - **Down ↕ up is estimated options sentiment.** Trades near the ask are treated as buyer-initiated and trades
          near the bid as seller-initiated. Bought calls and sold puts move the score up; bought puts and sold calls
          move it down.
        - **Dot size is evidence strength.** Farther from the center means a clearer directional reading; near the
          center means the signals are weak or mixed.
        """
    )
    st.info(
        "The cross at zero is deliberate: the top-right and bottom-left zones show price and options agreeing; "
        "the other two zones show a disagreement that may signal reversal interest or hedging."
    )
    st.plotly_chart(scatter_chart(), use_container_width=True)
    st.markdown("**The four zones**")
    quadrant_items = list(QUADRANT_EXPLANATIONS.items())
    for start in range(0, len(quadrant_items), 2):
        columns = st.columns(2)
        for column, (quadrant, explanation) in zip(columns, quadrant_items[start : start + 2]):
            with column.container(border=True):
                st.markdown(f"**{quadrant}**")
                st.caption(explanation)
    with st.expander("How are the two axes calculated?"):
        st.markdown(
            """
            - **Relative price (−100 to +100):** 60% five-session sector-relative rank plus 40% twenty-session
              S&P 500-relative rank. Zero is the middle of the scanned group—not a zero return.
            - **Estimated options sentiment (−100 to +100):** net bullish premium divided by total included premium
              across valid contracts. It is an approximation from delayed indicative snapshots, not complete market
              flow and not a probability that the stock will rise or fall.
            """
        )
    rotation, mix = st.columns([0.67, 0.33])
    with rotation:
        st.caption("Green means a sector beat SPY that week; red means it lagged SPY.")
        st.plotly_chart(heatmap_chart(), use_container_width=True)
    with mix:
        st.plotly_chart(opportunity_mix_chart(), use_container_width=True)

elif view == "4 · Trade Ideas":
    st.subheader("Ranked Ideas")
    st.info(
        "These are conditional research plans—not immediate buy or sell calls. A plan activates only if price crosses "
        "its trigger. Evidence is a transparent agreement score, not a win probability."
    )
    frame = ideas_frame()
    if frame.empty:
        st.info("No setup met the 65-point threshold and technical confirmation rules in this scan.")
    else:
        signal_by_ticker = {signal.ticker: signal for signal in scan.signals}
        all_ideas = sorted(scan.ideas, key=lambda item: item.evidence_score, reverse=True)
        setup_options = sorted({idea.quadrant for idea in all_ideas})
        setup_filter, direction_filter, count_filter, page_filter = st.columns([2, 1, 1, 1])
        selected_setups = setup_filter.multiselect("Setup type", setup_options, default=setup_options)
        selected_direction = direction_filter.selectbox("Direction", ["All", "Long", "Short"])
        page_size = count_filter.selectbox("Ideas per page", [5, 10, 20], index=1)
        filtered_ideas = [
            idea
            for idea in all_ideas
            if idea.quadrant in selected_setups
            and (selected_direction == "All" or idea.direction == selected_direction.lower())
        ]
        page_count = max(1, (len(filtered_ideas) + page_size - 1) // page_size)
        page = page_filter.selectbox("Page", list(range(1, page_count + 1)))
        start = (page - 1) * page_size
        visible_ideas = filtered_ideas[start : start + page_size]
        rank_by_ticker = {idea.ticker: rank for rank, idea in enumerate(all_ideas, start=1)}
        st.caption(
            f"Showing {len(visible_ideas)} of {len(filtered_ideas)} matching ideas · ranked highest evidence first"
        )
        if not visible_ideas:
            st.info("No ideas match these filters. Select at least one setup type or change the direction.")
        for idea in visible_ideas:
            rank = rank_by_ticker[idea.ticker]
            signal = signal_by_ticker[idea.ticker]
            risk = abs(idea.trigger - idea.stop)
            with st.container(border=True):
                heading, score = st.columns([4, 1])
                with heading:
                    st.markdown(f"### #{rank} · {signal.ticker} — {signal.name}")
                    st.caption(
                        f"{display_industry(signal)} · {signal.sector} · {idea.quadrant} · {idea.direction.upper()}"
                    )
                with score:
                    st.metric("Evidence", f"{idea.evidence_score:.1f}/100")
                    st.caption(evidence_label(idea.evidence_score))
                    if scan.option_feed == "indicative":
                        st.caption("Indicative snapshot")
                st.markdown("**Why this idea surfaced**")
                st.write(recommendation_reason(signal, idea))
                nearby_catalysts = [
                    catalyst
                    for catalyst in upcoming_catalysts
                    if catalyst.date <= scan.as_of + timedelta(days=7)
                    and (catalyst.scope == "macro" or idea.ticker in catalyst.tickers)
                ]
                if nearby_catalysts:
                    catalyst = nearby_catalysts[0]
                    st.warning(
                        f"Catalyst watch · {catalyst.date.strftime('%b %d')} {catalyst.time_et} ET · "
                        f"{catalyst.title}"
                    )
                levels = st.columns(4)
                levels[0].metric("Activation trigger", f"${idea.trigger:,.2f}")
                levels[1].metric("Exit if invalidated", f"${idea.stop:,.2f}")
                levels[2].metric("First target · 1R", f"${idea.target_1r:,.2f}")
                levels[3].metric("Second target · 2R", f"${idea.target_2r:,.2f}")
                st.caption(
                    f"Planned risk is ${risk:,.2f} per share. If the trigger is not reached within "
                    f"{idea.expires_after_sessions} sessions, the idea expires."
                )
        with st.expander("Compare all ideas in one table"):
            st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button(
        "Download ideas CSV",
        frame.to_csv(index=False),
        file_name=f"folioshift-ideas-{scan.as_of.isoformat()}.csv",
        mime="text/csv",
    )

elif view == "5 · Stock Explorer":
    company_signals = [signal for signal in scan.signals if display_industry(signal) != "Sector ETF"]
    all_signal_lookup = {signal.ticker: signal for signal in company_signals}
    if not company_signals:
        st.info("This scan has no company-level price data.")
    else:
        st.subheader("Stock Explorer")
        st.caption(
            "Start with the 100 companies that traded the most dollar value over the last five completed sessions, "
            "or search every company in the saved price scan. Watchlist stocks remain available even outside the top 100."
        )
        turnover_available = any(signal.dollar_turnover_5d > 0 for signal in company_signals)
        most_traded = sorted(company_signals, key=lambda item: (-item.dollar_turnover_5d, item.ticker))[:100]
        for item in watchlist_entries:
            watchlist_signal = all_signal_lookup.get(item.ticker)
            if watchlist_signal and watchlist_signal not in most_traded:
                most_traded.append(watchlist_signal)
        for item in portfolio_positions:
            portfolio_signal = all_signal_lookup.get(item.ticker)
            if portfolio_signal and portfolio_signal not in most_traded:
                most_traded.append(portfolio_signal)

        selector, finder, search_action = st.columns([0.30, 0.50, 0.20])
        explorer_mode = selector.selectbox(
            "Explorer universe",
            ["Most traded 100", "Options-enriched", "All scanned stocks"],
            help="Most traded uses trailing five-session closing price × volume. It is a liquidity ranking, not market cap.",
        )
        company_query = finder.text_input(
            "Find a scanned company",
            placeholder="Type Palantir, PLTR, Microsoft…",
            help="Search always covers every company in the saved scan, regardless of the universe filter.",
        )
        search_action.markdown("<div style='height: 1.75rem'></div>", unsafe_allow_html=True)
        search_action.button("Search stocks", type="primary", width="stretch")

        if explorer_mode == "Options-enriched":
            browse_signals = ranked_signals
        elif explorer_mode == "All scanned stocks":
            browse_signals = sorted(company_signals, key=lambda item: item.name.casefold())
        else:
            browse_signals = most_traded

        if not turnover_available and explorer_mode == "Most traded 100":
            st.warning("This older scan predates dollar-turnover ranking. Run a new scan to populate the top 100.")

        signal = None
        if company_query.strip():
            catalog_by_ticker = {entry.ticker: entry for entry in company_catalog()}
            searchable_catalog = [
                catalog_by_ticker.get(item.ticker)
                or CompanyCatalogEntry(
                    ticker=item.ticker,
                    name=item.name,
                    exchange="Saved scan",
                    sector=item.sector,
                    industry=display_industry(item),
                    sector_etf=item.sector_etf,
                )
                for item in company_signals
            ]
            matches = search_company_catalog(searchable_catalog, company_query, limit=12)
            matching_signals = [all_signal_lookup[entry.ticker] for entry in matches if entry.ticker in all_signal_lookup]
            if matching_signals:
                result_lookup = {f"{item.name} — {item.ticker}": item for item in matching_signals}
                selected_result = st.radio("Matching stocks", list(result_lookup), index=0)
                signal = result_lookup[selected_result]
            else:
                st.info(f'No scanned company matched “{company_query.strip()}”. Try its ticker or a shorter name.')
        elif browse_signals:
            browse_lookup = {item.ticker: item for item in browse_signals}
            ticker = st.selectbox(
                "Choose a stock",
                list(browse_lookup),
                format_func=lambda symbol: (
                    f"{browse_lookup[symbol].name} — {symbol} · "
                    f"{compact_dollars(browse_lookup[symbol].dollar_turnover_5d)} traded in 5 sessions"
                ),
            )
            signal = browse_lookup[ticker]

        if signal is None:
            st.stop()

        idea = next((item for item in scan.ideas if item.ticker == signal.ticker), None)
        profile = build_stock_profile(signal)
        st.subheader(f"{signal.ticker} · {signal.name}")
        if signal.options_axis is not None:
            st.caption(
                f"{display_industry(signal)} · {signal.sector} · {signal.quadrant} setup · "
                f"{signal.feed} options feed"
            )
        else:
            st.caption(f"{display_industry(signal)} · {signal.sector} · Price scan only")
        if idea:
            st.success(f"**Why it surfaced:** {recommendation_reason(signal, idea)}")
        elif signal.options_axis is None:
            relative_description = "outperforming" if signal.price_axis >= 0 else "lagging"
            st.info(
                f"**Price-scan context:** {signal.name} is {relative_description} its sector/SPY comparison set "
                f"({signal.price_axis:+.1f}/100 relative-price axis). It was not selected for options enrichment "
                "in this session, so no options-based evidence score or trade plan is shown."
            )
        else:
            st.info(f"**What the signal says:** {recommendation_reason(signal, None)}")
        symbol_catalysts = [
            catalyst
            for catalyst in upcoming_catalysts
            if catalyst.scope == "macro" or signal.ticker in catalyst.tickers
        ][:2]
        if symbol_catalysts:
            st.caption(
                "Next catalyst context: "
                + " · ".join(
                    f"{item.date.strftime('%b %d')} {item.title}" for item in symbol_catalysts
                )
            )
        st.markdown("#### At a glance")
        for start in (0, 3):
            kpi_columns = st.columns(3)
            for column, kpi in zip(kpi_columns, profile.kpis[start : start + 3]):
                column.metric(kpi.label, kpi.value, delta=kpi.delta, help=kpi.help)
        st.caption(f"Price is the saved close for {scan.as_of.isoformat()}, not a real-time intraday quote.")

        with st.container(border=True):
            trend_column, participation_column = st.columns(2)
            trend_column.markdown(f"**Trend · {profile.trend_label}**")
            trend_column.caption(profile.trend_explanation)
            participation_column.markdown(f"**Trading activity · {profile.participation_label}**")
            participation_column.caption(profile.participation_explanation)

        st.markdown("#### Price and relative performance")
        st.caption(
            "The first chart asks whether price and trend agree. The second asks whether the stock is creating value "
            "beyond its sector and the broad market. All series use saved completed sessions."
        )
        st.plotly_chart(profile.price_figure, use_container_width=True)
        st.plotly_chart(profile.relative_figure, use_container_width=True)

        st.markdown("#### Options and trade-plan context")
        signal_columns = st.columns(3)
        signal_columns[0].metric(
            "Evidence / 100",
            f"{signal.evidence_score:.1f}" if signal.evidence_score is not None else "Not enriched",
            help="Agreement across options, coverage, price, volume, and trend.",
        )
        signal_columns[1].metric(
            "Options pressure",
            f"{signal.options_axis:+.1f}" if signal.options_axis is not None else "Not enriched",
            help="Negative means bearish; positive means bullish inferred premium.",
        )
        signal_columns[2].metric(
            "Volume vs normal",
            f"{signal.volume_ratio:.2f}×",
            help="Latest session volume versus the prior 20-session average.",
        )
        st.markdown("#### Conditional plan")
        if idea:
            plan = st.columns(4)
            plan[0].metric("Activate at", f"${idea.trigger:,.2f}")
            plan[1].metric("Exit if wrong", f"${idea.stop:,.2f}")
            plan[2].metric("First target", f"${idea.target_1r:,.2f}")
            plan[3].metric("Second target", f"${idea.target_2r:,.2f}")
            action = "rises above" if idea.direction == "long" else "falls below"
            st.caption(
                f"This {idea.direction} plan activates only if price {action} the trigger. It expires after "
                f"{idea.expires_after_sessions} sessions if untriggered and is evaluated for up to "
                f"{idea.max_holding_sessions} sessions after activation."
            )
        elif signal.quadrant == "Hedged Rally":
            st.info("Watch-only: put pressure may represent portfolio hedging rather than a bearish directional view.")
        elif signal.options_axis is None:
            st.info("No options-based plan: this stock has price data but was outside this session's enrichment set.")
        else:
            st.info("No plan: the setup did not clear the score, confirmation, or maximum-risk-width rule.")

        with st.expander("Evidence and technical detail", expanded=professional_detail):
            if signal.options_axis is not None:
                st.markdown("#### How the evidence score was built")
                st.caption("Score points add to the displayed evidence score. Readings are normalized to 0–100.")
                components = pd.DataFrame(evidence_components(signal))
                st.dataframe(components, hide_index=True, width="stretch")
            else:
                st.info("Options and evidence components were not calculated for this stock in the selected scan.")
            left, right = st.columns(2)
            with left:
                st.markdown("#### Price evidence")
                st.dataframe(
                    pd.DataFrame(
                        [
                            ("Scan close", f"${signal.close:,.2f}", "Reference price at the saved close"),
                            ("5-session return", f"{signal.return_5d:+.2%}", "Recent move"),
                            ("20-session return", f"{signal.return_20d:+.2%}", "Roughly one trading month"),
                            (
                                "5-session dollar turnover",
                                compact_dollars(signal.dollar_turnover_5d),
                                "Closing price × shares traded",
                            ),
                            (
                                "5 sessions vs sector",
                                f"{signal.sector_relative_5d:+.2%}",
                                "Performance beyond sector ETF",
                            ),
                            (
                                "20 sessions vs SPY",
                                f"{signal.spy_relative_20d:+.2%}",
                                "Performance beyond the broad market",
                            ),
                            ("ATR · daily movement", f"${signal.atr14:,.2f}", "Typical 14-session trading range"),
                        ],
                        columns=["Measure", "Reading", "Plain meaning"],
                    ),
                    hide_index=True,
                    width="stretch",
                )
            with right:
                st.markdown("#### Trend reference")
                st.dataframe(
                    pd.DataFrame(
                        [
                            ("EMA 20", f"${signal.ema20:,.2f}", "Short trend"),
                            ("EMA 50", f"${signal.ema50:,.2f}", "Intermediate trend"),
                            ("EMA 200", f"${signal.ema200:,.2f}", "Long trend"),
                            ("10-session low", f"${signal.swing_low_10d:,.2f}", "Recent support reference"),
                            ("10-session high", f"${signal.swing_high_10d:,.2f}", "Recent resistance reference"),
                        ],
                        columns=["Measure", "Level", "Plain meaning"],
                    ),
                    hide_index=True,
                    width="stretch",
                )

        with st.expander("Options data quality and exclusions", expanded=professional_detail):
            if signal.options_axis is None:
                st.write("Not options-enriched in this scan; price and technical data remain available above.")
            else:
                st.write(
                    f"Latest included trade: "
                    f"{signal.latest_trade_at.isoformat() if signal.latest_trade_at else 'No valid timestamp'}"
                )
                st.write(
                    f"Usable contracts: {signal.valid_contracts} · Excluded contracts: {signal.excluded_contracts}"
                )
                if signal.exclusions:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"Exclusion reason": reason.replace("_", " ").title(), "Contracts": count}
                                for reason, count in signal.exclusions.items()
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                    )
                for warning in signal.warnings:
                    st.warning(warning)

elif view == "6 · Watchlist":
    st.subheader("My Portfolio")
    if PUBLIC_DEMO:
        st.caption(
            "A sample portfolio demonstrates the personalized update. Holdings are fictional, read-only and never sent "
            "to a broker. Your private local edition stores them only in its SQLite database."
        )
    else:
        st.caption(
            "Add shares and an optional average cost. FolioShift uses completed-session prices to explain daily changes; "
            "it never connects to order entry."
        )

    render_personal_update()
    with st.expander("How the daily update works"):
        st.markdown(
            "1. Add a holding or watchlist company.\n"
            "2. The private scheduler runs after 17:15 America/New_York on completed trading days.\n"
            "3. FolioShift saves the new closing-price, options and macro evidence, compares it with the prior scan, "
            "and surfaces only material changes.\n"
            "4. Every published trade idea stays frozen and is evaluated against later daily bars."
        )
        if PUBLIC_DEMO:
            st.info("This hosted showcase uses synthetic data. Use the private edition with Alpaca credentials for fresh after-close data.")
        elif os.getenv("ALPACA_API_KEY_ID") and os.getenv("ALPACA_API_SECRET_KEY"):
            st.success("Live after-close data is configured. Keep the FolioShift service running for automatic updates.")
        else:
            st.warning("Automatic market updates are off. Add Alpaca credentials to `.env`, then restart `./start.sh`.")
    portfolio = daily_intelligence["portfolio"]
    if portfolio["positions"]:
        st.markdown("#### Holdings")
        holding_rows = []
        for row in portfolio["positions"]:
            holding_rows.append(
                {
                    "Ticker": row["ticker"],
                    "Company": row["name"],
                    "Shares": row["shares"],
                    "Saved close": f"${row['current_price']:,.2f}" if row["current_price"] is not None else "Pending",
                    "Market value": f"${row['market_value']:,.0f}" if row["market_value"] is not None else "Pending",
                    "Session": f"{row['session_return']:+.2%}" if row["session_return"] is not None else "—",
                    "Unrealized": f"${row['unrealized_pnl']:+,.0f}" if row["unrealized_pnl"] is not None else "—",
                    "Setup": row["quadrant"] or "Price only",
                    "Evidence": f"{row['evidence']:.1f}" if row["evidence"] is not None else "—",
                }
            )
        st.dataframe(pd.DataFrame(holding_rows), hide_index=True, width="stretch")
        if portfolio["sector_exposure"]:
            exposure = pd.DataFrame(portfolio["sector_exposure"])
            exposure["Weight"] = exposure["weight"].map(lambda value: f"{value:.1%}")
            exposure["Value"] = exposure["market_value"].map(lambda value: f"${value:,.0f}")
            with st.expander("Portfolio concentration"):
                st.dataframe(
                    exposure[["sector", "Weight", "Value"]].rename(columns={"sector": "Sector"}),
                    hide_index=True,
                    width="stretch",
                )

    st.markdown("#### Add or update a holding")
    catalog_entries = company_catalog()
    position_tickers = {position.ticker for position in portfolio_positions}
    with st.form("portfolio_company_search", clear_on_submit=False, border=False):
        position_query = st.text_input(
            "Find a portfolio company",
            placeholder="Try Palantir, PLTR, Nu Bank, or NU",
        )
        st.form_submit_button("Search portfolio companies", type="primary", width="stretch")
    position_matches = search_company_catalog(catalog_entries, position_query, limit=8)
    selected_position_company = None
    if position_query.strip() and not position_matches:
        st.info(f'No company matched “{position_query.strip()}”. Try a ticker or shorter name.')
    elif position_matches:
        position_results = {
            f"{entry.name} — {entry.ticker} · {entry.exchange}": entry for entry in position_matches
        }
        selected_position_label = st.radio("Portfolio search results", list(position_results), index=0)
        selected_position_company = position_results[selected_position_label]

    if selected_position_company:
        existing_position = next(
            (item for item in portfolio_positions if item.ticker == selected_position_company.ticker),
            None,
        )
        with st.form("portfolio_position_editor", border=True):
            st.markdown(f"**{selected_position_company.name} ({selected_position_company.ticker})**")
            shares_column, cost_column = st.columns(2)
            shares = shares_column.number_input(
                "Shares",
                min_value=0.0001,
                value=float(existing_position.shares) if existing_position else 1.0,
                step=1.0,
            )
            average_cost = cost_column.number_input(
                "Average cost per share (optional)",
                min_value=0.0,
                value=float(existing_position.average_cost or 0.0) if existing_position else 0.0,
                step=1.0,
            )
            thesis = st.text_input(
                "Why do you own it? (optional)",
                value=existing_position.thesis if existing_position else "",
                placeholder="One sentence investment thesis",
            )
            if st.form_submit_button(
                "Public demo · read only" if PUBLIC_DEMO else "Save holding",
                type="primary",
                width="stretch",
                disabled=PUBLIC_DEMO,
            ):
                repo.upsert_position(
                    PortfolioPosition(
                        ticker=selected_position_company.ticker,
                        name=selected_position_company.name,
                        sector=selected_position_company.sector,
                        sector_etf=selected_position_company.sector_etf,
                        industry=selected_position_company.industry,
                        shares=shares,
                        average_cost=average_cost or None,
                        thesis=thesis,
                        created_at=existing_position.created_at if existing_position else None,
                    )
                )
                st.success(f"Saved {selected_position_company.name} in your portfolio.")
                st.rerun()

    if portfolio_positions and not PUBLIC_DEMO:
        position_lookup = {item.ticker: item for item in portfolio_positions}
        remove_position_ticker = st.selectbox(
            "Remove a holding",
            list(position_lookup),
            format_func=lambda symbol: f"{position_lookup[symbol].name} — {symbol}",
        )
        if st.button("Remove holding"):
            repo.remove_position(remove_position_ticker)
            st.rerun()

    st.divider()
    st.subheader("Watchlist")
    if PUBLIC_DEMO:
        st.caption(
            "This public showcase uses a curated, read-only watchlist. Search still demonstrates company discovery; "
            "the private edition can save results and prioritize them for the next scan."
        )
    else:
        st.caption(
            "Search by a familiar company name or ticker—sector and industry are filled in automatically. "
            "Watchlist names are prioritized for options enrichment on the next scan."
        )
    watchlist = watchlist_entries
    watchlist_tickers = {item.ticker for item in watchlist}
    if watchlist:
        pulse_by_ticker = {row["ticker"]: row for row in daily_intelligence["watchlist_pulse"]}
        pulse_rows = []
        for item in watchlist:
            pulse = pulse_by_ticker[item.ticker]
            pulse_rows.append(
                {
                    "Ticker": item.ticker,
                    "Company": item.name,
                    "Latest saved price": (
                        f"${pulse['current_price']:,.2f}" if pulse["current_price"] is not None else "Pending scan"
                    ),
                    "Change vs prior session": (
                        f"{pulse['price_change']:+.2%}" if pulse["price_change"] is not None else "New / unavailable"
                    ),
                    "Evidence": f"{pulse['evidence']:.1f}" if pulse["evidence"] is not None else "—",
                    "Evidence change": (
                        f"{pulse['evidence_change']:+.1f}" if pulse["evidence_change"] is not None else "—"
                    ),
                    "Setup": pulse["quadrant"] or "Not enriched",
                    "Status": pulse["status"],
                }
            )
        st.markdown("#### Daily Pulse")
        if previous_scan:
            st.caption(
                f"Latest saved session {scan.as_of.isoformat()} compared with {previous_scan.as_of.isoformat()}."
            )
        else:
            st.caption("Price and evidence changes appear after a second completed scan is available.")
        st.dataframe(
            pd.DataFrame(pulse_rows),
            hide_index=True,
            width="stretch",
        )
        with st.expander("Watchlist company classifications"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ticker": item.ticker,
                            "Company": item.name,
                            "Industry": item.industry,
                            "Sector": item.sector,
                            "Benchmark": item.sector_etf,
                        }
                        for item in watchlist
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    else:
        st.info("Your watchlist is empty. Search for a company below to add the first one.")

    available_companies = [entry for entry in catalog_entries if entry.ticker not in watchlist_tickers]
    st.markdown("#### Add a company")
    st.caption("Type a company name or ticker, then press **Search**. Results are ranked by best match.")
    with st.form("watchlist_company_search", clear_on_submit=False, border=False):
        search_field, search_action = st.columns([4, 1])
        company_query = search_field.text_input(
            "Find a company",
            placeholder="Try Palantir, PLTR, Nu Bank, or NU",
            help="Familiar aliases such as Nu Bank are supported.",
        )
        search_action.markdown("<div style='height: 1.75rem'></div>", unsafe_allow_html=True)
        search_action.form_submit_button("Search", type="primary", width="stretch")

    search_matches = search_company_catalog(available_companies, company_query, limit=8)
    selected_company = None
    if company_query.strip() and not search_matches:
        st.info(
            f'No company matched “{company_query.strip()}”. Try the ticker, a shorter company name, or an alias.'
        )
    elif search_matches:
        result_lookup = {
            f"{entry.name} — {entry.ticker} · {entry.exchange}": entry for entry in search_matches
        }
        selected_result = st.radio(
            "Search results",
            list(result_lookup),
            index=0,
            help="The closest match is selected automatically.",
        )
        selected_company = result_lookup[selected_result]

    if selected_company:
        with st.container(border=True):
            preview, action = st.columns([3, 2])
            preview.markdown(f"**{selected_company.name} ({selected_company.ticker})**")
            preview.caption(
                f"{selected_company.exchange} · {selected_company.industry} · {selected_company.sector} · "
                f"benchmark {selected_company.sector_etf}"
            )
            if selected_company.sector == "Unclassified":
                preview.caption("Sector not classified in the local catalog; SPY will be used as the fallback benchmark.")
            if action.button(
                "Public demo · read only" if PUBLIC_DEMO else "Add to watchlist",
                type="primary",
                width="stretch",
                disabled=PUBLIC_DEMO,
            ):
                repo.upsert_watchlist(
                    UniverseMember(
                        selected_company.ticker,
                        selected_company.name,
                        selected_company.sector,
                        selected_company.sector_etf,
                        True,
                        selected_company.industry,
                    )
                )
                st.success(f"Added {selected_company.name} to the watchlist.")
                st.rerun()
    st.caption(
        f"Search covers {len(catalog_entries):,} US-listed companies from the dated S&P 500 seed and the official "
        "Nasdaq Trader symbol directory. Newly added names enter the price scan on the next run."
    )
    if watchlist and not PUBLIC_DEMO:
        watchlist_lookup = {item.ticker: item for item in watchlist}
        remove = st.selectbox(
            "Remove a company",
            [item.ticker for item in watchlist],
            format_func=lambda symbol: f"{watchlist_lookup[symbol].name} — {symbol}",
        )
        if st.button("Remove from watchlist"):
            repo.remove_watchlist(remove)
            st.rerun()

elif view == "7 · Paper Results":
    st.subheader("Forward paper results")
    st.caption("Only scheduled ideas enter this log. Results use future daily highs and lows—no orders are placed.")
    with st.expander("Understand the statuses"):
        st.markdown(
            """
            - **Pending:** trigger has not been reached yet.
            - **Open:** trigger was reached and neither stop nor final target has closed the observation.
            - **Expired:** trigger was not reached within five sessions.
            - **Stopped / Target 1R / Target 2R:** the corresponding level was touched.
            - **Time exit:** twenty sessions elapsed after activation.

            If a stop and target occur inside the same daily bar, the app records the stop first.
            """
        )
    outcomes = repo.list_outcomes()
    if outcomes:
        frame = pd.DataFrame([outcome.to_dict() for outcome in outcomes])
        st.dataframe(frame, hide_index=True, width="stretch")
        closed = frame[frame["result_r"].notna()]
        if not closed.empty:
            columns = st.columns(3)
            columns[0].metric("Closed observations", len(closed))
            columns[1].metric("Average R", f"{closed['result_r'].mean():+.2f}")
            columns[2].metric("Positive outcomes", f"{(closed['result_r'] > 0).mean():.0%}")
    else:
        st.info(
            "Scheduled ideas will appear here as pending, triggered, stopped, targeted, or time-exited observations."
        )
    st.download_button(
        "Download outcomes JSON",
        export_outcomes_json(outcomes),
        file_name="folioshift-outcomes.json",
        mime="application/json",
    )

else:
    st.subheader("Method, data quality and scan history")
    st.info(
        "The scanner narrows a large universe into explainable conditional setups. It does not predict certainty or place trades."
    )
    health = st.columns(4)
    health[0].metric("Scan status", scan.status.title())
    health[1].metric("Price feed", scan.stock_feed.upper())
    health[2].metric("Options feed", scan.option_feed.title())
    health[3].metric("Warnings", len(scan.warnings))

    st.markdown("#### Data sources at a glance")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Layer": "Stock prices",
                    "Source": f"{scan.provider.title()} · {scan.stock_feed}",
                    "Use": "Relative performance, trend, ATR and volume",
                    "Important limit": "Demo scans are synthetic; live coverage depends on Alpaca entitlement",
                },
                {
                    "Layer": "Options pressure",
                    "Source": f"{scan.provider.title()} · {scan.option_feed}",
                    "Use": "Directional premium approximation",
                    "Important limit": "Latest snapshots are not a complete institutional flow tape",
                },
                {
                    "Layer": "Global macro",
                    "Source": "Market ETF proxies",
                    "Use": "Daily cross-asset risk, growth, inflation and dollar lens",
                    "Important limit": "Market-implied signal—not an official economic statistic",
                },
                {
                    "Layer": "Official outlook",
                    "Source": f"{outlook['source']} · {outlook['as_of']}",
                    "Use": "Slow-moving world growth and inflation reference",
                    "Important limit": "Forecasts can change and update less frequently than markets",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    st.markdown("#### The four setup types")
    st.dataframe(
        pd.DataFrame(
            [
                {"Setup": quadrant, "Plain-English meaning": explanation}
                for quadrant, explanation in QUADRANT_EXPLANATIONS.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Formula-level methodology", expanded=professional_detail):
        st.markdown(
            """
            **Price axis.** 60% five-session sector-relative percentile and 40% twenty-session SPY-relative percentile,
            mapped to −100…+100.

            **Options axis.** The latest contract trade is located between its bid and ask, weighted by premium notional.
            Bought calls and sold puts contribute bullish pressure; bought puts and sold calls contribute bearish pressure.
            Only 7–45 DTE contracts with |delta| 0.20–0.80, same-session trades, non-crossed quotes, and spreads ≤25% are used.

            **Evidence score.** 35% options magnitude, 20% contract coverage, 20% price displacement, 15% volume rank,
            and 10% bucket-specific trend confirmation. It is a ranking heuristic—not a probability.

            **Trade plans.** Only Contrarian Bid, Fear, and Chase setups scoring at least 65 with technical confirmation can
            produce a conditional trigger. Hedged Rally is watch-only. Plans use ATR and ten-session structure; risk wider
            than three ATR is rejected.

            **Forward log.** Scheduled ideas are frozen. A stop and target touched in the same daily bar is scored stop-first.
            The app never places orders and does not provide position sizing.
            """
        )

    st.markdown("#### Immutable scan history")
    st.caption("Use the Saved scan selector in the sidebar to revisit any frozen after-close snapshot.")
    history = pd.DataFrame(scan_rows).rename(
        columns={
            "id": "Scan",
            "as_of": "Market session",
            "scan_type": "Run type",
            "status": "Data status",
            "provider": "Source",
            "completed_at": "Completed at",
        }
    )
    st.dataframe(history, hide_index=True, width="stretch")
    st.download_button(
        "Download selected scan JSON",
        json.dumps(scan.to_dict(), indent=2, sort_keys=True),
        file_name=f"folioshift-scan-{scan.id}.json",
        mime="application/json",
    )
