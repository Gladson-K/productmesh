import hashlib

from helpers import audit_data, code_list, find_issue, iot_data, iot_manifest


def test_evidence_hash_matches(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"voltage": "3.3V"}\n')
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    data = iot_data()
    data["tests"][2]["evidence"] = [{"path": str(evidence), "sha256": digest}]
    result = audit_data(data, iot_manifest().base_dir)
    assert result["release_ready"] is True
    assert "EVIDENCE_HASH_MISMATCH" not in code_list(result)


def test_evidence_hash_mismatch(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n")
    data = iot_data()
    data["tests"][2]["evidence"] = [{"path": str(evidence), "sha256": "0" * 64}]
    result = audit_data(data, iot_manifest().base_dir)
    assert "EVIDENCE_HASH_MISMATCH" in code_list(result)


def test_evidence_missing(tmp_path):
    data = iot_data()
    data["tests"][2]["evidence"] = [{"path": str(tmp_path / "missing.json")}]
    result = audit_data(data, iot_manifest().base_dir)
    assert "EVIDENCE_MISSING" in code_list(result)


def test_failed_test_blocks_release():
    data = iot_data()
    data["tests"][0]["status"] = "failed"
    result = audit_data(data, iot_manifest().base_dir)
    issue = find_issue(result, "TEST_FAILED")
    assert issue is not None
    assert issue["severity"] == "critical"
    assert result["release_ready"] is False


def test_requirement_not_verified_when_linked_test_blocked():
    data = iot_data()
    data["tests"][0]["status"] = "blocked"
    result = audit_data(data, iot_manifest().base_dir)
    assert "REQUIREMENT_NOT_VERIFIED" in code_list(result)


def test_require_evidence_policy():
    data = iot_data()
    data["release"] = {"require_evidence": True}
    result = audit_data(data, iot_manifest().base_dir)
    assert "EVIDENCE_REQUIRED" in code_list(result)
    assert result["release_ready"] is False
