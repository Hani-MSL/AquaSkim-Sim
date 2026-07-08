#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] Python was not found on PATH." >&2
  exit 1
fi

python -m pip install --editable . --no-build-isolation --no-deps
python -m aquaskim.rebuild_from_zero
