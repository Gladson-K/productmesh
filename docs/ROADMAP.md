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

**V2.1 — next:**
- GitHub/GitLab API connectors for repository and pull-request metadata.
- Jira/Azure DevOps requirement import.
- YAML manifest support and richer JSON Schema validation in CI.
- Firmware binary/version fingerprinting and serial/USB device discovery.
- More electrical constraints: pin-map conflicts, bus address collisions, power budget.

**V3 — hardware and AI integration:**
- Hardware-in-the-loop test adapters.
- Board/firmware fingerprinting and lab inventory.
- ONNX Runtime/QNN compilation and benchmark evidence.
- Runtime observability correlation via OpenTelemetry.

**V4 — complete product engineering platform:**
- Cloud workspace, team collaboration and role-based access.
- Audit history, approvals and policy-as-code.
- AI-assisted root-cause analysis and compatibility recommendations.
- Enterprise deployment and release governance.
