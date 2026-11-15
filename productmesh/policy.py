from .issues import count_by_severity
from .manifest import load_data

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


BOOLEAN_KEYS = (
    "block_on_critical",
    "block_on_high",
    "block_on_medium",
    "block_on_low",
    "allow_dirty_repo",
    "require_sbom",
    "require_openapi",
    "require_evidence",
)
INTEGER_KEYS = ("max_critical", "max_high", "max_medium")


def load_policy(path):
    data = load_data(path)
    if not isinstance(data, dict):
        raise TypeError("Release policy must be an object.")
    return merge_policy(override=data)


def validate_policy(policy):
    errors = []
    for key in BOOLEAN_KEYS:
        if key in policy and not isinstance(policy[key], bool):
            errors.append({"path": key, "message": "Expected a boolean."})
    for key in INTEGER_KEYS:
        if key in policy and policy[key] is not None and not isinstance(policy[key], int):
            errors.append({"path": key, "message": "Expected an integer or null."})
    if "required_requirements" in policy and not isinstance(policy["required_requirements"], list):
        errors.append({"path": "required_requirements", "message": "Expected an array."})
    return {"valid": not errors, "errors": errors, "policy": policy, "status": "stub"}


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
