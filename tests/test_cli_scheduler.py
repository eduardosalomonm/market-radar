import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
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
        self.assertEqual(call.call_args.kwargs["cwd"].name, "market-radar")
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
