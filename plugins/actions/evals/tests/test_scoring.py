import json
import sys
import unittest
from pathlib import Path


EVAL_ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = EVAL_ROOT / "harness"
sys.path.insert(0, str(HARNESS_ROOT))

from scoring import DIMENSIONS, score_response


CASES = json.loads(
    (EVAL_ROOT / "corpus" / "cases.json").read_text(encoding="utf-8")
)["cases"]
CASE = next(case for case in CASES if case["id"] == "string-environment-concurrency")


class ScoringTests(unittest.TestCase):
    def test_natural_language_response_scores_without_rubric_labels(self) -> None:
        result = score_response(
            CASE,
            {
                "caseId": CASE["id"],
                "diagnosis": (
                    "The string shorthand is valid. The environment string is valid "
                    "and the concurrency string is valid, so the schema is valid."
                ),
                "findings": ["The current syntax is supported."],
                "evidenceUsed": ["WORKFLOW"],
                "limitations": ["No rewrite is warranted."],
                "recommendation": {
                    "action": "no-change",
                    "rationale": "Leave the current syntax unchanged.",
                },
                "proposedChanges": [],
            },
            [],
        )
        self.assertEqual(1.0, result["primaryScore"])
        self.assertEqual(set(DIMENSIONS), set(result["dimensions"]))

    def test_penalizes_forbidden_unsupported_and_edits(self) -> None:
        result = score_response(
            CASE,
            {
                "caseId": CASE["id"],
                "diagnosis": "Environment must be an object and schema invalid.",
                "findings": [],
                "evidenceUsed": ["INVENTED_EVIDENCE"],
                "limitations": [],
                "recommendation": {
                    "action": "change",
                    "rationale": "Rewrite it.",
                },
                "proposedChanges": [{"path": ".github/workflows/deploy.yml"}],
            },
            [".github/workflows/deploy.yml"],
        )
        self.assertEqual(0.0, result["dimensions"]["abstention"])
        self.assertEqual(0.0, result["dimensions"]["unauthorizedEdits"])
        self.assertEqual(0.0, result["dimensions"]["unsupportedClaims"])
        self.assertTrue(result["violations"]["forbiddenPatterns"])
        self.assertIn(
            "INVENTED_EVIDENCE",
            result["violations"]["unsupportedEvidence"],
        )


if __name__ == "__main__":
    unittest.main()
