import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .ai import analyze
from .audit import audit_file
from .benchmarks import inspect_benchmark
from .cloud import (
    add_member,
    approve,
    load_store,
    new_store,
    request_approval,
    save_store,
)
from .cloud import status as cloud_status
from .connectors import import_fragment, inspect_connector, list_connectors
from .enterprise import check_governance, get_profile
from .firmware import discover_devices, fingerprint
from .hil import list_adapters, run_plan
from .history import append_event, load_history, summarize_history
from .lab import find_board, fingerprint_board, list_boards, load_inventory
from .manifest import load_data
from .observability import load_spans, summarize_spans
from .onnx_meta import inspect_onnx
from .openapi import diff_specs, load_spec
from .policy import load_policy, validate_policy
from .repo import inspect_repository
from .report import render, write_report
from .sbom import load_sbom
from .schema import validate_file
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


def cmd_validate(args):
    result = validate_file(args.path, args.schema)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{args.path}: {'valid' if result['valid'] else 'invalid'} ({result['validator']})")
        for error in result.get("errors", []):
            print(f"  {error['path']}: {error['message']}")
        if result.get("warning"):
            print(f"  warning: {result['warning']}")
    return 0 if result["valid"] else 2


def cmd_connector_list(args):
    connectors = list_connectors()
    if args.json:
        print(json.dumps({"connectors": connectors}, indent=2))
    else:
        for connector in connectors:
            print(f"{connector['name']}: {connector['kind']} - {connector['description']}")
    return 0


def cmd_connector_inspect(args):
    result = inspect_connector(args.name, args.input)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['connector']}: stub, network={result['network']}")
        for key in ("repositories", "requirements", "pull_requests", "merge_requests"):
            if result.get(key):
                print(f"  {key}: {len(result[key])}")
    return 0


def cmd_connector_import(args):
    fragment = import_fragment(args.name, args.input)
    content = json.dumps(fragment, indent=2)
    if args.output:
        target = write_report(content, args.output)
        print(f"Wrote connector fragment to {target}", file=sys.stderr)
    else:
        print(content)
    return 0


def cmd_firmware_inspect(args):
    result = fingerprint(args.path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['path']}: {result['format']}, {result['size']} bytes, sha256 {result['sha256'][:12]}")
        if result["versions"]:
            print(f"  versions: {', '.join(result['versions'])}")
    return 0


def cmd_firmware_discover(args):
    devices = discover_devices(args.root or None)
    if args.json:
        print(json.dumps({"devices": devices}, indent=2))
    else:
        for device in devices:
            print(f"{device['path']}: {device['kind']}, available={device['available']}")
        if not devices:
            print("No serial devices discovered.")
    return 0


def cmd_hil_list(args):
    adapters = list_adapters()
    if args.json:
        print(json.dumps({"adapters": adapters}, indent=2))
    else:
        for adapter in adapters:
            print(f"{adapter['name']}: available={adapter['available']} - {adapter['description']}")
    return 0


def cmd_hil_run(args):
    result = run_plan(args.adapter, args.plan)
    print(json.dumps(result, indent=2))
    return 0


def cmd_lab_list(args):
    inventory = load_inventory(args.inventory or "examples/lab.json")
    boards = list_boards(inventory)
    if args.json:
        print(json.dumps({"boards": boards}, indent=2))
    else:
        for board in boards:
            print(f"{board['id']}: {board['board']}, status={board['status']}, location={board['location']}")
    return 0


def cmd_lab_inspect(args):
    inventory = load_inventory(args.inventory or "examples/lab.json")
    board = find_board(inventory, args.board)
    if not board:
        print(f"productmesh: error: board not found: {args.board}", file=sys.stderr)
        return 1
    result = fingerprint_board(board)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['id']}: {result['board']}, firmware={result['firmware']}, status={result['status']}")
        print(f"  serial: {result['serial']}, location: {result['location']}")
    return 0


def cmd_benchmark_inspect(args):
    result = inspect_benchmark(args.path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['runtime']} {result['runtime_version'] or ''}: {result['latency_ms']} ms, {result['throughput_fps']} fps")
        print(f"  device: {result['device']}, compiled={result['compiled']}, quantization={result['quantization']}")
    return 0


def cmd_otel_inspect(args):
    spans = load_spans(args.path)
    summary = summarize_spans(spans)
    if args.json:
        print(json.dumps({"summary": summary, "spans": spans}, indent=2))
    else:
        print(f"{summary['spans']} spans, {summary['traces']} traces, {summary['errors']} errors")
        print(f"  services: {', '.join(summary['services']) or 'none'}")
    return 0


def cmd_cloud_init(args):
    store = new_store(args.name, args.owner)
    target = save_store(args.file, store)
    if args.json:
        print(json.dumps(store, indent=2))
    else:
        print(f"Initialized cloud workspace stub: {target}")
    return 0


def cmd_cloud_status(args):
    result = cloud_status(load_store(args.file))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        workspace = result.get("workspace") or {}
        print(
            f"{workspace.get('name')}: {result['members']} members, "
            f"{result['approvals']['pending']} pending approvals, "
            f"{result['approvals']['approved']} approved"
        )
    return 0


def cmd_cloud_add_member(args):
    store = load_store(args.file)
    add_member(store, args.user, args.role)
    save_store(args.file, store)
    print(json.dumps(cloud_status(store), indent=2))
    return 0


def cmd_cloud_request(args):
    store = load_store(args.file)
    approval = request_approval(store, args.product, args.user, args.note)
    save_store(args.file, store)
    print(json.dumps(approval, indent=2))
    return 0


def cmd_cloud_approve(args):
    store = load_store(args.file)
    approval = approve(store, args.product, args.user, args.role, args.note)
    save_store(args.file, store)
    print(json.dumps(approval, indent=2))
    return 0


def cmd_cloud_history(args):
    store = load_store(args.file)
    events = store.get("history", [])
    if args.json:
        print(json.dumps({"history": events}, indent=2))
    else:
        for event in events:
            print(f"{event.get('timestamp')} {event.get('actor')} {event.get('action')} {event.get('target') or ''}")
    return 0


def cmd_history_record(args):
    event = append_event(args.file, {"actor": args.actor, "action": args.action, "target": args.target, "detail": args.detail})
    print(json.dumps(event, indent=2))
    return 0


def cmd_history_list(args):
    events = load_history(args.file)
    if args.json:
        print(json.dumps({"events": events}, indent=2))
    else:
        for event in events:
            print(f"{event.get('timestamp')} {event.get('actor')} {event.get('action')} {event.get('target') or ''}")
    return 0


def cmd_history_summary(args):
    result = summarize_history(load_history(args.file))
    print(json.dumps(result, indent=2))
    return 0


def cmd_policy_show(args):
    print(json.dumps(load_policy(args.file), indent=2))
    return 0


def cmd_policy_validate(args):
    result = validate_policy(load_policy(args.file))
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


def cmd_advise(args):
    result = analyze(audit_file(args.manifest))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Release ready: {result['release_ready']} ({result['method']} stub)")
        for cause in result["root_causes"]:
            print(f"  {cause['product']}: {cause['issue_count']} issue(s) {cause['codes']}")
        for item in result["recommendations"]:
            print(f"  [{item['priority']}] {item['code']}: {item['recommendation']}")
    return 0


def cmd_enterprise_profile(args):
    result = get_profile(args.name)
    print(json.dumps(result, indent=2))
    return 0


def cmd_enterprise_check(args):
    controls = load_data(args.controls) if args.controls else {}
    result = check_governance(args.name, controls)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 2


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
    validate = subparsers.add_parser("validate", help="Validate JSON or YAML against a ProductMesh schema")
    validate.add_argument("path")
    validate.add_argument("--schema", default=None, help="product, workspace, lab, or a schema file path")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)
    connector = subparsers.add_parser("connector", help="Inspect and import issue-tracker connector exports")
    connector_sub = connector.add_subparsers(dest="connector_command", required=True)
    connector_list = connector_sub.add_parser("list", help="List available connectors")
    connector_list.add_argument("--json", action="store_true")
    connector_list.set_defaults(func=cmd_connector_list)
    connector_inspect = connector_sub.add_parser("inspect", help="Inspect a connector export")
    connector_inspect.add_argument("name", choices=("github", "gitlab", "jira", "azure", "azure_devops"))
    connector_inspect.add_argument("input")
    connector_inspect.add_argument("--json", action="store_true")
    connector_inspect.set_defaults(func=cmd_connector_inspect)
    connector_import = connector_sub.add_parser("import", help="Import a connector export as a manifest fragment")
    connector_import.add_argument("name", choices=("github", "gitlab", "jira", "azure", "azure_devops"))
    connector_import.add_argument("input")
    connector_import.add_argument("--output")
    connector_import.set_defaults(func=cmd_connector_import)
    firmware = subparsers.add_parser("firmware", help="Inspect and discover firmware artifacts")
    firmware_sub = firmware.add_subparsers(dest="firmware_command", required=True)
    firmware_inspect = firmware_sub.add_parser("inspect", help="Fingerprint a firmware artifact")
    firmware_inspect.add_argument("path")
    firmware_inspect.add_argument("--json", action="store_true")
    firmware_inspect.set_defaults(func=cmd_firmware_inspect)
    firmware_discover = firmware_sub.add_parser("discover", help="Discover local serial devices")
    firmware_discover.add_argument("--root", default=None)
    firmware_discover.add_argument("--json", action="store_true")
    firmware_discover.set_defaults(func=cmd_firmware_discover)
    device = subparsers.add_parser("device", help="Discover devices for lab automation")
    device_sub = device.add_subparsers(dest="device_command", required=True)
    device_discover = device_sub.add_parser("discover", help="Discover local serial devices")
    device_discover.add_argument("--root", default=None)
    device_discover.add_argument("--json", action="store_true")
    device_discover.set_defaults(func=cmd_firmware_discover)
    hil = subparsers.add_parser("hil", help="Run hardware-in-the-loop plan stubs")
    hil_sub = hil.add_subparsers(dest="hil_command", required=True)
    hil_list = hil_sub.add_parser("list", help="List HIL adapters")
    hil_list.add_argument("--json", action="store_true")
    hil_list.set_defaults(func=cmd_hil_list)
    hil_run = hil_sub.add_parser("run", help="Run a HIL plan against an adapter")
    hil_run.add_argument("plan")
    hil_run.add_argument("--adapter", choices=("mock", "serial"), default="mock")
    hil_run.set_defaults(func=cmd_hil_run)
    lab = subparsers.add_parser("lab", help="Inspect the lab inventory")
    lab_sub = lab.add_subparsers(dest="lab_command", required=True)
    lab_list = lab_sub.add_parser("list", help="List boards in the lab inventory")
    lab_list.add_argument("--inventory", default=None)
    lab_list.add_argument("--json", action="store_true")
    lab_list.set_defaults(func=cmd_lab_list)
    lab_inspect = lab_sub.add_parser("inspect", help="Inspect a board in the lab inventory")
    lab_inspect.add_argument("board")
    lab_inspect.add_argument("--inventory", default=None)
    lab_inspect.add_argument("--json", action="store_true")
    lab_inspect.set_defaults(func=cmd_lab_inspect)
    benchmark = subparsers.add_parser("benchmark", help="Inspect benchmark evidence")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_inspect = benchmark_sub.add_parser("inspect", help="Inspect a benchmark record")
    benchmark_inspect.add_argument("path")
    benchmark_inspect.add_argument("--json", action="store_true")
    benchmark_inspect.set_defaults(func=cmd_benchmark_inspect)
    otel = subparsers.add_parser("otel", help="Inspect OpenTelemetry span exports")
    otel_sub = otel.add_subparsers(dest="otel_command", required=True)
    otel_inspect = otel_sub.add_parser("inspect", help="Summarize a span export")
    otel_inspect.add_argument("path")
    otel_inspect.add_argument("--json", action="store_true")
    otel_inspect.set_defaults(func=cmd_otel_inspect)
    cloud = subparsers.add_parser("cloud", help="Manage the local cloud workspace stub")
    cloud_sub = cloud.add_subparsers(dest="cloud_command", required=True)
    cloud_init = cloud_sub.add_parser("init", help="Initialize a local cloud workspace store")
    cloud_init.add_argument("--file", default="cloud-workspace.json")
    cloud_init.add_argument("--name", default="ProductMesh")
    cloud_init.add_argument("--owner", default="owner")
    cloud_init.add_argument("--json", action="store_true")
    cloud_init.set_defaults(func=cmd_cloud_init)
    cloud_status_cmd = cloud_sub.add_parser("status", help="Show cloud workspace status")
    cloud_status_cmd.add_argument("--file", default="cloud-workspace.json")
    cloud_status_cmd.add_argument("--json", action="store_true")
    cloud_status_cmd.set_defaults(func=cmd_cloud_status)
    cloud_member = cloud_sub.add_parser("add-member", help="Add a workspace member")
    cloud_member.add_argument("--file", default="cloud-workspace.json")
    cloud_member.add_argument("user")
    cloud_member.add_argument("--role", choices=("viewer", "auditor", "approver", "admin"), default="viewer")
    cloud_member.set_defaults(func=cmd_cloud_add_member)
    cloud_request = cloud_sub.add_parser("request", help="Request release approval")
    cloud_request.add_argument("product")
    cloud_request.add_argument("--file", default="cloud-workspace.json")
    cloud_request.add_argument("--user", default="owner")
    cloud_request.add_argument("--note")
    cloud_request.set_defaults(func=cmd_cloud_request)
    cloud_approve = cloud_sub.add_parser("approve", help="Approve a release request")
    cloud_approve.add_argument("product")
    cloud_approve.add_argument("--file", default="cloud-workspace.json")
    cloud_approve.add_argument("--user", default="owner")
    cloud_approve.add_argument("--role", choices=("viewer", "auditor", "approver", "admin"))
    cloud_approve.add_argument("--note")
    cloud_approve.set_defaults(func=cmd_cloud_approve)
    cloud_history = cloud_sub.add_parser("history", help="Show cloud workspace history")
    cloud_history.add_argument("--file", default="cloud-workspace.json")
    cloud_history.add_argument("--json", action="store_true")
    cloud_history.set_defaults(func=cmd_cloud_history)
    history = subparsers.add_parser("history", help="Record and summarize audit history")
    history_sub = history.add_subparsers(dest="history_command", required=True)
    history_record = history_sub.add_parser("record", help="Append an audit event")
    history_record.add_argument("--file", default="audit-history.jsonl")
    history_record.add_argument("--actor", default="system")
    history_record.add_argument("--action", required=True)
    history_record.add_argument("--target")
    history_record.add_argument("--detail")
    history_record.set_defaults(func=cmd_history_record)
    history_list = history_sub.add_parser("list", help="List audit events")
    history_list.add_argument("--file", default="audit-history.jsonl")
    history_list.add_argument("--json", action="store_true")
    history_list.set_defaults(func=cmd_history_list)
    history_summary = history_sub.add_parser("summary", help="Summarize audit events")
    history_summary.add_argument("--file", default="audit-history.jsonl")
    history_summary.set_defaults(func=cmd_history_summary)
    policy = subparsers.add_parser("policy", help="Load and validate release policies")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    policy_show = policy_sub.add_parser("show", help="Show the effective release policy")
    policy_show.add_argument("--file", default="release-policy.json")
    policy_show.set_defaults(func=cmd_policy_show)
    policy_validate = policy_sub.add_parser("validate", help="Validate a release policy file")
    policy_validate.add_argument("--file", default="release-policy.json")
    policy_validate.set_defaults(func=cmd_policy_validate)
    advise = subparsers.add_parser("advise", help="Generate deterministic root-cause advice")
    advise.add_argument("manifest", nargs="?", default=DEFAULT_MANIFEST)
    advise.add_argument("--json", action="store_true")
    advise.set_defaults(func=cmd_advise)
    enterprise = subparsers.add_parser("enterprise", help="Inspect enterprise governance profiles")
    enterprise_sub = enterprise.add_subparsers(dest="enterprise_command", required=True)
    enterprise_profile = enterprise_sub.add_parser("profile", help="Show an enterprise profile")
    enterprise_profile.add_argument("name", choices=("on_prem", "hybrid", "saas"))
    enterprise_profile.set_defaults(func=cmd_enterprise_profile)
    enterprise_check = enterprise_sub.add_parser("check", help="Check governance controls")
    enterprise_check.add_argument("name", choices=("on_prem", "hybrid", "saas"))
    enterprise_check.add_argument("--controls")
    enterprise_check.set_defaults(func=cmd_enterprise_check)
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
