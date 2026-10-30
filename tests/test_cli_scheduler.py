import io
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from market_radar.cli import main
from market_radar.providers import DemoProvider
from market_radar.repository import Repository
from market_radar.scheduler import scheduler_tick
from market_radar.universe import load_universe

UNIVERSE_CSV = """ticker,name,sector,industry,sector_etf,source,as_of
AAA,Alpha,Technology,Application Software,XLK,fixture,2026-08-28
BBB,Beta,Technology,Semiconductors,XLK,fixture,2026-08-28
CCC,Gamma,Technology,Technology Hardware,XLK,fixture,2026-08-28
"""


class CliSchedulerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "radar.db"
        self.universe_path = self.root / "universe.csv"
        self.universe_path.write_text(UNIVERSE_CSV, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_demo_command_creates_a_saved_scan_and_prints_summary(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "demo",
                    "--database",
                    str(self.database),
                    "--universe",
                    str(self.universe_path),
                    "--as-of",
                    "2026-08-28",
                ]
            )

        repository = Repository(self.database)
        saved = repository.latest_scan()
        self.assertEqual(exit_code, 0)
        self.assertEqual(saved.as_of, date(2026, 8, 28))
        self.assertEqual(saved.provider, "demo")
        self.assertIn("Saved demo scan", output.getvalue())

    def test_scheduler_runs_once_after_close_and_reuses_the_same_session(self):
        repository = Repository(self.database)
        universe = load_universe(self.universe_path, [])
        provider = DemoProvider()
        now = datetime(2026, 8, 28, 17, 30, tzinfo=ZoneInfo("America/New_York"))

        first = scheduler_tick(provider, repository, universe, now)
        second = scheduler_tick(provider, repository, universe, now)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(repository.list_scans()), 1)
        self.assertEqual(repository.latest_scan().scan_type, "scheduled")

    def test_scheduler_catches_up_the_previous_session_before_today_is_complete(self):
        repository = Repository(self.database)
        universe = load_universe(self.universe_path, [])
        before_cutoff = datetime(2026, 8, 28, 16, 45, tzinfo=ZoneInfo("America/New_York"))

        result = scheduler_tick(DemoProvider(), repository, universe, before_cutoff)

        self.assertIsNotNone(result)
        self.assertEqual(repository.latest_scan().as_of, date(2026, 8, 27))

    def test_scheduler_does_not_freeze_a_scan_whose_option_trades_belong_to_a_later_day(self):
        class NextDayOptions(DemoProvider):
            # Latest-only snapshot fetched after the next open: every trade is a day newer than the session.
            def get_option_chain(self, symbol, as_of):
                return [replace(c, trade_timestamp=c.trade_timestamp + timedelta(days=1))
                        for c in super().get_option_chain(symbol, as_of)]

        repository = Repository(self.database)
        universe = load_universe(self.universe_path, [])
        next_morning = datetime(2026, 8, 28, 10, 30, tzinfo=ZoneInfo("America/New_York"))

        with redirect_stdout(io.StringIO()) as output:
            result = scheduler_tick(NextDayOptions(), repository, universe, next_morning)

        self.assertIsNone(result)
        self.assertEqual(repository.list_scans(), [])
        self.assertIn("Skipped scheduled scan for 2026-08-27", output.getvalue())

    def test_scheduled_scans_keep_charts_only_for_recent_sessions(self):
        repository = Repository(self.database)
        universe = load_universe(self.universe_path, [])
        for day in range(24, 29):
            scheduler_tick(DemoProvider(), repository, universe, datetime(2026, 8, day, 17, 30, tzinfo=ZoneInfo("America/New_York")))
        scans = repository.list_scans()
        before = repository.get_scan(scans[-1]["id"])
        for key in ("demo:daily-bars:old", "demo:option-chain:old", "portfolio-options:old", "portfolio_closes"):
            repository.cache_put(key, {"kept": False})
        with repository._connect() as db:
            db.execute("UPDATE raw_cache SET fetched_at = '2026-01-01T00:00:00'")

        repository.prune_history(keep_chart_scans=2)

        newest, oldest = repository.get_scan(scans[0]["id"]), repository.get_scan(scans[-1]["id"])
        self.assertEqual(len(repository.list_scans()), 5)
        self.assertTrue(newest.signals[0].price_history)
        self.assertEqual(oldest.signals[0].price_history, [])
        self.assertEqual(oldest.signals[0].relative_history, [])
        self.assertEqual([s.evidence_score for s in oldest.signals], [s.evidence_score for s in before.signals])
        self.assertEqual(oldest.ideas, before.ideas)
        for key in ("demo:daily-bars:old", "demo:option-chain:old", "portfolio-options:old"):
            self.assertIsNone(repository.cache_get(key))
        self.assertEqual(repository.cache_get("portfolio_closes"), {"kept": False})

    def test_scheduler_resolves_a_fresh_followed_universe_at_scan_time(self):
        repository = Repository(self.database)
        calls = []

        def universe_loader():
            calls.append(True)
            return load_universe(self.universe_path, [])

        result = scheduler_tick(
            DemoProvider(),
            repository,
            universe_loader,
            datetime(2026, 8, 28, 17, 30, tzinfo=ZoneInfo("America/New_York")),
        )

        self.assertIsNotNone(result)
        self.assertEqual(calls, [True])

    def test_serve_uses_the_documented_port_and_project_streamlit_config(self):
        with patch("market_radar.cli.subprocess.call", return_value=0) as call:
            exit_code = main(
                [
                    "serve",
                    "--database",
                    str(self.database),
                    "--universe",
                    str(self.universe_path),
                    "--port",
                    "8502",
                ]
            )

        command = call.call_args.args[0]
        self.assertEqual(exit_code, 0)
        self.assertTrue((call.call_args.kwargs["cwd"] / ".streamlit" / "config.toml").is_file())
        self.assertIn("--server.port", command)
        self.assertEqual(command[command.index("--server.port") + 1], "8502")
        self.assertEqual(call.call_args.kwargs["env"]["MARKET_RADAR_DATABASE"], str(self.database.resolve()))
        self.assertEqual(call.call_args.kwargs["env"]["MARKET_RADAR_UNIVERSE"], str(self.universe_path.resolve()))

    def test_bootstrap_creates_demo_data_once_for_first_launch(self):
        first = main(
            [
                "bootstrap",
                "--database",
                str(self.database),
                "--universe",
                str(self.universe_path),
                "--as-of",
                "2026-08-28",
            ]
        )
        second = main(
            [
                "bootstrap",
                "--database",
                str(self.database),
                "--universe",
                str(self.universe_path),
                "--as-of",
                "2026-08-28",
            ]
        )

        self.assertEqual((first, second), (0, 0))
        self.assertEqual(len(Repository(self.database).list_scans()), 1)


if __name__ == "__main__":
    unittest.main()
