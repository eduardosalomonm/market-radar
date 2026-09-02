import json
import unittest
from types import SimpleNamespace

from test_pipeline import FakeProvider
from test_pipeline import PipelineTest as _PipelineFixture

from market_radar.ai import generate_daily_brief
from market_radar.pipeline import run_scan


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "headline": "Technology leads while options pressure confirms selected names",
                    "summary": "The saved evidence favors selective momentum rather than broad exposure.",
                    "leaders": ["AAA"],
                    "risks": ["Indicative quotes are delayed and modified."],
                }
            )
        )


class AiBriefTest(unittest.TestCase):
    def setUp(self):
        fixture = _PipelineFixture()
        fixture.setUp()
        self.scan = run_scan(FakeProvider(fixture.bars), fixture.universe, fixture.as_of)

    def test_missing_ai_configuration_returns_deterministic_brief(self):
        brief = generate_daily_brief(self.scan)

        self.assertEqual(brief["source"], "deterministic")
        self.assertIn(self.scan.market_regime["label"], brief["headline"])
        self.assertTrue(brief["risks"])

    def test_ai_receives_only_saved_evidence_and_cannot_change_the_scan(self):
        responses = FakeResponses()
        client = SimpleNamespace(responses=responses)
        before = self.scan.to_dict()

        brief = generate_daily_brief(self.scan, client=client, model="test-model")

        self.assertEqual(brief["source"], "openai")
        self.assertEqual(self.scan.to_dict(), before)
        self.assertFalse(responses.kwargs["store"])
        self.assertEqual(responses.kwargs["tool_choice"], "none")
        self.assertEqual(responses.kwargs["text"]["format"]["type"], "json_schema")
        payload = json.loads(responses.kwargs["input"])
        self.assertEqual(payload["as_of"], self.scan.as_of.isoformat())
        self.assertNotIn("api_key", payload)

    def test_invalid_ai_output_falls_back_without_breaking_the_dashboard(self):
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text="not json")))

        brief = generate_daily_brief(self.scan, client=client)

        self.assertEqual(brief["source"], "deterministic")
        self.assertIn("AI brief unavailable", brief["risks"][-1])


if __name__ == "__main__":
    unittest.main()
