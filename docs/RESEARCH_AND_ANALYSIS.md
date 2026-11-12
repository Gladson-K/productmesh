# Research and product analysis — 5 November 2026

## Problem thesis
Defects frequently occur at product boundaries: an unverified requirement, a mobile client expecting a field the backend removed, firmware targeting a different board/voltage, an exported model unsupported by the edge runtime, or a release assembled from incompatible versions. Teams distribute truth across tickets, repositories, API specs, spreadsheets, CAD/EDA, CI logs, lab notes and deployment tools. The gap is a connected, queryable relationship between intent, implementation, interfaces, environment, evidence and release configuration.

A 2026 open-access MBSE/digital-thread paper identifies fragmented tools, varied formats and incompatibilities as barriers to lifecycle continuity; it advocates standards-based integration and traceability [1].

## Three target use cases
### UC1 — IoT/embedded product
ESP32/STM32, sensors, power, firmware, app and cloud. Common defects: pin-map disagreement, 3.3V/5V mismatch, wrong board revision, bus/protocol mismatch, stale firmware/API payload, calibration gaps and toolchain drift. ProductMesh links requirements, firmware, board/environment profiles, interfaces, devices and tests. V2 detects declared references, missing tests, voltage mismatches, device/resource conflicts and repository drift; later HIL adapters can ingest board IDs, firmware hashes and serial test output.

### UC2 — Mobile/web application + backend
Android/iOS, API gateway, backend, identity provider and database. Common defects: client/server schema drift, API version incompatibility, token issuer/audience mismatch, environment drift, unsupported OS/runtime, stale SDKs and migration ordering. ProductMesh models versioned contracts and environment profiles. OpenAPI is a declarative API contract format and a natural integration target [2]. V2 diffs baseline/current specs and flags removed operations, newly required fields, type changes and auth changes; deeper request/response semantic testing remains future scope.

### UC3 — AI model to edge deployment
Training/export, ONNX, quantization, accelerator compile, runtime and app. Common defects: tensor shape/dtype/layout mismatch, unsupported operators, quantization metadata separated from weights, runtime/device mismatch, stale artifacts and preprocessing/performance regressions. ProductMesh links model, runtime, target and tensor contract. V2 inspects ONNX metadata, expected tensor shapes/dtypes, quantization metadata, SBOM components and artifact hashes; accelerator compile reports and benchmarks remain future adapters. Updated 2026 SBOM guidance covers AI and SaaS as well as conventional software [3].

## Product principles
1. Digital thread, not another task tracker. 2. Contract-first interfaces. 3. Evidence-based release gates. 4. Local-first portable manifest. 5. Integrate with existing tools rather than replace them. 6. Secure lifecycle: NIST SSDF 1.1 is a finalized baseline; SSDF 1.2 was an initial public draft published Dec 2025, so verify status before treating it as final [4]. 7. Runtime evidence can later use OpenTelemetry's vendor-neutral traces, metrics and logs [5].

## Ecosystem positioning
Complement Jira/Azure DevOps (work), GitHub/GitLab (source/CI), PLM/MBSE (engineering models), OpenAPI tooling (API contracts), SBOM scanners (dependency visibility) and observability backends. Differentiation hypothesis: lightweight cross-domain consistency graph and release-readiness gate without an enterprise PLM deployment.

## V1 scope
JSON manifest; requirement-to-test coverage; broken component/interface/test/environment references; duplicate IDs; declared voltage mismatch; CLI/JSON output; non-zero release-gate exit; local dashboard; three examples.

## V2 scope
Multi-product workspaces; multi-device fleets; Git repository state and commit/ref checks; OpenAPI baseline/current contract diff; CycloneDX/SPDX SBOM ingestion; ONNX metadata and quantization checks; evidence hashes; policy-based release gates; SARIF/Markdown reports; JSON schemas; reusable GitHub Action. V2 still validates declared metadata and artifacts, not physical hardware behaviour.

## V2.1 and roadmap stubs
Local connector export normalization; YAML and schema validation; firmware and serial device discovery; electrical pin/bus/power checks; mock/serial HIL adapters; lab inventory; benchmark evidence; OpenTelemetry span correlation; local cloud workspace, RBAC, approvals, JSONL history, policy-as-code, deterministic advice and enterprise governance profiles. These stubs are local-first and deterministic; they do not call external APIs, run physical hardware, execute benchmarks or host multi-user services.

## Risks and validation
Manifest quality/ownership can become overhead. Static checks cannot establish functional correctness, safety, security or real physical compatibility. Pilot across one embedded, one app/API and one edge-AI team. Encode 10–20 historical integration defects per team and measure defect coverage, precision/false positives, diagnosis time and manifest maintenance time. Continue only if useful defects surface earlier without high upkeep.

## References
[1] Formalizing the Digital Thread: A Standards-Based MBSE Integration Framework, Procedia Computer Science (2026), https://doi.org/10.1016/j.procs.2026.02.096
[2] OpenAPI Initiative FAQ, https://www.openapis.org/faq
[3] CISA, 2026 Minimum Elements for an SBOM, https://content.govdelivery.com/accounts/USDHSCISA/bulletins/422a7eb
[4] NIST SP 800-218 SSDF v1.1, https://csrc.nist.gov/pubs/sp/800/218/final ; SSDF v1.2 initial public draft, https://csrc.nist.gov/pubs/sp/800/218/r1/ipd
[5] OpenTelemetry overview, https://opentelemetry.io/docs/what-is-opentelemetry/
