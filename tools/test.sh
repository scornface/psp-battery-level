#!/bin/sh
# Host-only tests; PSPDEV is not needed for these policy/maintenance checks.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT="$ROOT/build/tests"
CC=${CC:-cc}
export CC
case "${1:-}" in
    '') ;;
    --sanitize) TEST_SANITIZE=1; export TEST_SANITIZE ;;
    *) printf 'Usage: %s [--sanitize]\n' "$0" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    printf 'Usage: %s [--sanitize]\n' "$0" >&2
    exit 2
fi
mkdir -p "$OUTPUT"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT/tests" -p '*_test.py'
