# Contributing to ProductMesh

## Development setup

```bash
./setup.sh --dev
.venv/bin/python -m pytest -q
```

## Adding a product example

1. Create `examples/<product-id>/product.json` using the schema in `schemas/product.schema.json`.
2. Add any artifacts (OpenAPI specs, SBOM, ONNX model, evidence) under the product directory.
3. Add the product to `examples/workspace.json`.
4. Run `productmesh workspace audit examples/workspace.json`.
5. Add or update tests when introducing a new check.

## Adding a check

- Add a module under `productmesh/` or extend an existing one.
- Return issues through the audit `add(code, severity, where, message, **details)` callback.
- Add the check to `docs/V2_FEATURES.md`.
- Add a positive and a negative test under `tests/`.
- Keep core runtime standard-library only. Optional dependencies belong in `pyproject.toml`.

## Style

- Python 3.10+.
- Keep checks deterministic and offline-first.
- Do not add network calls to tests.
- Do not commit secrets, credentials or large binary artifacts.
- Report issues by severity: `critical`, `high`, `medium`, `low`, `info`.

## Pull requests

Include the command output for the examples and tests you ran. If a check changes the release gate, explain the migration path for existing manifests.
