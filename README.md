# ProductMesh V2.1

**Connect every stage. Detect every mismatch.**

ProductMesh is a cross-discipline product lifecycle integrity workspace. It connects requirements, software, firmware, hardware-facing interfaces, environments, AI/ML artifacts, repositories, SBOMs, verification evidence and release policy so incompatibilities are detected before they become expensive integration failures.

V2.1 is a local-first Python engine with a multi-product workspace, a device fleet model, a read-only dashboard and deterministic stubs for the V3/V4 roadmap. It complements rather than replaces GitHub/GitLab, Jira, PLM/MBSE, CAD/EDA, CI/CD and observability tools. Stubs normalize local exports and declared metadata; they do not call external services or drive real hardware.

## Capabilities

| Area | Implementation |
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
| Connectors | Local GitHub/GitLab/Jira/Azure DevOps JSON export normalization |
| Firmware and lab | Firmware fingerprinting, serial discovery, lab inventory and board lookup |
| Electrical | Pin-map conflicts, bus-address collisions and power-budget checks |
| HIL and benchmarks | Mock/serial HIL adapters, benchmark evidence and regression limits |
| Observability | OpenTelemetry span import, service summary and product/device correlation |
| Cloud and governance | Local cloud workspace store, RBAC, approvals, audit history and enterprise profiles |

V1 compatibility is preserved: existing product manifests, `audit` output and the three original examples continue to work.

## Quick start

Python 3.10+ is required. Core functionality uses only the standard library.

```bash
./setup.sh
.venv/bin/python -m productmesh.cli validate examples/iot-edge-monitor/product.json
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
productmesh validate <file> [--schema product|workspace|lab|PATH] [--json]
productmesh connector list [--json]
productmesh connector inspect <github|gitlab|jira|azure_devops> <export.json> [--json]
productmesh connector import <name> <export.json> [--output FILE]
productmesh firmware inspect <artifact> [--json]
productmesh firmware discover [--root PATTERN] [--json]
productmesh device discover [--root PATTERN] [--json]
productmesh hil list [--json]
productmesh hil run <plan.json> [--adapter mock|serial]
productmesh lab list [--inventory FILE] [--json]
productmesh lab inspect <board> [--inventory FILE] [--json]
productmesh benchmark inspect <record.json> [--json]
productmesh otel inspect <spans.json> [--json]
productmesh cloud init|status|add-member|request|approve|history [options]
productmesh history record|list|summary [options]
productmesh policy show|validate [--file FILE]
productmesh advise [manifest] [--json]
productmesh enterprise profile|check <on_prem|hybrid|saas> [--controls FILE]
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

## Roadmap stub integrations

The V2.1/V3/V4 roadmap is exposed as deterministic local stubs. They normalize files, validate declarations and produce machine-readable results, but do not perform network calls, drive hardware or run benchmarks.

### Connectors

```bash
productmesh connector list
productmesh connector inspect github examples/connectors/github.json --json
productmesh connector import jira examples/connectors/jira.json --output jira-fragment.json
```

Local exports for GitHub, GitLab, Jira and Azure DevOps are normalized into repository, pull-request, merge-request and requirement fragments. `azure_devops` is accepted as an alias for `azure`.

### Firmware, electrical and lab

```json
"firmware": [
  {"id": "FW-ESP32", "component": "CMP-FW", "path": "firmware/esp32-app.bin", "version": "0.1.0"}
],
"electrical": {"check_pins": true, "check_buses": true, "check_power": true},
"lab": {"path": "../lab.json"}
```

Checks cover firmware SHA-256/version drift, serial device discovery, pin conflicts, bus-address collisions, power budgets, lab inventory presence and board availability. Use `firmware inspect`, `device discover`, `lab list` and `lab inspect`.

### HIL, benchmarks and observability

```json
"hil": [{"id": "HIL-IOT", "adapter": "mock", "plan": "hil-plan.json"}],
"benchmarks": [
  {
    "id": "BENCH-ORT-CPU",
    "path": "benchmarks/ort-cpu.json",
    "runtime": "onnxruntime",
    "max_latency_ms": 50,
    "min_throughput_fps": 20
  }
],
"observability": {
  "path": "observability/spans.json",
  "required_attributes": ["service.name", "productmesh.product", "productmesh.device"]
}
```

The mock HIL adapter is deterministic; the serial adapter is a placeholder. Benchmark checks compare declared latency/throughput limits and model hashes. OpenTelemetry checks summarize spans, flag missing required attributes and correlate spans by product/device.

### Cloud, history, policy and advice

```bash
productmesh cloud init --file cloud-workspace.json --name Demo --owner alice
productmesh cloud add-member bob --role approver --file cloud-workspace.json
productmesh cloud request iot-edge-monitor --user bob --file cloud-workspace.json
productmesh cloud approve iot-edge-monitor --user bob --file cloud-workspace.json
productmesh history record --actor ci --action audit --target iot-edge-monitor
productmesh policy validate --file examples/release-policy.json
productmesh advise examples/iot-edge-monitor/product.json --json
productmesh enterprise check on_prem --controls examples/enterprise-controls.json
```

Cloud workspaces use a local JSON store with viewer/auditor/approver/admin roles. Audit history is JSONL. Policy-as-code validates release policy files. Advice is deterministic heuristic output, not a hosted AI service. Enterprise profiles declare on-prem, hybrid or SaaS governance expectations.

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

- `examples/iot-edge-monitor`: ESP32 firmware, sensor bus, HTTP API, two devices, voltage checks, firmware artifact, lab inventory link and mock HIL plan.
- `examples/mobile-api-contract`: mobile/backend OpenAPI v1→v2 contract diff and environment profiles.
- `examples/edge-ai-deployment`: ONNX model, quantization metadata, CycloneDX SBOM, benchmark record, OpenTelemetry spans and two deployment targets.
- `examples/lab.json`: shared lab inventory for the reference boards.
- `examples/connectors/`: GitHub, GitLab, Jira and Azure DevOps local export fixtures.
- `examples/release-policy.json` and `examples/enterprise-controls.json`: policy-as-code and governance fixtures.
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

Editor and CI schemas are provided in `schemas/product.schema.json`, `schemas/workspace.schema.json` and `schemas/lab.schema.json`. Packaged copies live in `productmesh/schemas/` so installed wheels can validate files with `productmesh validate`.

## Limitations

Checks operate on declared metadata, repository state, artifacts, local exports and evidence. The roadmap stubs do not perform physical electrical measurements, PCB parsing, source semantic analysis, real hardware-in-the-loop execution, accelerator benchmarking, network connector calls or hosted AI analysis. A green gate means the declared checks passed, not that the product is physically safe or functionally correct. Install `jsonschema` for full schema validation (`pip install productmesh[schema]`).

## Documentation

See `docs/ARCHITECTURE.md`, `docs/V2_FEATURES.md`, `docs/USE_CASES.md`, `docs/ROADMAP.md`, `docs/RESEARCH_AND_ANALYSIS.md`, `docs/REFERENCES.md` and `PROJECT_MAP.md`.
