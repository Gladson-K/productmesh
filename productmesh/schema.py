import json
from pathlib import Path

from .manifest import load_data

ROOT_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
PACKAGE_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
SCHEMA_DIR = ROOT_SCHEMA_DIR if ROOT_SCHEMA_DIR.is_dir() else PACKAGE_SCHEMA_DIR
SCHEMAS = {
    "product": SCHEMA_DIR / "product.schema.json",
    "workspace": SCHEMA_DIR / "workspace.schema.json",
    "lab": SCHEMA_DIR / "lab.schema.json",
}


def schema_path(name):
    if name in SCHEMAS:
        return SCHEMAS[name]
    target = Path(name)
    if target.is_file():
        return target
    raise ValueError(f"Unknown schema: {name}")


def load_schema(name):
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def infer_schema(path):
    name = Path(path).name.lower()
    if name.startswith("workspace") or name.endswith(".workspace.json"):
        return "workspace"
    if name.startswith("lab") or name.endswith(".lab.json"):
        return "lab"
    return "product"


def validate_data(data, schema_name):
    schema = load_schema(schema_name)
    try:
        import jsonschema
    except ImportError:
        return {
            "valid": True,
            "schema": str(schema_path(schema_name)),
            "validator": "unavailable",
            "errors": [],
            "warning": "Install jsonschema for full schema validation: pip install productmesh[schema]",
        }
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    return {
        "valid": not errors,
        "schema": str(schema_path(schema_name)),
        "validator": "jsonschema",
        "errors": [
            {
                "path": ".".join(str(part) for part in error.path) or "<root>",
                "message": error.message,
            }
            for error in errors
        ],
    }


def validate_file(path, schema_name=None):
    data = load_data(path)
    return validate_data(data, schema_name or infer_schema(path))
