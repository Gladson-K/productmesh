import json
from pathlib import Path

from . import __version__

SARIF_LEVELS = {"critical": "error", "high": "error", "medium": "warning", "low": "note", "info": "note"}


def to_sarif(result):
    issues = result.get("issues") or []
    results = []
    for issue in issues:
        location = str(issue.get("where") or result.get("project", {}).get("id") or "productmesh")
        results.append(
            {
                "ruleId": issue.get("code"),
                "level": SARIF_LEVELS.get(issue.get("severity"), "warning"),
                "message": {"text": issue.get("message", "")},
                "properties": {"severity": issue.get("severity")},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": location}}}],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ProductMesh", "version": __version__, "informationUri": "https://github.com/productmesh/productmesh"}},
                "results": results,
                "properties": {"release_ready": result.get("release_ready"), "summary": result.get("summary")},
            }
        ],
    }


def to_markdown(result):
    lines = []
    if "workspace" in result:
        workspace = result.get("workspace") or {}
        lines.append(f"# {workspace.get('name', 'ProductMesh workspace')}")
        lines.append("")
        summary = result.get("summary", {})
        lines.append(f"- Products: {summary.get('products', 0)}")
        lines.append(f"- Ready: {summary.get('ready', 0)}")
        lines.append(f"- Blocked: {summary.get('blocked', 0)}")
        lines.append(f"- Issues: {summary.get('issues', 0)}")
        lines.append(f"- Release ready: {result.get('release_ready')}")
        lines.append("")
        lines.append("| Product | Release | Issues |")
        lines.append("| --- | --- | --- |")
        for product in result.get("products", []):
            lines.append(f"| {product.get('id')} | {'READY' if product.get('release_ready') else 'BLOCKED'} | {product.get('issues', 0)} |")
        if result.get("devices"):
            lines.append("")
            lines.append("| Product | Device | Board | Firmware | Voltage | Status |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for device in result["devices"]:
                lines.append(
                    f"| {device.get('product')} | {device.get('id')} | {device.get('board')} | {device.get('firmware')} | {device.get('logic_voltage')} | {device.get('status')} |"
                )
    else:
        project = result.get("project") or {}
        lines.append(f"# {project.get('name', 'ProductMesh audit')}")
        lines.append("")
        summary = result.get("summary", {})
        lines.append(f"- Release ready: {result.get('release_ready')}")
        lines.append(f"- Issues: {summary.get('issues', 0)}")
        lines.append(f"- High/critical: {summary.get('high_or_critical', 0)}")
        lines.append(f"- Devices: {summary.get('devices', 0)}")
    lines.append("")
    if result.get("issues"):
        lines.append("| Severity | Code | Where | Message |")
        lines.append("| --- | --- | --- | --- |")
        for issue in result["issues"]:
            message = str(issue.get("message", "")).replace("|", "\\|")
            lines.append(f"| {issue.get('severity')} | {issue.get('code')} | {issue.get('where')} | {message} |")
    else:
        lines.append("No consistency issues found.")
    return "\n".join(lines) + "\n"


def render(result, fmt="json"):
    if fmt == "json":
        return json.dumps(result, indent=2)
    if fmt == "sarif":
        return json.dumps(to_sarif(result), indent=2)
    if fmt in ("markdown", "md"):
        return to_markdown(result)
    raise ValueError(f"Unknown report format: {fmt}")


def write_report(content, path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
