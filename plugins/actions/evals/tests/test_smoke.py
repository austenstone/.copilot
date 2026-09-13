import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))
import smoke


CASES = {case["id"]: case for case in smoke.load_cases()}


def response_for(case, diagnosis, findings=None, limitations=None, action="no-change", changes=None):
    return {
        "diagnosis": diagnosis,
        "findings": findings or [],
        "evidenceUsed": [item["id"] for item in smoke.evidence_catalog(case)[0]],
        "limitations": limitations or [],
        "recommendation": {"action": action, "rationale": diagnosis},
        "proposedChanges": changes or [],
    }


def evaluate(case, response, changed=None, observed=None, activations=None, trace=None):
    return smoke.assertions_for(
        case, response, changed or [],
        set(response["evidenceUsed"]) if observed is None else observed,
        [{"name": name} for name in smoke.target_skills(case)] if activations is None else activations,
        trace or [],
    )[0]


class SmokeAssertionTests(unittest.TestCase):
    def test_smoke_model_is_fixed_to_luna(self):
        self.assertEqual("gpt-5.6-luna", smoke.MODEL)

    def test_unknown_case_fails_before_any_cli_invocation(self):
        result = subprocess.run(
            [sys.executable, str(EVAL_ROOT / "smoke.py"), "--case", "../unknown"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("invalid choice", result.stderr)

    def test_matrix_and_dispatch_cover_exact_corpus_with_unique_artifacts(self):
        workflow = (EVAL_ROOT.parents[2] / ".github/workflows/actions-copilot-smoke.yml").read_text()
        match = re.search(r"\|\|\s*'(\[.*?\])'\)", workflow, re.DOTALL)
        matrix = json.loads(match.group(1))
        self.assertEqual(set(CASES), set(matrix))
        self.assertEqual(12, len(matrix))
        choices = re.findall(r"^          - ([a-z0-9-]+)$", workflow, re.MULTILINE)
        self.assertEqual({"all", *CASES}, set(choices))
        self.assertIn("name: actions-copilot-smoke-${{ matrix.case }}", workflow)
        self.assertEqual(12, len({f"actions-copilot-smoke-{case}" for case in matrix}))
        self.assertIn("fail-fast: false", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotRegex(workflow, r"\bsleep\b")
        self.assertIn("runs-on: ubuntu-slim", workflow)
        self.assertNotIn("max-parallel", workflow)
        self.assertIn('smoke.py --case "$EVAL_CASE"', workflow)
        self.assertNotIn("pull_request:", workflow)

    def test_all_five_skills_are_targeted_without_changing_manual_targets(self):
        self.assertEqual(
            {"actions-debug", "actions-workflow-toolkit", "actions-security-review",
             "actions-architecture-review", "actions-optimization"},
            {skill for case in CASES.values() for skill in smoke.target_skills(case)},
        )
        self.assertEqual(["actions-workflow-toolkit"], CASES["failure-only-earlier-attempt"]["skills"])

    def test_prompts_exclude_case_answers_labels_and_oracle_outputs(self):
        for case in CASES.values():
            with self.subTest(case=case["id"]):
                prompt = smoke.build_prompt(case)
                self.assertNotIn(case["id"], prompt)
                self.assertNotIn(case["title"], prompt)
                for label in case["evidenceIds"] + case["scoring"]["allowedClaims"]:
                    self.assertNotIn(label, prompt)
                for values in case["scoring"]["must"].values():
                    for label in values:
                        self.assertNotIn(label, prompt)
                for rule in case["fixture"]["ghRules"]:
                    for field in ("stdout", "stderr"):
                        if rule.get(field):
                            self.assertNotIn(rule[field], prompt)
                catalog, aliases = smoke.evidence_catalog(case)
                self.assertEqual(set(case["evidenceIds"]), {label for labels in aliases.values() for label in labels})
                for source in catalog:
                    if "file" in source:
                        self.assertIn(source["file"], case["fixture"]["files"])
                    else:
                        self.assertIn(shlex.split(source["command"])[1:], [rule["argv"] for rule in case["fixture"]["ghRules"]])

    def test_oracle_and_fake_gh_are_outside_agent_workspace(self):
        case = CASES["unreadable-reusable-callee"]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            workspace = smoke.materialize_case(case, output)
            self.assertTrue((output / "private/gh-fixture.json").is_file())
            self.assertTrue((output / "private/bin/gh").is_file())
            self.assertFalse((workspace / ".actions-eval").exists())
            self.assertEqual(
                set(case["fixture"]["files"]),
                {path.relative_to(workspace).as_posix() for path in workspace.rglob("*")
                 if path.is_file() and "plugin" not in path.relative_to(workspace).parts},
            )

    def test_evidence_needs_successful_reads_or_exact_fixture_commands(self):
        case = CASES["unreadable-reusable-callee"]
        workspace = Path("/synthetic/workspace")
        events = [
            {"type": "tool.execution_start", "data": {"toolName": "view", "toolCallId": "v1",
             "arguments": {"path": str(workspace / ".github/workflows/caller.yml")}}},
            {"type": "tool.execution_complete", "data": {"toolCallId": "v1", "success": True}},
        ]
        transcript = "\n".join(json.dumps(event) for event in events)
        trace = [{"argv": case["fixture"]["ghRules"][0]["argv"], "matched": True}]
        self.assertEqual({"E1", "E2"}, smoke.observed_evidence(case, transcript, trace, workspace))
        self.assertEqual({"E1"}, smoke.observed_evidence(case, transcript, [], workspace))
        events[-1]["data"]["success"] = False
        self.assertEqual(
            set(), smoke.observed_evidence(case, "\n".join(map(json.dumps, events)), [], workspace),
        )

    def test_always_answering_no_cannot_pass_any_case(self):
        for case in CASES.values():
            with self.subTest(case=case["id"]):
                self.assertFalse(all(evaluate(case, response_for(case, "No.")).values()))

    def test_valid_scalar_no_change_control_passes(self):
        case = CASES["string-environment-concurrency"]
        response = response_for(
            case, "The string shorthand is valid. The environment string is valid and the "
            "concurrency string is valid, so the schema is valid.",
            ["The current syntax is supported."], ["No rewrite is warranted."],
        )
        self.assertTrue(all(evaluate(case, response).values()))
        self.assertFalse(evaluate(case, response, observed=set())["evidenceRead"])
        self.assertFalse(evaluate(case, response, activations=[])["targetSkills"])
        self.assertFalse(evaluate(case, response, changed=["workflow.yml"])["unauthorizedEdits"])
        self.assertFalse(evaluate(case, response, trace=[{"matched": False}])["fixtureCommands"])

    def test_healthy_estate_no_change_control_passes(self):
        case = CASES["healthy-small-estate-unchanged"]
        response = response_for(
            case, "Healthy. No material security finding and no material optimization. "
            "No extraction is justified. No changes recommended.",
            ["Leave unchanged."], ["Avoid churn."],
        )
        self.assertTrue(all(evaluate(case, response).values()))

    def test_extraction_control_requires_proposal_and_preserved_contracts(self):
        case = CASES["justified-extraction-preserves-contracts"]
        response = response_for(
            case, "Extraction is justified by repetition of three similar jobs.",
            ["Preserve inputs, preserve secrets, preserve permissions, preserve outputs, "
             "and preserve environment gates."],
            ["Preserve the contract and the environment gate."],
            action="change",
            changes=[{"path": ".github/workflows/release.yml", "summary": "Extract repeated jobs.",
                      "preserves": ["inputs, secrets, permissions, outputs, environment gate"]}],
        )
        self.assertTrue(all(evaluate(case, response).values()))
        response["proposedChanges"] = []
        self.assertFalse(evaluate(case, response)["offersRefactorProposal"])

    def test_response_shape_and_final_message_are_not_success_shaped(self):
        for value in (None, [], "No", {"diagnosis": "No", "findings": None}):
            self.assertFalse(smoke.valid_response(value))
        transcript = "\n".join(
            json.dumps({"type": "assistant.message", "data": {"content": content}})
            for content in ('{"diagnosis":"earlier draft"}', "Final malformed response")
        )
        self.assertEqual("Final malformed response", smoke.final_answer(transcript))

    def test_invalid_jsonl_is_not_a_pass(self):
        with self.assertRaises(json.JSONDecodeError):
            smoke.final_answer("No. This is not native CLI JSONL.")


if __name__ == "__main__":
    unittest.main()
