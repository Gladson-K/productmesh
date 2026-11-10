import json
import re
from pathlib import Path

from .issues import make_issue, sort_issues
from .manifest import as_list, resolve_path

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def load_spec(path):
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("YAML OpenAPI specs require PyYAML; install productmesh[yaml].") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise TypeError("OpenAPI document must be an object.")
    if "openapi" not in data and "swagger" not in data:
        raise ValueError("Document does not declare openapi or swagger version.")
    return data


def _resolve_ref(doc, ref):
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {}
    current = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            return {}
        current = current[part]
    return current


def _deref(doc, value, seen=None):
    seen = seen or set()
    if not isinstance(value, dict):
        return value
    ref = value.get("$ref")
    if not ref or ref in seen:
        return value
    seen.add(ref)
    resolved = _resolve_ref(doc, ref)
    if not isinstance(resolved, dict):
        return value
    merged = dict(resolved)
    merged.update({key: item for key, item in value.items() if key != "$ref"})
    return _deref(doc, merged, seen)


def _schema_type(schema):
    if not isinstance(schema, dict):
        return None
    declared = schema.get("type")
    if isinstance(declared, list):
        return tuple(sorted(declared))
    if declared:
        return declared
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return None


def _major_version(value):
    if value is None:
        return None
    match = re.match(r"(\d+)", str(value).strip().lower().lstrip("v"))
    return int(match.group(1)) if match else None


def _compare_schema(old_doc, new_doc, old, new, where, add, seen, direction):
    old = _deref(old_doc, old)
    new = _deref(new_doc, new)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    marker = (id(old), id(new), direction)
    if marker in seen:
        return
    seen.add(marker)
    old_type = _schema_type(old)
    new_type = _schema_type(new)
    if old_type and new_type and old_type != new_type:
        add("API_TYPE_CHANGED", "high", where, f"Schema type changed from {old_type} to {new_type}.", old=old_type, new=new_type)
    old_enum = set(old.get("enum") or [])
    new_enum = set(new.get("enum") or [])
    if old_enum and new_enum and not old_enum <= new_enum:
        removed = sorted(map(str, old_enum - new_enum))
        add("API_ENUM_NARROWED", "high", where, f"Enum values removed: {', '.join(removed)}.", removed=removed)
    if old.get("nullable") is True and new.get("nullable") is False:
        add("API_NULLABLE_REMOVED", "high", where, "Schema no longer allows null.")
    old_props = old.get("properties") or {}
    new_props = new.get("properties") or {}
    old_required = set(old.get("required") or [])
    new_required = set(new.get("required") or [])
    for prop in sorted(set(old_props) - set(new_props)):
        severity = "high" if prop in old_required else ("medium" if direction == "response" else "low")
        add("API_FIELD_REMOVED", severity, f"{where}.{prop}", f"Field {prop} was removed.", field=prop)
    for prop in sorted(set(new_props) - set(old_props)):
        if prop in new_required:
            severity = "high" if direction == "request" else "medium"
            add(
                "API_REQUIRED_FIELD_ADDED",
                severity,
                f"{where}.{prop}",
                f"New required {direction} field {prop} was added.",
                field=prop,
            )
        else:
            add("API_FIELD_ADDED", "info", f"{where}.{prop}", f"Optional {direction} field {prop} was added.")
    for prop in sorted(set(old_props) & set(new_props)):
        _compare_schema(old_doc, new_doc, old_props[prop], new_props[prop], f"{where}.{prop}", add, seen, direction)
    if "items" in old or "items" in new:
        _compare_schema(old_doc, new_doc, old.get("items", {}), new.get("items", {}), f"{where}[]", add, seen, direction)
    old_format = old.get("format")
    new_format = new.get("format")
    if old_format and new_format and old_format != new_format:
        add("API_FORMAT_CHANGED", "medium", where, f"Format changed from {old_format} to {new_format}.")
    if old.get("pattern") and new.get("pattern") and old["pattern"] != new["pattern"]:
        add("API_PATTERN_CHANGED", "medium", where, "Validation pattern changed.")
    if old.get("additionalProperties") is not False and new.get("additionalProperties") is False:
        add("API_ADDITIONAL_PROPERTIES_RESTRICTED", "high", where, "Schema no longer allows additional properties.")
    old_min = old.get("minimum")
    new_min = new.get("minimum")
    if new_min is not None and (old_min is None or new_min > old_min):
        add("API_CONSTRAINT_TIGHTENED", "medium", where, f"Minimum increased from {old_min} to {new_min}.")
    old_max = old.get("maximum")
    new_max = new.get("maximum")
    if new_max is not None and (old_max is None or new_max < old_max):
        add("API_CONSTRAINT_TIGHTENED", "medium", where, f"Maximum decreased from {old_max} to {new_max}.")
    for combinator in ("allOf", "oneOf", "anyOf"):
        old_items = old.get(combinator) or []
        new_items = new.get(combinator) or []
        if old_items and new_items:
            for index in range(min(len(old_items), len(new_items))):
                _compare_schema(old_doc, new_doc, old_items[index], new_items[index], f"{where}.{combinator}[{index}]", add, seen, direction)


def _content_schema(container):
    if not isinstance(container, dict):
        return None
    content = container.get("content")
    if isinstance(content, dict) and content:
        for media_type in sorted(content, key=lambda item: (item != "application/json", "+json" not in item, item)):
            schema = content[media_type].get("schema")
            if schema is not None:
                return schema
    return container.get("schema")


def _merged_parameters(doc, path_item, operation):
    merged = {}
    for source in (path_item.get("parameters") or [], operation.get("parameters") or []):
        for parameter in source:
            parameter = _deref(doc, parameter)
            key = (parameter.get("in"), parameter.get("name"))
            merged[key] = parameter
    return merged


def _compare_parameters(old_doc, new_doc, old_params, new_params, where, add):
    for key in sorted(set(old_params) - set(new_params), key=str):
        parameter = old_params[key]
        severity = "high" if parameter.get("required") else "medium"
        add("API_PARAM_REMOVED", severity, f"{where} {key[0]}:{key[1]}", f"Parameter {key[1]} ({key[0]}) was removed.")
    for key in sorted(set(new_params) - set(old_params), key=str):
        parameter = new_params[key]
        severity = "high" if parameter.get("required") else "info"
        add("API_PARAM_ADDED", severity, f"{where} {key[0]}:{key[1]}", f"Parameter {key[1]} ({key[0]}) was added.")
    for key in sorted(set(old_params) & set(new_params), key=str):
        old = old_params[key]
        new = new_params[key]
        location = f"{where} {key[0]}:{key[1]}"
        if not old.get("required") and new.get("required"):
            add("API_PARAM_REQUIRED_ADDED", "high", location, f"Parameter {key[1]} became required.")
        _compare_schema(old_doc, new_doc, old.get("schema", {}), new.get("schema", {}), location, add, set(), "request")


def _request_schema(doc, operation):
    schema = _content_schema(_deref(doc, operation.get("requestBody", {})))
    if schema is not None:
        return schema
    for parameter in operation.get("parameters") or []:
        parameter = _deref(doc, parameter)
        if parameter.get("in") == "body":
            return parameter.get("schema")
    return None


def _compare_operations(old_doc, new_doc, old_path, new_path, path_key, method, add):
    old = _deref(old_doc, old_path[method])
    new = _deref(new_doc, new_path[method])
    where = f"{method.upper()} {path_key}"
    _compare_parameters(
        old_doc,
        new_doc,
        _merged_parameters(old_doc, old_path, old),
        _merged_parameters(new_doc, new_path, new),
        where,
        add,
    )
    old_body = _request_schema(old_doc, old)
    new_body = _request_schema(new_doc, new)
    if old_body is not None and new_body is None:
        add("API_REQUEST_BODY_REMOVED", "high", where, "Request body was removed.")
    elif old_body is None and new_body is not None:
        required = bool(_deref(new_doc, new.get("requestBody", {})).get("required"))
        add(
            "API_REQUEST_BODY_ADDED",
            "high" if required else "info",
            where,
            f"Request body was added{' and is required' if required else ''}.",
        )
    elif old_body is not None and new_body is not None:
        _compare_schema(old_doc, new_doc, old_body, new_body, f"{where} request", add, set(), "request")
    old_responses = old.get("responses") or {}
    new_responses = new.get("responses") or {}
    for status in sorted(set(old_responses) - set(new_responses), key=str):
        add("API_RESPONSE_REMOVED", "high", f"{where} {status}", f"Response {status} was removed.")
    for status in sorted(set(new_responses) - set(old_responses), key=str):
        add("API_RESPONSE_ADDED", "info", f"{where} {status}", f"Response {status} was added.")
    for status in sorted(set(old_responses) & set(new_responses), key=str):
        old_schema = _content_schema(_deref(old_doc, old_responses[status]))
        new_schema = _content_schema(_deref(new_doc, new_responses[status]))
        if old_schema is not None or new_schema is not None:
            _compare_schema(old_doc, new_doc, old_schema or {}, new_schema or {}, f"{where} {status} response", add, set(), "response")
    if old.get("deprecated") is not True and new.get("deprecated") is True:
        add("API_OPERATION_DEPRECATED", "info", where, "Operation is now deprecated.")


def diff_specs(old_doc, new_doc):
    issues = []

    def add(code, severity, where, message, **details):
        issues.append(make_issue(code, severity, where, message, **details))

    old_paths = old_doc.get("paths") or {}
    new_paths = new_doc.get("paths") or {}
    for path_key in sorted(set(old_paths) - set(new_paths)):
        add("API_PATH_REMOVED", "critical", path_key, f"Path {path_key} was removed.")
    for path_key in sorted(set(new_paths) - set(old_paths)):
        add("API_PATH_ADDED", "info", path_key, f"Path {path_key} was added.")
    for path_key in sorted(set(old_paths) & set(new_paths)):
        old_path = _deref(old_doc, old_paths[path_key])
        new_path = _deref(new_doc, new_paths[path_key])
        old_methods = {method for method in HTTP_METHODS if method in old_path}
        new_methods = {method for method in HTTP_METHODS if method in new_path}
        for method in sorted(old_methods - new_methods):
            add("API_OPERATION_REMOVED", "critical", f"{method.upper()} {path_key}", f"Operation {method.upper()} was removed.")
        for method in sorted(new_methods - old_methods):
            add("API_OPERATION_ADDED", "info", f"{method.upper()} {path_key}", f"Operation {method.upper()} was added.")
        for method in sorted(old_methods & new_methods):
            _compare_operations(old_doc, new_doc, old_path, new_path, path_key, method, add)
    old_schemes = (old_doc.get("components") or {}).get("securitySchemes") or old_doc.get("securityDefinitions") or {}
    new_schemes = (new_doc.get("components") or {}).get("securitySchemes") or new_doc.get("securityDefinitions") or {}
    for name in sorted(set(old_schemes) - set(new_schemes)):
        add("API_AUTH_SCHEME_REMOVED", "high", name, f"Security scheme {name} was removed.")
    for name in sorted(set(new_schemes) - set(old_schemes)):
        add("API_AUTH_SCHEME_ADDED", "info", name, f"Security scheme {name} was added.")
    if (old_doc.get("security") or []) != (new_doc.get("security") or []):
        add("API_AUTH_CHANGED", "high", "security", "Top-level security requirements changed.")
    old_version = (old_doc.get("info") or {}).get("version")
    new_version = (new_doc.get("info") or {}).get("version")
    if old_version != new_version:
        add("API_VERSION_CHANGED", "info", "info.version", f"API version changed from {old_version} to {new_version}.")
    return sort_issues(issues)


def audit_api_contracts(manifest, maps, add, base_dir, policy):
    contracts = as_list(manifest.get("api_contracts"))
    if not contracts and policy.get("require_openapi"):
        add("API_SPEC_MISSING", "high", "api_contracts", "OpenAPI contract is required but not declared.")
    results = []
    for index, contract in enumerate(contracts):
        if isinstance(contract, str):
            contract = {"current": contract}
        elif not isinstance(contract, dict):
            add("API_SPEC_INVALID", "high", f"api_contract[{index}]", "Contract entry must be a path or object.")
            continue
        where = contract.get("id") or contract.get("interface") or f"api_contract[{index}]"
        interface_id = contract.get("interface")
        interface = maps["interfaces"].get(interface_id) if interface_id else None
        if interface_id and not interface:
            add("API_INTERFACE_MISSING", "high", where, f"Interface {interface_id} does not exist.")
        current_path = contract.get("current")
        if not current_path:
            add("API_SPEC_MISSING", "high", where, "Contract does not declare a current spec path.")
            results.append({"id": where, "interface": interface_id, "error": "missing current"})
            continue
        try:
            current = load_spec(resolve_path(base_dir, current_path))
        except Exception as exc:
            add("API_SPEC_INVALID", "high", where, f"Cannot load current spec: {exc}")
            results.append({"id": where, "interface": interface_id, "error": str(exc)})
            continue
        spec_version = (current.get("info") or {}).get("version")
        interface_version = (interface or {}).get("version")
        if interface_version and spec_version and _major_version(interface_version) != _major_version(spec_version):
            add(
                "API_INTERFACE_VERSION_MISMATCH",
                "high",
                where,
                f"Interface declares {interface_version} but spec publishes {spec_version}.",
                expected=interface_version,
                actual=spec_version,
            )
        breaking = 0
        baseline_path = contract.get("baseline")
        if baseline_path:
            try:
                baseline = load_spec(resolve_path(base_dir, baseline_path))
            except Exception as exc:
                add("API_BASELINE_INVALID", "high", where, f"Cannot load baseline spec: {exc}")
                baseline = None
            if baseline is not None:
                diff = diff_specs(baseline, current)
                breaking = sum(1 for issue in diff if issue["severity"] in ("critical", "high"))
                if breaking and contract.get("allow_breaking"):
                    add(
                        "API_BREAKING_ALLOWED",
                        "info",
                        where,
                        f"{breaking} breaking change(s) allowed by contract policy.",
                        breaking=breaking,
                    )
                else:
                    for issue in diff:
                        add(issue["code"], issue["severity"], f"{where} {issue['where']}", issue["message"], **issue.get("details", {}))
        elif contract.get("require_baseline"):
            add("API_BASELINE_MISSING", "high", where, "Contract requires a baseline spec.")
        results.append(
            {
                "id": where,
                "interface": interface_id,
                "current": current_path,
                "baseline": baseline_path,
                "spec_version": spec_version,
                "interface_version": interface_version,
                "breaking": breaking,
            }
        )
    return results
