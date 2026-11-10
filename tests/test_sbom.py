from helpers import (
    ROOT,
    audit_data,
    code_list,
    edge_manifest,
    find_issue,
    iot_data,
    write_json,
)

from productmesh.sbom import load_sbom

CYCLONEDX = ROOT / "examples/edge-ai-deployment/sbom.cdx.json"


def test_load_cyclonedx_example():
    sbom = load_sbom(CYCLONEDX)
    assert sbom["format"] == "cyclonedx"
    assert sbom["spec_version"] == "1.6"
    assert len(sbom["components"]) == 3


def test_load_spdx(tmp_path):
    path = write_json(
        tmp_path / "sbom.spdx.json",
        {
            "spdxVersion": "SPDX-2.3",
            "packages": [
                {
                    "name": "onnxruntime",
                    "versionInfo": "1.18.0",
                    "SPDXID": "SPDXRef-Package",
                    "licenseConcluded": "MIT",
                    "externalRefs": [{"referenceType": "purl", "referenceLocator": "pkg:pypi/onnxruntime@1.18.0"}],
                }
            ],
        },
    )
    sbom = load_sbom(path)
    assert sbom["format"] == "spdx"
    assert sbom["components"][0]["purl"] == "pkg:pypi/onnxruntime@1.18.0"
    assert sbom["components"][0]["licenses"] == ["MIT"]


def test_edge_product_sbom_is_clean():
    manifest = edge_manifest()
    result = audit_data(dict(manifest), manifest.base_dir)
    assert result["summary"]["sboms"] == 1
    assert "SBOM_INVALID" not in code_list(result)
    assert "SBOM_COMPONENT_MISSING" not in code_list(result)


def test_missing_required_component(tmp_path):
    data = iot_data()
    data["sbom"] = {"id": "SBOM-IOT", "path": str(CYCLONEDX), "required_components": ["pkg:generic/does-not-exist@1.0.0"]}
    result = audit_data(data, tmp_path)
    assert "SBOM_REQUIRED_COMPONENT_MISSING" in code_list(result)


def test_component_version_mismatch(tmp_path):
    data = iot_data()
    data["components"][0]["purl"] = "pkg:pypi/onnxruntime@1.18.0"
    data["components"][0]["version"] = "9.9.9"
    data["components"][0]["sbom_name"] = "onnxruntime"
    data["sbom"] = {"id": "SBOM-IOT", "path": str(CYCLONEDX), "check_components": True}
    result = audit_data(data, tmp_path)
    assert "SBOM_VERSION_MISMATCH" in code_list(result)


def test_vulnerability_blocks(tmp_path):
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"type": "library", "name": "openssl", "version": "3.0.0"}],
        "vulnerabilities": [{"id": "CVE-2026-0001", "ratings": [{"severity": "high"}]}],
    }
    path = write_json(tmp_path / "vuln.json", sbom)
    data = iot_data()
    data["sbom"] = {"id": "SBOM-IOT", "path": str(path), "check_components": False}
    result = audit_data(data, tmp_path)
    issue = find_issue(result, "SBOM_VULNERABILITY")
    assert issue is not None
    assert issue["severity"] == "high"
    assert result["release_ready"] is False


def test_unsupported_sbom(tmp_path):
    path = write_json(tmp_path / "bad.json", {"not": "an sbom"})
    data = iot_data()
    data["sbom"] = {"id": "SBOM-IOT", "path": str(path)}
    result = audit_data(data, tmp_path)
    assert "SBOM_INVALID" in code_list(result)
