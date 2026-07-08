#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "========================================================================"
echo "AquaSkim-Sim - One-command rebuild from zero to final delivery"
echo "========================================================================"
echo "This command regenerates outputs/ and records/ locally from source."
echo "Generated artifacts are intentionally ignored by Git."
echo

if ! command -v conda >/dev/null 2>&1; then
  echo "[ERROR] Conda was not found on PATH." >&2
  echo "[INFO] Install Miniconda or Mambaforge, open a new shell, then run this script again." >&2
  exit 1
fi

# Make 'conda activate' available in non-interactive shells.
CONDA_BASE="$(conda info --base)"
# shellcheck source=/dev/null
source "$CONDA_BASE/etc/profile.d/conda.sh"

if conda env list | awk '{print $1}' | grep -qx "aquaskim-sim"; then
  echo "[INFO] Conda environment aquaskim-sim already exists. Updating it from environment.yml..."
  conda env update -n aquaskim-sim -f environment.yml --prune
else
  echo "[INFO] Conda environment aquaskim-sim was not found. Creating it from environment.yml..."
  conda env create -f environment.yml
fi

conda activate aquaskim-sim
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

echo "[INFO] Installing package in editable mode using local build tools."
python -m pip install --editable . --no-build-isolation --no-deps

python -m aquaskim.rebuild_from_zero

echo "========================================================================"
echo "DONE - New output folder and final delivery package are ready."
echo "Package: outputs/deliverables/AquaSkim-Sim_Final_Delivery_v1.6.21.zip"
echo "========================================================================"
