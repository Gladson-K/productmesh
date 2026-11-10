from productmesh.issues import make_issue
from productmesh.policy import evaluate_gate, merge_policy


def issue(severity, code="TEST"):
    return make_issue(code, severity, "test", "message")


def test_default_policy_blocks_critical_and_high():
    assert not evaluate_gate([issue("critical")], merge_policy())["ready"]
    assert not evaluate_gate([issue("high")], merge_policy())["ready"]
    assert evaluate_gate([issue("medium")], merge_policy())["ready"]


def test_block_on_medium_blocks_without_explicit_limit():
    gate = evaluate_gate([issue("medium")], merge_policy(override={"block_on_medium": True}))
    assert not gate["ready"]
    assert "medium issues" in gate["blockers"][0]


def test_custom_high_limit_allows_declared_count():
    policy = merge_policy(override={"max_high": 2})
    assert evaluate_gate([issue("high"), issue("high")], policy)["ready"]
    assert not evaluate_gate([issue("high")] * 3, policy)["ready"]


def test_dirty_repository_can_be_allowed():
    dirty = issue("high", "REPO_DIRTY")
    assert not evaluate_gate([dirty], merge_policy())["ready"]
    policy = merge_policy(override={"allow_dirty_repo": True, "block_on_high": False})
    assert evaluate_gate([dirty], policy)["ready"]
    assert evaluate_gate([issue("info", "REPO_DIRTY")], merge_policy())["ready"]


def test_required_sbom_blocks_when_missing():
    gate = evaluate_gate([issue("medium", "SBOM_MISSING")], merge_policy(override={"require_sbom": True}))
    assert not gate["ready"]
    assert "SBOM required" in gate["blockers"][0]


def test_legacy_high_severity_key_is_supported():
    policy = merge_policy({"release": {"block_on_high_severity": False}})
    assert policy["block_on_high"] is False
