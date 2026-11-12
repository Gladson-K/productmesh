PROFILES = {
    "on_prem": {
        "name": "on_prem",
        "deployment": "self-hosted",
        "sso": True,
        "audit_export": True,
        "rbac": True,
        "retention_days": 365,
        "data_residency": "customer",
    },
    "hybrid": {
        "name": "hybrid",
        "deployment": "hybrid",
        "sso": True,
        "audit_export": True,
        "rbac": True,
        "retention_days": 180,
        "data_residency": "regional",
    },
    "saas": {
        "name": "saas",
        "deployment": "managed",
        "sso": True,
        "audit_export": False,
        "rbac": True,
        "retention_days": 90,
        "data_residency": "vendor",
    },
}


def get_profile(name):
    profile = PROFILES.get(str(name).lower())
    if profile is None:
        raise ValueError(f"Unknown enterprise profile: {name}")
    return dict(profile, status="stub")


def check_governance(profile_name, controls=None):
    profile = get_profile(profile_name)
    controls = controls or {}
    issues = []
    for key in ("sso", "audit_export", "rbac"):
        if profile.get(key) and not controls.get(key):
            issues.append(
                {
                    "code": f"GOVERNANCE_{key.upper()}_MISSING",
                    "severity": "high",
                    "message": f"{key} is required by the {profile_name} profile.",
                }
            )
    retention = controls.get("retention_days")
    if retention is not None and retention < profile.get("retention_days", 0):
        issues.append(
            {
                "code": "GOVERNANCE_RETENTION_SHORT",
                "severity": "high",
                "message": f"Retention {retention} days is below the {profile['retention_days']} day profile minimum.",
            }
        )
    return {
        "status": "stub",
        "profile": profile,
        "controls": controls,
        "ready": not issues,
        "issues": issues,
    }
