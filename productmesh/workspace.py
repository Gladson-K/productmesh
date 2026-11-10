from pathlib import Path

from .audit import audit
from .issues import count_by_severity, make_issue, sort_issues
from .manifest import Workspace, as_list, load_manifest, load_workspace, resolve_path
from .policy import evaluate_gate, merge_policy


def discover_workspace(directory):
    base = Path(directory).resolve()
    explicit = base / "workspace.json"
    if explicit.is_file():
        return load_workspace(explicit)
    manifests = sorted(base.glob("*/product.json"))
    if not manifests:
        raise ValueError(f"No workspace.json or */product.json found under {base}")
    products = [{"id": path.parent.name, "manifest": str(path.relative_to(base))} for path in manifests]
    return Workspace(
        {
            "schema_version": "2.0",
            "workspace": {"id": base.name, "name": base.name},
            "products": products,
        },
        base_dir=base,
        source_path=explicit,
    )


def load_workspace_or_discover(path=None):
    if path:
        target = Path(path).resolve()
        if target.is_dir():
            return discover_workspace(target)
        return load_workspace(target)
    return discover_workspace(Path.cwd())


def workspace_products(workspace):
    if not isinstance(workspace, Workspace):
        workspace = Workspace(workspace)
    entries = as_list(workspace.get("products"))
    products = []
    for index, entry in enumerate(entries):
        if isinstance(entry, str):
            entry = {"manifest": entry}
        elif not isinstance(entry, dict):
            continue
        manifest_value = entry.get("manifest") or entry.get("path")
        if not manifest_value:
            continue
        product_id = entry.get("id") or Path(manifest_value).parent.name or f"product[{index}]"
        products.append(
            {
                "id": product_id,
                "manifest": manifest_value,
                "path": resolve_path(workspace.base_dir, manifest_value),
                "policy": entry.get("policy"),
                "devices": entry.get("devices"),
            }
        )
    return products


def audit_workspace(workspace, policy=None):
    if not isinstance(workspace, Workspace):
        workspace = Workspace(workspace)
    products = []
    device_rows = []
    all_issues = []
    for product in workspace_products(workspace):
        entry = {"id": product["id"], "manifest": product["manifest"], "path": str(product["path"])}
        try:
            manifest = load_manifest(product["path"])
            result = audit(manifest, policy=product.get("policy") or policy)
            entry["result"] = result
            entry["release_ready"] = result["release_ready"]
            entry["issues"] = result["summary"]["issues"]
            for row in result.get("devices", []):
                device_rows.append({**row, "product": product["id"], "status": "ready" if result["release_ready"] else "blocked"})
        except Exception as exc:
            issue = make_issue("PRODUCT_LOAD_ERROR", "high", product["id"], f"Cannot audit product: {exc}")
            result = {
                "project": {"id": product["id"], "name": product["id"]},
                "summary": {"issues": 1, "high_or_critical": 1, "by_severity": count_by_severity([issue])},
                "issues": [issue],
                "release_ready": False,
                "gate": {"ready": False, "blockers": [str(exc)], "counts": count_by_severity([issue])},
            }
            entry["result"] = result
            entry["release_ready"] = False
            entry["issues"] = 1
            entry["error"] = str(exc)
        products.append(entry)
        for issue in result["issues"]:
            all_issues.append({**issue, "product": product["id"], "where": f"{product['id']}:{issue.get('where')}"})
    all_issues = sort_issues(all_issues)
    counts = count_by_severity(all_issues)
    workspace_policy = merge_policy(workspace, policy)
    gate = evaluate_gate(all_issues, workspace_policy)
    blocked = [product["id"] for product in products if not product["release_ready"]]
    ready = not blocked and gate["ready"]
    summary = {
        "products": len(products),
        "ready": len(products) - len(blocked),
        "blocked": len(blocked),
        "issues": len(all_issues),
        "high_or_critical": counts.get("critical", 0) + counts.get("high", 0),
        "devices": len(device_rows),
        "by_severity": counts,
    }
    return {
        "schema_version": workspace.get("schema_version"),
        "workspace": workspace.get("workspace"),
        "summary": summary,
        "products": products,
        "devices": device_rows,
        "issues": all_issues,
        "release_ready": ready,
        "blocked_products": blocked,
        "gate": gate,
    }
