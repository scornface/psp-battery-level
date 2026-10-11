#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-release}
case "$MODE" in
    release) DIAGNOSTICS=0 ;;
    diagnostic) DIAGNOSTICS=1 ;;
    *) printf 'Usage: %s [release|diagnostic]\n' "$0" >&2; exit 2 ;;
esac
IMAGE=pspdev/pspdev@sha256:b22811072ea0721d7f6c666a5a279b6def2b0cd95892b819d9570f8ffc4452c0
OUTPUT="$ROOT/build/$MODE"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tools/clean.py" --check-only
mkdir -p "$ROOT/build"
LOCK="$ROOT/build/.build-$MODE.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    printf 'Build lock exists: %s (another build or an interrupted invocation)\n' "$LOCK" >&2
    exit 1
fi
STAGE=
trap 'test -z "$STAGE" || rm -rf "$STAGE"; rmdir "$LOCK"' EXIT
trap 'exit 130' INT TERM
STAGE=$(mktemp -d "$ROOT/build/.${MODE}.XXXXXX")
RELATIVE=${STAGE##*/}
docker run --rm --platform linux/amd64 -v "$ROOT:/workspace" \
    -w "/workspace/build/$RELATIVE" "$IMAGE" \
    make -f /workspace/src/Makefile all DIAGNOSTICS="$DIAGNOSTICS"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tools/check_build.py" "$STAGE/battery_level.prx" --mode "$MODE"
mkdir -p "$OUTPUT"
mv "$STAGE/battery_level.elf" "$OUTPUT/battery_level.elf"
mv "$STAGE/battery_level.prx" "$OUTPUT/battery_level.prx"
shasum -a 256 "$OUTPUT/battery_level.prx"
