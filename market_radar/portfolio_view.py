"""Personal portfolio UI. Public portfolios live only in their visitor's session."""

import os
import time
from dataclasses import replace
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from .catalog import search_company_catalog
from .models import CashBalance, PortfolioPosition
from .portfolio_tracker import export_portfolio, import_portfolio, portfolio_report, refresh_prices
from .providers import AlpacaProvider


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
    st.subheader("My Portfolio")
    if public:
        st.info("Your portfolio is separate from other visitors. This guest workspace resets when you reload or leave. Download a backup to restore it later. Saved accounts are not enabled yet.")
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
        st.caption(f"After-close data · last check: {cached.get('checked_at', 'pending')} · IEX US stocks · FX rates entered manually")
    else:
        st.info("Daily market updates are awaiting data-feed setup. Your saved broker values are available below.")
    if cached.get("errors"):
        st.warning("Could not refresh: " + ", ".join(cached["errors"]) + ". Saved references remain available.")
    if cached.get("session"):
        st.caption(f"Daily comparison ends at market session {cached['session']}. This is the latest successfully checked session.")
    if any(p.reference_price is not None and p.reference_price_at is None for p in positions):
        st.warning("Some broker prices have an unknown date. Confirm their date in the holding editor before enabling automatic replacement by market closes.")

    limit = st.slider("Single holding review limit", 10, 60, int(repo.get_setting("position_limit", "25")), 5,
                      help="Your own concentration threshold. This is a review prompt, not an automatic sell instruction.")
    repo.set_setting("position_limit", str(limit))
    report = portfolio_report(positions, cash, currency, cached, limit / 100)
    columns = st.columns(3)
    columns[0].metric("Portfolio value" if report["complete"] else "Known portfolio value", fmt(report["total"]))
    columns[1].metric("Last session change", fmt(report["daily"]))
    columns[2].metric("Cash", fmt(report["cash"]))
    st.caption(f"Comparable daily prices: {report['daily_coverage']}/{len(positions)} holdings. Daily change holds shares and FX fixed; deposits, trades, dividends and fees are excluded.")
    if positions:
        st.write(f"Your three largest holdings account for **{report['top_three']:.1%}** of known value.")
        st.markdown("#### Your portfolio review")
        for action in report["actions"]:
            with st.container(border=True):
                st.markdown(f"**{action['title']}**")
                st.write(action["why"])
                st.write(action["action"])
                if action["scenario"]:
                    st.caption(action["scenario"])
        st.caption("Scenarios use saved values and assume no fees or taxes. They help you review risk; they do not predict returns.")
        st.markdown("#### Holdings")
        for row in report["rows"]:
            with st.expander(f"{row['ticker']} · {row['name']} · {fmt(row['value'])} · {row['weight']:.1%}"):
                st.write(f"{row['shares']:g} shares · {row['currency']} {row['price'] if row['price'] is not None else 'unavailable'}")
                st.caption(f"{row['source']} · price date: {row['as_of'] or 'unknown — confirm before updating'}")
                st.write(f"Last session contribution: {fmt(row['daily_change'])}")
                st.write(row["thesis"] or "Add your investment thesis below.")
        valued = [r for r in report["rows"] if r["value"] is not None]
        if valued:
            frame = pd.DataFrame(valued)
            chart = px.bar(frame, x="value", y="ticker", orientation="h", labels={"value": currency, "ticker": "Holding"})
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
    with st.expander("Import or back up your portfolio"):
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
