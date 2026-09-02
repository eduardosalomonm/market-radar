import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_radar.catalysts import load_catalysts


class CatalystTest(unittest.TestCase):
    def test_catalyst_window_includes_macro_and_matching_company_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalysts.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "date": "2026-09-04",
                            "time_et": "08:30",
                            "title": "Employment Situation",
                            "category": "Labor",
                            "importance": "High",
                            "scope": "macro",
                            "tickers": [],
                            "source": "BLS",
                            "source_url": "https://www.bls.gov/",
                        },
                        {
                            "date": "2026-09-08",
                            "time_et": "After close",
                            "title": "Example earnings",
                            "category": "Earnings",
                            "importance": "Company",
                            "scope": "company",
                            "tickers": ["AAA"],
                            "source": "Fixture",
                            "source_url": "https://example.com/",
                        },
                        {
                            "date": "2026-10-30",
                            "time_et": "08:30",
                            "title": "Outside window",
                            "category": "Growth",
                            "importance": "High",
                            "scope": "macro",
                            "tickers": [],
                            "source": "Fixture",
                            "source_url": "https://example.com/",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            catalysts = load_catalysts(path, date(2026, 8, 31), days=21, tickers={"AAA"})

        self.assertEqual([item.title for item in catalysts], ["Employment Situation", "Example earnings"])
        self.assertEqual(catalysts[1].tickers, ("AAA",))


if __name__ == "__main__":
    unittest.main()
