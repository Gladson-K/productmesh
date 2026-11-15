# ProductMesh V2 feature guide

## Design goal

V2 turns ProductMesh from a single-manifest checker into a reusable lifecycle integrity engine for many products and device variants. The core remains deterministic and local-first so it can run in a developer laptop, a CI job or a container without a database or cloud account.

## Workspace model

A workspace is a versioned JSON file listing product manifests:

```json
{
  "schema_version": "2.0",
  "workspace": {"id": "fleet", "name": "Product Fleet"},
  "products": [
    {"id": "product-a", "manifest": "products/a/product.json"},
    {"id": "product-b", "manifest": "products/b/product.json", "policy": {"block_on_medium": true}}
  ]
}
```

`workspace audit` loads every product, runs the full audit, aggregates issues and produces a device matrix. A workspace can also be discovered from a directory containing `*/product.json`.

## Device fleet model

Devices make a product manifest usable across hardware variants. Each device binds a board, firmware component, environment, voltage and interface list to a product. This is the main mechanism for using one product definition across several open-source hardware products.

Checks:

| Code | Severity | Meaning |
| --- | --- | --- |
| `DEVICE_INVALID` | high | Device entry is not an object |
| `DEVICE_ID_MISSING` | high | Device has no id |
| `DEVICE_DUPLICATE_ID` | high | Device id is reused |
| `DEVICE_FIRMWARE_MISSING` | high | Firmware component is missing or unknown |
| `DEVICE_ENVIRONMENT_MISSING` | high | Environment reference is unknown |
| `DEVICE_VOLTAGE_MISSING` | high | Device does not declare logic voltage |
| `DEVICE_VOLTAGE_MISMATCH` | critical | Interface voltage differs from device voltage |
| `DEVICE_ENV_VOLTAGE_MISMATCH` | critical | Device voltage differs from its environment |
| `DEVICE_INTERFACE_MISSING` | high | Device references an unknown interface |
| `DEVICE_INTERFACE_UNSUPPORTED` | high | Firmware does not declare the device interface |
| `DEVICE_BOARD_MISMATCH` | medium | Board does not match firmware target |
| `DEVICE_SPEC_MISSING` | medium | Resource constraint has no matching spec |
| `DEVICE_RESOURCE_SHORTFALL` | high | Flash/RAM/clock is below the declared minimum |

## Repository integration

Repositories are inspected with Git. Local paths provide commit, branch, tags, describe, dirty files, submodules and origin URL. Remote-only repositories use `git ls-remote` and are resolved by ref.

Checks:

| Code | Severity | Meaning |
| --- | --- | --- |
| `REPO_UNAVAILABLE` | high | Repository cannot be inspected |
| `REPO_MISSING` | high | Declared local path does not exist |
| `REPO_NOT_GIT` | high | Path is not a Git repository |
| `REPO_EMPTY` | high | Repository has no commits |
| `REPO_DIRTY` | high | Working tree has uncommitted changes |
| `REPO_SUBMODULE_DIRTY` | high | Submodule is modified or conflicted |
| `REPO_COMMIT_MISMATCH` | high | Declared commit differs from HEAD/remote |
| `REPO_REF_MISMATCH` | high | Declared ref does not resolve to HEAD |
| `REPO_REMOTE_MISMATCH` | medium | Origin differs from the declared remote |
| `REPO_REF_NOT_FOUND` | high | Remote ref does not exist |
| `REPO_COMPONENT_MISSING` | high | Repository references an unknown component |

`required_clean` defaults to true. Set it to false for repositories where local work is expected. Set `optional: true` to downgrade repository failures to informational severity.

## OpenAPI contract diff

`openapi diff` compares a baseline and current OpenAPI/Swagger document. Product manifests bind contracts to interfaces and can require a baseline.

Breaking checks include:

- `API_PATH_REMOVED` (critical)
- `API_OPERATION_REMOVED` (critical)
- `API_PARAM_REMOVED` (high for required, medium for optional)
- `API_PARAM_REQUIRED_ADDED` (high)
- `API_REQUIRED_FIELD_ADDED` (high for requests, medium for responses)
- `API_FIELD_REMOVED` (high for required fields)
- `API_TYPE_CHANGED` (high)
- `API_ENUM_NARROWED` (high)
- `API_RESPONSE_REMOVED` (high)
- `API_AUTH_SCHEME_REMOVED` / `API_AUTH_CHANGED` (high)
- `API_ADDITIONAL_PROPERTIES_RESTRICTED` (high)
- `API_INTERFACE_VERSION_MISMATCH` (high)

Non-breaking changes such as added paths, optional fields, version changes and deprecations are informational.

## SBOM ingestion

CycloneDX and SPDX JSON SBOMs are normalized into a common component list. Product components can declare `purl`, `sbom_name` and `version`; the audit checks that the SBOM contains matching components and versions.

Checks: `SBOM_MISSING`, `SBOM_INVALID`, `SBOM_REQUIRED_COMPONENT_MISSING`, `SBOM_COMPONENT_MISSING`, `SBOM_VERSION_MISMATCH`, `SBOM_DUPLICATE_COMPONENT`, `SBOM_LICENSE_MISSING`, `SBOM_VULNERABILITY`.

## ONNX metadata inspection

The ONNX protobuf is parsed without the `onnx` package. The inspector extracts:

- IR version, producer, domain and model version
- opset imports per domain
- graph inputs/outputs with dtype and shape (static or symbolic)
- initializer names and dimensions
- metadata properties

Checks: `MODEL_MISSING`, `MODEL_INVALID`, `MODEL_HASH_MISMATCH`, `MODEL_IR_VERSION_MISMATCH`, `MODEL_OPSET_MISMATCH`, `MODEL_INPUT_MISSING`, `MODEL_INPUT_DTYPE_MISMATCH`, `MODEL_INPUT_SHAPE_MISMATCH`, `MODEL_OUTPUT_MISSING`, `MODEL_OUTPUT_DTYPE_MISMATCH`, `MODEL_OUTPUT_SHAPE_MISMATCH`, `MODEL_QUANTIZATION_MISSING`, `MODEL_QUANTIZATION_INVALID`, `MODEL_QUANTIZATION_MISMATCH`, `MODEL_COMPONENT_MISSING`, `MODEL_PRODUCER_MISMATCH`.

Symbolic dimensions (`"batch"`) are treated as wildcards. Static dimensions must match exactly.

## Evidence and release policy

Test entries can declare `status` and `evidence` files. Evidence can include a SHA-256 digest. Tests with `failed` status are critical; `blocked`, `not_run`, `skipped` and `pending` are high. Requirements linked only to failed/blocked tests produce `REQUIREMENT_NOT_VERIFIED`.

Release policy fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `block_on_critical` | true | Block on critical issues |
| `block_on_high` | true | Block on high issues |
| `block_on_medium` | false | Block on medium issues |
| `block_on_low` | false | Block on low issues |
| `max_critical` | 0 | Allowed critical count |
| `max_high` | 0 | Allowed high count |
| `max_medium` | 0 | Allowed medium count when enabled |
| `allow_dirty_repo` | false | Allow dirty repositories |
| `require_sbom` | false | Require an SBOM |
| `require_openapi` | false | Require an OpenAPI contract |
| `require_evidence` | false | Require evidence for verified requirements |
| `required_requirements` | [] | Reserved for stricter requirement policy |

Legacy V1 keys such as `block_on_high_severity` are accepted as aliases for the canonical `block_on_high` form.

## Reports

- Human-readable CLI output
- JSON for automation
- SARIF 2.1.0 for GitHub code scanning
- Markdown for pull requests and release notes

## What V2 deliberately does not do

V2 does not measure physical voltage, parse PCB layouts, inspect firmware binaries, execute hardware-in-the-loop tests, run model benchmarks or call GitHub/Jira APIs. Those remain V3/V4 integrations. Repository and remote checks are read-only.

## Roadmap stubs added in 0.3.0

- Local connector exports for GitHub, GitLab, Jira and Azure DevOps.
- YAML manifests and `productmesh validate` schema validation.
- Firmware fingerprinting, serial discovery and electrical checks.
- Mock/serial HIL adapters and lab inventory lookup.
- Benchmark evidence checks and OpenTelemetry span correlation.
- Local cloud workspace, RBAC, approvals, JSONL history, policy-as-code and deterministic advice.
- Enterprise on-prem/hybrid/SaaS governance profiles.

These are deterministic local stubs. They validate declared files and metadata but do not call external APIs, run physical hardware, execute benchmarks, collect live telemetry or host multi-user services.
