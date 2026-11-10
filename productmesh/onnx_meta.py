import json
from pathlib import Path

from .manifest import as_list, resolve_path, sha256_file

DATA_TYPES = {
    1: "float32",
    2: "uint8",
    3: "int8",
    4: "uint16",
    5: "int16",
    6: "int32",
    7: "int64",
    8: "string",
    9: "bool",
    10: "float16",
    11: "float64",
    12: "uint32",
    13: "uint64",
    14: "complex64",
    15: "complex128",
    16: "bfloat16",
    17: "float8e4m3fn",
    18: "float8e4m3fnuz",
    19: "float8e5m2",
    20: "float8e5m2fnuz",
    21: "uint4",
    22: "int4",
    23: "float4e2m1",
}


def _read_varint(data, position):
    result = 0
    shift = 0
    while position < len(data):
        byte = data[position]
        position += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, position
        shift += 7
        if shift > 70:
            raise ValueError("Invalid varint")
    raise ValueError("Unexpected end of protobuf data")


def _to_signed64(value):
    return value - (1 << 64) if value >= (1 << 63) else value


def _parse_message(data):
    fields = {}
    position = 0
    while position < len(data):
        key, position = _read_varint(data, position)
        field = key >> 3
        wire = key & 7
        if field == 0:
            raise ValueError("Invalid protobuf field number")
        if wire == 0:
            value, position = _read_varint(data, position)
        elif wire == 1:
            value = data[position : position + 8]
            position += 8
        elif wire == 2:
            length, position = _read_varint(data, position)
            value = data[position : position + length]
            position += length
        elif wire == 5:
            value = data[position : position + 4]
            position += 4
        elif wire in (3, 4):
            raise ValueError("Protobuf groups are not supported")
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}")
        fields.setdefault(field, []).append(value)
    return fields


def _scalar(fields, number, default=None):
    values = fields.get(number)
    return values[0] if values else default


def _string(fields, number, default=""):
    value = _scalar(fields, number)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if value is not None else default


def _messages(fields, number):
    return [_parse_message(value) for value in fields.get(number, []) if isinstance(value, bytes)]


def _varints(fields, number):
    values = []
    for value in fields.get(number, []):
        if isinstance(value, int):
            values.append(_to_signed64(value))
        elif isinstance(value, bytes):
            position = 0
            while position < len(value):
                item, position = _read_varint(value, position)
                values.append(_to_signed64(item))
    return values


def _parse_shape(fields):
    shape = []
    for dimension in _messages(fields, 1):
        value = _scalar(dimension, 1)
        if value is not None:
            shape.append(_to_signed64(value))
        else:
            shape.append(_string(dimension, 2, "?"))
    return shape


def _parse_tensor_type(fields):
    elem_type = _scalar(fields, 1, 0)
    shape_value = _scalar(fields, 2)
    shape = _parse_shape(_parse_message(shape_value)) if isinstance(shape_value, bytes) else []
    return {"elem_type": elem_type, "dtype": DATA_TYPES.get(elem_type, f"unknown({elem_type})"), "shape": shape}


def _parse_type(fields):
    tensor = _scalar(fields, 1)
    if isinstance(tensor, bytes):
        return _parse_tensor_type(_parse_message(tensor))
    return {"elem_type": None, "dtype": "unknown", "shape": []}


def _parse_value_info(fields):
    type_value = _scalar(fields, 2)
    parsed_type = _parse_type(_parse_message(type_value)) if isinstance(type_value, bytes) else {}
    return {
        "name": _string(fields, 1),
        "dtype": parsed_type.get("dtype", "unknown"),
        "elem_type": parsed_type.get("elem_type"),
        "shape": parsed_type.get("shape", []),
    }


def _parse_tensor(fields):
    return {
        "name": _string(fields, 8),
        "dims": _varints(fields, 1),
        "elem_type": _scalar(fields, 2, 0),
    }


def _parse_opset(fields):
    return {"domain": _string(fields, 1), "version": _to_signed64(_scalar(fields, 2, 0))}


def _parse_graph(fields):
    initializers = [_parse_tensor(item) for item in _messages(fields, 5)]
    return {
        "name": _string(fields, 2),
        "node_count": len(fields.get(1, [])),
        "initializers": initializers,
        "inputs": [_parse_value_info(item) for item in _messages(fields, 11)],
        "outputs": [_parse_value_info(item) for item in _messages(fields, 12)],
    }


def inspect_onnx(path):
    target = Path(path)
    data = target.read_bytes()
    if not data:
        raise ValueError("ONNX file is empty.")
    fields = _parse_message(data)
    graph_fields = _scalar(fields, 7)
    graph = _parse_graph(_parse_message(graph_fields)) if isinstance(graph_fields, bytes) else None
    if graph is None and 1 not in fields:
        raise ValueError("File does not look like an ONNX ModelProto.")
    metadata = {}
    for entry in _messages(fields, 14):
        metadata[_string(entry, 1)] = _string(entry, 2)
    return {
        "path": str(target),
        "size": len(data),
        "sha256": sha256_file(target),
        "ir_version": _to_signed64(_scalar(fields, 1, 0)),
        "producer_name": _string(fields, 2),
        "producer_version": _string(fields, 3),
        "domain": _string(fields, 4),
        "model_version": _to_signed64(_scalar(fields, 5, 0)),
        "opset_imports": [_parse_opset(item) for item in _messages(fields, 8)],
        "graph": graph,
        "metadata": metadata,
    }


def _expected_shape_matches(expected, actual):
    if not isinstance(expected, (list, tuple)) or not isinstance(actual, (list, tuple)):
        return True
    if len(expected) != len(actual):
        return False
    for expected_dim, actual_dim in zip(expected, actual):
        if isinstance(expected_dim, str):
            continue
        if isinstance(actual_dim, str):
            return False
        if expected_dim != actual_dim:
            return False
    return True


def _compare_value_infos(actual, expected, direction, where, add, strict):
    actual_by_name = {item.get("name"): item for item in actual}
    expected_entries = []
    for item in expected or []:
        if isinstance(item, str):
            expected_entries.append({"name": item})
        elif isinstance(item, dict):
            expected_entries.append(item)
    expected_names = set()
    for entry in expected_entries:
        name = entry.get("name")
        expected_names.add(name)
        actual_item = actual_by_name.get(name)
        code_prefix = "MODEL_INPUT" if direction == "input" else "MODEL_OUTPUT"
        if not actual_item:
            add(f"{code_prefix}_MISSING", "high", where, f"Expected {direction} {name} is missing from the model.")
            continue
        if entry.get("dtype") and actual_item.get("dtype") != entry["dtype"]:
            add(
                f"{code_prefix}_DTYPE_MISMATCH",
                "high",
                where,
                f"{direction.title()} {name} dtype is {actual_item.get('dtype')}, expected {entry['dtype']}.",
                expected=entry["dtype"],
                actual=actual_item.get("dtype"),
            )
        if "shape" in entry and not _expected_shape_matches(entry["shape"], actual_item.get("shape")):
            add(
                f"{code_prefix}_SHAPE_MISMATCH",
                "high",
                where,
                f"{direction.title()} {name} shape is {actual_item.get('shape')}, expected {entry['shape']}.",
                expected=entry["shape"],
                actual=actual_item.get("shape"),
            )
    if strict:
        for name in sorted(set(actual_by_name) - expected_names):
            code_prefix = "MODEL_INPUT" if direction == "input" else "MODEL_OUTPUT"
            add(f"{code_prefix}_UNEXPECTED", "medium", where, f"Unexpected {direction} {name} is present in the model.")


def _opset_version(imports, domain=""):
    for item in imports:
        if (item.get("domain") or "") == domain:
            return item.get("version")
    return None


def _compare_ir_version(actual, expected, where, add):
    if expected is None:
        return
    if isinstance(expected, dict):
        minimum = expected.get("min")
        maximum = expected.get("max")
        if minimum is not None and actual < minimum:
            add("MODEL_IR_VERSION_MISMATCH", "high", where, f"IR version {actual} is below minimum {minimum}.")
        if maximum is not None and actual > maximum:
            add("MODEL_IR_VERSION_MISMATCH", "high", where, f"IR version {actual} is above maximum {maximum}.")
    elif actual != expected:
        add("MODEL_IR_VERSION_MISMATCH", "high", where, f"IR version is {actual}, expected {expected}.", expected=expected, actual=actual)


def _audit_quantization(model, spec, where, add, base_dir):
    quantization = spec.get("quantization")
    if not quantization:
        return
    if isinstance(quantization, str):
        quantization = {"path": quantization}
    elif not isinstance(quantization, dict):
        add("MODEL_QUANTIZATION_INVALID", "high", where, "Quantization metadata must be a path or object.")
        return
    path_value = quantization.get("path")
    if not path_value:
        return
    path = resolve_path(base_dir, path_value)
    if not path.is_file():
        add("MODEL_QUANTIZATION_MISSING", "medium", where, f"Quantization metadata is missing: {path_value}")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        add("MODEL_QUANTIZATION_INVALID", "high", where, f"Cannot parse quantization metadata: {exc}")
        return
    if not isinstance(data, dict):
        add("MODEL_QUANTIZATION_INVALID", "high", where, "Quantization metadata must be a JSON object.")
        return
    if data.get("model_sha256") and data["model_sha256"] != model["sha256"]:
        add(
            "MODEL_QUANTIZATION_MISMATCH",
            "high",
            where,
            "Quantization metadata does not match the model artifact hash.",
            expected=data["model_sha256"],
            actual=model["sha256"],
        )
    if quantization.get("scheme") and data.get("scheme") and quantization["scheme"] != data["scheme"]:
        add(
            "MODEL_QUANTIZATION_MISMATCH",
            "high",
            where,
            f"Quantization scheme is {data['scheme']}, expected {quantization['scheme']}.",
            expected=quantization["scheme"],
            actual=data["scheme"],
        )


def audit_models(manifest, maps, add, base_dir):
    results = []
    specs = as_list(manifest.get("models"))
    for index, spec in enumerate(specs):
        if isinstance(spec, str):
            spec = {"path": spec}
        elif not isinstance(spec, dict):
            add("MODEL_INVALID", "high", f"model[{index}]", "Model entry must be a path or object.")
            continue
        where = spec.get("id") or f"model[{index}]"
        component_id = spec.get("component")
        if component_id and component_id not in maps["components"]:
            add("MODEL_COMPONENT_MISSING", "high", where, f"Model references unknown component {component_id}.")
        path_value = spec.get("path")
        if not path_value:
            add("MODEL_MISSING", "high", where, "Model entry has no path.")
            continue
        path = resolve_path(base_dir, path_value)
        if not path.is_file():
            add("MODEL_MISSING", "high", where, f"Model artifact is missing: {path_value}")
            continue
        try:
            model = inspect_onnx(path)
        except Exception as exc:
            add("MODEL_INVALID", "high", where, f"Cannot parse ONNX model: {exc}")
            continue
        if spec.get("sha256") and spec["sha256"] != model["sha256"]:
            add(
                "MODEL_HASH_MISMATCH",
                "high",
                where,
                "Model artifact hash does not match the declared hash.",
                expected=spec["sha256"],
                actual=model["sha256"],
            )
        expected = spec.get("expected") or {}
        if not isinstance(expected, dict):
            add("MODEL_INVALID", "high", where, "Model expected metadata must be an object.")
            expected = {}
        _compare_ir_version(model["ir_version"], expected.get("ir_version"), where, add)
        expected_opset = expected.get("opset")
        if isinstance(expected_opset, int):
            actual = _opset_version(model["opset_imports"])
            if actual != expected_opset:
                add("MODEL_OPSET_MISMATCH", "high", where, f"Default opset is {actual}, expected {expected_opset}.", expected=expected_opset, actual=actual)
        elif isinstance(expected_opset, dict):
            for domain, version in expected_opset.items():
                actual = _opset_version(model["opset_imports"], domain)
                if actual != version:
                    add(
                        "MODEL_OPSET_MISMATCH",
                        "high",
                        where,
                        f"Opset for domain '{domain}' is {actual}, expected {version}.",
                        expected=version,
                        actual=actual,
                    )
        graph = model.get("graph") or {"inputs": [], "outputs": []}
        _compare_value_infos(graph["inputs"], expected.get("inputs"), "input", where, add, spec.get("strict", False))
        _compare_value_infos(graph["outputs"], expected.get("outputs"), "output", where, add, spec.get("strict", False))
        if expected.get("producer_name") and model["producer_name"] != expected["producer_name"]:
            add("MODEL_PRODUCER_MISMATCH", "medium", where, f"Producer is {model['producer_name']}, expected {expected['producer_name']}.")
        _audit_quantization(model, spec, where, add, base_dir)
        results.append(
            {
                "id": where,
                "path": path_value,
                "sha256": model["sha256"],
                "ir_version": model["ir_version"],
                "opset": model["opset_imports"],
                "inputs": graph["inputs"],
                "outputs": graph["outputs"],
            }
        )
    return results
