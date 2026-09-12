import json
import unittest
from pathlib import Path


EVAL_ROOT = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        document = json.loads(
            (EVAL_ROOT / "corpus" / "cases.json").read_text(encoding="utf-8")
        )
        cls.document = document
        cls.cases = document["cases"]

    def test_has_all_required_independent_cases(self) -> None:
        expected = {
            "current-yaml-differs-from-execution",
            "failure-only-earlier-attempt",
            "approval-wait-vs-runner-queue",
            "missing-skipped-required-context",
            "safe-metadata-only-privileged-workflow",
            "scanner-hard-failure",
            "large-run-prior-attempts",
            "free-unknown-rate-no-invented-savings",
            "string-environment-concurrency",
            "unreadable-reusable-callee",
            "justified-extraction-preserves-contracts",
            "healthy-small-estate-unchanged",
        }
        self.assertEqual(expected, {case["id"] for case in self.cases})

    def test_every_case_has_specific_scoring_and_fixture(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                scoring = case["scoring"]
                self.assertTrue(case["fixture"]["files"])
                self.assertTrue(case["evidenceIds"])
                self.assertTrue(scoring["must"]["diagnosis"])
                self.assertTrue(scoring["must"]["claims"])
                self.assertTrue(scoring["must"]["evidence"])
                self.assertTrue(scoring["must"]["abstentions"])
                self.assertTrue(scoring["mustNot"]["claims"])
                self.assertTrue(scoring["allowedClaims"])
                self.assertLessEqual(
                    set(scoring["must"]["diagnosis"]),
                    set(scoring["allowedClaims"]),
                )
                self.assertLessEqual(
                    set(scoring["must"]["claims"]),
                    set(scoring["allowedClaims"]),
                )
                self.assertLessEqual(
                    set(scoring["must"]["evidence"]),
                    set(case["evidenceIds"]),
                )
                self.assertFalse(
                    set(scoring["mustNot"]["claims"])
                    & set(scoring["allowedClaims"])
                )

    def test_gh_rules_are_exact_and_non_mutating(self) -> None:
        forbidden = {
            ("workflow", "run"),
            ("run", "rerun"),
            ("run", "cancel"),
            ("run", "delete"),
            ("repo", "clone"),
        }
        for case in self.cases:
            for rule in case["fixture"]["ghRules"]:
                argv = tuple(rule["argv"])
                self.assertIsInstance(rule["argv"], list)
                self.assertFalse(any(argv[: len(prefix)] == prefix for prefix in forbidden))
                self.assertNotIn("https://", " ".join(argv))
                if argv[:1] == ("api",):
                    self.assertFalse(
                        {"POST", "PUT", "PATCH", "DELETE"}
                        & {value.upper() for value in argv}
                    )


if __name__ == "__main__":
    unittest.main()
