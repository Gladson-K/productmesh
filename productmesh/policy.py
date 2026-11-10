from .issues import count_by_severity

LEGACY_POLICY_KEYS = {
    "block_on_critical_severity": "block_on_critical",
    "block_on_high_severity": "block_on_high",
    "block_on_medium_severity": "block_on_medium",
    "block_on_low_severity": "block_on_low",
}

DEFAULT_POLICY = {
    "block_on_critical": True,
    "block_on_high": True,
    "block_on_medium": False,
    "block_on_low": False,
    "max_critical": 0,
    "max_high": 0,
    "max_medium": 0,
    "allow_dirty_repo": False,
    "require_sbom": False,
    "require_openapi": False,
    "require_evidence": False,
    "required_requirements": [],
}


def merge_policy(manifest=None, override=None):
    policy = dict(DEFAULT_POLICY)
    if isinstance(manifest, dict):
        declared = manifest.get("release")
        if isinstance(declared, dict):
            declared = dict(declared)
            for legacy, canonical in LEGACY_POLICY_KEYS.items():
                if legacy in declared and canonical not in declared:
                    declared[canonical] = declared[legacy]
            policy.update(declared)
    if isinstance(override, dict):
        policy.update(override)
    return policy


def _limit_exceeded(count, limit):
    return limit is not None and count > limit


def evaluate_gate(issues, policy):
    counts = count_by_severity(issues)
    blockers = []
    if policy.get("block_on_critical"):
        limit = policy.get("max_critical")
        limit = 0 if limit is None else limit
        if _limit_exceeded(counts.get("critical", 0), limit):
            blockers.append(f"critical issues: {counts.get('critical', 0)} > {limit}")
    if policy.get("block_on_high"):
        limit = policy.get("max_high")
        limit = 0 if limit is None else limit
        if _limit_exceeded(counts.get("high", 0), limit):
            blockers.append(f"high issues: {counts.get('high', 0)} > {limit}")
    if policy.get("block_on_medium"):
        limit = policy.get("max_medium")
        limit = 0 if limit is None else limit
        if _limit_exceeded(counts.get("medium", 0), limit):
            blockers.append(f"medium issues: {counts.get('medium', 0)} > {limit}")
    if policy.get("block_on_low") and counts.get("low", 0):
        blockers.append(f"low issues: {counts.get('low', 0)}")
    if not policy.get("allow_dirty_repo", False):
        dirty = [issue for issue in issues if issue.get("code") == "REPO_DIRTY" and issue.get("severity") in ("critical", "high")]
        if dirty:
            blockers.append(f"dirty repositories: {len(dirty)}")
    if policy.get("require_sbom"):
        missing = [issue for issue in issues if issue.get("code") == "SBOM_MISSING"]
        if missing:
            blockers.append("SBOM required but missing")
    if policy.get("require_openapi"):
        missing = [issue for issue in issues if issue.get("code") in ("API_SPEC_MISSING", "API_INTERFACE_MISSING")]
        if missing:
            blockers.append("OpenAPI contract required but missing")
    if policy.get("require_evidence"):
        missing = [issue for issue in issues if issue.get("code") in ("EVIDENCE_MISSING", "EVIDENCE_REQUIRED")]
        if missing:
            blockers.append("evidence required but missing")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "counts": counts,
        "policy": policy,
        "blocking_issues": bool(blockers),
    }
