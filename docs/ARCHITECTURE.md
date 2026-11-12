# Architecture

ProductMesh is a local-first lifecycle integrity layer that complements (not replaces) issue trackers, source control, PLM/MBSE, CAD/EDA, CI and observability.

## Flow

1. Load a product manifest or a multi-product workspace, as JSON or YAML.
2. Build an indexed lifecycle graph of requirements, components, interfaces, environments, tests, devices, repositories, API contracts, SBOMs, models, firmware, benchmarks, HIL plans, lab inventory and observability exports.
3. Run deterministic checks across the graph.
4. Evaluate the declared release policy.
5. Emit human, JSON, SARIF or Markdown output and exit non-zero when the gate is blocked.
6. Optionally record history, request approval or generate deterministic advice.

## Modules

| Module | Responsibility |
| --- | --- |
| `manifest.py` | Manifest/workspace loading, JSON/YAML support, path resolution, file hashes |
| `audit.py` | Core lifecycle checks and audit orchestration |
| `devices.py` | Multi-device compatibility and resource checks |
| `electrical.py` | Pin-map conflicts, bus-address collisions and power budgets |
| `repo.py` | Git repository inspection (local and remote) |
| `openapi.py` | OpenAPI loading and contract diff |
| `sbom.py` | CycloneDX/SPDX ingestion and supply-chain checks |
| `onnx_meta.py` | ONNX protobuf metadata extraction and model checks |
| `firmware.py` | Firmware fingerprinting, serial discovery and firmware checks |
| `benchmarks.py` | Benchmark evidence normalization and regression checks |
| `hil.py` | Mock/serial HIL adapter interface and plan runner |
| `lab.py` | Lab inventory, board lookup and availability checks |
| `observability.py` | OpenTelemetry span import, summary and correlation |
| `connectors.py` | Local GitHub/GitLab/Jira/Azure DevOps export normalization |
| `evidence.py` | Test status, evidence files and hashes |
| `policy.py` | Release policy, policy-as-code loading and gate evaluation |
| `schema.py` | JSON Schema loading, inference and validation |
| `workspace.py` | Multi-product aggregation and device matrix |
| `cloud.py` | Local cloud workspace, RBAC and approvals |
| `history.py` | JSONL audit history |
| `ai.py` | Deterministic root-cause advice |
| `enterprise.py` | Enterprise governance profiles |
| `report.py` | SARIF and Markdown rendering |
| `cli.py` | Command-line interface |
| `server.py` | Local read-only dashboard and JSON API |
| `issues.py` | Issue model, severity ordering and counts |

## Entities

- Requirement: statement, criticality, linked tests.
- Component: application, firmware, model, service or runtime, with target, version, purl and interfaces.
- Interface: protocol, version, schema, electrical constraints, pins, bus and address.
- Environment: OS, runtime, board target, voltage and API version.
- Device: board + firmware + environment + voltage + interfaces + resource constraints.
- Firmware: artifact path, hash, version and linked component.
- Repository: local path or remote URL, ref, commit and cleanliness policy.
- API contract: baseline/current OpenAPI specs bound to an interface.
- SBOM: CycloneDX/SPDX inventory and vulnerabilities.
- Model: ONNX artifact, expected tensor contract and quantization metadata.
- Benchmark: runtime/device latency, throughput and model hash evidence.
- HIL plan: adapter, test plan and expected results.
- Lab board: inventory ID, board type, firmware, serial, location and availability.
- Span export: OpenTelemetry resource/span attributes for correlation.
- Test/evidence: verification status, linked checks, evidence files and hashes.
- Release: policy that turns issues into a release gate.
- Cloud workspace: local members, roles, approvals and history.
- Enterprise profile: governance controls for on-prem, hybrid or SaaS deployment.

## Non-goals

Live electrical probing, PCB parsing, source semantic analysis, real firmware execution, physical hardware-in-the-loop testing, accelerator benchmarking, network connector APIs, hosted multi-user services, hosted AI analysis and safety certification. Static declared metadata cannot prove physical compatibility.

## Extension points

- Replace local connector exports with GitHub/GitLab/Jira/Azure DevOps API clients.
- Replace mock/serial HIL placeholders with real device bridges.
- Replace benchmark and OpenTelemetry stubs with runtime and collector integrations.
- Replace the local cloud JSON store and JSONL history with a multi-user service.
- Preserve the deterministic audit and release-gate contract when adding adapters.
