#!/usr/bin/env python3
"""Contract tests for the bounded workflow inventory helper."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HELPER = (
    PLUGIN_ROOT
    / "skills"
    / "actions-workflow-toolkit"
    / "scripts"
    / "inventory-workflows.py"
)
SCRATCH = Path(__file__).resolve().parent / f".inventory-workflows-test-{os.getpid()}"
PINNED_SHA = "0123456789abcdef0123456789abcdef01234567"
APP_SHA = "1111111111111111111111111111111111111111"
ONE_SHA = "2222222222222222222222222222222222222222"
LOCAL_SHA = "3333333333333333333333333333333333333333"
YAML_SHA = "4444444444444444444444444444444444444444"
FEATURE_SHA = "5555555555555555555555555555555555555555"


def content_payload(text: str, sha: str) -> dict[str, str]:
    return {
        "content": base64.b64encode(text.encode()).decode(),
        "encoding": "base64",
        "sha": sha,
        "html_url": "https://github.com/acme/example/blob/ref/workflow.yml",
    }


def directory(*paths: str) -> list[dict[str, str]]:
    return [{"type": "file", "path": path} for path in paths]


class InventoryWorkflowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        cls.bin_dir = SCRATCH / "bin"
        cls.bin_dir.mkdir(parents=True)
        cls.fake_gh = cls.bin_dir / "gh"
        cls.fake_gh.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys

if sys.argv[1:] == ["--version"]:
    print("gh version 2.99.0 (fixture)")
    raise SystemExit(0)
expected = [
    "api", "--hostname", "github.com", "--method", "GET",
    "-H", "Accept: application/vnd.github+json",
    "-H", "X-GitHub-Api-Version: 2022-11-28",
]
if sys.argv[1:10] != expected or len(sys.argv) != 11:
    print("unsupported gh call: " + " ".join(sys.argv[1:]), file=sys.stderr)
    raise SystemExit(97)
endpoint = sys.argv[10]
with open(os.environ["GH_CALL_LOG"], "a", encoding="utf-8") as handle:
    handle.write(endpoint + "\\n")
with open(os.environ["GH_FIXTURES"], encoding="utf-8") as handle:
    fixtures = json.load(handle)
if endpoint not in fixtures:
    print("unsupported gh endpoint: " + endpoint, file=sys.stderr)
    raise SystemExit(98)
fixture = fixtures[endpoint]
if "error" in fixture:
    print(fixture["error"], file=sys.stderr)
    raise SystemExit(fixture.get("exit", 1))
json.dump(fixture["json"], sys.stdout)
""",
            encoding="utf-8",
        )
        cls.fake_gh.chmod(0o755)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def run_helper(
        self, fixtures: dict[str, dict[str, Any]], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        fixture_path = SCRATCH / f"fixtures-{self.id().rsplit('.', 1)[-1]}.json"
        call_log = SCRATCH / f"calls-{self.id().rsplit('.', 1)[-1]}.txt"
        fixture_path.write_text(json.dumps(fixtures), encoding="utf-8")
        call_log.unlink(missing_ok=True)
        environment = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "GH_FIXTURES": str(fixture_path),
            "GH_CALL_LOG": str(call_log),
        }
        completed = subprocess.run(
            [sys.executable, str(HELPER), *arguments],
            cwd=PLUGIN_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.last_calls = (
            call_log.read_text(encoding="utf-8").splitlines()
            if call_log.exists()
            else []
        )
        return completed

    def test_inventory_preserves_contracts_and_follows_transitive_calls(self) -> None:
        caller = """name: CI
on: [pull_request, merge_group]
permissions:
  contents: read
concurrency: ci-${{ github.ref }}
jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    environment: production
    permissions:
      contents: read
    outputs:
      artifact: ${{ steps.package.outputs.name }}
    steps:
      - uses: actions/checkout@v4
      - id: package
        run: echo package
  shared:
    uses: acme/platform/.github/workflows/shared.yml@0123456789abcdef0123456789abcdef01234567
    with:
      channel: stable
    secrets: inherit
    permissions:
      contents: read
    concurrency: shared-${{ github.ref }}
"""
        reordered = """name: Other
on:
  workflow_dispatch:
jobs:
  same-build:
    outputs:
      artifact: ${{ steps.package.outputs.name }}
    permissions: {contents: read}
    environment: production
    runs-on: ubuntu-latest
    name: Build
    steps:
      - uses: actions/checkout@v4
      - run: echo package
        id: package
  object-contract:
    runs-on: [self-hosted, linux]
    environment:
      url: https://example.test
      name: production
    concurrency:
      cancel-in-progress: true
      group: deploy-${{ github.ref }}
    permissions:
      id-token: write
      contents: read
    outputs:
      url: ${{ steps.deploy.outputs.url }}
    steps:
      - id: deploy
        run: echo deploy
"""
        shared = """name: Shared
on:
  workflow_call:
    outputs:
      artifact:
        value: ${{ jobs.build.outputs.artifact }}
jobs:
  nested:
    uses: acme/private/.github/workflows/deploy.yml@v1
"""
        fixtures = {
            "repos/acme/app": {
                "json": {
                    "full_name": "acme/app",
                    "default_branch": "main",
                    "archived": False,
                }
            },
            "repos/acme/app/commits/main": {"json": {"sha": APP_SHA}},
            f"repos/acme/app/contents/.github/workflows?ref={APP_SHA}": {
                "json": directory(
                    ".github/workflows/ci.yml", ".github/workflows/other.yaml"
                )
            },
            f"repos/acme/app/contents/.github/workflows/ci.yml?ref={APP_SHA}": {
                "json": content_payload(caller, "caller")
            },
            f"repos/acme/app/contents/.github/workflows/other.yaml?ref={APP_SHA}": {
                "json": content_payload(reordered, "other")
            },
            (
                "repos/acme/platform/contents/.github/workflows/shared.yml"
                f"?ref={PINNED_SHA}"
            ): {"json": content_payload(shared, "shared")},
            "repos/acme/private/commits/v1": {
                "error": "gh: Not Found (HTTP 404)",
                "exit": 1,
            },
            "repos/acme/private/contents/.github/workflows/deploy.yml?ref=v1": {
                "error": "gh: Not Found (HTTP 404)",
                "exit": 1,
            },
        }
        completed = self.run_helper(
            fixtures,
            "--repository",
            "acme/app",
            "--max-workflows",
            "10",
            "--max-depth",
            "3",
            "--max-callees",
            "5",
            "--max-comparisons",
            "50",
            "--similarity-threshold",
            "0.5",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        document = json.loads(completed.stdout)
        self.assertEqual(document["schema_version"], "actions-helper/v1")
        self.assertIn("WARNING inaccessible_input:", completed.stderr)
        self.assertEqual(
            document["provenance"]["gh_version"], "gh version 2.99.0 (fixture)"
        )
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertEqual(document["result"]["summary"]["workflows"], 3)
        self.assertEqual(document["result"]["summary"]["reusable_workflow_edges"], 2)

        jobs = {
            (job["workflow"], job["id"]): job
            for workflow in document["result"]["workflows"]
            for job in workflow["jobs"]
        }
        build = jobs[("acme/app:.github/workflows/ci.yml@<default>", "build")]
        same = jobs[("acme/app:.github/workflows/other.yaml@<default>", "same-build")]
        object_contract = jobs[
            ("acme/app:.github/workflows/other.yaml@<default>", "object-contract")
        ]
        self.assertEqual(build["canonical_sha256"], same["canonical_sha256"])
        self.assertEqual(build["environment"], "production")
        self.assertEqual(object_contract["environment"]["name"], "production")
        self.assertTrue(object_contract["concurrency"]["cancel-in-progress"])
        self.assertEqual(object_contract["permissions"]["id-token"], "write")
        self.assertIn("url", object_contract["outputs"])
        self.assertNotEqual(build["canonical_sha256"], object_contract["canonical_sha256"])
        caller_workflow = next(
            workflow
            for workflow in document["result"]["workflows"]
            if workflow["repository"] == "acme/app"
            and workflow["path"] == ".github/workflows/ci.yml"
        )
        self.assertEqual(caller_workflow["concurrency"], "ci-${{ github.ref }}")

        edges = document["result"]["reusable_workflow_edges"]
        self.assertTrue(edges[0]["pin"]["pinned"])
        self.assertEqual(edges[0]["status"], "resolved")
        self.assertEqual(edges[0]["caller_contract"]["with"]["channel"], "stable")
        self.assertEqual(edges[0]["caller_contract"]["secrets"], "inherit")
        shared_workflow = next(
            workflow
            for workflow in document["result"]["workflows"]
            if workflow["repository"] == "acme/platform"
        )
        self.assertIn("artifact", shared_workflow["workflow_call"]["outputs"])
        self.assertFalse(edges[1]["pin"]["pinned"])
        self.assertEqual(edges[1]["status"], "inaccessible_or_unexamined")
        self.assertEqual(edges[1]["ambiguity"], "not_found_or_inaccessible")
        self.assertEqual(edges[1]["http_status"], 404)
        self.assertFalse(
            document["result"]["duplication"]["similarity_is_semantic_equivalence"]
        )
        self.assertTrue(
            all(
                pair["semantic_equivalence"] == "not_asserted"
                for pair in document["result"]["duplication"]["similar_pairs"]
            )
        )
        self.assertIn(
            "Incoming callers are limited",
            document["result"]["caller_coverage"]["limitations"][0],
        )

    def test_organization_inventory_reports_repository_bound(self) -> None:
        workflow = """on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""
        fixtures = {
            "orgs/acme/repos?type=all&per_page=100&page=1": {
                "json": [
                    {
                        "full_name": "acme/one",
                        "default_branch": "main",
                        "archived": False,
                    },
                    {
                        "full_name": "acme/two",
                        "default_branch": "main",
                        "archived": False,
                    },
                ]
            },
            "repos/acme/one/commits/main": {"json": {"sha": ONE_SHA}},
            f"repos/acme/one/contents/.github/workflows?ref={ONE_SHA}": {
                "json": directory(".github/workflows/ci.yml")
            },
            f"repos/acme/one/contents/.github/workflows/ci.yml?ref={ONE_SHA}": {
                "json": content_payload(workflow, "one")
            },
        }
        completed = self.run_helper(
            fixtures,
            "--organization",
            "acme",
            "--max-repositories",
            "1",
            "--max-workflows",
            "5",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        document = json.loads(completed.stdout)
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertIn(
            "repository_limit_reached", document["coverage"]["limitations"]
        )
        self.assertEqual(document["result"]["summary"]["repositories"], 1)

    def test_actions_yaml_loader_preserves_on_scalars_anchors_and_blocks(self) -> None:
        workflow = """name: YAML features
on:
  push:
jobs:
  anchored: &shared_job
    concurrency: build
    environment: production
    env:
      LEGACY_YES: yes
      LEGACY_OFF: off
      REAL_BOOL: true
    runs-on: ubuntu-latest
    steps:
      - run: |
          echo one
          echo "# two"
  merged:
    <<: *shared_job
"""
        fixtures = {
            "repos/acme/yaml": {
                "json": {
                    "full_name": "acme/yaml",
                    "default_branch": "main",
                    "archived": False,
                }
            },
            "repos/acme/yaml/commits/main": {"json": {"sha": YAML_SHA}},
            f"repos/acme/yaml/contents/.github/workflows?ref={YAML_SHA}": {
                "json": directory(".github/workflows/features.yml")
            },
            f"repos/acme/yaml/contents/.github/workflows/features.yml?ref={YAML_SHA}": {
                "json": content_payload(workflow, "yaml")
            },
        }
        completed = self.run_helper(
            fixtures,
            "--repository",
            "acme/yaml",
            "--max-workflows",
            "2",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        document = json.loads(completed.stdout)
        parsed = document["result"]["workflows"][0]
        self.assertEqual(parsed["events"], ["push"])
        anchored, merged = parsed["jobs"]
        self.assertEqual(anchored["canonical_sha256"], merged["canonical_sha256"])
        self.assertEqual(list(anchored["canonical_job"]), sorted(anchored["canonical_job"]))
        self.assertEqual(anchored["canonical_job"]["env"]["LEGACY_YES"], "yes")
        self.assertEqual(anchored["canonical_job"]["env"]["LEGACY_OFF"], "off")
        self.assertIs(anchored["canonical_job"]["env"]["REAL_BOOL"], True)
        self.assertEqual(
            anchored["canonical_job"]["steps"][0]["run"],
            'echo one\necho "# two"\n',
        )

    def test_manifest_ref_local_call_and_safe_output(self) -> None:
        caller = """on: workflow_dispatch
jobs:
  local:
    uses: ./.github/workflows/local.yml
"""
        callee = """on:
  workflow_call:
    inputs:
      mode:
        type: string
        required: false
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo local
"""
        fixtures = {
            "repos/acme/local": {
                "json": {
                    "full_name": "acme/local",
                    "default_branch": "main",
                    "archived": False,
                }
            },
            "repos/acme/local/commits/release%2Fv1": {
                "json": {"sha": LOCAL_SHA}
            },
            f"repos/acme/local/contents/.github/workflows?ref={LOCAL_SHA}": {
                "json": directory(".github/workflows/caller.yml")
            },
            f"repos/acme/local/contents/.github/workflows/caller.yml?ref={LOCAL_SHA}": {
                "json": content_payload(caller, "caller")
            },
            f"repos/acme/local/contents/.github/workflows/local.yml?ref={LOCAL_SHA}": {
                "json": content_payload(callee, "callee")
            },
        }
        manifest = SCRATCH / "repositories.txt"
        manifest.write_text("acme/local@release/v1\n", encoding="utf-8")
        output = f"tests/{SCRATCH.name}/output/result.json"
        completed = self.run_helper(
            fixtures,
            "--input",
            str(manifest),
            "--max-repositories",
            "1",
            "--max-workflows",
            "3",
            "--output",
            output,
            "--pretty",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(completed.stdout, "")
        document = json.loads((PLUGIN_ROOT / output).read_text(encoding="utf-8"))
        edge = document["result"]["reusable_workflow_edges"][0]
        self.assertEqual(edge["pin"]["kind"], "local_same_commit")
        self.assertTrue(edge["pin"]["pinned"])
        self.assertEqual(edge["pin"]["value"], LOCAL_SHA)
        self.assertEqual(edge["callee_ref"], "release/v1")
        self.assertEqual(
            self.last_calls.count("repos/acme/local/commits/release%2Fv1"), 1
        )
        self.assertEqual(
            document["result"]["workflows"][0]["requested_ref"], "release/v1"
        )

    def test_local_call_is_unverified_when_commit_resolution_fails(self) -> None:
        fixtures = {
            "repos/acme/unverified": {
                "json": {
                    "full_name": "acme/unverified",
                    "default_branch": "main",
                    "archived": False,
                }
            },
            "repos/acme/unverified/commits/main": {
                "error": "gh: Not Found (HTTP 404)",
                "exit": 1,
            },
            "repos/acme/unverified/contents/.github/workflows": {
                "json": directory(".github/workflows/caller.yml")
            },
            "repos/acme/unverified/contents/.github/workflows/caller.yml": {
                "json": content_payload(
                    """on: push
jobs:
  local:
    uses: ./.github/workflows/local.yml
""",
                    "caller",
                )
            },
            "repos/acme/unverified/contents/.github/workflows/local.yml": {
                "json": content_payload(
                    """on: workflow_call
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""",
                    "local",
                )
            },
        }
        completed = self.run_helper(
            fixtures,
            "--repository",
            "acme/unverified",
            "--max-workflows",
            "3",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        document = json.loads(completed.stdout)
        edge = document["result"]["reusable_workflow_edges"][0]
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertEqual(edge["pin"]["kind"], "local_ref_unverified")
        self.assertFalse(edge["pin"]["pinned"])
        self.assertIsNone(edge["pin"]["value"])
        self.assertEqual(document["result"]["summary"]["unverified_local_edges"], 1)
        self.assertEqual(document["result"]["summary"]["unpinned_remote_edges"], 0)
        self.assertEqual(edge["callee_resolution"]["status"], "unverified")
        self.assertEqual(
            self.last_calls.count("repos/acme/unverified/commits/main"), 1
        )

    def test_scalar_sequence_workflow_call_and_invalid_job_ids(self) -> None:
        fixtures = {
            "repos/acme/contracts": {
                "json": {
                    "full_name": "acme/contracts",
                    "default_branch": "main",
                    "archived": False,
                }
            },
            "repos/acme/contracts/commits/main": {"json": {"sha": FEATURE_SHA}},
            f"repos/acme/contracts/contents/.github/workflows?ref={FEATURE_SHA}": {
                "json": directory(
                    ".github/workflows/malformed.yml",
                    ".github/workflows/scalar.yml",
                    ".github/workflows/sequence.yml",
                )
            },
            (
                "repos/acme/contracts/contents/.github/workflows/malformed.yml"
                f"?ref={FEATURE_SHA}"
            ): {
                "json": content_payload(
                    """on: push
jobs:
  1: {}
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo valid
""",
                    "malformed",
                )
            },
            (
                "repos/acme/contracts/contents/.github/workflows/scalar.yml"
                f"?ref={FEATURE_SHA}"
            ): {
                "json": content_payload(
                    """on: workflow_call
jobs:
  scalar:
    runs-on: ubuntu-latest
    steps:
      - run: echo scalar
""",
                    "scalar",
                )
            },
            (
                "repos/acme/contracts/contents/.github/workflows/sequence.yml"
                f"?ref={FEATURE_SHA}"
            ): {
                "json": content_payload(
                    """on: [workflow_call]
jobs:
  sequence:
    runs-on: ubuntu-latest
    steps:
      - run: echo sequence
""",
                    "sequence",
                )
            },
        }
        completed = self.run_helper(
            fixtures,
            "--repository",
            "acme/contracts",
            "--max-workflows",
            "5",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        document = json.loads(completed.stdout)
        workflows = {
            workflow["path"]: workflow for workflow in document["result"]["workflows"]
        }
        empty_contract = {"inputs": {}, "secrets": {}, "outputs": {}}
        self.assertEqual(
            workflows[".github/workflows/scalar.yml"]["workflow_call"],
            empty_contract,
        )
        self.assertEqual(
            workflows[".github/workflows/sequence.yml"]["workflow_call"],
            empty_contract,
        )
        malformed = workflows[".github/workflows/malformed.yml"]
        self.assertEqual([job["id"] for job in malformed["jobs"]], ["build"])
        self.assertEqual(document["coverage"]["status"], "partial")
        invalid = [
            item
            for item in document["diagnostics"]
            if item["code"] == "invalid_input"
        ]
        self.assertEqual(invalid[0]["metadata"]["job_id"], "1")

    def test_rate_limit_and_forbidden_ambiguity_are_explicit(self) -> None:
        for message, expected in (
            ("gh: API rate limit exceeded (HTTP 403)", "rate_limited"),
            ("gh: Resource not accessible by integration (HTTP 403)", "online_failure"),
        ):
            with self.subTest(expected=expected):
                fixtures = {
                    "repos/acme/blocked": {
                        "error": message,
                        "exit": 1,
                    }
                }
                completed = self.run_helper(
                    fixtures,
                    "--repository",
                    "acme/blocked",
                    "--max-workflows",
                    "5",
                )
                self.assertEqual(completed.returncode, 4)
                document = json.loads(completed.stdout)
                metadata = document["diagnostics"][0]["metadata"]
                ambiguity = metadata["ambiguity"]
                if expected == "rate_limited":
                    self.assertEqual(
                        document["diagnostics"][0]["code"], "rate_limiting"
                    )
                    self.assertEqual(ambiguity, "rate_limited")
                else:
                    self.assertEqual(ambiguity, "forbidden_or_rate_limited")
                self.assertEqual(metadata["http_status"], 403)

    def test_invalid_invocations_are_structured_and_do_not_call_gh(self) -> None:
        completed = self.run_helper({}, "--repository", "acme/app")
        self.assertEqual(completed.returncode, 2)
        document = json.loads(completed.stdout)
        self.assertEqual(document["diagnostics"][0]["code"], "invalid_input")
        self.assertIn("ERROR invalid_input:", completed.stderr)

        completed = self.run_helper(
            {},
            "--repository",
            "acme/app",
            "--max-workflows",
            "1",
            "--output",
            "../outside.json",
        )
        self.assertEqual(completed.returncode, 2)
        document = json.loads(completed.stdout)
        self.assertIn("current working directory", document["diagnostics"][0]["message"])

    def test_missing_pyyaml_is_structured_and_does_not_call_gh(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-S",
                str(HELPER),
                "--repository",
                "acme/app",
                "--max-workflows",
                "1",
            ],
            cwd=PLUGIN_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 4)
        document = json.loads(completed.stdout)
        self.assertEqual(document["coverage"]["status"], "unavailable")
        self.assertEqual(document["diagnostics"][0]["code"], "missing_dependency")
        self.assertIn("PyYAML", document["diagnostics"][0]["message"])
        self.assertIn("ERROR missing_dependency:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
