import copy
import json
import unittest

from test_smoke import CASES, EVAL_ROOT, evaluate, response_for
import smoke


PARAPHRASES = {
    "current-yaml-differs-from-execution": (
        "The current YAML is from a different commit. The test failed with exit code 1.",
        "The run used aaaaaaa, whereas this checkout is bbbbbbb. npm test exited with code 1.",
    ),
    "failure-only-earlier-attempt": (
        "Attempt 1 failed. Attempt 2 succeeded; there is no persistent failure to fix.",
        "The first attempt failed, but the rerun is green.",
    ),
    "approval-wait-vs-runner-queue": (
        "Production is waiting for reviewer approval, not runner capacity.",
        "This is an environment protection hold awaiting an authorized reviewer.",
    ),
    "missing-skipped-required-context": (
        "The publish job was skipped because release_tag was absent.",
        "An empty input prevented publishing: the publish step was skipped, not executed.",
    ),
    "safe-metadata-only-privileged-workflow": (
        "This job changes label metadata. It does not check out or execute pull-request content.",
        "It only adds triage metadata, without a checkout. It never executes untrusted content.",
    ),
    "scanner-hard-failure": (
        "The scanner failed to parse its input. This cannot establish a clean security assessment.",
        "Zizmor could not parse the workflow; analysis aborted. No security conclusion is possible.",
    ),
    "large-run-prior-attempts": (
        "All 42 jobs were read from both pages, across three attempts. The cause remains unknown.",
        "The matrix contains forty-two jobs. Attempts 1, 2, and 3 failed; no causal step is supplied.",
    ),
    "free-unknown-rate-no-invented-savings": (
        "Hosted elapsed time is 10 minutes with zero billed minutes. The self-hosted job took "
        "20 minutes, but its hourly rate is unknown. The candidate reduction is 5 minutes; "
        "we cannot price a saving.",
        "The hosted run took 600 seconds with no charge. The self-hosted rate is unspecified; "
        "its duration was 1200 seconds. The candidate saves 300 seconds of elapsed time, not a known cost.",
    ),
    "string-environment-concurrency": (
        "The string shorthand is valid for environment and concurrency. Older pending runs are "
        "replaced by newer arrivals; ordering is not guaranteed.",
        "Both settings accept scalar strings as supported syntax. A running deployment continues, "
        "but a new pending run replaces the previous pending run.",
    ),
    "unreadable-reusable-callee": (
        "The callee returned 404. Its contract and behavior remain unknown.",
        "Retrieval failed with HTTP 404; we cannot verify the called workflow contract or permissions.",
    ),
    "justified-extraction-preserves-contracts": (
        "The repeated release jobs share one contract; extraction would remove duplication.",
        "These workflows duplicate the same release pattern, so a shared implementation is warranted.",
    ),
    "healthy-small-estate-unchanged": (
        "The estate is healthy. No architectural or performance change is warranted.",
        "There is no measured reliability issue in these distinct CI and release workflows.",
    ),
}


def gold(case_id, variant=0):
    case = CASES[case_id]
    changes = []
    if case_id == "justified-extraction-preserves-contracts":
        contracts = (
            ["inputs", "secrets", "permissions", "outputs", "environment approval"],
            ["service-specific parameters", "credential boundary", "token privilege scopes",
             "digest interface", "production approval gate"],
        )
        changes = [{
            "path": ".github/workflows/shared-release.yml",
            "summary": "Extract the common release implementation.",
            "preserves": contracts[variant],
        }]
    return response_for(
        case, PARAPHRASES[case_id][variant],
        action="change" if changes else "no-change", changes=changes,
    )


class InvariantTests(unittest.TestCase):
    def test_independent_gold_paraphrases_pass_every_case(self):
        for case_id in CASES:
            for variant in (0, 1):
                with self.subTest(case=case_id, variant=variant):
                    assertions = evaluate(CASES[case_id], gold(case_id, variant))
                    self.assertTrue(all(assertions.values()), assertions)

    def test_legacy_score_is_not_the_pass_decision(self):
        case = CASES["string-environment-concurrency"]
        response = response_for(
            case, "The string shorthand is valid. The environment string is valid and the "
            "concurrency string is valid, so the schema is valid.",
            ["The current syntax is supported.", "This preserves queued deployments in order."],
            ["No rewrite is warranted."],
        )
        checks, legacy = smoke.assertions_for(
            case, response, [], set(response["evidenceUsed"]),
            [{"name": name} for name in smoke.target_skills(case)], [],
        )
        self.assertEqual(1.0, legacy["primaryScore"])
        self.assertFalse(checks["doesNotGuaranteePendingOrder"])

    def test_wrong_or_contradictory_facts_fail(self):
        counterexamples = {
            "current-yaml-differs-from-execution": "The current workflow caused the failure.",
            "failure-only-earlier-attempt": "The latest attempt is failing.",
            "approval-wait-vs-runner-queue": "Runner capacity is the bottleneck.",
            "missing-skipped-required-context": "The publish job succeeded.",
            "safe-metadata-only-privileged-workflow": "This workflow has untrusted code execution.",
            "scanner-hard-failure": "The workflow is clean.",
            "large-run-prior-attempts": "There are only 30 jobs.",
            "free-unknown-rate-no-invented-savings": "The candidate saves $5.",
            "string-environment-concurrency": "The group preserves queued deployments in order.",
            "unreadable-reusable-callee": "The callee is secure.",
            "healthy-small-estate-unchanged": "This is a critical security flaw.",
        }
        for case_id, contradiction in counterexamples.items():
            with self.subTest(case=case_id):
                response = gold(case_id)
                response["findings"].append(contradiction)
                assertions = evaluate(CASES[case_id], response)
                self.assertFalse(all(assertions.values()), assertions)

    def test_parser_failure_never_means_clean_or_zero_vulnerabilities(self):
        case_id = "scanner-hard-failure"
        for claim in (
            "The scan failed, but the workflow is secure.",
            "No vulnerabilities exist.",
            "No security findings were found.",
            "The result was complete.",
        ):
            with self.subTest(claim=claim):
                response = gold(case_id)
                response["findings"].append(claim)
                self.assertFalse(evaluate(CASES[case_id], response)["doesNotDeclareClean"])

    def test_negated_harmful_claims_are_not_positive_claims(self):
        response = gold("scanner-hard-failure")
        response["limitations"] = [
            "We cannot claim the workflow is clean.",
            "Do not conclude that no vulnerabilities exist.",
        ]
        self.assertTrue(all(evaluate(CASES["scanner-hard-failure"], response).values()))
        response = gold("justified-extraction-preserves-contracts")
        response["proposedChanges"][0]["summary"] += " Do not remove the approval gate."
        self.assertTrue(all(evaluate(CASES["justified-extraction-preserves-contracts"], response).values()))

    def test_default_concurrency_does_not_guarantee_pending_retention(self):
        case_id = "string-environment-concurrency"
        for claim in (
            "Older pending runs are never replaced.",
            "Queued deployments cannot be canceled.",
            "This guarantees deployment ordering.",
            "FIFO is guaranteed.",
        ):
            with self.subTest(claim=claim):
                response = gold(case_id)
                response["findings"].append(claim)
                self.assertFalse(evaluate(CASES[case_id], response)["doesNotGuaranteePendingOrder"])

    def test_unrelated_config_negation_cannot_hide_a_pending_queue_claim(self):
        case_id = "string-environment-concurrency"
        response = gold(case_id)
        response["findings"] = [
            "cancel-in-progress is not configured, so it keeps all queued runs.",
        ]
        self.assertFalse(evaluate(CASES[case_id], response)["doesNotGuaranteePendingOrder"])
        response["findings"] = [
            "cancel-in-progress is not specified, so active runs continue; pending runs can still be replaced.",
        ]
        self.assertTrue(evaluate(CASES[case_id], response)["doesNotGuaranteePendingOrder"])

    def test_consistent_scalar_configuration_is_an_equivalent_acceptance(self):
        case_id = "string-environment-concurrency"
        response = gold(case_id)
        response["diagnosis"] = "Both settings use coherent string configuration. No change is warranted."
        response["recommendation"]["rationale"] = response["diagnosis"]
        self.assertTrue(all(evaluate(CASES[case_id], response).values()))

    def test_unit_bearing_metadata_citations_preserve_the_numeric_fact(self):
        case_id = "free-unknown-rate-no-invented-savings"
        for citation in ("candidate_reduction_minutes: 5", "candidate_reduction_minutes value of 5",
                         '"candidate_reduction_minutes": 5'):
            with self.subTest(citation=citation):
                response = gold(case_id)
                response["diagnosis"] = response["diagnosis"].replace(
                    "The candidate reduction is 5 minutes", f"The fixture gives {citation}",
                )
                response["recommendation"]["rationale"] = response["diagnosis"]
                self.assertTrue(all(evaluate(CASES[case_id], response).values()))
                wrong_value = copy.deepcopy(response)
                wrong_value["diagnosis"] = wrong_value["diagnosis"].replace(citation, citation.replace("5", "50"))
                wrong_value["recommendation"]["rationale"] = wrong_value["diagnosis"]
                self.assertFalse(evaluate(CASES[case_id], wrong_value)["reportsCandidateTime"])
                response["findings"].append("The candidate reduction is 5 seconds.")
                self.assertFalse(evaluate(CASES[case_id], response)["keepsMinuteUnits"])

    def test_duration_unit_and_cost_near_misses_fail(self):
        case_id = "free-unknown-rate-no-invented-savings"
        for wrong in ("10 seconds", "20 seconds"):
            response = gold(case_id)
            response["diagnosis"] = response["diagnosis"].replace(wrong.replace("seconds", "minutes"), wrong)
            self.assertFalse(evaluate(CASES[case_id], response)["keepsMinuteUnits"])
        for invented in ("This saves 5 dollars.", "Cost savings are 50%."):
            response = gold(case_id)
            response["findings"].append(invented)
            self.assertFalse(evaluate(CASES[case_id], response)["doesNotInventMoney"])

    def test_every_required_proposed_contract_must_be_preserved(self):
        case_id = "justified-extraction-preserves-contracts"
        complete = gold(case_id)
        for index in range(5):
            response = copy.deepcopy(complete)
            del response["proposedChanges"][0]["preserves"][index]
            response["limitations"] = ["The inputs, secrets, permissions, outputs and environment were reviewed."]
            self.assertFalse(all(evaluate(CASES[case_id], response).values()))

    def test_meaningful_unsafe_changes_fail_even_with_good_diagnosis(self):
        case_id = "justified-extraction-preserves-contracts"
        for unsafe in ("Remove the approval gate.", "Drop secrets.", "Disable token permissions.",
                       "Discard the digest output.", "Unpin the checkout action."):
            with self.subTest(proposal=unsafe):
                response = gold(case_id)
                response["proposedChanges"][0]["summary"] = unsafe
                self.assertFalse(evaluate(CASES[case_id], response)["preserveSafetyBoundaries"])

    def test_investigation_is_not_a_workflow_change(self):
        for case_id in ("approval-wait-vs-runner-queue", "free-unknown-rate-no-invented-savings",
                        "healthy-small-estate-unchanged"):
            response = gold(case_id)
            response["recommendation"]["action"] = "investigate"
            self.assertTrue(all(evaluate(CASES[case_id], response).values()))

    def test_current_fixtures_and_execution_have_no_delays(self):
        for case in CASES.values():
            self.assertNotRegex(json.dumps(case["fixture"]["files"]), r"\bsleep\s+\d")
        for path in (EVAL_ROOT / "smoke.py", EVAL_ROOT / "harness/fake_gh.py"):
            self.assertNotIn("time.sleep", path.read_text())
        timing = json.loads(CASES["free-unknown-rate-no-invented-savings"]["fixture"]["files"]["durations.json"])
        self.assertEqual({"hosted_minutes": 10, "self_hosted_minutes": 20,
                          "candidate_reduction_minutes": 5}, timing)

    def test_repaired_healthy_fixture_has_checkout_setup_package_and_auth(self):
        case = CASES["healthy-small-estate-unchanged"]
        self.assertEqual(2, case["fixtureRevision"])
        files = case["fixture"]["files"]
        for name in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
            for required in ("actions/checkout@", "actions/setup-node@", "npm ci", "npm test"):
                self.assertIn(required, files[name])
        self.assertIn("NODE_AUTH_TOKEN: ${{ github.token }}", files[".github/workflows/release.yml"])
        self.assertIn("https://npm.pkg.github.com", files[".github/workflows/release.yml"])
        package, lock = json.loads(files["package.json"]), json.loads(files["package-lock.json"])
        self.assertEqual(package["name"], lock["packages"][""]["name"])
        self.assertEqual(package["version"], lock["packages"][""]["version"])
        self.assertIn("index.js", files)


if __name__ == "__main__":
    unittest.main()
