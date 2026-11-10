from .manifest import resolve_path, sha256_file

PASSING_STATUSES = ("passed", "pass", "ok", "green")
FAILING_STATUSES = ("failed", "fail", "error", "red")
BLOCKED_STATUSES = ("blocked", "not_run", "not-run", "skipped", "pending")


def _test_status(test):
    status = test.get("status")
    return str(status).strip().lower() if status is not None else None


def _evidence_entries(test):
    entries = test.get("evidence") or []
    if isinstance(entries, str):
        entries = [entries]
    normalized = []
    for entry in entries:
        if isinstance(entry, str):
            normalized.append({"path": entry})
        elif isinstance(entry, dict):
            normalized.append(entry)
    return normalized


def audit_evidence(manifest, maps, add, base_dir, policy):
    evidence_count = 0
    for test in maps["tests"].values():
        where = test.get("id")
        status = _test_status(test)
        if status is not None:
            if status in FAILING_STATUSES:
                add("TEST_FAILED", "critical", where, f"Test status is {status}.")
            elif status in BLOCKED_STATUSES:
                add("TEST_BLOCKED", "high", where, f"Test status is {status}.")
            elif status not in PASSING_STATUSES:
                add("TEST_STATUS_INVALID", "medium", where, f"Unknown test status: {status}.")
        for entry in _evidence_entries(test):
            evidence_count += 1
            path_value = entry.get("path")
            if not path_value:
                add("EVIDENCE_MISSING", "high", where, "Evidence entry has no path.")
                continue
            path = resolve_path(base_dir, path_value)
            if not path.is_file():
                add("EVIDENCE_MISSING", "high", where, f"Evidence file is missing: {path_value}")
                continue
            expected = entry.get("sha256")
            if expected:
                actual = sha256_file(path)
                if actual != expected:
                    add(
                        "EVIDENCE_HASH_MISMATCH",
                        "high",
                        where,
                        f"Evidence hash for {path_value} does not match.",
                        expected=expected,
                        actual=actual,
                    )
    if policy.get("require_evidence"):
        for requirement in maps["requirements"].values():
            if not requirement.get("verified_by"):
                continue
            has_evidence = any(
                _evidence_entries(maps["tests"].get(test_id, {}))
                for test_id in requirement.get("verified_by", [])
                if test_id in maps["tests"]
            )
            if not has_evidence:
                add("EVIDENCE_REQUIRED", "high", requirement.get("id"), "Evidence is required but no evidence is attached.")
    for requirement in maps["requirements"].values():
        linked = requirement.get("verified_by") or []
        if not linked:
            continue
        statuses = [_test_status(maps["tests"][test_id]) for test_id in linked if test_id in maps["tests"]]
        known_statuses = [status for status in statuses if status is not None]
        if known_statuses and all(status in FAILING_STATUSES + BLOCKED_STATUSES for status in known_statuses):
            add(
                "REQUIREMENT_NOT_VERIFIED",
                "high",
                requirement.get("id"),
                "All linked verification tests are failed, blocked or not run.",
            )
    return {"evidence": evidence_count}
