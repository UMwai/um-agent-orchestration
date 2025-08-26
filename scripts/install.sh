#!/usr/bin/env bash
set -euo pipefail

# Install Python deps
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Verify gh auth
if ! gh auth status >/dev/null 2>&1; then
  echo "WARNING: gh auth not configured. Run: gh auth login"
fi

# Optional: install Gemini CLI & Cursor CLI (follow official docs)
# Gemini CLI: https://cloud.google.com/gemini/docs/codeassist/gemini-cli
# Cursor CLI: curl https://cursor.com/install -fsS | bash

echo "Done. Configure .env and run 'make dev' + 'rq worker autodev'."