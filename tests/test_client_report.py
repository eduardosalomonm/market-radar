import unittest

from test_pipeline import FakeProvider
from test_pipeline import PipelineTest as _PipelineFixture

from market_radar.client_report import build_client_brief_pdf
from market_radar.daily_intelligence import build_daily_intelligence
from market_radar.pipeline import run_scan


class ClientReportTest(unittest.TestCase):
    def test_client_brief_is_a_nontrivial_pdf_with_saved_scan_content(self):
        fixture = _PipelineFixture()
        fixture.setUp()
        scan = run_scan(FakeProvider(fixture.bars), fixture.universe, fixture.as_of)
        intelligence = build_daily_intelligence(scan, None, ["AAA"])

        report = build_client_brief_pdf(scan, intelligence, [])

        self.assertTrue(report.startswith(b"%PDF"))
        self.assertGreater(len(report), 3_000)
        self.assertIn(b"Market Radar Client Brief", report)


if __name__ == "__main__":
    unittest.main()
