# Roadmap

**V1 — implemented:** manifest, static audit, CLI, JSON report, local dashboard, three examples, tests, setup and CI.

**V2 — implemented:**
- Multi-product workspaces and multi-device fleet checks.
- Git repository inspection (local and remote), dirty/commit/ref/remote checks.
- OpenAPI baseline/current contract diff with breaking-change detection.
- CycloneDX and SPDX SBOM ingestion, component drift and vulnerability checks.
- ONNX metadata inspection without the `onnx` dependency.
- Evidence file hashes, test status, policy-based release gates.
- SARIF and Markdown reports.
- JSON schemas, reusable GitHub Action and expanded CI.

**V2.1 — implemented (local-first):**
- GitHub/GitLab/Jira/Azure DevOps local-export connectors. Network API clients are not implemented.
- YAML manifest support and JSON Schema validation (`productmesh validate`).
- Firmware SHA-256/version fingerprinting and serial/USB device discovery.
- Electrical pin-map conflicts, bus-address collisions and power budgets.
- Packaged schemas for installed wheels and CI validation.

**V3 — implemented as deterministic stubs:**
- Hardware-in-the-loop adapter interface with mock and serial placeholders.
- Lab inventory and board/firmware fingerprint lookup.
- Benchmark evidence ingestion with latency, throughput, runtime and model-hash checks. ONNX Runtime/QNN execution is not implemented.
- OpenTelemetry span import, summary, required-attribute checks and product/device correlation. No collector or live backend integration.

**V4 — implemented as deterministic stubs:**
- Local cloud workspace store with viewer/auditor/approver/admin roles.
- Local approval workflow and JSONL audit history.
- Policy-as-code loading and validation.
- Deterministic heuristic root-cause advice. No hosted AI service.
- Enterprise on-prem/hybrid/SaaS governance profiles.

**Stub boundary:** roadmap stubs read local files, validate declared metadata and return stable JSON. They do not make network calls, flash hardware, run HIL plans on physical boards, execute benchmarks, collect live telemetry, host multi-user services or provide safety certification.

**Next:** replace stubs with real adapters while preserving the deterministic audit and release-gate contract.
