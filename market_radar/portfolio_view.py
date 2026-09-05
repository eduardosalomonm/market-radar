"""Personal portfolio UI. Public portfolios live only in their visitor's session."""

import json
import os
import time
from dataclasses import replace
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from .catalog import search_company_catalog
from .models import CashBalance, PortfolioPosition
from .portfolio_intelligence import earnings_exposure, market_report, refresh_intelligence
from .portfolio_tracker import export_portfolio, import_portfolio, portfolio_report, refresh_prices
from .providers import AlpacaProvider


def insight_cards(items):
    """Escape user-controlled labels; color supplements, never replaces, text."""
    cards = "".join(
        f'<article class="folio-kpi {tone}"><div class="folio-label">{escape(label)}</div>'
        f'<strong>{escape(value)}</strong><p>{escape(note)}</p></article>'
        for label, value, note, tone in items
    )
    st.markdown(f'<div class="folio-grid">{cards}</div>', unsafe_allow_html=True)


def render_market_intelligence(repo, report, currency):
    evidence = repo.cache_get("portfolio_market_evidence") or {}
    market = market_report(report, evidence)
    st.markdown("#### What markets say about your portfolio")
    st.caption("Market evidence—not an expected-growth forecast. Requires real data and valuation dates matching the evidence session.")
    option_leader = market["options"][0] if market["options"] else None
    risk_leader = market["risk"][0] if market["risk"] else None
    skew_rows = [r for r in market["options"] if r["skew_points"] is not None]
    skew_leader = max(skew_rows, key=lambda r: r["skew_points"]) if skew_rows else None
    try:
        records = json.loads(repo.get_setting("earnings_calendar", "[]"))
    except (ValueError, TypeError):
        records = []
    events = earnings_exposure(report["rows"], records, datetime.now().date())
    with st.expander("Market signals" if evidence else "Market signals · connect a data feed", expanded=bool(evidence)):
        insight_cards([
        ("Biggest risk contributor", risk_leader["ticker"] if risk_leader else "Unavailable",
         f"{risk_leader['risk_share']:.0%} of modeled variance · {risk_leader['capital_weight']:.0%} of capital" if risk_leader else "Needs aligned history for every holding", "amber"),
        ("Trend breadth · EMA50", f"{market['trend_breadth']:.0%}" if market["trend_breadth"] is not None else "Unavailable",
         f"Above 50-day trend · covered value {market['history_coverage']:.0%}", "teal"),
        ("Largest options-priced move", f"{currency} ±{option_leader['movement_value']:,.0f}" if option_leader else "Unavailable",
         f"{option_leader['ticker']} · 30 days · ±{option_leader['move_pct']:.1f}% stock move" if option_leader else "Needs liquid IV around the 30-day horizon", "blue"),
        ("Highest protection premium", f"{skew_leader['skew_points']:+.1f} vol pts" if skew_leader else "Unavailable",
         f"{skew_leader['ticker']} · 25-delta put IV minus call IV" if skew_leader else "Needs comparable put and call quotes", "purple"),
        ("Earnings · next 30 days", f"{events['weight30']:.0%} of portfolio" if events["coverage"] else "Unavailable",
         f"Verified calendar coverage: {events['coverage']:.0%} · known events only", "amber"),
        ("Portfolio movement · 30 days", f"{currency} ±{market['hybrid_move']:,.0f}" if market["hybrid_move"] is not None else "Unavailable",
         "Hybrid: options IV + historical correlations · fixed FX", "rose"),
        ])
    st.caption(f"Options coverage: {market['option_coverage']:.0%} of portfolio value · session {evidence.get('session', 'not loaded')} · {evidence.get('feed', 'feed not connected')}.")
    if evidence.get("feed") == "indicative":
        st.warning("Indicative options: delayed trades and modified quotes. Movement and protection pricing are approximations, not directional predictions.")
    if evidence.get("errors"):
        st.caption("Refresh incomplete: " + ", ".join(sorted(evidence["errors"])) + ". Previous data is retained; stale inputs are excluded.")
    with st.expander("Holdings evidence & calculation details"):
        st.write("Movement estimates describe uncertainty, not profit odds or guaranteed ranges. Standalone stock moves cannot be added to estimate portfolio movement.")
        st.write("Risk uses up to 252 aligned daily returns (minimum 60), adjusted for corporate actions. Current weights and FX are held fixed; this is not your realized performance. Risk shares can be negative when a holding offsets other risks.")
        st.caption(f"Model: {evidence.get('version', 'portfolio-market-v1')} · aligned observations: {market['observations']} · source: {evidence.get('source', 'none')}")
        if market["options"]:
            st.dataframe(pd.DataFrame(market["options"]), hide_index=True)
        if market["risk"]:
            frame = pd.DataFrame(market["risk"])
            chart = px.bar(frame, x="ticker", y=["capital_weight", "risk_share"], barmode="group",
                           color_discrete_sequence=["#93c5fd", "#fbbf24"])
            chart.update_layout(yaxis_tickformat=".0%", yaxis_title="Share", legend_title="Capital vs modeled risk")
            st.plotly_chart(chart, use_container_width=True)
        if evidence:
            exclusions = [{"ticker": t, "valid_quotes": s.get("options", {}).get("valid", 0),
                           "exclusions": str(s.get("options", {}).get("excluded", {}))}
                          for t, s in evidence.get("symbols", {}).items() if t in {r["ticker"] for r in report["rows"]}]
            st.dataframe(pd.DataFrame(exclusions), hide_index=True)
            st.download_button("Download market evidence", json.dumps(evidence, indent=2), "portfolio-market-evidence.json", "application/json")
    with st.expander("Verified earnings calendar"):
        st.caption("No earnings feed is connected. Import reviewed records with a source URL, verification date and coverage period. Uncovered companies remain unknown.")
        for event in events["events"]:
            st.write(f"{event['ticker']} · {event['date']}")
            st.link_button("Calendar source", event["source"])
        sample = [{"ticker": "AAPL", "earnings_date": None, "verified_on": "YYYY-MM-DD", "coverage_through": "YYYY-MM-DD", "source_url": "https://investor.apple.com/"}]
        st.download_button("Calendar format", json.dumps(sample, indent=2), "earnings-calendar-example.json", "application/json")
        uploaded = st.file_uploader("Reviewed earnings calendar JSON", type=["json"], key="earnings_upload")
        if uploaded and st.button("Save reviewed calendar"):
            try:
                if uploaded.size > 250_000:
                    raise ValueError("Calendar must be under 250 KB")
                data = json.loads(uploaded.getvalue())
                if not isinstance(data, list) or len(data) > 100 or not all(isinstance(i, dict) for i in data):
                    raise ValueError("Use a list of up to 100 company records")
                for item in data:
                    if not isinstance(item.get("ticker"), str) or not item.get("source_url", "").startswith("https://"):
                        raise ValueError("Each company needs a ticker and HTTPS source")
                    for key in ("verified_on", "coverage_through", "earnings_date"):
                        if key != "earnings_date" or item.get(key):
                            datetime.strptime(item[key], "%Y-%m-%d")
                repo.set_setting("earnings_calendar", json.dumps(data))
                st.rerun()
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                st.error(f"Calendar not saved: {exc}")


class SessionPortfolio:
    """No global cache, shared database, URL token or cross-session lookup."""

    def __init__(self, state):
        self.state = state
        self.state.setdefault("visitor_portfolio", {"positions": [], "cash": [], "currency": "EUR", "cache": {}})

    @property
    def data(self):
        return self.state["visitor_portfolio"]

    def list_positions(self):
        return list(self.data["positions"])

    def list_cash_balances(self):
        return list(self.data["cash"])

    def get_setting(self, key, default):
        return self.data.get(key, self.data["currency"] if key == "portfolio_base_currency" else default)

    def set_setting(self, key, value):
        self.data[key] = value

    def upsert_position(self, position):
        self.data["positions"] = [p for p in self.list_positions() if p.ticker != position.ticker] + [position]

    def remove_position(self, ticker):
        self.data["positions"] = [p for p in self.list_positions() if p.ticker != ticker]

    def upsert_cash_balance(self, balance):
        self.data["cash"] = [c for c in self.list_cash_balances() if c.currency != balance.currency] + [balance]

    def cache_get(self, key):
        return self.data["cache"].get(key)

    def cache_put(self, key, value):
        self.data["cache"][key] = value


def credential(key):
    value = os.getenv(key)
    if value:
        return value
    try:
        return st.secrets.get(key)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return None


@st.fragment(run_every="15m")
def render_portfolio(repository, catalog, public=False):
    repo = SessionPortfolio(st.session_state) if public else repository
    positions, cash = repo.list_positions(), repo.list_cash_balances()
    currency = repo.get_setting("portfolio_base_currency", "USD")
    def fmt(value):
        return f"{currency} {value:,.2f}" if value is not None else "Unavailable"
    st.markdown("#### Privacy & prices")
    if public:
        st.info("Private guest session · Not saved after reload. Download a backup before leaving. Accounts are not enabled yet.")
    else:
        st.caption("Your holdings are saved on this computer. Values below use broker references or real completed market closes.")

    configured = bool(credential("ALPACA_API_KEY_ID") and credential("ALPACA_API_SECRET_KEY"))
    public_feed = credential("MARKET_RADAR_PUBLIC_DATA_LICENSED") == "1"
    can_refresh = configured and (not public or public_feed)
    cached = repo.cache_get("portfolio_closes") or {}
    if can_refresh and positions:
        last_attempt = st.session_state.get("portfolio_refresh_attempt", 0)
        if time.time() - last_attempt > 900:
            st.session_state["portfolio_refresh_attempt"] = time.time()
            try:
                with st.spinner("Checking the latest completed market session…"):
                    cached = refresh_prices(AlpacaProvider(credential("ALPACA_API_KEY_ID"), credential("ALPACA_API_SECRET_KEY")), repo, positions)
            except Exception:
                st.warning("Market refresh is unavailable. Your last saved prices are still available.")
            try:
                with st.spinner("Updating portfolio market evidence…"):
                    refresh_intelligence(AlpacaProvider(credential("ALPACA_API_KEY_ID"), credential("ALPACA_API_SECRET_KEY")), repo, positions)
            except Exception:
                st.warning("Market evidence refresh unavailable. Last saved evidence is retained.")
        st.caption(f"After-close data · last check: {cached.get('checked_at', 'pending')} · IEX US stocks · FX rates entered manually")
    else:
        st.info("Daily market updates are awaiting data-feed setup. Your saved broker values are available below.")
    if cached.get("errors"):
        st.warning("Could not refresh: " + ", ".join(cached["errors"]) + ". Saved references remain available.")
    if cached.get("session"):
        st.caption(f"Daily comparison ends at market session {cached['session']}. This is the latest successfully checked session.")
    if any(p.reference_price is not None and p.reference_price_at is None for p in positions):
        st.warning("Some broker prices have an unknown date. Confirm their date in the holding editor before enabling automatic replacement by market closes.")

    with st.expander("Review settings"):
        limit = st.slider("Single holding review limit", 10, 60, int(repo.get_setting("position_limit", "25")), 5,
                          help="Your concentration threshold—not an automatic sell instruction.")
    repo.set_setting("position_limit", str(limit))
    report = portfolio_report(positions, cash, currency, cached, limit / 100)
    st.markdown("#### At a glance")
    if not positions:
        st.info("Start with one holding: search a company below, enter your shares, then save. Or restore a portfolio backup.")
    columns = st.columns(3)
    columns[0].metric("Portfolio value" if report["complete"] else "Known portfolio value", fmt(report["total"]))
    columns[1].metric("Last session change", fmt(report["daily"]))
    columns[2].metric("Cash", fmt(report["cash"]))
    st.caption(f"Comparable daily prices: {report['daily_coverage']}/{len(positions)} holdings. Daily change holds shares and FX fixed; deposits, trades, dividends and fees are excluded.")
    if positions:
        d = report["diagnostics"]
        largest = report["rows"][0]
        st.markdown("#### Your risk, in 10 seconds")
        insight_cards([
            ("Largest position", f"{largest['weight']:.1%}", largest["ticker"] + f" · your limit {limit}%", "amber" if d["over_limit"] else "blue"),
            ("Top 3 concentration", f"{report['top_three']:.1%}", "Share of known portfolio value", "purple"),
            ("Effective holdings", f"{d['effective_holdings']:.1f}" if d["effective_holdings"] else "—", f"Across {len(positions)} positions · allocation only", "blue"),
            ("Cash share", f"{d['cash_weight']:.1%}" if d["cash_weight"] is not None else "—", "Uninvested share · not a target", "teal"),
        ])
        st.caption("Effective holdings: the number of equal-sized positions with the same concentration. Excludes cash; does not measure correlation or ETF overlap.")
        st.markdown("#### Quick takeaways")
        pills = [(f"{d['over_limit']} above your position limit", "amber"),
                 (f"{report['daily_coverage']}/{len(positions)} daily prices available", "blue"),
                 ("Complete valuation" if report["complete"] else "Partial valuation", "teal" if report["complete"] else "amber")]
        st.markdown('<div class="folio-pills">' + ''.join(
            f'<span class="{tone}">{escape(label)}</span>' for label, tone in pills) + '</div>', unsafe_allow_html=True)
        if report["complete"] and report["total"] > 0:
            st.markdown("#### What could move your balance?")
            scenarios = [(f"{largest['ticker']} falls 20%", fmt(-d["largest_drop_20"]),
                          f"Portfolio impact: −{d['largest_drop_20'] / report['total']:.1%} · other prices fixed", "rose")]
            if d["usd_drop_10"] is not None:
                scenarios.append((f"USD falls 10% vs {currency}", fmt(-d["usd_drop_10"]), "USD-quoted positions only · stock prices fixed", "purple"))
            insight_cards(scenarios)
            st.caption("Separate hypothetical shocks—not forecasts. No fees, taxes, correlations or ETF look-through included.")
            st.markdown("#### A next step to consider")
            if d["over_limit"]:
                st.write(f"**Review {largest['ticker']} before adding more.** It exceeds your own {limit}% position limit.")
                insight_cards([
                    ("Without selling", fmt(d["new_cash_to_limit"]), f"New money elsewhere to bring {largest['ticker']} to {limit}%", "blue"),
                    ("Reduce the position", fmt(largest["value"] - report["total"] * limit / 100),
                     f"Shift from {largest['ticker']} to cash to reach {limit}% · before tax/fees", "amber"),
                ])
                st.caption("These are arithmetic alternatives, not instructions to invest or sell. Both assume unchanged prices.")
            else:
                st.success("No holding exceeds your chosen limit. Check shared sector exposure and your investment thesis next.")
        with st.expander("More context & review notes"):
            for action in report["actions"]:
                st.markdown(f"**{action['title']}**")
                st.write(action["why"])
                st.write(action["action"])
        render_market_intelligence(repo, report, currency)
        st.markdown("#### Allocation map")
        valued = [r for r in report["rows"] if r["value"] is not None and r["value"] > 0]
        if valued:
            allocation = px.treemap(pd.DataFrame(valued), path=["sector", "ticker"], values="value", color="sector",
                                    color_discrete_sequence=["#60a5fa", "#a78bfa", "#2dd4bf", "#fbbf24", "#fb7185", "#38bdf8"])
            allocation.update_layout(height=330, margin=dict(t=5, b=5, l=0, r=0))
            st.plotly_chart(allocation, use_container_width=True, config={"displayModeBar": False})
            st.caption("Box area = position value. Colors = recorded sectors, not risk ratings. ETF underlying holdings are not expanded.")
        st.markdown("#### Holdings")
        for row in report["rows"]:
            with st.expander(f"{row['ticker']} · {row['name']} · {fmt(row['value'])} · {row['weight']:.1%}"):
                st.write(f"{row['shares']:g} shares · {row['currency']} {row['price'] if row['price'] is not None else 'unavailable'}")
                st.caption(f"{row['source']} · price date: {row['as_of'] or 'unknown — confirm before updating'}")
                st.write(f"Last session contribution: {fmt(row['daily_change'])}")
                st.write(row["thesis"] or "Add your investment thesis below.")
        valued = [r for r in report["rows"] if r["value"] is not None]
        if valued:
            st.markdown("#### Where your money is")
            frame = pd.DataFrame(valued)
            chart = px.bar(frame, x="value", y="ticker", color="sector", orientation="h", labels={"value": currency, "ticker": "Holding"},
                           color_discrete_sequence=["#60a5fa", "#a78bfa", "#2dd4bf", "#fbbf24", "#fb7185", "#38bdf8"])
            chart.update_layout(yaxis={"autorange": "reversed"}, height=max(280, 24 * len(frame)))
            st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})
        contributors = [r for r in report["rows"] if r["daily_change"] is not None]
        if contributors:
            st.markdown("#### What moved your portfolio")
            st.dataframe(pd.DataFrame(contributors)[["ticker", "daily_change", "as_of"]], hide_index=True)
        if any("screenshot" in p.reference_source.lower() for p in positions):
            st.caption("Screenshot gain percentages are not a verified purchase cost. Confirm broker cost basis before using gain estimates for a sale or tax decision.")

    with st.expander("Cash and reporting currency"):
        st.caption("Reporting currency is fixed once holdings exist, so saved values cannot silently change currency.")
        with st.form("tracker_cash"):
            selected = st.selectbox("Base currency", ["EUR", "USD", "GBP"], index=["EUR", "USD", "GBP"].index(currency), disabled=bool(positions or cash))
            existing = next((c.amount for c in cash if c.currency == currency), 0.0)
            amount = st.number_input(f"Cash ({currency})", min_value=0.0, value=float(existing))
            if st.form_submit_button("Save cash"):
                repo.set_setting("portfolio_base_currency", selected)
                repo.upsert_cash_balance(CashBalance(selected, amount))
                st.rerun()

    st.markdown("#### Add or update a holding")
    with st.form("tracker_search"):
        query = st.text_input("Find a portfolio company", placeholder="Palantir, Nu Bank, or a ticker")
        st.form_submit_button("Search portfolio companies")
    matches = search_company_catalog(catalog, query, limit=8)
    choices = {f"{p.name} — {p.ticker}": p for p in positions}
    choices.update({f"{m.name} — {m.ticker} · {m.exchange}": m for m in matches})
    selected = st.selectbox("Edit a holding", [""] + list(choices))
    if query and matches:
        label = st.radio("Portfolio search results", [f"{m.name} — {m.ticker} · {m.exchange}" for m in matches])
        entry = choices[label]
    else:
        entry = choices.get(selected)
    if entry:
        existing = next((p for p in positions if p.ticker == entry.ticker), None)
        with st.form("tracker_editor"):
            st.write(f"{entry.name} ({entry.ticker})")
            shares = st.number_input("Shares", min_value=0.000001, value=float(existing.shares) if existing else 1.0)
            cost = st.number_input("Average cost per share (optional)", min_value=0.0, value=float(existing.average_cost or 0) if existing else 0.0)
            quote_currency = st.selectbox("Quote currency", ["USD", "EUR", "GBP"], index=["USD", "EUR", "GBP"].index(existing.quote_currency) if existing else 0)
            rate = st.number_input(f"FX: base currency per unit of quote currency ({currency})", min_value=0.000001, value=float(existing.fx_to_base) if existing else 1.0, format="%.6f")
            reference = st.number_input("Broker price (optional)", min_value=0.0, value=float(existing.reference_price or 0) if existing else 0.0)
            reference_date = st.date_input("Broker price date (leave blank if unknown)", value=existing.reference_price_at.date() if existing and existing.reference_price_at else None)
            thesis = st.text_input("Why do you own it? (optional)", value=existing.thesis if existing else "")
            if st.form_submit_button("Save holding", type="primary"):
                p = PortfolioPosition(entry.ticker, entry.name, entry.sector, entry.sector_etf, shares, cost or None, entry.industry,
                                      thesis=thesis, quote_currency=quote_currency, fx_to_base=rate,
                                      reference_price=reference or None,
                                      reference_price_at=datetime.combine(reference_date, datetime.min.time()) if reference_date else None,
                                      reference_source="Manual broker reference")
                if existing and (shares, reference, quote_currency) == (existing.shares, existing.reference_price, existing.quote_currency):
                    p = replace(p, reference_value_base=existing.reference_value_base, reference_source=existing.reference_source)
                try:
                    import_portfolio(export_portfolio([p], [], currency))
                    if existing is None and len(positions) >= 100:
                        raise ValueError("Maximum 100 holdings")
                    repo.upsert_position(p)
                    st.session_state.pop("portfolio_refresh_attempt", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    st.markdown("#### Backup & restore")
    with st.expander("Import or back up your portfolio", expanded=not positions):
        st.caption("JSON import merges holdings by ticker after validating the full file. Backups contain your financial data; keep them private.")
        st.download_button("Download portfolio backup", export_portfolio(positions, cash, currency), "my-portfolio.json", "application/json")
        sample = PortfolioPosition("AAPL", "Apple", "Information Technology", "XLK", 1, quote_currency=currency)
        st.download_button("Download import example", export_portfolio([sample], [], currency), "portfolio-example.json", "application/json")
        uploaded = st.file_uploader("Import portfolio JSON", type=["json"])
        if uploaded and st.button("Validate and import"):
            try:
                imported, balances, base = import_portfolio(uploaded.getvalue())
                if (positions or cash) and base != currency:
                    raise ValueError("Import must match your current reporting currency")
                if len({p.ticker for p in positions + imported}) > 100:
                    raise ValueError("Maximum 100 holdings")
                for p in imported:
                    repo.upsert_position(p)
                for c in balances:
                    repo.upsert_cash_balance(c)
                repo.set_setting("portfolio_base_currency", base)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if positions:
        with st.expander("Remove a holding"):
            ticker = st.selectbox("Holding to remove", [p.ticker for p in positions])
            if st.button("Remove holding"):
                repo.remove_position(ticker)
                st.rerun()
