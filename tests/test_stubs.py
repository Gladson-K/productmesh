import json

import pytest
from helpers import ROOT, audit_data, code_list, iot_data, write_json

from productmesh import cli
from productmesh.ai import analyze
from productmesh.audit import audit_file
from productmesh.benchmarks import inspect_benchmark
from productmesh.cloud import add_member, approve, new_store, request_approval, status
from productmesh.connectors import import_fragment, inspect_connector, list_connectors
from productmesh.enterprise import check_governance, get_profile
from productmesh.firmware import fingerprint
from productmesh.hil import list_adapters, run_plan
from productmesh.history import append_event, load_history, summarize_history
from productmesh.lab import find_board, fingerprint_board, list_boards, load_inventory
from productmesh.observability import correlate, load_spans, summarize_spans
from productmesh.policy import load_policy, validate_policy
from productmesh.schema import validate_data, validate_file


def test_schema_validation_examples():
    assert validate_file(ROOT / "examples/iot-edge-monitor/product.json")["valid"] is True
    assert validate_file(ROOT / "examples/edge-ai-deployment/product.json")["valid"] is True
    assert validate_file(ROOT / "examples/lab.json")["valid"] is True
    assert validate_file(ROOT / "examples/workspace.json")["valid"] is True


def test_schema_validation_rejects_invalid_lab():
    result = validate_data({"boards": "not-a-list"}, "lab")
    assert result["valid"] is False
    assert result["errors"]


def test_reference_examples_audit_clean():
    assert audit_file(ROOT / "examples/iot-edge-monitor/product.json")["release_ready"] is True
    assert audit_file(ROOT / "examples/edge-ai-deployment/product.json")["release_ready"] is True


def test_connectors_normalize_and_alias():
    assert len(list_connectors()) == 4
    github = inspect_connector("github", ROOT / "examples/connectors/github.json")
    assert github["repositories"][0]["id"] == "productmesh/iot-edge-monitor"
    assert github["pull_requests"][0]["id"] == 42
    jira = inspect_connector("jira", ROOT / "examples/connectors/jira.json")
    assert jira["requirements"][0]["id"] == "PM-101"
    azure = inspect_connector("azure_devops", ROOT / "examples/connectors/azure.json")
    assert azure["requirements"][0]["id"] == "501"
    fragment = import_fragment("gitlab", ROOT / "examples/connectors/gitlab.json")
    assert fragment["source"] == "gitlab"
    assert fragment["merge_requests"]


def test_firmware_fingerprint_and_audit_failures(tmp_path):
    info = fingerprint(ROOT / "examples/iot-edge-monitor/firmware/esp32-app.bin")
    assert info["format"] == "binary"
    assert len(info["sha256"]) == 64
    assert "0.1.0" in info["versions"]

    data = iot_data()
    data["firmware"] = [{"id": "FW-X", "path": "missing.bin"}]
    assert "FIRMWARE_MISSING" in code_list(audit_data(data, tmp_path))

    artifact = tmp_path / "fw.bin"
    artifact.write_bytes(b"version=9.9.9\n")
    data["firmware"] = [{"id": "FW-X", "path": "fw.bin", "sha256": "0" * 64, "version": "0.1.0"}]
    result = audit_data(data, tmp_path)
    assert "FIRMWARE_HASH_MISMATCH" in code_list(result)
    assert "FIRMWARE_VERSION_MISMATCH" in code_list(result)


def test_electrical_pin_bus_and_power_checks(tmp_path):
    data = iot_data()
    data["interfaces"].append(
        {"id": "IF-EXTRA", "name": "Extra bus", "protocol": "I2C", "pins": {"sda": "GPIO21"}, "bus": "i2c0", "address": "0x40"}
    )
    data["interfaces"][0]["bus"] = "i2c0"
    data["interfaces"][0]["address"] = "0x40"
    data["devices"].append(
        {
            "id": "DEV-POWER",
            "board": "esp32-c3-mini",
            "firmware": "CMP-FW",
            "logic_voltage": "3.3V",
            "constraints": {"max_current_ma": 100},
            "specs": {"current_ma": 200},
        }
    )
    result = audit_data(data, tmp_path)
    codes = code_list(result)
    assert "PIN_CONFLICT" in codes
    assert "BUS_ADDRESS_CONFLICT" in codes
    assert "POWER_BUDGET_EXCEEDED" in codes


def test_hil_adapters_and_plan(tmp_path):
    assert {item["name"] for item in list_adapters()} == {"mock", "serial"}
    result = run_plan("mock", ROOT / "examples/iot-edge-monitor/hil-plan.json")
    assert result["status"] == "completed"
    assert len(result["results"]) == 2

    data = iot_data()
    data["hil"] = [{"id": "HIL-X", "adapter": "missing", "plan": "plan.json"}]
    assert "HIL_ADAPTER_UNKNOWN" in code_list(audit_data(data, tmp_path))


def test_lab_inventory_and_audit(tmp_path):
    inventory = load_inventory(ROOT / "examples/lab.json")
    assert len(list_boards(inventory)) == 4
    board = find_board(inventory, "esp32-s3-devkitc-1")
    assert board["id"] == "LAB-ESP32-S3"
    assert fingerprint_board(board)["status"] == "available"

    write_json(tmp_path / "lab.json", {"boards": []})
    data = iot_data()
    data["lab"] = {"path": "lab.json"}
    result = audit_data(data, tmp_path)
    assert "LAB_BOARD_MISSING" in code_list(result)

    write_json(tmp_path / "lab.json", {"boards": [{"id": "LAB-1", "board": "esp32-s3-devkitc-1", "status": "offline"}]})
    data["lab"] = {"path": "lab.json"}
    result = audit_data(data, tmp_path)
    assert "LAB_BOARD_UNAVAILABLE" in code_list(result)


def test_benchmark_inspect_and_regressions(tmp_path):
    record = inspect_benchmark(ROOT / "examples/edge-ai-deployment/benchmarks/ort-cpu.json")
    assert record["runtime"] == "onnxruntime"
    assert record["throughput_fps"] == 80.6

    write_json(
        tmp_path / "bench.json",
        {"runtime": "onnxruntime", "device": "DEV-CPU", "latency_ms": 100, "throughput_fps": 5},
    )
    data = iot_data()
    data["benchmarks"] = [
        {
            "id": "BENCH-X",
            "path": "bench.json",
            "runtime": "onnxruntime",
            "device": "DEV-CPU",
            "max_latency_ms": 50,
            "min_throughput_fps": 20,
        }
    ]
    result = audit_data(data, tmp_path)
    assert "BENCHMARK_LATENCY_REGRESSION" in code_list(result)
    assert "BENCHMARK_THROUGHPUT_REGRESSION" in code_list(result)

    data["benchmarks"][0]["path"] = "missing.json"
    assert "BENCHMARK_MISSING" in code_list(audit_data(data, tmp_path))


def test_observability_summary_correlation_and_audit(tmp_path):
    spans = load_spans(ROOT / "examples/edge-ai-deployment/observability/spans.json")
    summary = summarize_spans(spans)
    assert summary["spans"] == 1
    assert summary["services"] == ["edge-inference"]
    assert len(correlate(spans, product="edge-ai-deployment", device="DEV-CPU")) == 1

    write_json(
        tmp_path / "spans.json",
        {"spans": [{"traceId": "t", "name": "x", "attributes": {"service.name": "svc"}}]},
    )
    data = iot_data()
    data["observability"] = {"path": "spans.json", "required_attributes": ["productmesh.device"]}
    assert "OTEL_ATTRIBUTE_MISSING" in code_list(audit_data(data, tmp_path))


def test_cloud_rbac_approvals_and_history():
    store = new_store("Demo", "alice")
    add_member(store, "bob", "viewer")
    with pytest.raises(PermissionError):
        approve(store, "product", "bob")
    add_member(store, "carol", "approver")
    request_approval(store, "product", "carol")
    approval = approve(store, "product", "carol")
    assert approval["status"] == "approved"
    assert status(store)["approvals"]["approved"] == 1


def test_audit_history_summary(tmp_path):
    path = tmp_path / "history.jsonl"
    append_event(path, {"actor": "ci", "action": "audit", "target": "product"})
    append_event(path, {"actor": "ci", "action": "audit", "target": "product"})
    events = load_history(path)
    assert len(events) == 2
    summary = summarize_history(events)
    assert summary["actions"] == {"audit": 2}
    assert summary["actors"] == {"ci": 2}


def test_policy_loading_and_validation():
    policy = load_policy(ROOT / "examples/release-policy.json")
    assert validate_policy(policy)["valid"] is True
    assert validate_policy({"block_on_high": "yes"})["valid"] is False


def test_ai_advice_and_enterprise_governance():
    analysis = analyze(
        {"release_ready": False, "issues": [{"code": "PIN_CONFLICT", "where": "P1", "severity": "high"}]}
    )
    assert analysis["recommendations"][0]["priority"] == "high"
    assert analysis["root_causes"][0]["product"] == "P1"

    profile = get_profile("on_prem")
    assert profile["sso"] is True
    assert check_governance("on_prem", {})["ready"] is False
    controls = {"sso": True, "audit_export": True, "rbac": True, "retention_days": 365}
    assert check_governance("on_prem", controls)["ready"] is True


def test_cli_validate_and_advise(capsys):
    assert cli.main(["validate", str(ROOT / "examples/iot-edge-monitor/product.json")]) == 0
    assert "valid" in capsys.readouterr().out

    assert cli.main(["advise", str(ROOT / "examples/iot-edge-monitor/product.json"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["release_ready"] is True
    assert payload["status"] == "stub"
