from .manifest import as_list, load_data, resolve_path


def _value(value):
    if isinstance(value, dict):
        for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if key in value:
                return value[key]
        return value
    return value


def _attributes(value):
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    result = {}
    for item in as_list(value):
        if isinstance(item, dict) and item.get("key"):
            result[item["key"]] = _value(item.get("value"))
    return result


def _spans_from_resource(data):
    spans = []
    for resource_span in as_list(data.get("resourceSpans")):
        if not isinstance(resource_span, dict):
            continue
        resource = _attributes((resource_span.get("resource") or {}).get("attributes"))
        for scope_span in as_list(resource_span.get("scopeSpans") or resource_span.get("instrumentationLibrarySpans")):
            if not isinstance(scope_span, dict):
                continue
            for span in as_list(scope_span.get("spans")):
                if isinstance(span, dict):
                    spans.append({"resource": resource, "span": span})
    return spans


def load_spans(path):
    data = load_data(path)
    if isinstance(data, list):
        raw = [{"resource": {}, "span": span} for span in data if isinstance(span, dict)]
    elif isinstance(data, dict):
        raw = _spans_from_resource(data)
        if not raw:
            raw = [{"resource": {}, "span": span} for span in as_list(data.get("spans")) if isinstance(span, dict)]
    else:
        raise TypeError("Span document must be an object or array.")
    spans = []
    for item in raw:
        span = item["span"]
        attributes = {**item.get("resource", {}), **_attributes(span.get("attributes"))}
        status = span.get("status") or {}
        spans.append(
            {
                "trace_id": span.get("traceId") or span.get("trace_id"),
                "span_id": span.get("spanId") or span.get("span_id"),
                "name": span.get("name"),
                "service": attributes.get("service.name"),
                "attributes": attributes,
                "status": status.get("code") or status.get("message") or "UNSET",
                "error": bool(span.get("error")) or str(status.get("code", "")).upper() == "ERROR",
            }
        )
    return spans


def summarize_spans(spans):
    traces = {span.get("trace_id") for span in spans if span.get("trace_id")}
    services = {span.get("service") for span in spans if span.get("service")}
    return {
        "spans": len(spans),
        "traces": len(traces),
        "services": sorted(services),
        "errors": sum(1 for span in spans if span.get("error")),
        "status": "stub",
    }


def correlate(spans, product=None, device=None):
    matches = []
    for span in spans:
        attributes = span.get("attributes") or {}
        if product and attributes.get("productmesh.product") != product:
            continue
        if device and attributes.get("productmesh.device") != device:
            continue
        matches.append(span)
    return matches


def audit_observability(manifest, add, base_dir):
    specs = as_list(manifest.get("observability"))
    if isinstance(manifest.get("observability"), dict):
        specs = [manifest["observability"]]
    results = []
    for index, spec in enumerate(specs):
        if isinstance(spec, str):
            spec = {"path": spec}
        elif not isinstance(spec, dict):
            add("OTEL_INVALID", "high", f"observability[{index}]", "Observability entry must be a path or object.")
            continue
        where = spec.get("id") or f"observability[{index}]"
        path_value = spec.get("path")
        if not path_value:
            add("OTEL_MISSING", "high", where, "Observability entry has no path.")
            continue
        path = resolve_path(base_dir, path_value)
        if not path.is_file():
            add("OTEL_MISSING", "high", where, f"Span export is missing: {path_value}")
            continue
        try:
            spans = load_spans(path)
        except Exception as exc:
            add("OTEL_INVALID", "high", where, f"Cannot load span export: {exc}")
            continue
        summary = summarize_spans(spans)
        for attribute in as_list(spec.get("required_attributes")):
            if not any(attribute in (span.get("attributes") or {}) for span in spans):
                add(
                    "OTEL_ATTRIBUTE_MISSING",
                    "high",
                    where,
                    f"Required span attribute is missing: {attribute}",
                    attribute=attribute,
                )
        results.append({"id": where, "path": path_value, **summary})
    return results
