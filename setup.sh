#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PIP_DISABLE_PIP_VERSION_CHECK=1
PYTHON_BIN="${PYTHON:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
if [[ "${1:-}" == "--dev" ]]; then
  .venv/bin/python -m pip install --no-build-isolation -e ".[dev]"
else
  .venv/bin/python -m pip install --no-build-isolation -e .
fi
echo "Setup complete."
echo "Audit:     .venv/bin/python -m productmesh.cli audit"
echo "Workspace: .venv/bin/python -m productmesh.cli workspace audit examples/workspace.json"
echo "Dashboard: .venv/bin/python -m productmesh.cli serve"
