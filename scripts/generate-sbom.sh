#!/usr/bin/env bash
set -euo pipefail

# Generate SBOM for the project
# Requires: syft, pip-audit (optional)

echo "Generating Python SBOM..."
pip freeze > backend/requirements-lock.txt

echo "Generating npm lockfiles..."
cd frontend && npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts

echo "Creating SBOM JSON..."
if command -v syft &> /dev/null; then
  syft dir:. -o spdx-json=sbom.spdx.json
  echo "SBOM generated: sbom.spdx.json"
else
  echo "syft not found. Install: brew install syft"
  echo "Lockfiles generated:"
  echo "  - backend/requirements-lock.txt"
  echo "  - frontend/package-lock.json (existing)"
fi