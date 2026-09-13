import json
import re


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def claims(pattern: str, text: str) -> bool:
    for clause in re.split(r"(?<=[.!?;])\s+|[,\n]|\b(?:but|however|and)\b", text):
        for match in re.finditer(pattern, clause, re.IGNORECASE):
            assertion = re.sub(r"^no\s+", "", match.group(), flags=re.IGNORECASE)
            prefix = clause[:match.start()] + assertion
            if not has(r"\b(?:no|not|never|cannot|can't|couldn't|doesn't|didn't|without|avoid)\b", prefix):
                return True
    return False


def case_invariants(case: dict, response: dict) -> dict[str, bool]:
    text = "\n".join([
        response["diagnosis"], *response["findings"], *response["limitations"],
        response["recommendation"]["rationale"],
    ]).replace("`", "").replace("’", "'")
    changes = response["proposedChanges"]
    plan = "\n".join([
        response["recommendation"]["rationale"],
        *(change["summary"] for change in changes),
        *(value for change in changes for value in change["preserves"]),
    ]).replace("`", "")
    checks = {
        "preserveSafetyBoundaries": not claims(
            r"\b(?:remove|disable|drop|bypass|discard)\b.{0,45}\b"
            r"(?:approvals?|gates?|permissions?|secrets?|credentials?|outputs?|digest)\b"
            r"|\bunpin\b.{0,30}\b(?:action|sha|commit)\b", plan
        ),
    }
    if case["id"] != "justified-extraction-preserves-contracts":
        checks["noUnwarrantedChanges"] = (
            response["recommendation"]["action"] != "change" and not changes
        )

    match case["id"]:
        case "current-yaml-differs-from-execution":
            checks.update({
                "distinguishesRevisions": has(
                    r"(?:different|distinct|mismatch|not the same).{0,30}(?:commit|revision)"
                    r"|aaaaaaa.{0,200}bbbbbbb", text
                ),
                "identifiesTestFailure": claims(r"(?:test|npm).{0,80}(?:fail|exit.{0,15}\b1\b)", text),
                "doesNotAttributeFailureToCurrentYaml": not claims(
                    r"(?:current|checked.out|bbbbbbb).{0,35}(?:yaml|workflow|revision)"
                    r".{0,30}(?:caused|explains).{0,30}fail", text
                ),
            })
        case "failure-only-earlier-attempt":
            checks.update({
                "earlierAttemptFailed": claims(r"(?:attempt\s*1|first attempt).{0,40}fail", text),
                "latestAttemptSucceeded": claims(
                    r"(?:attempt\s*2|second attempt|latest.{0,15}attempt|run\s*420|rerun)"
                    r".{0,50}(?:success|succeed|green)", text
                ),
                "noStaleCurrentFailure": not claims(
                    r"(?:latest|current|second|attempt\s*2).{0,20}"
                    r"(?:is|was|remains)\s+(?:a\s+)?(?:fail\w*|broken)", text
                ),
            })
        case "approval-wait-vs-runner-queue":
            checks.update({
                "identifiesApprovalWait": has(r"approv|reviewer|environment protection", text),
                "doesNotBlameCapacity": not claims(
                    r"runner.{0,15}(?:capacity|queue).{0,30}(?:bottleneck|shortage|cause)"
                    r"|(?:buy|add|increase).{0,20}(?:runners|runner capacity)", plan + "\n" + text
                ),
            })
        case "missing-skipped-required-context":
            checks.update({
                "identifiesSkippedPublish": has(r"publish.{0,50}skip|skip.{0,30}publish", text),
                "identifiesMissingInput": has(
                    r"(?:input|release_tag).{0,50}(?:missing|absent|empty|not supplied)"
                    r"|(?:missing|absent|empty|no).{0,30}(?:input|release_tag)", text
                ),
                "doesNotClaimPublication": not claims(
                    r"publish(?:ing)?(?:\s+(?:job|step))?\s+(?:was\s+)?"
                    r"(?:succeeded|successful|executed|ran)", text
                ),
            })
        case "safe-metadata-only-privileged-workflow":
            checks.update({
                "identifiesMetadataOperation": has(r"metadata|label|triage", text),
                "identifiesExecutionBoundary": has(
                    r"(?:no|without).{0,40}(?:checkout|check.out|untrusted.{0,20}execution)"
                    r"|(?:does not|doesn't|never).{0,40}(?:check out|execut.{0,30}(?:pull.request|untrusted))",
                    text,
                ),
                "doesNotInventExploit": not claims(
                    r"(?:workflow|trigger).{0,25}(?:is|has)\s+(?:a\s+)?(?:vulnerab|unsafe)"
                    r"|\buntrusted code execution\b", text
                ),
            })
        case "scanner-hard-failure":
            checks.update({
                "identifiesIncompleteScan": has(
                    r"(?:fail|unable|could not|couldn't).{0,35}pars"
                    r"|(?:scan|analysis|assessment).{0,35}(?:incomplete|did not complete|aborted)", text
                ),
                "doesNotDeclareClean": not claims(
                    r"(?:workflow|scan|result|assessment)\s+(?:is|was|looks|appears)\s+"
                    r"(?:clean|secure|safe|successful|complete)"
                    r"|\bno (?:security )?(?:findings|vulnerabilities) (?:were found|exist)\b", text
                ),
                "withholdsSecurityConclusion": has(
                    r"(?:not|cannot|can't|no).{0,90}(?:clean|security assessment|security conclusion)"
                    r"|no conclusion.{0,40}(?:drawn|possible)", text
                ),
            })
        case "large-run-prior-attempts":
            checks.update({
                "reportsAllJobs": has(r"\b(?:42|forty.two)\b.{0,25}(?:job|matrix)|(?:job|matrix).{0,25}\b42\b", text),
                "reportsAttemptHistory": has(
                    r"(?:three|3).{0,20}attempt|attempts?\s*1.{0,25}\b2\b.{0,25}\b3\b", text
                ),
                "doesNotTruncateCoverage": not claims(r"(?:only|total of|exactly)\s+30\s+jobs", text),
            })
        case "free-unknown-rate-no-invented-savings":
            durations = json.loads(case["fixture"]["files"]["durations.json"])
            checks.update({
                "recognizesZeroHostedBilling": has(
                    r"(?:zero|0).{0,30}(?:hosted|billed)"
                    r"|hosted.{0,70}(?:zero|free|no charge|billed.{0,10}\b0\b)", text
                ),
                "recognizesUnknownRate": has(
                    r"(?:self.hosted|hourly rate).{0,90}(?:unknown|unspecified|unavailable|not supplied|no.{0,10}rate)"
                    r"|(?:no|unknown|unspecified).{0,40}self.hosted.{0,20}rate"
                    r"|self.hosted cost.{0,20}cannot", text
                ),
                "reportsCandidateTime": has(
                    r"\b(?:5|five)[ -]minutes?\b|\b300[ -]seconds?\b"
                    r"|\bcandidate_reduction_minutes\b['\"]?\s*"
                    r"(?:(?:value\s+(?:of\s+)?)|[:=]\s*|is\s+)?5\b", text
                ),
                "doesNotInventMoney": not claims(
                    r"[$£€]\s*[1-9]\d*(?:\.\d+)?"
                    r"|\b[1-9]\d*(?:\.\d+)?\s*(?:dollars?|USD)\b"
                    r"|\b(?:cost|savings?|save)\b.{0,30}\b\d+\s*%", text
                ),
                "keepsMinuteUnits": not any(
                    claims(
                        rf"\b{job}\b.{{0,50}}\b{durations[key]}\s*(?:seconds?|secs?)\b", text
                    )
                    for job, key in (("hosted", "hosted_minutes"), ("self.hosted", "self_hosted_minutes"))
                ) and not claims(
                    r"(?:candidate|reduction|saving).{0,40}\b(?:5|five)[ -](?:seconds?|secs?)\b", text
                ),
            })
        case "string-environment-concurrency":
            checks.update({
                "recognizesScalarSyntax": has(r"\b(?:string|scalar|shorthand)\b", text)
                and claims(r"\b(?:valid|supported|accepted|legal|allowed|coherent|consistent)\b", text),
                "doesNotDemandMappingSyntax": not claims(
                    r"(?:environment|concurrency|schema).{0,35}"
                    r"(?:invalid|must be (?:an? )?(?:object|mapping))", text
                ),
                "doesNotGuaranteePendingOrder": not (
                    claims(r"(?:preserv|retain|keep).{0,35}(?:pending|queued)"
                           r"|(?:preserv|guarantee).{0,30}(?:deployment )?order"
                           r"|(?:FIFO|ordering).{0,20}(?:is guaranteed|is preserved)", text)
                    or has(r"(?:pending|queued).{0,40}(?:never|not|cannot|can't).{0,25}(?:cancel|replac)", text)
                ),
            })
        case "unreadable-reusable-callee":
            checks.update({
                "recognizesAccessBoundary": has(r"404|inaccessible|unreadable|could not.{0,20}(?:fetch|retriev)", text),
                "withholdsCalleeContract": has(
                    r"(?:contract|callee|definition|behavior).{0,70}"
                    r"(?:unknown|unverified|cannot|could not|inaccessible|not.{0,20}(?:assess|verif))"
                    r"|(?:cannot|can't|could not).{0,40}(?:assess|verif|inspect).{0,40}(?:callee|contract|called workflow)",
                    text,
                ),
                "doesNotInventCalleeAssurance": not claims(
                    r"callee.{0,20}(?:is|was|verified as)\s+(?:secure|safe|validated)", text
                ),
            })
        case "justified-extraction-preserves-contracts":
            preserved = "\n".join(value for change in changes for value in change["preserves"])
            checks["offersRefactorProposal"] = response["recommendation"]["action"] == "change" and bool(changes)
            checks["identifiesSharedPattern"] = has(r"duplicat|repetit|shared|same.{0,30}(?:job|contract)", text)
            for contract, pattern in {
                "Inputs": r"input|parameter|service.specific",
                "Secrets": r"secret|credential|authentication material",
                "Permissions": r"permission|privilege|token.{0,20}scope",
                "Outputs": r"output|digest",
                "Environment": r"environment|production.{0,20}approv|deployment.{0,20}gate",
            }.items():
                checks[f"preserves{contract}"] = has(pattern, preserved)
        case "healthy-small-estate-unchanged":
            checks.update({
                "recognizesHealthyEvidence": has(
                    r"healthy|(?:no|not).{0,60}(?:measured|material|performance|reliability).{0,30}"
                    r"(?:problem|issue|change|finding|warrant)", text
                ),
                "doesNotInventCriticalFinding": not claims(
                    r"\b(?:critical|severe|exploitable)\b.{0,30}(?:vulnerability|security flaw)"
                    r"|workflow.{0,15}is insecure", text
                ),
            })
        case _:
            raise ValueError(f"No invariants defined for case {case['id']}")
    return checks
