SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
BLOCKING_SEVERITIES = ("critical", "high")


def make_issue(code, severity, where, message, **details):
    issue = {"code": code, "severity": severity, "where": where, "message": message}
    if details:
        issue["details"] = details
    return issue


def sort_issues(issues):
    return sorted(
        issues,
        key=lambda item: (
            SEVERITY_ORDER.get(item.get("severity"), 99),
            str(item.get("where", "")),
            str(item.get("code", "")),
        ),
    )


def count_by_severity(issues):
    counts = {name: 0 for name in SEVERITY_ORDER}
    for issue in issues:
        severity = issue.get("severity", "info")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def has_blocking(issues, severities=BLOCKING_SEVERITIES):
    return any(issue.get("severity") in severities for issue in issues)
