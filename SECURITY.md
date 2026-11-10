# Security policy

ProductMesh reads local manifests, repository metadata and artifact files. It does not execute product code, firmware or model inference.

## Reporting a vulnerability

Open a private security advisory on the repository or contact the maintainers directly. Do not include secrets or sensitive product data in a public issue.

## Scope

In scope:
- Path traversal or unsafe file handling in the CLI/server.
- Unexpected command execution through repository or manifest input.
- Denial-of-service parsing of untrusted SBOM/ONNX/OpenAPI files.
- Information disclosure through the local dashboard.

Out of scope:
- Physical hardware safety.
- Accuracy of third-party SBOM or vulnerability data.
- Security of external tools invoked by users (Git, package managers, CI).

## Hardening notes

- The dashboard binds to `127.0.0.1` by default.
- Repository inspection uses read-only Git commands.
- Remote inspection disables terminal prompts and uses batch-mode SSH.
- Product names in the HTTP API are restricted to safe filename characters.
