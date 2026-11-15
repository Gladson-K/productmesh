# Changelog

## 0.3.0 — V2.1 and roadmap stubs

### Added
- JSON/YAML schema validation CLI with packaged product, workspace and lab schemas.
- Local GitHub, GitLab, Jira and Azure DevOps export connectors.
- Firmware fingerprinting, serial/USB discovery and firmware artifact checks.
- Electrical pin-map, bus-address and power-budget checks.
- Mock/serial HIL adapters and HIL plan runner.
- Lab inventory lookup and board availability checks.
- Benchmark evidence checks for latency, throughput, runtime, device and model hash.
- OpenTelemetry span import, summary and product/device correlation.
- Local cloud workspace store with RBAC and approvals.
- JSONL audit history and deterministic root-cause advice.
- Policy-as-code loading/validation and enterprise governance profiles.
- New example fixtures for lab inventory, connectors, firmware, HIL, benchmarks, OpenTelemetry, release policy and governance controls.
- Schema, connector, firmware, electrical, HIL, lab, benchmark, observability, cloud, history, policy, advice and enterprise tests.

### Changed
- Package version bumped to `0.3.0`.
- Development extras now include `jsonschema` and `ruff`.
- Audit summaries include firmware, benchmark, HIL, lab, observability and electrical counts.
- README, architecture, roadmap, project map and CI cover the stub integrations.

### Stub boundary
- Connectors use local exports; no external API calls.
- HIL uses a deterministic mock adapter; serial execution is a placeholder.
- Benchmarks, OpenTelemetry and cloud features operate on local files only.
- AI advice is deterministic heuristics; no hosted model or service.

## 0.2.0 — V2

### Added
- Multi-product workspace audit (`workspace.json`) with aggregated release status and device matrix.
- Multi-device fleet model with board, firmware, environment, voltage, interface and resource checks.
- Git repository inspection for local paths and remote URLs: dirty tree, submodules, commit/ref/remote drift.
- OpenAPI baseline/current contract diff with breaking-change detection.
- CycloneDX and SPDX SBOM ingestion, required-component checks, version drift and vulnerability reporting.
- ONNX protobuf metadata inspection without the `onnx` dependency, including tensor contracts, hashes and quantization metadata.
- Test status, evidence files, SHA-256 evidence checks and policy-based release gates.
- SARIF 2.1.0 and Markdown reports.
- JSON Schemas for product manifests and workspaces.
- Reusable GitHub Action release gate and expanded CI.
- V2 example artifacts: OpenAPI v1/v2 specs, CycloneDX SBOM, tiny ONNX model and quantization metadata.
- Dashboard workspace summary, product audit and device matrix.

### Changed
- Product manifest `release` section now drives a policy-aware gate.
- CLI now supports `release`, `workspace`, `repo`, `openapi`, `sbom` and `model` commands.
- Server now exposes workspace, product, device and health endpoints.
- Packaging now installs a `productmesh` console script.

### Preserved
- V1 product manifests, `audit` output and the original IoT voltage mismatch workflow remain compatible.

## 0.1.0 — V1

- Initial local prototype: manifest audit, requirement traceability, reference checks, voltage mismatch detection, CLI, JSON output, dashboard, three examples, tests, CI and container scaffolding.
