import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from test_pipeline import FakeProvider
from test_pipeline import PipelineTest as _PipelineFixture

from market_radar.exports import export_ideas_csv, export_outcomes_json
from market_radar.models import CashBalance, IdeaOutcome, PortfolioPosition, UniverseMember
from market_radar.pipeline import run_scan
from market_radar.repository import Repository


class RepositoryTest(unittest.TestCase):
    def test_portfolio_accepts_utc_z_timestamps(self):
        self.repository.upsert_position(PortfolioPosition("AAA", "Alpha", "Technology", "XLK", 1, 100))
        with self.repository._connect() as connection:
            connection.execute("UPDATE portfolio_positions SET updated_at = '2026-09-05T10:01:23Z'")
        self.assertEqual(self.repository.list_positions()[0].updated_at.utcoffset(), timedelta(0))

    def test_closed_outcome_cannot_be_rewritten_by_later_evaluation(self):
        saved = self.repository.get_scan(self.repository.save_scan(self.result))
        idea = saved.ideas[0]
        original = IdeaOutcome(idea.ticker, "stopped", -1.0, self.as_of, self.as_of, 1, idea.id)
        self.repository.save_outcome(original)
        self.repository.save_outcome(replace(original, status="target_2r", result_r=2.0))
        self.assertEqual(self.repository.list_outcomes(), [original])

    def test_nonfinite_position_values_are_rejected(self):
        position = PortfolioPosition("AAA", "Alpha", "Technology", "XLK", 1, 100)
        for invalid in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                self.repository.upsert_position(replace(position, shares=invalid))
            with self.assertRaises(ValueError):
                self.repository.upsert_position(replace(position, average_cost=invalid))
            with self.assertRaises(ValueError):
                self.repository.upsert_position(replace(position, fx_to_base=invalid))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repository = Repository(Path(self.temp.name) / "radar.db")
        fixture = _PipelineFixture()
        fixture.setUp()
        self.as_of = fixture.as_of
        self.result = run_scan(FakeProvider(fixture.bars), fixture.universe, fixture.as_of, scan_type="scheduled")

    def tearDown(self):
        self.temp.cleanup()

    def test_saved_scan_round_trips_signals_ideas_and_source_metadata(self):
        scan_id = self.repository.save_scan(self.result)

        saved = self.repository.get_scan(scan_id)

        self.assertEqual(saved.id, scan_id)
        self.assertEqual(saved.as_of, self.as_of)
        self.assertEqual(saved.option_feed, "indicative")
        self.assertEqual(len(saved.signals), 3)
        self.assertEqual([idea.ticker for idea in saved.ideas], [idea.ticker for idea in self.result.ideas])
        self.assertEqual(saved.signals[0].to_dict(), self.result.signals[0].to_dict())

    def test_second_scheduled_scan_for_same_session_reuses_existing_record(self):
        first_id = self.repository.save_scan(self.result)
        second = replace(self.result, completed_at=self.result.completed_at)

        second_id = self.repository.save_scan(second)

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(self.repository.list_scans()), 1)
        self.assertTrue(self.repository.scheduled_scan_exists(self.as_of))

    def test_manual_scans_for_same_session_remain_separate(self):
        manual = replace(self.result, scan_type="manual")

        first_id = self.repository.save_scan(manual)
        second_id = self.repository.save_scan(manual)

        self.assertNotEqual(first_id, second_id)

    def test_previous_scan_uses_an_earlier_session_from_the_same_provider(self):
        older = replace(
            self.result,
            as_of=self.as_of - timedelta(days=1),
            scan_type="manual",
        )
        current = replace(self.result, scan_type="manual")
        older_id = self.repository.save_scan(older)
        current_id = self.repository.save_scan(current)

        previous = self.repository.previous_scan(current_id)

        self.assertEqual(previous.id, older_id)
        self.assertEqual(self.repository.latest_scan().id, current_id)

    def test_watchlist_is_editable_through_repository_interface(self):
        member = UniverseMember(
            "NVDA",
            "NVIDIA",
            "Technology",
            "XLK",
            is_watchlist=True,
            industry="Semiconductors",
        )
        self.repository.upsert_watchlist(member)

        self.assertEqual(self.repository.list_watchlist(), [member])

        self.repository.remove_watchlist("NVDA")
        self.assertEqual(self.repository.list_watchlist(), [])

    def test_portfolio_positions_round_trip_and_join_the_followed_universe(self):
        position = PortfolioPosition(
            ticker="PLTR",
            name="Palantir Technologies",
            sector="Information Technology",
            sector_etf="XLK",
            industry="Application Software",
            shares=12.5,
            average_cost=71.2,
            thesis="Durable AI platform adoption",
            quote_currency="USD",
            fx_to_base=0.86,
            reference_price=150.0,
            reference_source="Broker snapshot",
        )

        self.repository.upsert_position(position)

        saved = self.repository.list_positions()[0]
        self.assertEqual(saved.ticker, "PLTR")
        self.assertEqual(saved.shares, 12.5)
        self.assertEqual(saved.average_cost, 71.2)
        self.assertEqual(saved.fx_to_base, 0.86)
        self.assertEqual(saved.reference_price, 150.0)
        self.assertEqual(self.repository.list_followed_members()[0].ticker, "PLTR")

        self.repository.remove_position("PLTR")
        self.assertEqual(self.repository.list_positions(), [])

    def test_portfolio_settings_and_cash_round_trip(self):
        self.repository.set_setting("portfolio_base_currency", "EUR")
        self.repository.upsert_cash_balance(CashBalance("EUR", 125.50))

        self.assertEqual(self.repository.get_setting("portfolio_base_currency", "USD"), "EUR")
        self.assertEqual(self.repository.list_cash_balances()[0].amount, 125.50)

    def test_outcome_and_exports_use_saved_public_records(self):
        scan_id = self.repository.save_scan(self.result)
        saved = self.repository.get_scan(scan_id)
        idea = saved.ideas[0]
        outcome = IdeaOutcome(idea.ticker, "target_1r", 1.0, date(2026, 9, 1), date(2026, 9, 3), 3, idea.id)
        self.repository.save_outcome(outcome)

        outcomes = self.repository.list_outcomes()
        csv_text = export_ideas_csv(saved.ideas)
        json_text = export_outcomes_json(outcomes)

        self.assertIn("ticker,quadrant,direction,evidence_score", csv_text)
        self.assertIn(idea.ticker, csv_text)
        self.assertEqual(json.loads(json_text)[0]["status"], "target_1r")


if __name__ == "__main__":
    unittest.main()
