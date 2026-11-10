from pathlib import Path

from helpers import ROOT, code_list, write_json

from productmesh.manifest import load_workspace
from productmesh.workspace import (
    audit_workspace,
    discover_workspace,
    workspace_products,
)


def test_example_workspace_ready():
    result = audit_workspace(load_workspace(ROOT / "examples/workspace.json"))
    assert result["release_ready"] is True
    assert result["summary"]["products"] == 3
    assert result["summary"]["devices"] == 4
    assert result["blocked_products"] == []


def test_workspace_device_matrix():
    result = audit_workspace(load_workspace(ROOT / "examples/workspace.json"))
    devices = {row["id"]: row for row in result["devices"]}
    assert devices["DEV-ESP32-S3"]["product"] == "iot-edge-monitor"
    assert devices["DEV-QCS6490"]["product"] == "edge-ai-deployment"
    assert all(row["status"] == "ready" for row in result["devices"])


def test_discover_workspace_from_examples_directory():
    workspace = discover_workspace(ROOT / "examples")
    products = workspace_products(workspace)
    assert {product["id"] for product in products} == {"iot-edge-monitor", "mobile-api-contract", "edge-ai-deployment"}


def test_workspace_missing_product_is_blocked(tmp_path):
    workspace_path = write_json(
        tmp_path / "workspace.json",
        {
            "workspace": {"id": "broken", "name": "Broken workspace"},
            "products": [{"id": "missing", "manifest": "missing/product.json"}],
        },
    )
    result = audit_workspace(load_workspace(workspace_path))
    assert result["release_ready"] is False
    assert "missing" in result["blocked_products"]
    assert "PRODUCT_LOAD_ERROR" in code_list(result)


def test_workspace_products_relative_to_workspace(tmp_path):
    product = tmp_path / "nested" / "product.json"
    write_json(product, __import__("json").loads((ROOT / "examples/iot-edge-monitor/product.json").read_text()))
    workspace_path = write_json(
        tmp_path / "workspace.json",
        {
            "workspace": {"id": "nested", "name": "Nested"},
            "products": [{"id": "nested-product", "manifest": "nested/product.json"}],
        },
    )
    products = workspace_products(load_workspace(workspace_path))
    assert products[0]["path"] == Path(product).resolve()
