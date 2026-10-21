#!/usr/bin/env bash
set -euo pipefail

BRISANCE_INTERFACE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "${BRISANCE_INTERFACE_DIR}/run_from_file.py" "$@"
