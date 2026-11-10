# ProductMesh V2

**Connect every stage. Detect every mismatch.**

ProductMesh is a cross-discipline product lifecycle integrity workspace. It connects requirements, software, firmware, hardware-facing interfaces, environments, AI/ML artifacts, repositories, SBOMs, verification evidence and release policy so incompatibilities are detected before they become expensive integration failures.

V2 is a local-first Python engine with a multi-product workspace, a device fleet model and a read-only dashboard. It complements rather than replaces GitHub/GitLab, Jira, PLM/MBSE, CAD/EDA, CI/CD and observability tools.

## V2 capabilities

| Area | V2 implementation |
| --- | --- |
| Multi-product workspace | `workspace.json` audits many products and aggregates release status |
| Multiple devices per product | Board, firmware, environment, voltage, interface and resource checks |
| Git repository integration | Local or remote repository inspection, dirty tree, commit/ref/remote checks |
| OpenAPI contract diff | Removed paths/operations, required-field changes, type/enum/auth changes |
| SBOM ingestion | CycloneDX and SPDX JSON, required components, version drift, vulnerabilities |
| ONNX metadata inspection | IR version, opset, tensor names, dtype, shapes, hash and quantization metadata |
| Evidence and release gates | Test status, evidence file hashes, policy-based release blocking |
| Reports | Human output, JSON, SARIF 2.1.0 and Markdown |
| Dashboard | Workspace summary, product audit and device matrix |
| CI/CD | GitHub Actions workflow and reusable `action.yml` release gate |

V1 compatibility is preserved: existing product manifests, `audit` output and the three original examples continue to work.

## Quick start

Python 3.10+ is required. Core functionality uses only the standard library.

```bash
./setup.sh
.venv/bin/python -m productmesh.cli audit examples/iot-edge-monitor/product.json
.venv/bin/python -m productmesh.cli workspace audit examples/workspace.json
.venv/bin/python -m productmesh.cli serve
```

Open http://127.0.0.1:8080. Override with `PRODUCTMESH_PORT=18080` if the port is occupied.

Run tests:

```bash
./setup.sh --dev
.venv/bin/python -m pytest -q
```

## CLI

```bash
productmesh audit [manifest] [--json] [--format json|sarif|markdown] [--output FILE]
productmesh release [manifest] [--json] [--format json|sarif|markdown] [--output FILE]
productmesh workspace audit [workspace.json] [--json] [--format json|sarif|markdown]
productmesh workspace list [workspace.json] [--json]
productmesh repo inspect <path-or-remote-url> [--json]
productmesh openapi diff <baseline> <current> [--json] [--fail-on-breaking]
productmesh sbom inspect <sbom.json> [--json]
productmesh model inspect <model.onnx> [--json]
productmesh serve [--host HOST] [--port PORT]
```

Exit codes: `0` release ready, `2` release blocked, `1` unexpected error.

## Workspace and multiple devices

A workspace groups products:

```json
{
  "schema_version": "2.0",
  "workspace": {"id": "fleet", "name": "Product Fleet"},
  "products": [
    {"id": "iot-edge-monitor", "manifest": "iot-edge-monitor/product.json"},
    {"id": "edge-ai-deployment", "manifest": "edge-ai-deployment/product.json"}
  ]
}
```

A product can declare several devices:

```json
"devices": [
  {
    "id": "DEV-ESP32-S3",
    "board": "esp32-s3-devkitc-1",
    "firmware": "CMP-FW",
    "environment": "ENV-DEV",
    "logic_voltage": "3.3V",
    "interfaces": ["IF-SENSOR", "IF-HTTP"],
    "constraints": {"min_flash_mb": 8, "min_ram_kb": 512},
    "specs": {"flash_mb": 8, "ram_kb": 512}
  }
]
```

Device checks include missing firmware/environment/interface references, voltage mismatches, board/firmware target mismatches, unsupported interfaces, duplicate device IDs and resource shortfalls.

## Repository integration

```json
"repositories": [
  {
    "id": "REPO-FW",
    "role": "firmware",
    "component": "CMP-FW",
    "path": "../firmware",
    "remote": "https://github.com/example/firmware.git",
    "ref": "v1.2.0",
    "required_clean": true
  }
]
```

Local repositories are inspected with Git. Remote-only repositories are resolved with `git ls-remote`. Checks cover missing/non-Git paths, dirty trees, dirty submodules, commit/ref drift and remote mismatch. Repository inspection is offline-first; remote lookups require network access.

## OpenAPI contract comparison

```json
"api_contracts": [
  {
    "id": "API-REST",
    "interface": "IF-REST",
    "baseline": "specs/openapi-v1.json",
    "current": "specs/openapi-v2.json",
    "allow_breaking": false
  }
]
```

The diff detects removed paths/operations/responses, removed or newly required parameters/fields, type/enum/format changes, tightened constraints and authentication changes. JSON specs work with the standard library; YAML requires `pip install productmesh[yaml]`.

## SBOM ingestion

```json
"sbom": {
  "id": "SBOM-EDGE",
  "path": "sbom.cdx.json",
  "required_components": ["pkg:pypi/onnxruntime@1.18.0"]
}
```

CycloneDX and SPDX JSON are supported. Checks cover required components, declared component/version drift, duplicates, missing licenses (optional) and high/critical vulnerabilities.

## ONNX model inspection

```json
"models": [
  {
    "id": "MDL-TINY",
    "component": "CMP-MODEL",
    "path": "models/tiny.onnx",
    "sha256": "...",
    "quantization": {"path": "models/tiny.quant.json", "scheme": "int8"},
    "expected": {
      "ir_version": 8,
      "opset": 17,
      "inputs": [{"name": "input", "dtype": "float32", "shape": ["batch", 3, 224, 224]}],
      "outputs": [{"name": "output", "dtype": "float32", "shape": ["batch", 1000]}]
    }
  }
]
```

ONNX metadata is parsed directly from the protobuf wire format; the `onnx` package is not required. Checks cover IR/opset drift, input/output names, dtype, static shape dimensions, artifact hash and quantization metadata consistency.

## Evidence and release policy

```json
"tests": [
  {
    "id": "TEST-003",
    "name": "Board and voltage compatibility",
    "status": "passed",
    "evidence": [{"path": "evidence/voltage.json", "sha256": "..."}],
    "checks": {"requirement": "REQ-003", "component": "CMP-FW", "environment": "ENV-DEV", "voltage": "3.3V"}
  }
],
"release": {
  "block_on_high": true,
  "allow_dirty_repo": false,
  "require_sbom": true,
  "require_evidence": true
}
```

Failed/blocked tests, missing evidence, evidence hash drift, SBOM/OpenAPI requirements and dirty repositories can block the release gate.

## Examples

- `examples/iot-edge-monitor`: ESP32 firmware, sensor bus, HTTP API, two devices, voltage checks.
- `examples/mobile-api-contract`: mobile/backend OpenAPI v1→v2 contract diff and environment profiles.
- `examples/edge-ai-deployment`: ONNX model, quantization metadata, CycloneDX SBOM and two deployment targets.
- `examples/workspace.json`: all three products in one fleet workspace.

## CI and GitHub Action

`.github/workflows/ci.yml` runs tests, audits every example, checks the workspace, diffs OpenAPI, inspects the SBOM/ONNX model and uploads a SARIF report.

Use the composite action in another repository:

```yaml
- uses: your-org/productmesh@v2
  with:
    workspace: path/to/workspace.json
    format: sarif
    output: productmesh.sarif
```

## JSON schemas

Editor and CI schemas are provided in `schemas/product.schema.json` and `schemas/workspace.schema.json`.

## Limitations

Checks operate on declared metadata, repository state, artifacts and evidence. They do not perform physical electrical measurements, PCB parsing, source semantic analysis, hardware-in-the-loop testing or accelerator benchmarking. A green gate means the declared V2 checks passed, not that the product is physically safe or functionally correct.

## Documentation

See `docs/ARCHITECTURE.md`, `docs/V2_FEATURES.md`, `docs/USE_CASES.md`, `docs/ROADMAP.md`, `docs/RESEARCH_AND_ANALYSIS.md`, `docs/REFERENCES.md` and `PROJECT_MAP.md`.
