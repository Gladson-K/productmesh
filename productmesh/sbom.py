import json
from pathlib import Path

from .manifest import as_list, resolve_path

VULNERABILITY_SEVERITIES = ("critical", "high")


def _flatten_cyclonedx(components):
    flattened = []
    for component in components or []:
        if not isinstance(component, dict):
            continue
        flattened.append(component)
        flattened.extend(_flatten_cyclonedx(component.get("components")))
    return flattened


def _licenses_from_cyclonedx(component):
    licenses = []
    for entry in as_list(component.get("licenses")):
        if isinstance(entry, str):
            licenses.append(entry)
        elif isinstance(entry, dict):
            license_data = entry.get("license") or {}
            value = license_data.get("id") or license_data.get("name")
            if value:
                licenses.append(value)
    return licenses


def _licenses_from_spdx(package):
    if not isinstance(package, dict):
        return []
    value = package.get("licenseConcluded") or package.get("licenseDeclared")
    if not value or value == "NOASSERTION":
        return []
    return [value]


def _purl_from_spdx(package):
    for reference in as_list(package.get("externalRefs")):
        if isinstance(reference, dict) and reference.get("referenceType") in ("purl", "PACKAGE-MANAGER"):
            return reference.get("referenceLocator")
    return None


def load_sbom(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("SBOM document must be an object.")
    if data.get("bomFormat") == "CycloneDX" or ("components" in data and "specVersion" in data):
        components = []
        for component in _flatten_cyclonedx(data.get("components")):
            components.append(
                {
                    "name": component.get("name"),
                    "version": component.get("version"),
                    "purl": component.get("purl"),
                    "type": component.get("type"),
                    "licenses": _licenses_from_cyclonedx(component),
                    "bom_ref": component.get("bom-ref"),
                }
            )
        vulnerabilities = []
        for vulnerability in as_list(data.get("vulnerabilities")):
            if not isinstance(vulnerability, dict):
                continue
            ratings = as_list(vulnerability.get("ratings"))
            severities = [rating.get("severity", "").lower() for rating in ratings if isinstance(rating, dict)]
            vulnerabilities.append(
                {
                    "id": vulnerability.get("id"),
                    "severities": [severity for severity in severities if severity],
                    "description": vulnerability.get("description"),
                }
            )
        return {
            "format": "cyclonedx",
            "spec_version": data.get("specVersion"),
            "components": components,
            "vulnerabilities": vulnerabilities,
        }
    if data.get("spdxVersion") or "packages" in data:
        components = []
        for package in as_list(data.get("packages")):
            if not isinstance(package, dict):
                continue
            components.append(
                {
                    "name": package.get("name"),
                    "version": package.get("versionInfo"),
                    "purl": _purl_from_spdx(package),
                    "type": package.get("primaryPackagePurpose"),
                    "licenses": _licenses_from_spdx(package),
                    "bom_ref": package.get("SPDXID"),
                }
            )
        return {
            "format": "spdx",
            "spec_version": data.get("spdxVersion"),
            "components": components,
            "vulnerabilities": [],
        }
    raise ValueError("Unsupported SBOM format; expected CycloneDX or SPDX JSON.")


def _component_keys(component):
    keys = set()
    if component.get("purl"):
        keys.add(str(component["purl"]).lower())
    if component.get("name"):
        name = str(component["name"]).lower()
        keys.add(name)
        if component.get("version"):
            keys.add(f"{name}@{component['version']}")
    return keys


def _index(components):
    index = {}
    for component in components:
        for key in _component_keys(component):
            index.setdefault(key, []).append(component)
    return index


def _find(index, value):
    if not value:
        return []
    return index.get(str(value).lower(), [])


def _declared_components(maps):
    declared = []
    for component in maps["components"].values():
        purl = component.get("purl")
        name = component.get("sbom_name") or component.get("name")
        version = component.get("version")
        if purl or name:
            declared.append({"id": component.get("id"), "purl": purl, "name": name, "version": version})
    return declared


def audit_sbom(manifest, maps, add, base_dir, policy):
    specs = as_list(manifest.get("sboms"))
    if not specs and manifest.get("sbom") is not None:
        specs = as_list(manifest.get("sbom"))
    if not specs and policy.get("require_sbom"):
        add("SBOM_MISSING", "high", "sbom", "SBOM is required but not declared.")
    results = []
    for index, spec in enumerate(specs):
        if isinstance(spec, str):
            spec = {"path": spec}
        elif not isinstance(spec, dict):
            add("SBOM_INVALID", "high", f"sbom[{index}]", "SBOM entry must be a path or object.")
            continue
        where = spec.get("id") or f"sbom[{index}]"
        path_value = spec.get("path")
        if not path_value:
            add("SBOM_MISSING", "high", where, "SBOM entry has no path.")
            continue
        try:
            sbom = load_sbom(resolve_path(base_dir, path_value))
        except Exception as exc:
            add("SBOM_INVALID", "high", where, f"Cannot load SBOM: {exc}")
            results.append({"id": where, "path": path_value, "error": str(exc)})
            continue
        index_by_key = _index(sbom["components"])
        for required in as_list(spec.get("required_components")):
            if not _find(index_by_key, required):
                add("SBOM_REQUIRED_COMPONENT_MISSING", "high", where, f"Required component is missing from SBOM: {required}", component=required)
        for declared in _declared_components(maps):
            matches = _find(index_by_key, declared.get("purl")) or _find(index_by_key, declared.get("name"))
            if not matches:
                if spec.get("check_components", True):
                    add(
                        "SBOM_COMPONENT_MISSING",
                        "high",
                        where,
                        f"Declared component {declared.get('id') or declared.get('name')} is missing from SBOM.",
                        component=declared.get("id"),
                    )
                continue
            if declared.get("version"):
                versions = {str(match.get("version")) for match in matches if match.get("version")}
                if versions and declared["version"] not in versions:
                    add(
                        "SBOM_VERSION_MISMATCH",
                        "high",
                        where,
                        f"Component {declared.get('id') or declared.get('name')} declares {declared['version']} but SBOM has {sorted(versions)}.",
                        expected=declared["version"],
                        actual=sorted(versions),
                    )
        seen = {}
        for component in sbom["components"]:
            key = component.get("purl") or (f"{component.get('name')}@{component.get('version')}" if component.get("name") else None)
            if not key:
                continue
            if key in seen:
                add("SBOM_DUPLICATE_COMPONENT", "medium", where, f"SBOM contains duplicate component {key}.", component=key)
            seen[key] = component
        for vulnerability in as_list(sbom.get("vulnerabilities")):
            if not isinstance(vulnerability, dict):
                continue
            severities = as_list(vulnerability.get("severities"))
            for severity in severities:
                if severity in VULNERABILITY_SEVERITIES:
                    add(
                        "SBOM_VULNERABILITY",
                        "critical" if severity == "critical" else "high",
                        where,
                        f"SBOM reports {severity} vulnerability {vulnerability.get('id')}.",
                        vulnerability=vulnerability.get("id"),
                    )
                    break
        if spec.get("require_licenses", False):
            for component in sbom["components"]:
                if not component.get("licenses"):
                    add(
                        "SBOM_LICENSE_MISSING",
                        "low",
                        where,
                        f"Component has no declared license: {component.get('name')}@{component.get('version')}",
                        component=component.get("name"),
                    )
        results.append(
            {
                "id": where,
                "path": path_value,
                "format": sbom["format"],
                "spec_version": sbom["spec_version"],
                "components": len(sbom["components"]),
                "vulnerabilities": len(sbom["vulnerabilities"]),
            }
        )
    return results
