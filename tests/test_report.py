import json

import pytest
from helpers import ROOT, iot_manifest

from productmesh.audit import audit
from productmesh.manifest import load_workspace
from productmesh.report import render, to_markdown, to_sarif
from productmesh.workspace import audit_workspace


def test_sarif_shape():
    result = audit(iot_manifest())
    sarif = to_sarif(result)
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "ProductMesh"
    assert sarif["runs"][0]["results"] == []


def test_sarif_contains_issues():
    data = dict(iot_manifest())
    data["environments"] = [dict(data["environments"][0], logic_voltage="5V")]
    result = audit(data, base_dir=iot_manifest().base_dir)
    sarif = to_sarif(result)
    assert sarif["runs"][0]["results"]
    assert sarif["runs"][0]["results"][0]["level"] == "error"


def test_markdown_audit():
    text = to_markdown(audit(iot_manifest()))
    assert "# IoT Edge Monitor" in text
    assert "Release ready: True" in text


def test_markdown_workspace():
    text = to_markdown(audit_workspace(load_workspace(ROOT / "examples/workspace.json")))
    assert "ProductMesh Example Workspace" in text
    assert "DEV-ESP32-S3" in text


def test_render_json_roundtrip():
    result = audit(iot_manifest())
    assert json.loads(render(result, "json"))["project"]["name"] == "IoT Edge Monitor"


def test_unknown_format():
    with pytest.raises(ValueError):
        render({}, "xml")
