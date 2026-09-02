import unittest

from test_pipeline import FakeProvider
from test_pipeline import PipelineTest as _PipelineFixture

from market_radar.pipeline import run_scan
from market_radar.presentation import evidence_components, executive_brief, recommendation_reason


class PresentationTest(unittest.TestCase):
    def setUp(self):
        fixture = _PipelineFixture()
        fixture.setUp()
        self.scan = run_scan(FakeProvider(fixture.bars), fixture.universe, fixture.as_of)

    def test_recommendation_reason_names_evidence_and_conditional_trigger(self):
        idea = self.scan.ideas[0]
        signal = next(item for item in self.scan.signals if item.ticker == idea.ticker)

        reason = recommendation_reason(signal, idea)

        self.assertIn("options pressure", reason.lower())
        self.assertIn("activates only", reason.lower())
        self.assertIn(f"${idea.trigger:,.2f}", reason)

    def test_evidence_components_reproduce_the_saved_score(self):
        signal = next(item for item in self.scan.signals if item.evidence_score is not None)

        components = evidence_components(signal)

        self.assertAlmostEqual(sum(item["Score points"] for item in components), signal.evidence_score, places=1)

    def test_executive_brief_connects_market_context_to_qualified_ideas(self):
        brief = executive_brief(self.scan)

        self.assertEqual(brief["idea_count"], len(self.scan.ideas))
        self.assertIn("conditional ideas qualified", brief["takeaways"][1])
        self.assertTrue(brief["risks"])


if __name__ == "__main__":
    unittest.main()
