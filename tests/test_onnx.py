from helpers import ROOT, audit_data, code_list, edge_manifest, iot_data

from productmesh.onnx_meta import inspect_onnx

MODEL = ROOT / "examples/edge-ai-deployment/models/tiny.onnx"


def test_inspect_tiny_model():
    model = inspect_onnx(MODEL)
    assert model["ir_version"] == 8
    assert model["producer_name"] == "productmesh-example"
    assert model["opset_imports"] == [{"domain": "", "version": 17}]
    assert model["graph"]["inputs"][0]["name"] == "input"
    assert model["graph"]["inputs"][0]["dtype"] == "float32"
    assert model["graph"]["inputs"][0]["shape"] == ["batch", 3, 224, 224]
    assert model["graph"]["outputs"][0]["shape"] == ["batch", 1000]


def test_edge_product_model_is_clean():
    manifest = edge_manifest()
    result = audit_data(dict(manifest), manifest.base_dir)
    assert result["summary"]["models"] == 1
    assert "MODEL_INVALID" not in code_list(result)
    assert "MODEL_INPUT_SHAPE_MISMATCH" not in code_list(result)


def test_model_shape_mismatch():
    manifest = edge_manifest()
    data = dict(manifest)
    data["models"] = [dict(data["models"][0])]
    data["models"][0]["expected"] = dict(data["models"][0]["expected"])
    data["models"][0]["expected"]["inputs"] = [{"name": "input", "dtype": "float32", "shape": ["batch", 3, 128, 128]}]
    result = audit_data(data, manifest.base_dir)
    assert "MODEL_INPUT_SHAPE_MISMATCH" in code_list(result)


def test_model_dtype_mismatch():
    manifest = edge_manifest()
    data = dict(manifest)
    data["models"] = [dict(data["models"][0])]
    data["models"][0]["expected"] = dict(data["models"][0]["expected"])
    data["models"][0]["expected"]["inputs"] = [{"name": "input", "dtype": "int8", "shape": ["batch", 3, 224, 224]}]
    result = audit_data(data, manifest.base_dir)
    assert "MODEL_INPUT_DTYPE_MISMATCH" in code_list(result)


def test_model_hash_mismatch():
    manifest = edge_manifest()
    data = dict(manifest)
    data["models"] = [dict(data["models"][0])]
    data["models"][0]["sha256"] = "0" * 64
    result = audit_data(data, manifest.base_dir)
    assert "MODEL_HASH_MISMATCH" in code_list(result)


def test_model_missing(tmp_path):
    data = iot_data()
    data["models"] = [{"id": "MDL-MISSING", "path": "missing.onnx"}]
    result = audit_data(data, tmp_path)
    assert "MODEL_MISSING" in code_list(result)


def test_quantization_scheme_mismatch():
    manifest = edge_manifest()
    data = dict(manifest)
    data["models"] = [dict(data["models"][0])]
    data["models"][0]["quantization"] = {"path": "models/tiny.quant.json", "scheme": "fp16"}
    result = audit_data(data, manifest.base_dir)
    assert "MODEL_QUANTIZATION_MISMATCH" in code_list(result)


def test_invalid_onnx(tmp_path):
    path = tmp_path / "bad.onnx"
    path.write_bytes(b"\xff\xff\xff")
    data = iot_data()
    data["models"] = [{"id": "MDL-BAD", "path": str(path)}]
    result = audit_data(data, tmp_path)
    assert "MODEL_INVALID" in code_list(result)
