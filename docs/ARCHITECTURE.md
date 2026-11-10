# Architecture

ProductMesh is a local-first lifecycle integrity layer that complements (not replaces) issue trackers, source control, PLM/MBSE, CAD/EDA, CI and observability.

## V2 flow

1. Load a product manifest or a multi-product workspace.
2. Build an indexed lifecycle graph of requirements, components, interfaces, environments, tests, devices, repositories, API contracts, SBOMs and models.
3. Run deterministic checks across the graph.
4. Evaluate the declared release policy.
5. Emit human, JSON, SARIF or Markdown output and exit non-zero when the gate is blocked.

## Modules

| Module | Responsibility |
| --- | --- |
| `manifest.py` | Manifest/workspace loading, path resolution, file hashes |
| `audit.py` | Core lifecycle checks and audit orchestration |
| `devices.py` | Multi-device compatibility and resource checks |
| `repo.py` | Git repository inspection (local and remote) |
| `openapi.py` | OpenAPI loading and contract diff |
| `sbom.py` | CycloneDX/SPDX ingestion and supply-chain checks |
| `onnx_meta.py` | ONNX protobuf metadata extraction and model checks |
| `evidence.py` | Test status, evidence files and hashes |
| `policy.py` | Release policy and gate evaluation |
| `workspace.py` | Multi-product aggregation and device matrix |
| `report.py` | SARIF and Markdown rendering |
| `cli.py` | Command-line interface |
| `server.py` | Local read-only dashboard and JSON API |
| `issues.py` | Issue model, severity ordering and counts |

## Entities

- Requirement: statement, criticality, linked tests.
- Component: application, firmware, model, service or runtime, with target, version, purl and interfaces.
- Interface: protocol, version, schema, electrical constraints and pins.
- Environment: OS, runtime, board target, voltage and API version.
- Device: board + firmware + environment + voltage + interfaces + resource constraints.
- Repository: local path or remote URL, ref, commit and cleanliness policy.
- API contract: baseline/current OpenAPI specs bound to an interface.
- SBOM: CycloneDX/SPDX inventory and vulnerabilities.
- Model: ONNX artifact, expected tensor contract and quantization metadata.
- Test/evidence: verification status, linked checks, evidence files and hashes.
- Release: policy that turns issues into a release gate.

## Non-goals

Live electrical probing, PCB parsing, source semantic analysis, firmware binary analysis, hardware-in-the-loop execution, accelerator benchmarking, external connector APIs, multi-user/cloud deployment and safety certification. Static declared metadata cannot prove physical compatibility.

## Extension points

- Add connector modules that populate manifests from GitHub/GitLab, Jira/Azure DevOps, PLM or CI.
- Add adapters for serial/USB board discovery and firmware fingerprinting.
- Add ONNX Runtime/QNN benchmark evidence and OpenTelemetry correlation.
- Replace the local JSON store with a cloud workspace while keeping the deterministic engine.
