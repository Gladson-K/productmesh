from .manifest import as_list, load_data, resolve_path


def inspect_benchmark(path):
    data = load_data(path)
    if not isinstance(data, dict):
        raise TypeError("Benchmark record must be an object.")
    return {
        "id": data.get("id"),
        "runtime": data.get("runtime"),
        "runtime_version": data.get("runtime_version"),
        "device": data.get("device"),
        "model_sha256": data.get("model_sha256"),
        "latency_ms": data.get("latency_ms"),
        "p50_ms": data.get("p50_ms"),
        "p95_ms": data.get("p95_ms"),
        "throughput_fps": data.get("throughput_fps"),
        "compiled": data.get("compiled"),
        "quantization": data.get("quantization"),
        "status": "stub",
    }


def _model_ids(manifest):
    return {item.get("id") for item in as_list(manifest.get("models")) if isinstance(item, dict)}


def audit_benchmarks(manifest, maps, add, base_dir):
    results = []
    models = _model_ids(manifest)
    for index, spec in enumerate(as_list(manifest.get("benchmarks"))):
        if not isinstance(spec, dict):
            add("BENCHMARK_INVALID", "high", f"benchmark[{index}]", "Benchmark entry must be an object.")
            continue
        where = spec.get("id") or f"benchmark[{index}]"
        component = spec.get("component")
        if component and component not in maps["components"]:
            add("BENCHMARK_COMPONENT_MISSING", "high", where, f"Benchmark references unknown component {component}.")
        model_id = spec.get("model")
        if model_id and model_id not in models:
            add("BENCHMARK_MODEL_MISSING", "high", where, f"Benchmark references unknown model {model_id}.")
        path_value = spec.get("path")
        if not path_value:
            add("BENCHMARK_MISSING", "high", where, "Benchmark entry has no path.")
            continue
        path = resolve_path(base_dir, path_value)
        if not path.is_file():
            add("BENCHMARK_MISSING", "high", where, f"Benchmark record is missing: {path_value}")
            continue
        try:
            record = inspect_benchmark(path)
        except Exception as exc:
            add("BENCHMARK_INVALID", "high", where, f"Cannot load benchmark record: {exc}")
            continue
        expected_runtime = spec.get("runtime")
        if expected_runtime and record.get("runtime") and expected_runtime != record["runtime"]:
            add(
                "BENCHMARK_RUNTIME_MISMATCH",
                "medium",
                where,
                f"Benchmark runtime is {record['runtime']}, expected {expected_runtime}.",
                expected=expected_runtime,
                actual=record["runtime"],
            )
        expected_device = spec.get("device")
        if expected_device and record.get("device") and expected_device != record["device"]:
            add(
                "BENCHMARK_DEVICE_MISMATCH",
                "medium",
                where,
                f"Benchmark device is {record['device']}, expected {expected_device}.",
                expected=expected_device,
                actual=record["device"],
            )
        expected_hash = spec.get("model_sha256")
        if expected_hash and record.get("model_sha256") and expected_hash != record["model_sha256"]:
            add(
                "BENCHMARK_MODEL_HASH_MISMATCH",
                "high",
                where,
                "Benchmark model hash does not match the declared hash.",
                expected=expected_hash,
                actual=record["model_sha256"],
            )
        max_latency = spec.get("max_latency_ms")
        latency = record.get("latency_ms")
        if isinstance(max_latency, (int, float)) and isinstance(latency, (int, float)) and latency > max_latency:
            add(
                "BENCHMARK_LATENCY_REGRESSION",
                "high",
                where,
                f"Latency {latency} ms exceeds limit {max_latency} ms.",
                limit=max_latency,
                actual=latency,
            )
        min_throughput = spec.get("min_throughput_fps")
        throughput = record.get("throughput_fps")
        if isinstance(min_throughput, (int, float)) and isinstance(throughput, (int, float)) and throughput < min_throughput:
            add(
                "BENCHMARK_THROUGHPUT_REGRESSION",
                "high",
                where,
                f"Throughput {throughput} fps is below minimum {min_throughput} fps.",
                limit=min_throughput,
                actual=throughput,
            )
        results.append(
            {
                "id": where,
                "path": path_value,
                "runtime": record.get("runtime"),
                "device": record.get("device"),
                "latency_ms": latency,
                "throughput_fps": throughput,
                "compiled": record.get("compiled"),
                "quantization": record.get("quantization"),
            }
        )
    return results
