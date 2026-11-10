from helpers import ROOT, audit_data, code_list, find_issue, iot_data, write_json

from productmesh.openapi import diff_specs, load_spec

V1 = ROOT / "examples/mobile-api-contract/specs/openapi-v1.json"
V2 = ROOT / "examples/mobile-api-contract/specs/openapi-v2.json"


def test_example_diff_is_non_breaking():
    issues = diff_specs(load_spec(V1), load_spec(V2))
    breaking = [issue for issue in issues if issue["severity"] in ("critical", "high")]
    assert breaking == []
    assert any(issue["code"] == "API_VERSION_CHANGED" for issue in issues)


def test_removed_path_is_breaking():
    old = {"openapi": "3.0.3", "info": {"version": "1"}, "paths": {"/pets": {"get": {"responses": {}}}}}
    new = {"openapi": "3.0.3", "info": {"version": "1"}, "paths": {}}
    issues = diff_specs(old, new)
    issue = next(item for item in issues if item["code"] == "API_PATH_REMOVED")
    assert issue["severity"] == "critical"


def test_new_required_request_field_is_breaking():
    old = {
        "openapi": "3.0.3",
        "paths": {
            "/pets": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {},
                }
            }
        },
    }
    new = {
        "openapi": "3.0.3",
        "paths": {
            "/pets": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name", "age"],
                                    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                                }
                            }
                        }
                    },
                    "responses": {},
                }
            }
        },
    }
    issues = diff_specs(old, new)
    assert any(item["code"] == "API_REQUIRED_FIELD_ADDED" and item["severity"] == "high" for item in issues)


def test_type_change_is_breaking():
    old = {"openapi": "3.0.3", "paths": {"/x": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}}}}}}
    new = {"openapi": "3.0.3", "paths": {"/x": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object", "properties": {"id": {"type": "integer"}}}}}}}}}}}
    issues = diff_specs(old, new)
    assert any(item["code"] == "API_TYPE_CHANGED" and item["severity"] == "high" for item in issues)


def test_removed_auth_scheme_is_breaking():
    old = {"openapi": "3.0.3", "paths": {}, "components": {"securitySchemes": {"bearer": {"type": "http"}}}}
    new = {"openapi": "3.0.3", "paths": {}, "components": {"securitySchemes": {}}}
    issues = diff_specs(old, new)
    assert any(item["code"] == "API_AUTH_SCHEME_REMOVED" and item["severity"] == "high" for item in issues)


def test_interface_version_mismatch(tmp_path):
    data = iot_data()
    data["interfaces"][0]["version"] = "v1"
    data["api_contracts"] = [
        {"id": "API-REST", "interface": "IF-SENSOR", "current": str(V2)}
    ]
    result = audit_data(data, tmp_path)
    assert "API_INTERFACE_VERSION_MISMATCH" in code_list(result)


def test_breaking_allowed_is_info(tmp_path):
    old = {"openapi": "3.0.3", "info": {"version": "1.0.0"}, "paths": {"/pets": {"get": {"responses": {}}}}}
    new = {"openapi": "3.0.3", "info": {"version": "2.0.0"}, "paths": {}}
    baseline = write_json(tmp_path / "baseline.json", old)
    current = write_json(tmp_path / "current.json", new)
    data = iot_data()
    data["api_contracts"] = [
        {
            "id": "API-REST",
            "interface": "IF-SENSOR",
            "baseline": str(baseline),
            "current": str(current),
            "allow_breaking": True,
        }
    ]
    result = audit_data(data, tmp_path)
    allowed = find_issue(result, "API_BREAKING_ALLOWED")
    assert allowed is not None
    assert allowed["severity"] == "info"
    assert find_issue(result, "API_PATH_REMOVED") is None
