import os
import tempfile
import unittest
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest
from test_cli_scheduler import UNIVERSE_CSV

from market_radar.cli import main
from market_radar.repository import Repository


class DashboardTest(unittest.TestCase):
    def setUp(self):
        st.cache_resource.clear()
        st.cache_data.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "radar.db"
        self.universe = self.root / "universe.csv"
        self.catalog = self.root / "symbol_catalog.csv"
        self.universe.write_text(
            UNIVERSE_CSV
            + "PLTR,Palantir Technologies,Information Technology,Application Software,XLK,fixture,2026-08-28\n",
            encoding="utf-8",
        )
        self.catalog.write_text(
            "ticker,name,exchange,sector,industry,sector_etf,aliases,source,as_of\n"
            "PLTR,Palantir Technologies,NASDAQ,Information Technology,Application Software,XLK,Palantir,test,2026-09-01\n"
            "NU,Nu Holdings Ltd.,NYSE,Financials,Financial Services,XLF,Nu Bank;Nubank,test,2026-09-01\n",
            encoding="utf-8",
        )
        main(
            [
                "demo",
                "--database",
                str(self.database),
                "--universe",
                str(self.universe),
                "--as-of",
                "2026-08-28",
            ]
        )
        os.environ["MARKET_RADAR_DATABASE"] = str(self.database)
        os.environ["MARKET_RADAR_UNIVERSE"] = str(self.universe)
        os.environ["MARKET_RADAR_SYMBOL_CATALOG"] = str(self.catalog)

    def tearDown(self):
        os.environ.pop("MARKET_RADAR_DATABASE", None)
        os.environ.pop("MARKET_RADAR_UNIVERSE", None)
        os.environ.pop("MARKET_RADAR_SYMBOL_CATALOG", None)
        os.environ.pop("MARKET_RADAR_PUBLIC_DEMO", None)
        self.temp.cleanup()

    def test_saved_scan_renders_all_dashboard_navigation_views(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.title[0].value, "FolioShift")
        navigation = next(item for item in app.radio if item.label == "Sections")
        self.assertIn("Daily Brief", navigation.options)
        self.assertIn("Global Economy", navigation.options)
        self.assertIn("Trade Ideas", navigation.options)
        self.assertIn("Paper Results", navigation.options)
        self.assertTrue(any("What changed since the prior session" in item.value for item in app.subheader))

        navigation.set_value("3 · Opportunity Map").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any("Market Driver Heatmap" in item.value for item in app.subheader))

        navigation = next(item for item in app.radio if item.label == "Sections")
        navigation.set_value("4 · Trade Ideas").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any("Ranked Ideas" in item.value for item in app.subheader))
        self.assertTrue(any("conditional research plans" in item.value for item in app.info))

        navigation = next(item for item in app.radio if item.label == "Sections")
        navigation.set_value("2 · Global Macro").run()

        self.assertEqual(app.exception, [])
        rendered_text = " ".join(item.value for item in app.markdown)
        self.assertIn("Market-implied world economy", rendered_text)

    def test_primary_navigation_is_in_main_content_for_mobile_access(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        popover = app.get("popover")[0]
        self.assertEqual(popover.proto.popover.label, "Menu")
        navigation = next(item for item in app.radio if item.label == "Sections")
        self.assertIn("Daily Brief", navigation.options)
        self.assertIn("Stock Explorer", navigation.options)
        self.assertIn("My Portfolio", navigation.options)

        navigation.set_value("5 · Stock Explorer").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any(item.label == "Latest saved price" for item in app.metric))

    def test_opportunity_map_explains_axes_quadrants_and_signal_strength(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("3 · Opportunity Map").run()

        rendered_text = " ".join(
            item.value for group in (app.markdown, app.caption, app.info) for item in group
        )
        self.assertIn("Each dot is one stock", rendered_text)
        self.assertIn("The cross at zero is deliberate", rendered_text)
        self.assertIn("not a return percentage", rendered_text)

    def test_watchlist_has_a_plain_search_box_with_short_ranked_company_results(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("6 · Watchlist").run()

        self.assertEqual(app.exception, [])
        search = next(item for item in app.text_input if item.label == "Find a company")
        search.set_value("palantir")
        next(item for item in app.button if item.label == "Search").click().run()

        results = next(item for item in app.radio if item.label == "Search results")
        self.assertEqual(results.options, ["Palantir Technologies — PLTR · NASDAQ"])
        results.set_value("Palantir Technologies — PLTR · NASDAQ").run()
        next(item for item in app.button if item.label == "Add to watchlist").click().run()

        self.assertEqual([item.ticker for item in Repository(self.database).list_watchlist()], ["PLTR"])
        rendered_text = " ".join(item.value for item in app.markdown)
        self.assertIn("Daily Pulse", rendered_text)

    def test_watchlist_search_understands_nu_bank_alias(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("6 · Watchlist").run()
        next(item for item in app.text_input if item.label == "Find a company").set_value("Nu Bank")
        next(item for item in app.button if item.label == "Search").click().run()

        results = next(item for item in app.radio if item.label == "Search results")
        self.assertEqual(results.options, ["Nu Holdings Ltd. — NU · NYSE"])

    def test_portfolio_can_search_and_save_a_holding(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("6 · Watchlist").run()
        next(item for item in app.text_input if item.label == "Find a portfolio company").set_value("Palantir")
        next(item for item in app.button if item.label == "Search portfolio companies").click().run()

        results = next(item for item in app.radio if item.label == "Portfolio search results")
        self.assertEqual(results.options, ["Palantir Technologies — PLTR · NASDAQ"])
        next(item for item in app.number_input if item.label == "Shares").set_value(15.0)
        next(item for item in app.number_input if item.label == "Average cost per share (optional)").set_value(70.0)
        next(item for item in app.button if item.label == "Save holding").click().run()

        saved = Repository(self.database).list_positions()
        self.assertEqual(saved[0].ticker, "PLTR")
        self.assertEqual(saved[0].shares, 15.0)

    def test_stock_explorer_shows_the_latest_saved_price_prominently(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("5 · Stock Explorer").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any(item.label == "Latest saved price" for item in app.metric))
        rendered_text = " ".join(item.value for item in app.markdown)
        self.assertIn("At a glance", rendered_text)
        self.assertIn("Price and relative performance", rendered_text)
        self.assertIn("Options and trade-plan context", rendered_text)

    def test_stock_explorer_can_find_palantir_across_all_scanned_stocks(self):
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        next(item for item in app.radio if item.label == "Sections").set_value("5 · Stock Explorer").run()

        universe = next(item for item in app.selectbox if item.label == "Explorer universe")
        self.assertIn("Most traded 100", universe.options)
        self.assertIn("All scanned stocks", universe.options)

        universe.set_value("All scanned stocks").run()
        search = next(item for item in app.text_input if item.label == "Find a scanned company")
        search.set_value("Palantir")
        next(item for item in app.button if item.label == "Search stocks").click().run()
        result = next(item for item in app.radio if item.label == "Matching stocks")
        self.assertIn("Palantir Technologies — PLTR", result.options)

    def test_public_showcase_is_read_only(self):
        os.environ["MARKET_RADAR_PUBLIC_DEMO"] = "1"
        st.cache_resource.clear()
        app_path = Path(__file__).parents[1] / "market_radar" / "dashboard.py"
        app = AppTest.from_file(str(app_path), default_timeout=10).run()

        self.assertEqual(app.exception, [])
        sidebar_buttons = [item.label for item in app.sidebar.button]
        self.assertNotIn("Run demo scan", sidebar_buttons)
        self.assertNotIn("Run live Alpaca scan", sidebar_buttons)

        next(item for item in app.radio if item.label == "Sections").set_value("6 · Watchlist").run()
        next(item for item in app.text_input if item.label == "Find a portfolio company").set_value("Palantir")
        next(item for item in app.button if item.label == "Search portfolio companies").click().run()

        read_only = next(item for item in app.button if item.label == "Public demo · read only")
        self.assertTrue(read_only.disabled)
        self.assertFalse(any(item.label == "Remove from watchlist" for item in app.button))


if __name__ == "__main__":
    unittest.main()
