#!/usr/bin/env bash
set -euo pipefail
BRISANCE_REPOSITORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.8 or later is required. Ask the server administrator to provide Python.' >&2
  exit 1
fi
exec python3 -B "${BRISANCE_REPOSITORY}/interface/setup_brisance.py" "$@"
