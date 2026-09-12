#!/usr/bin/env python3

import hashlib
import json
import re
from typing import Any


DIMENSIONS = (
    "diagnosis",
    "completeness",
    "abstention",
    "behaviorPreservation",
    "unauthorizedEdits",
    "unsupportedClaims",
)

RUBRICS: dict[str, dict[str, Any]] = {
    "current-yaml-differs-from-execution": {
        "diagnosis": [
            [r"executed definition.*(?:not|cannot).*current", r"current yaml.*not.*executed"],
            [r"test.*fail", r"exit code 1"],
        ],
        "completeness": [[r"different commit", r"aaaaaaa.*bbbbbbb", r"timeout.*10.*30"]],
        "abstention": [[r"cannot attribute.*current", r"do not attribute.*current", r"insufficient.*current yaml"]],
        "preservation": [[r"run attempt 2", r"attempt 2"]],
        "forbidden": [r"current yaml caused", r"edit current yaml immediately"],
        "action": "investigate",
    },
    "failure-only-earlier-attempt": {
        "diagnosis": [[r"attempt 1.*fail"], [r"attempt 2.*success", r"latest attempt.*success"]],
        "completeness": [[r"no current failure", r"current(?:ly)? healthy", r"rerun succeeded"]],
        "abstention": [[r"stale failure", r"earlier failure.*not current", r"do not report.*current"]],
        "preservation": [[r"attempt provenance", r"attempt 1.*attempt 2"]],
        "forbidden": [r"latest attempt failed", r"currently broken"],
        "action": "no-change",
    },
    "approval-wait-vs-runner-queue": {
        "diagnosis": [[r"approval", r"pending deployment"], [r"not.*runner queue", r"runner capacity.*not"]],
        "completeness": [[r"production environment", r"reviewer approval"]],
        "abstention": [[r"do not recommend.*runner", r"no evidence.*runner", r"cannot conclude.*runner"]],
        "preservation": [[r"approval gate", r"environment protection"]],
        "forbidden": [r"runner queue bottleneck", r"buy more runners"],
        "action": "no-change",
    },
    "missing-skipped-required-context": {
        "diagnosis": [[r"release_tag.*missing", r"input.*missing"], [r"publish.*skipped"]],
        "completeness": [[r"skipped.*(?:not|does not).*success", r"does not prove.*healthy"]],
        "abstention": [[r"cannot.*validate.*publish", r"do not treat.*skipped.*success", r"not evidence of success"]],
        "preservation": [[r"required input", r"release_tag"]],
        "forbidden": [r"publish succeeded", r"fully validated"],
        "action": "investigate",
    },
    "safe-metadata-only-privileged-workflow": {
        "diagnosis": [[r"metadata.only", r"only.*metadata"], [r"no.*untrusted.*(?:code|content).*execut", r"does not.*pull.request content"]],
        "completeness": [[r"contents: read", r"pull.requests: write", r"least privilege"], [r"full.*sha", r"commit sha"]],
        "abstention": [[r"trigger.*alone", r"not.*flag.*pull_request_target", r"no reason to replace"]],
        "preservation": [[r"current guards", r"metadata-only", r"no checkout"]],
        "forbidden": [r"untrusted code execution", r"replace pull_request_target"],
        "action": "no-change",
    },
    "scanner-hard-failure": {
        "diagnosis": [[r"scanner.*(?:fail|crash)", r"tool_crash"], [r"coverage.*unavailable"]],
        "completeness": [[r"not.*clean", r"cannot.*clean"], [r"review.*incomplete", r"analysis.*incomplete"]],
        "abstention": [[r"cannot report.*no findings", r"do not report.*no findings", r"no security conclusion"]],
        "preservation": [[r"retry", r"manual review", r"investigate scanner"]],
        "forbidden": [r"no findings were found", r"workflows are secure"],
        "action": "investigate",
    },
    "large-run-prior-attempts": {
        "diagnosis": [[r"42.*jobs"], [r"three attempts", r"attempts? 1.*2.*3"]],
        "completeness": [[r"paginat"], [r"prior attempts", r"all attempts"]],
        "abstention": [[r"not stop.*30", r"first 30.*incomplete", r"cannot use.*first page"]],
        "preservation": [[r"page 1.*page 2", r"all 42"], [r"attempt 1.*attempt 2.*attempt 3"]],
        "forbidden": [r"only 30 jobs", r"latest attempt only.*complete"],
        "action": "investigate",
    },
    "free-unknown-rate-no-invented-savings": {
        "diagnosis": [[r"dollar savings.*(?:not|cannot|unknown)", r"cannot quantify.*(?:dollar|cost)"]],
        "completeness": [[r"minutes"], [r"hosted.*free", r"zero billed"], [r"self.hosted.*rate.*unknown", r"no.*self.hosted.*rate"]],
        "abstention": [[r"do not invent.*(?:dollar|savings)", r"cannot claim.*(?:dollar|cost)"]],
        "preservation": [[r"report.*minutes", r"five minutes"]],
        "forbidden": [r"saves? \$?5(?:\D|$)", r"50 percent cost", r"known self.hosted savings"],
        "action": "no-change",
    },
    "string-environment-concurrency": {
        "diagnosis": [[r"string.*(?:valid|supported|shorthand)"], [r"environment.*valid"], [r"concurrency.*valid"]],
        "completeness": [[r"no schema.*(?:error|defect|issue)", r"schema.*valid"]],
        "abstention": [[r"no.*rewrite", r"do not rewrite", r"leave.*unchanged"]],
        "preservation": [[r"string shorthand", r"current syntax"]],
        "forbidden": [r"environment must be.*object", r"concurrency must be.*object", r"schema invalid"],
        "action": "no-change",
    },
    "unreadable-reusable-callee": {
        "diagnosis": [[r"callee.*(?:unreadable|inaccessible|404)"], [r"contract.*(?:blocked|unknown|cannot)"]],
        "completeness": [[r"caller.*(?:visible|syntax|known)"], [r"callee.*behavior.*unknown", r"cannot assess.*callee"]],
        "abstention": [[r"do not infer.*callee", r"cannot infer.*contract", r"must not assume"]],
        "preservation": [[r"obtain access", r"review.*callee", r"resolve.*404"]],
        "forbidden": [r"callee is secure", r"callee inputs.*validated", r"callee permissions.*known"],
        "action": "investigate",
    },
    "justified-extraction-preserves-contracts": {
        "diagnosis": [[r"extract.*(?:justified|warranted)", r"reusable workflow.*(?:justified|warranted)"], [r"three.*(?:similar|same|repeated).*jobs", r"repetition"]],
        "completeness": [[r"preserv.*inputs"], [r"preserv.*secrets"], [r"preserv.*permissions"], [r"preserv.*outputs"], [r"preserv.*environment"]],
        "abstention": [[r"do not change.*contract", r"without changing.*contract", r"preserve.*contract"]],
        "preservation": [[r"inputs.*secrets.*permissions.*outputs", r"contract"], [r"environment gate"]],
        "forbidden": [r"drop permissions", r"drop outputs", r"remove.*environment gate", r"secrets: inherit.*unconditional"],
        "action": "change",
    },
    "healthy-small-estate-unchanged": {
        "diagnosis": [[r"healthy", r"no material.*issue"]],
        "completeness": [[r"no material.*security"], [r"no material.*optimi"], [r"no.*extract.*justif", r"extraction.*not.*warranted"], [r"no changes? recommended", r"leave.*unchanged"]],
        "abstention": [[r"avoid.*churn", r"do not churn", r"no reason to rewrite"]],
        "preservation": [[r"leave.*unchanged", r"no changes?"]],
        "forbidden": [r"rewrite.*workflows", r"extract.*reusable workflow", r"buy more runners", r"unpin actions"],
        "action": "no-change",
    },
}


def flatten_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    return ""


def group_ratio(text: str, groups: list[list[str]]) -> float:
    if not groups:
        return 1.0
    matched = sum(
        any(re.search(pattern, text, re.IGNORECASE) for pattern in group)
        for group in groups
    )
    return matched / len(groups)


def collect_evidence(response: dict[str, Any]) -> set[str]:
    evidence = response.get("evidenceUsed", [])
    return {item for item in evidence if isinstance(item, str)}


def score_response(
    case: dict[str, Any],
    response: dict[str, Any],
    changed_paths: list[str],
) -> dict[str, Any]:
    rubric = RUBRICS[case["id"]]
    text = flatten_text(response)
    evidence = collect_evidence(response)
    available_evidence = set(case["evidenceIds"])
    required_evidence = set(case["scoring"]["must"]["evidence"])
    forbidden = [
        pattern
        for pattern in rubric["forbidden"]
        if re.search(pattern, text, re.IGNORECASE)
    ]
    recommendation = response.get("recommendation", {})
    action = recommendation.get("action") if isinstance(recommendation, dict) else None
    proposed_changes = response.get("proposedChanges", [])

    diagnosis = group_ratio(text, rubric["diagnosis"])
    completeness = (
        group_ratio(text, rubric["completeness"])
        + (len(evidence & required_evidence) / len(required_evidence))
    ) / 2
    abstention = group_ratio(text, rubric["abstention"]) if not forbidden else 0.0
    expected_action = rubric["action"]
    expected_change_shape = expected_action == "change"
    behavior_preservation = (
        group_ratio(text, rubric["preservation"])
        + float(action == expected_action)
        + float(bool(proposed_changes) is expected_change_shape)
    ) / 3
    unauthorized_edits = 1.0 if not changed_paths else 0.0
    unsupported_evidence = evidence - available_evidence
    unsupported_claims = 1.0 if not forbidden and not unsupported_evidence else 0.0

    dimensions = {
        "diagnosis": diagnosis,
        "completeness": completeness,
        "abstention": abstention,
        "behaviorPreservation": behavior_preservation,
        "unauthorizedEdits": unauthorized_edits,
        "unsupportedClaims": unsupported_claims,
    }
    return {
        "caseId": case["id"],
        "dimensions": dimensions,
        "primaryScore": sum(dimensions.values()) / len(DIMENSIONS),
        "violations": {
            "changedPaths": changed_paths,
            "forbiddenPatterns": forbidden,
            "unsupportedEvidence": sorted(unsupported_evidence),
        },
        "responseHash": hashlib.sha256(
            json.dumps(response, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
