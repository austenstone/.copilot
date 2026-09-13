import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


EVAL_ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = EVAL_ROOT / "harness"
SCRATCH_ROOT = EVAL_ROOT / ".test-work-harness"
sys.path.insert(0, str(HARNESS_ROOT))

import run_eval


class HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
        SCRATCH_ROOT.mkdir()
        self.case = run_eval.load_cases()[0]

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)

    def test_model_and_isolation_flags_are_fixed(self) -> None:
        command = run_eval.build_command(
            "/usr/bin/copilot",
            SCRATCH_ROOT / "workspace",
            SCRATCH_ROOT / "overlay",
            SCRATCH_ROOT / "output",
            "prompt",
            "primary",
            "skill-enabled",
            SCRATCH_ROOT / "package",
            "GH_TOKEN",
        )
        self.assertEqual("gpt-5.6-sol-fast", command[command.index("--model") + 1])
        for flag in (
            "--no-ask-user",
            "--no-custom-instructions",
            "--disable-builtin-mcps",
            "--no-remote-export",
            "--no-bash-env",
            "--disallow-temp-dir",
        ):
            self.assertIn(flag, command)
        self.assertIn("--output-format", command)
        self.assertIn("--secret-env-vars=GH_TOKEN", command)
        available_index = command.index("--available-tools")
        self.assertEqual(
            ["bash", "view", "rg", "glob", "skill"],
            command[available_index + 1 : available_index + 6],
        )
        self.assertNotIn("--plugin-dir", command)

    def test_full_package_is_separately_enabled(self) -> None:
        enabled = run_eval.build_command(
            "copilot",
            SCRATCH_ROOT / "workspace-a",
            SCRATCH_ROOT / "overlay-a",
            SCRATCH_ROOT / "output-a",
            "prompt",
            "full-package",
            "skill-enabled",
            SCRATCH_ROOT / "package",
            "GH_TOKEN",
        )
        disabled = run_eval.build_command(
            "copilot",
            SCRATCH_ROOT / "workspace-b",
            SCRATCH_ROOT / "overlay-b",
            SCRATCH_ROOT / "output-b",
            "prompt",
            "full-package",
            "skill-disabled",
            SCRATCH_ROOT / "package",
            "GH_TOKEN",
        )
        self.assertIn("--plugin-dir", enabled)
        self.assertNotIn("--plugin-dir", disabled)

    def test_fixture_state_is_reproducible(self) -> None:
        hashes = []
        for name in ("a", "b"):
            workspace = SCRATCH_ROOT / name
            workspace.mkdir()
            run_eval.materialize_fixture(self.case, workspace)
            hashes.append(run_eval.hash_tree(workspace))
        self.assertEqual(hashes[0], hashes[1])

    def test_timeout_with_partial_byte_output_is_recorded(self) -> None:
        artifacts = SCRATCH_ROOT / "timeout-artifacts"
        with (
            patch.dict(os.environ, {"GH_TOKEN": "redacted-test-value"}, clear=True),
            patch.object(
                run_eval.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(
                    ["copilot"],
                    900,
                    output=b'{"type":"partial"}\n\xff',
                    stderr=b"partial error \xfe",
                ),
            ),
        ):
            result = run_eval.run_variant(
                self.case,
                "primary",
                "skill-enabled",
                artifacts,
                "copilot",
                "GH_TOKEN",
                run_eval.PLUGIN_ROOT,
            )

        output = artifacts / "primary" / self.case["id"] / "skill-enabled"
        self.assertEqual(124, result["exitCode"])
        self.assertFalse(result["interpreted"])
        self.assertEqual(
            '{"type":"partial"}\n\ufffd',
            (output / "transcript.jsonl").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            "partial error \ufffd",
            (output / "stderr.txt").read_text(encoding="utf-8"),
        )

    def test_primary_overlay_contains_only_enabled_skill_content(self) -> None:
        enabled = SCRATCH_ROOT / "enabled"
        disabled = SCRATCH_ROOT / "disabled"
        run_eval.create_overlay(self.case, enabled, True)
        run_eval.create_overlay(self.case, disabled, False)
        enabled_files = run_eval.hash_tree(enabled)
        self.assertEqual({}, run_eval.hash_tree(disabled))
        for name in {*self.case["skills"], "actions-workflow-toolkit"}:
            self.assertIn(f".github/skills/{name}/SKILL.md", enabled_files)
        self.assertTrue(all(Path(name).suffix == ".md" for name in enabled_files))

    def test_environment_keeps_only_selected_ephemeral_auth(self) -> None:
        workspace = SCRATCH_ROOT / "workspace"
        output = SCRATCH_ROOT / "output"
        with patch.dict(
            os.environ,
            {
                "HOME": str(SCRATCH_ROOT),
                "GH_TOKEN": "redacted-test-value",
                "GITHUB_TOKEN": "must-not-propagate",
            },
            clear=True,
        ):
            environment = run_eval.sanitized_environment(
                workspace,
                output,
                "GH_TOKEN",
            )
        self.assertEqual("redacted-test-value", environment["GH_TOKEN"])
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertEqual(str(output / "home"), environment["HOME"])
        self.assertEqual(str(output / "copilot-home"), environment["COPILOT_HOME"])
        self.assertNotEqual(environment["HOME"], environment["COPILOT_HOME"])
        self.assertNotEqual(str(SCRATCH_ROOT), environment["HOME"])
        self.assertTrue((output / "home").is_dir())
        self.assertTrue((output / "copilot-home").is_dir())
        self.assertEqual("", environment["COPILOT_CUSTOM_INSTRUCTIONS_DIRS"])

    def test_prompts_and_staged_fixtures_do_not_leak_rubric_tokens(self) -> None:
        prompts = [run_eval.build_prompt(case) for case in run_eval.load_cases()]
        for case, prompt in zip(run_eval.load_cases(), prompts, strict=True):
            workspace = SCRATCH_ROOT / case["id"]
            workspace.mkdir()
            run_eval.materialize_fixture(case, workspace)
            staged = " ".join(
                path.read_text(encoding="utf-8")
                for path in workspace.rglob("*")
                if path.is_file() and path.name != "gh"
            )
            rubric_tokens = {
                *case["scoring"]["must"]["diagnosis"],
                *case["scoring"]["must"]["claims"],
                *case["scoring"]["must"]["abstentions"],
                *case["scoring"]["mustNot"]["claims"],
                *case["scoring"]["behavior"]["preserveClaims"],
            }
            self.assertNotIn("Comparison label", prompt)
            self.assertNotIn("skill-enabled", prompt)
            self.assertNotIn("skill-disabled", prompt)
            self.assertNotIn("Allowed claim IDs", prompt)
            self.assertNotIn("Allowed abstention IDs", prompt)
            self.assertNotIn("claim vocabulary", prompt.lower())
            self.assertNotIn("abstention vocabulary", prompt.lower())
            self.assertNotIn('"mustNot"', prompt)
            for token in rubric_tokens:
                self.assertNotIn(token, prompt)
                self.assertNotIn(token, staged)

    def test_prompt_requires_supported_skill_activation(self) -> None:
        prompt = run_eval.build_prompt(self.case)
        self.assertIn("using the skill tool", prompt)
        self.assertIn(self.case["skills"][0], prompt)
        self.assertIn("Do not open SKILL.md", prompt)

    def test_extracts_json_response_from_jsonl(self) -> None:
        expected = {
            "caseId": "case",
            "claims": ["A"],
            "evidence": ["E"],
            "abstentions": [],
            "proposedChanges": [],
        }
        transcript = json.dumps(
            {
                "type": "assistant.message",
                "data": {"content": json.dumps(expected)},
            }
        )
        self.assertEqual(expected, run_eval.extract_response(transcript))

    def test_does_not_extract_echoed_user_schema(self) -> None:
        transcript = json.dumps(
            {
                "type": "user.message",
                "data": {
                    "content": '{"caseId":"case","claims":["A"]}',
                },
            }
        )
        self.assertIsNone(run_eval.extract_response(transcript))

    def test_extracts_exact_advertised_tool_whitelist(self) -> None:
        transcript = json.dumps(
            {
                "type": "session.usage_checkpoint",
                "data": {
                    "promptCacheBreakState": [
                        {
                            "models": {
                                "gpt-5.6-sol-fast": {
                                    "tools": [
                                        {"name": name}
                                        for name in (
                                            "bash",
                                            "view",
                                            "rg",
                                            "glob",
                                            "skill",
                                        )
                                    ]
                                }
                            }
                        }
                    ]
                },
            }
        )
        self.assertEqual(
            ["bash", "glob", "rg", "skill", "view"],
            run_eval.advertised_tools(transcript),
        )
        self.assertTrue(
            run_eval.tools_are_exact(["bash", "glob", "rg", "skill", "view"])
        )
        self.assertFalse(
            run_eval.tools_are_exact(
                ["bash", "glob", "rg", "session_history", "skill", "view"]
            )
        )
        self.assertFalse(run_eval.tools_are_exact(["glob", "rg", "view"]))

    def test_model_confirmation_requires_exclusive_positive_exact_usage(self) -> None:
        usage_path = SCRATCH_ROOT / "usage.json"

        def write_usage(model_metrics: dict, current_model: str = "gpt-5.6-sol-fast") -> bool:
            usage_path.write_text(
                json.dumps(
                    {
                        "currentModel": current_model,
                        "modelMetrics": model_metrics,
                    }
                ),
                encoding="utf-8",
            )
            return run_eval.confirm_model_usage(usage_path)[0]

        exact = {
            "gpt-5.6-sol-fast": {
                "requests": {"count": 1},
                "usage": {"inputTokens": 10, "outputTokens": 5},
            }
        }
        self.assertTrue(write_usage(exact))
        self.assertFalse(
            write_usage(
                {
                    **exact,
                    "gpt-5.6-sol": {
                        "requests": {"count": 1},
                        "usage": {"inputTokens": 1, "outputTokens": 1},
                    },
                }
            )
        )
        self.assertFalse(
            write_usage(
                {
                    "gpt-5.6-sol-fast": {
                        "requests": {"count": 0},
                        "usage": {"inputTokens": 0, "outputTokens": 0},
                    }
                }
            )
        )
        usage_path.write_text(
            '{"note":"gpt-5.6-sol-fast","modelMetrics":{}}',
            encoding="utf-8",
        )
        self.assertFalse(run_eval.confirm_model_usage(usage_path)[0])

    def test_records_discovery_and_successful_skill_consumption(self) -> None:
        transcript = "\n".join(
            (
                json.dumps(
                    {
                        "type": "session.skills_loaded",
                        "data": {
                            "skills": [
                                {
                                    "name": "actions-workflow-toolkit",
                                    "enabled": True,
                                }
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "tool.execution_start",
                        "data": {
                            "toolName": "skill",
                            "toolCallId": "call-1",
                            "arguments": {"skill": "actions-workflow-toolkit"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "tool.execution_complete",
                        "data": {
                            "toolCallId": "call-1",
                            "success": True,
                            "result": {"content": "procedure body"},
                        },
                    }
                ),
            )
        )
        self.assertEqual(
            ["actions-workflow-toolkit"],
            run_eval.discovered_skills(transcript),
        )
        consumed = run_eval.consumed_skills(
            transcript,
            ["actions-workflow-toolkit"],
        )
        self.assertEqual(["actions-workflow-toolkit"], [item["name"] for item in consumed])
        self.assertRegex(consumed[0]["resultHash"], r"^[0-9a-f]{64}$")
        records = run_eval.procedure_content_records(
            self.case,
            run_eval.PLUGIN_ROOT / "skills",
        )
        self.assertTrue(all(record["present"] for record in records))
        self.assertTrue(
            all(
                len(record["contentHash"]) == 64
                and len(record["directoryHash"]) == 64
                for record in records
            )
        )

    def test_rejects_artifacts_inside_repository(self) -> None:
        with self.assertRaises(ValueError):
            run_eval.ensure_artifacts_outside_repo(EVAL_ROOT / "artifacts")

    def test_fixture_gh_read_does_not_modify_workspace(self) -> None:
        case = next(
            case for case in run_eval.load_cases() if case["fixture"]["ghRules"]
        )
        workspace = SCRATCH_ROOT / "fixture-workspace"
        workspace.mkdir()
        run_eval.materialize_fixture(case, workspace)
        baseline = run_eval.hash_tree(workspace)
        rule = case["fixture"]["ghRules"][0]
        result = subprocess.run(
            [str(workspace / ".actions-eval" / "bin" / "gh"), *rule["argv"]],
            env={
                "ACTIONS_EVAL_GH_FIXTURE": str(
                    workspace / ".actions-eval" / "gh-fixture.json"
                ),
                "PATH": os.environ["PATH"],
            },
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rule.get("exitCode", 0), result.returncode)
        self.assertEqual(baseline, run_eval.hash_tree(workspace))

    def test_pair_parity_blocks_mismatched_fixtures(self) -> None:
        artifacts = SCRATCH_ROOT / "artifacts"
        results = [
            {
                "caseId": "case",
                "comparison": "primary",
                "variant": "skill-enabled",
                "fixtureStateHash": "a",
                "advertisedTools": ["bash", "glob", "rg", "skill", "view"],
                "toolAccessConfirmed": True,
                "procedureTreatment": {
                    "discoveryRate": 1.0,
                    "consumptionRate": 1.0,
                },
                "interpreted": True,
                "score": {},
            },
            {
                "caseId": "case",
                "comparison": "primary",
                "variant": "skill-disabled",
                "fixtureStateHash": "b",
                "advertisedTools": ["bash", "glob", "rg", "skill", "view"],
                "toolAccessConfirmed": True,
                "procedureTreatment": {
                    "discoveryRate": 0.0,
                    "consumptionRate": 0.0,
                },
                "interpreted": True,
                "score": {},
            },
        ]
        run_eval.enforce_pair_parity(results, artifacts)
        self.assertTrue(all(not result["interpreted"] for result in results))
        self.assertTrue(all(not result["pairParityConfirmed"] for result in results))
        self.assertTrue(all("score" not in result for result in results))

    def test_pair_parity_blocks_extra_advertised_tool(self) -> None:
        artifacts = SCRATCH_ROOT / "tool-artifacts"
        common = {
            "caseId": "case",
            "comparison": "primary",
            "fixtureStateHash": "same",
            "toolAccessConfirmed": True,
            "interpreted": True,
            "score": {},
        }
        results = [
            {
                **common,
                "variant": "skill-enabled",
                "advertisedTools": ["bash", "glob", "rg", "skill", "view"],
                "procedureTreatment": {
                    "discoveryRate": 1.0,
                    "consumptionRate": 1.0,
                },
            },
            {
                **common,
                "variant": "skill-disabled",
                "advertisedTools": [
                    "bash",
                    "glob",
                    "rg",
                    "session_history",
                    "skill",
                    "view",
                ],
                "procedureTreatment": {
                    "discoveryRate": 0.0,
                    "consumptionRate": 0.0,
                },
            },
        ]
        run_eval.enforce_pair_parity(results, artifacts)
        self.assertTrue(all(not result["interpreted"] for result in results))

    def test_unconsumed_enabled_skill_is_not_procedure_effectiveness(self) -> None:
        artifacts = SCRATCH_ROOT / "unconsumed-artifacts"
        common = {
            "caseId": "case",
            "comparison": "primary",
            "fixtureStateHash": "same",
            "advertisedTools": ["bash", "glob", "rg", "skill", "view"],
            "toolAccessConfirmed": True,
            "modelConfirmed": True,
            "interpreted": True,
            "changedPaths": [],
            "score": {"primaryScore": 0.8},
        }
        results = [
            {
                **common,
                "variant": "skill-enabled",
                "procedureTreatment": {
                    "targetSkills": ["actions-workflow-toolkit"],
                    "discoveredTargets": ["actions-workflow-toolkit"],
                    "consumptions": [],
                    "discoveryRate": 1.0,
                    "consumptionRate": 0.0,
                },
            },
            {
                **common,
                "variant": "skill-disabled",
                "procedureTreatment": {
                    "targetSkills": ["actions-workflow-toolkit"],
                    "discoveredTargets": [],
                    "consumptions": [],
                    "discoveryRate": 0.0,
                    "consumptionRate": 0.0,
                },
            },
        ]
        run_eval.enforce_pair_parity(results, artifacts)
        self.assertTrue(all(result["pairParityConfirmed"] for result in results))
        self.assertTrue(all(not result["procedureTreatmentValid"] for result in results))
        aggregates = run_eval.aggregate_results(results)
        conditional = aggregates["conditionalProcedureEffectiveness"]["primary"]
        self.assertEqual(0, conditional["eligiblePairs"])
        self.assertIsNone(conditional["meanScoreDelta"])


if __name__ == "__main__":
    unittest.main()
