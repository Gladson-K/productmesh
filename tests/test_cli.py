import json
import subprocess
import sys

from helpers import ROOT, write_json


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "productmesh.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_version():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "ProductMesh" in result.stdout


def test_audit_example():
    result = run_cli("audit", "examples/iot-edge-monitor/product.json")
    assert result.returncode == 0
    assert "release_ready=True" in result.stdout


def test_workspace_audit():
    result = run_cli("workspace", "audit", "examples/workspace.json")
    assert result.returncode == 0
    assert "3 products" in result.stdout
    assert "4 devices" in result.stdout


def test_workspace_list_json():
    result = run_cli("workspace", "list", "examples/workspace.json", "--json")
    payload = json.loads(result.stdout)
    assert len(payload["products"]) == 3


def test_audit_sarif_output(tmp_path):
    output = tmp_path / "report.sarif"
    result = run_cli(
        "audit",
        "examples/iot-edge-monitor/product.json",
        "--format",
        "sarif",
        "--output",
        str(output),
    )
    assert result.returncode == 0
    assert output.is_file()
    assert json.loads(output.read_text())["version"] == "2.1.0"


def test_openapi_diff_fail_on_breaking(tmp_path):
    old = {"openapi": "3.0.3", "paths": {"/pets": {"get": {"responses": {}}}}}
    new = {"openapi": "3.0.3", "paths": {}}
    baseline = write_json(tmp_path / "old.json", old)
    current = write_json(tmp_path / "new.json", new)
    result = run_cli("openapi", "diff", str(baseline), str(current), "--fail-on-breaking")
    assert result.returncode == 2
    assert "API_PATH_REMOVED" in result.stdout


def test_model_inspect():
    result = run_cli("model", "inspect", "examples/edge-ai-deployment/models/tiny.onnx", "--json")
    payload = json.loads(result.stdout)
    assert payload["ir_version"] == 8


def test_sbom_inspect():
    result = run_cli("sbom", "inspect", "examples/edge-ai-deployment/sbom.cdx.json", "--json")
    payload = json.loads(result.stdout)
    assert payload["format"] == "cyclonedx"
