#!/bin/sh
# Host-only tests; PSPDEV is not needed for these policy/maintenance checks.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT="$ROOT/build/tests"
CC=${CC:-cc}
mkdir -p "$OUTPUT"
for POLICY in layout recovery update; do
    "$CC" -std=c99 -Wall -Wextra -Werror "$ROOT/tests/${POLICY}_policy.c" \
        -o "$OUTPUT/${POLICY}_policy"
    "$OUTPUT/${POLICY}_policy"
    printf '%s policy passed\n' "$POLICY"
done
"$CC" -std=c99 -Wall -Wextra -Werror -I"$ROOT/tests" "$ROOT/tests/runtime_controller.c" -o "$OUTPUT/runtime_controller"
"$OUTPUT/runtime_controller"
printf 'runtime controller passed\n'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT/tests" -p '*_test.py'
