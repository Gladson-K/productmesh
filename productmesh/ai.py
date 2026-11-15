RECOMMENDATIONS = {
    "VOLTAGE_MISMATCH": ("Align interface, device and environment logic voltage", "critical"),
    "DEVICE_VOLTAGE_MISMATCH": ("Change the device voltage or the interface contract", "critical"),
    "DEVICE_ENV_VOLTAGE_MISMATCH": ("Reconcile the device and environment voltage declarations", "critical"),
    "PIN_CONFLICT": ("Move one interface to a free pin or mark the pin as shared", "high"),
    "BUS_ADDRESS_CONFLICT": ("Reassign the I2C/SPI address or isolate the bus segment", "high"),
    "POWER_BUDGET_EXCEEDED": ("Reduce current draw, raise the budget or split the power rail", "high"),
    "REPO_DIRTY": ("Commit or stash local changes before release", "high"),
    "REPO_COMMIT_MISMATCH": ("Check out the declared commit or update the manifest", "high"),
    "API_PATH_REMOVED": ("Restore the path or version the API and client together", "critical"),
    "API_REQUIRED_FIELD_ADDED": ("Make the field optional or coordinate a client migration", "high"),
    "SBOM_COMPONENT_MISSING": ("Regenerate the SBOM or update the declared component", "high"),
    "SBOM_VULNERABILITY": ("Patch, upgrade or document the vulnerable dependency", "critical"),
    "MODEL_HASH_MISMATCH": ("Rebuild the model or update the declared artifact hash", "high"),
    "MODEL_INPUT_SHAPE_MISMATCH": ("Re-export the model with the expected input contract", "high"),
    "FIRMWARE_HASH_MISMATCH": ("Rebuild the firmware or update the declared hash", "high"),
    "BENCHMARK_LATENCY_REGRESSION": ("Profile the runtime, reduce model size or relax the latency limit", "high"),
    "BENCHMARK_THROUGHPUT_REGRESSION": ("Check runtime settings and accelerator configuration", "high"),
    "TEST_FAILED": ("Fix the failing verification test before release", "critical"),
    "EVIDENCE_MISSING": ("Attach reproducible verification evidence", "high"),
}


def recommend(issues):
    recommendations = []
    for issue in issues:
        code = issue.get("code")
        title, priority = RECOMMENDATIONS.get(
            code,
            ("Review the issue details and update the declaration or artifact", "medium"),
        )
        recommendations.append(
            {
                "code": code,
                "where": issue.get("where"),
                "severity": issue.get("severity"),
                "priority": priority,
                "recommendation": title,
                "status": "stub",
            }
        )
    return recommendations


def root_causes(issues):
    groups = {}
    for issue in issues:
        where = str(issue.get("where") or "unknown")
        product = issue.get("product") or where.split(":", 1)[0]
        groups.setdefault(product, []).append(issue.get("code"))
    return [
        {"product": product, "issue_count": len(codes), "codes": sorted(set(codes))}
        for product, codes in sorted(groups.items())
    ]


def analyze(result):
    issues = result.get("issues") or []
    return {
        "status": "stub",
        "method": "deterministic heuristic",
        "release_ready": result.get("release_ready"),
        "root_causes": root_causes(issues),
        "recommendations": recommend(issues),
    }
