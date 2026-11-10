import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import audit_file
from .onnx_meta import inspect_onnx
from .openapi import diff_specs, load_spec
from .repo import inspect_repository
from .report import render, write_report
from .sbom import load_sbom
from .workspace import audit_workspace, load_workspace_or_discover, workspace_products

DEFAULT_MANIFEST = "examples/iot-edge-monitor/product.json"


def _add_report_options(parser):
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--format", choices=("json", "sarif", "markdown", "md"), default="human")
    parser.add_argument("--output", help="Write the report to a file")


def _print_issues(issues):
    for issue in issues:
        print(f"[{issue.get('severity')}] {issue.get('code')} ({issue.get('where')}): {issue.get('message')}")


def _print_audit(result):
    project = result.get("project") or {}
    summary = result.get("summary") or {}
    print(
        f"{project.get('name')}: {summary.get('issues', 0)} issues; release_ready={result.get('release_ready')} "
        f"({summary.get('requirements', 0)} requirements, {summary.get('components', 0)} components, {summary.get('devices', 0)} devices)"
    )
    if result.get("gate", {}).get("blockers"):
        print("Blockers: " + "; ".join(result["gate"]["blockers"]))
    _print_issues(result.get("issues") or [])


def _print_workspace(result):
    workspace = result.get("workspace") or {}
    summary = result.get("summary") or {}
    print(
        f"{workspace.get('name')}: {summary.get('products', 0)} products, "
        f"{summary.get('devices', 0)} devices, {summary.get('issues', 0)} issues; "
        f"release_ready={result.get('release_ready')}"
    )
    for product in result.get("products", []):
        print(f"  {'READY  ' if product.get('release_ready') else 'BLOCKED'} {product.get('id')} ({product.get('issues', 0)} issues)")
    _print_issues(result.get("issues") or [])


def _emit(result, args, exit_code):
    fmt = "json" if args.json else args.format
    if args.output and fmt == "human":
        fmt = "json"
    if fmt == "human":
        _print_audit(result)
    else:
        content = render(result, fmt)
        if args.output:
            target = write_report(content, args.output)
            print(f"Wrote {fmt} report to {target}", file=sys.stderr)
        else:
            print(content)
    return exit_code


def cmd_audit(args):
    result = audit_file(args.manifest)
    return _emit(result, args, 0 if result["release_ready"] else 2)


def cmd_release(args):
    result = audit_file(args.manifest)
    return _emit(result, args, 0 if result["release_ready"] else 2)


def cmd_workspace_audit(args):
    workspace = load_workspace_or_discover(args.workspace)
    result = audit_workspace(workspace)
    fmt = "json" if args.json else args.format
    if args.output and fmt == "human":
        fmt = "json"
    if fmt == "human":
        _print_workspace(result)
    else:
        content = render(result, fmt)
        if args.output:
            target = write_report(content, args.output)
            print(f"Wrote {fmt} report to {target}", file=sys.stderr)
        else:
            print(content)
    return 0 if result["release_ready"] else 2


def cmd_workspace_list(args):
    workspace = load_workspace_or_discover(args.workspace)
    products = workspace_products(workspace)
    serializable = [{**product, "path": str(product["path"])} for product in products]
    if args.json:
        print(json.dumps({"workspace": workspace.get("workspace"), "products": serializable}, indent=2))
        return 0
    print(workspace.get("workspace", {}).get("name", "workspace"))
    for product in products:
        print(f"  {product['id']}: {product['manifest']}")
    return 0


def cmd_repo_inspect(args):
    value = args.path
    is_remote = "://" in value or value.startswith(("git@", "ssh:"))
    info = inspect_repository({"remote": value} if is_remote else {"path": value}, Path.cwd())
    if args.json:
        print(json.dumps(info, indent=2))
        return 0
    print(f"{info.get('kind')}: {info.get('path') or info.get('remote')}")
    if info.get("error"):
        print(f"error: {info['error']}")
        return 1
    if info.get("kind") == "local" and (info.get("exists") is False or info.get("is_repo") is False):
        print("error: path is missing or not a Git repository")
        return 1
    for key in ("commit", "branch", "describe", "remote", "resolved_commit"):
        if info.get(key):
            print(f"  {key}: {info[key]}")
    if info.get("dirty"):
        print(f"  dirty: {len(info.get('dirty_files', []))} file(s)")
    if info.get("tags"):
        print(f"  tags: {', '.join(info['tags'])}")
    return 0


def cmd_openapi_diff(args):
    old = load_spec(args.baseline)
    new = load_spec(args.current)
    issues = diff_specs(old, new)
    if args.json:
        print(json.dumps({"issues": issues, "breaking": sum(1 for i in issues if i["severity"] in ("critical", "high"))}, indent=2))
    else:
        breaking = sum(1 for issue in issues if issue["severity"] in ("critical", "high"))
        print(f"{breaking} breaking change(s), {len(issues)} total issue(s)")
        _print_issues(issues)
    if args.fail_on_breaking and any(issue["severity"] in ("critical", "high") for issue in issues):
        return 2
    return 0


def cmd_sbom_inspect(args):
    sbom = load_sbom(args.path)
    if args.json:
        print(json.dumps(sbom, indent=2))
        return 0
    print(f"{sbom['format']} {sbom.get('spec_version') or ''}: {len(sbom['components'])} components, {len(sbom['vulnerabilities'])} vulnerabilities")
    for component in sbom["components"]:
        print(f"  {component.get('name')} {component.get('version') or ''} {component.get('purl') or ''}".rstrip())
    return 0


def cmd_model_inspect(args):
    model = inspect_onnx(args.path)
    if args.json:
        print(json.dumps(model, indent=2))
        return 0
    print(f"ONNX IR {model['ir_version']}, producer {model.get('producer_name') or 'unknown'}, sha256 {model['sha256'][:12]}")
    for item in model.get("opset_imports", []):
        print(f"  opset {item.get('domain') or 'default'}: {item.get('version')}")
    for direction in ("inputs", "outputs"):
        for value in (model.get("graph") or {}).get(direction, []):
            print(f"  {direction[:-1]} {value.get('name')}: {value.get('dtype')} {value.get('shape')}")
    return 0


def cmd_serve(args):
    from .server import main as serve

    serve(host=args.host, port=args.port)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="productmesh", description="Cross-discipline product lifecycle integrity checker")
    parser.add_argument("--version", action="version", version=f"ProductMesh {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, handler, help_text in (
        ("audit", cmd_audit, "Audit a product manifest"),
        ("release", cmd_release, "Evaluate the release gate for a product manifest"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("manifest", nargs="?", default=DEFAULT_MANIFEST)
        _add_report_options(command)
        command.set_defaults(func=handler)
    serve = subparsers.add_parser("serve", help="Start the local dashboard")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.set_defaults(func=cmd_serve)
    workspace = subparsers.add_parser("workspace", help="Audit multiple products and devices")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_audit = workspace_sub.add_parser("audit", help="Audit every product in a workspace")
    workspace_audit.add_argument("workspace", nargs="?", default=None)
    _add_report_options(workspace_audit)
    workspace_audit.set_defaults(func=cmd_workspace_audit)
    workspace_list = workspace_sub.add_parser("list", help="List workspace products")
    workspace_list.add_argument("workspace", nargs="?", default=None)
    workspace_list.add_argument("--json", action="store_true")
    workspace_list.set_defaults(func=cmd_workspace_list)
    repo = subparsers.add_parser("repo", help="Inspect a Git repository")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    repo_inspect = repo_sub.add_parser("inspect", help="Inspect a local path or remote URL")
    repo_inspect.add_argument("path")
    repo_inspect.add_argument("--json", action="store_true")
    repo_inspect.set_defaults(func=cmd_repo_inspect)
    openapi = subparsers.add_parser("openapi", help="Compare OpenAPI contracts")
    openapi_sub = openapi.add_subparsers(dest="openapi_command", required=True)
    openapi_diff = openapi_sub.add_parser("diff", help="Diff a baseline and current spec")
    openapi_diff.add_argument("baseline")
    openapi_diff.add_argument("current")
    openapi_diff.add_argument("--json", action="store_true")
    openapi_diff.add_argument("--fail-on-breaking", action="store_true")
    openapi_diff.set_defaults(func=cmd_openapi_diff)
    sbom = subparsers.add_parser("sbom", help="Inspect SBOM files")
    sbom_sub = sbom.add_subparsers(dest="sbom_command", required=True)
    sbom_inspect = sbom_sub.add_parser("inspect", help="Inspect a CycloneDX or SPDX JSON SBOM")
    sbom_inspect.add_argument("path")
    sbom_inspect.add_argument("--json", action="store_true")
    sbom_inspect.set_defaults(func=cmd_sbom_inspect)
    model = subparsers.add_parser("model", help="Inspect ONNX model metadata")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_inspect = model_sub.add_parser("inspect", help="Inspect an ONNX model")
    model_inspect.add_argument("path")
    model_inspect.add_argument("--json", action="store_true")
    model_inspect.set_defaults(func=cmd_model_inspect)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"productmesh: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
