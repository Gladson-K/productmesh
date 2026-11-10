from pathlib import Path

from .devices import audit_devices, device_matrix
from .evidence import audit_evidence
from .issues import count_by_severity, make_issue, sort_issues
from .manifest import Manifest, as_list, base_dir_for, load_manifest
from .onnx_meta import audit_models
from .openapi import audit_api_contracts
from .policy import evaluate_gate, merge_policy
from .repo import audit_repositories
from .sbom import audit_sbom

REQUIRED_FIELDS = ("project", "requirements", "components", "interfaces", "environments", "tests")
COLLECTIONS = ("requirements", "components", "interfaces", "environments", "tests")


def _maps(manifest):
    return {name: {item.get("id"): item for item in as_list(manifest.get(name)) if isinstance(item, dict)} for name in COLLECTIONS}


def _audit_core(manifest, maps, add):
    for requirement in maps["requirements"].values():
        if not requirement.get("verified_by"):
            add("REQ_UNVERIFIED", "high", requirement.get("id"), "Requirement has no verification test.")
        for test_id in requirement.get("verified_by") or []:
            if test_id not in maps["tests"]:
                add("TEST_REFERENCE_MISSING", "high", requirement.get("id"), f"Linked test {test_id} does not exist.")
    for component in maps["components"].values():
        if not component.get("id"):
            add("COMPONENT_ID_MISSING", "high", "component", "Component has no id.")
        for interface_id in component.get("interfaces") or []:
            if interface_id not in maps["interfaces"]:
                add("INTERFACE_REFERENCE_MISSING", "high", component.get("id"), f"Unknown interface {interface_id}.")
    for interface in maps["interfaces"].values():
        if not interface.get("id"):
            add("INTERFACE_ID_MISSING", "high", "interface", "Interface has no id.")
        if not interface.get("protocol"):
            add("INTERFACE_PROTOCOL_MISSING", "medium", interface.get("id"), "Interface has no protocol.")
    for environment in maps["environments"].values():
        if not environment.get("id"):
            add("ENVIRONMENT_ID_MISSING", "high", "environment", "Environment has no id.")
    for test in maps["tests"].values():
        if not test.get("id"):
            add("TEST_ID_MISSING", "high", "test", "Test has no id.")
        checks = test.get("checks") or {}
        references = (
            ("requirement", "requirements", "REQUIREMENT_REFERENCE_MISSING"),
            ("interface", "interfaces", "TEST_INTERFACE_MISSING"),
            ("component", "components", "TEST_COMPONENT_MISSING"),
            ("environment", "environments", "TEST_ENVIRONMENT_MISSING"),
        )
        for field, collection, code in references:
            reference = checks.get(field)
            if reference and reference not in maps[collection]:
                add(code, "high", test.get("id"), f"Unknown {field} {reference}.")
        requirement_id = checks.get("requirement")
        if requirement_id in maps["requirements"]:
            linked = maps["requirements"][requirement_id].get("verified_by") or []
            if test.get("id") not in linked:
                add(
                    "TEST_REQUIREMENT_NOT_LINKED",
                    "medium",
                    test.get("id"),
                    f"Test checks {requirement_id} but the requirement does not list this test in verified_by.",
                )
        environment_id = checks.get("environment")
        if environment_id in maps["environments"] and checks.get("voltage"):
            declared = maps["environments"][environment_id].get("logic_voltage")
            if declared not in (None, checks["voltage"]):
                add(
                    "VOLTAGE_MISMATCH",
                    "critical",
                    test.get("id"),
                    f"Expected {checks['voltage']}, environment declares {declared}.",
                    expected=checks["voltage"],
                    actual=declared,
                )
    for component in maps["components"].values():
        for interface_id in component.get("interfaces") or []:
            interface = maps["interfaces"].get(interface_id)
            if not interface:
                continue
            voltage = interface.get("voltage")
            for environment in maps["environments"].values():
                if voltage and environment.get("logic_voltage") and voltage != environment["logic_voltage"]:
                    add(
                        "VOLTAGE_MISMATCH",
                        "critical",
                        component.get("id"),
                        f"Interface {interface_id} requires {voltage}; environment {environment.get('id')} declares {environment['logic_voltage']}.",
                        expected=voltage,
                        actual=environment["logic_voltage"],
                    )
    seen = set()
    for name in COLLECTIONS:
        for item in as_list(manifest.get(name)):
            if not isinstance(item, dict):
                add("OBJECT_INVALID", "high", name, f"{name} entry must be an object.")
                continue
            item_id = item.get("id")
            if item_id in seen:
                add("DUPLICATE_ID", "high", item_id, "ID reused across objects.")
            seen.add(item_id)


def _audit_project(manifest, add):
    project = manifest.get("project")
    if not isinstance(project, dict):
        add("PROJECT_INVALID", "high", "project", "Project must be an object.")
        return
    for field in ("id", "name", "version"):
        if not project.get(field):
            add("PROJECT_FIELD_MISSING", "high", project.get("id", "project"), f"Project is missing {field}.")


def audit(manifest, base_dir=None, policy=None):
    if not isinstance(manifest, Manifest):
        manifest = Manifest(manifest, base_dir=base_dir or Path.cwd())
    missing = [key for key in REQUIRED_FIELDS if key not in manifest]
    if missing:
        raise ValueError(f"Missing top-level field: {missing[0]}")
    base = base_dir_for(manifest, base_dir)
    maps = _maps(manifest)
    issues = []

    def add(code, severity, where, message, **details):
        issues.append(make_issue(code, severity, where, message, **details))

    _audit_project(manifest, add)
    _audit_core(manifest, maps, add)
    devices = audit_devices(manifest, maps, add)
    repositories = audit_repositories(manifest, maps, add, base)
    api_contracts = audit_api_contracts(manifest, maps, add, base, merge_policy(manifest, policy))
    sboms = audit_sbom(manifest, maps, add, base, merge_policy(manifest, policy))
    models = audit_models(manifest, maps, add, base)
    evidence = audit_evidence(manifest, maps, add, base, merge_policy(manifest, policy))

    issues = sort_issues(issues)
    counts = count_by_severity(issues)
    gate = evaluate_gate(issues, merge_policy(manifest, policy))
    summary = {
        "issues": len(issues),
        "high_or_critical": counts.get("critical", 0) + counts.get("high", 0),
        "requirements": len(maps["requirements"]),
        "components": len(maps["components"]),
        "interfaces": len(maps["interfaces"]),
        "environments": len(maps["environments"]),
        "tests": len(maps["tests"]),
        "devices": len(devices),
        "repositories": len(repositories),
        "api_contracts": len(api_contracts),
        "sboms": len(sboms),
        "models": len(models),
        "evidence": evidence.get("evidence", 0),
        "by_severity": counts,
    }
    return {
        "schema_version": manifest.get("schema_version"),
        "project": manifest.get("project"),
        "summary": summary,
        "issues": issues,
        "release_ready": gate["ready"],
        "gate": gate,
        "devices": device_matrix(manifest),
        "repositories": repositories,
        "api_contracts": api_contracts,
        "sboms": sboms,
        "models": models,
    }


def audit_file(path, policy=None):
    return audit(load_manifest(path), policy=policy)
