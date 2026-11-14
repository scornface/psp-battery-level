#!/bin/sh
# One installed PRX: independently verified user payload and kernel runtime.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-release}
case "$MODE" in
    release) DIAGNOSTICS=0 ;;
    diagnostic) DIAGNOSTICS=1 ;;
    *) printf 'Usage: %s [release|diagnostic]\n' "$0" >&2; exit 2 ;;
esac
IMAGE=pspdev/pspdev@sha256:b22811072ea0721d7f6c666a5a279b6def2b0cd95892b819d9570f8ffc4452c0
mkdir -p "$ROOT/build"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/tools/clean.py" --check-only
LOCK="$ROOT/build/.build-$MODE.lock"
mkdir "$LOCK" || exit 1
STAGE=
trap 'test -z "$STAGE" || rm -rf "$STAGE"; rmdir "$LOCK"' EXIT
trap 'exit 130' INT TERM
STAGE=$(mktemp -d "$ROOT/build/.${MODE}.XXXXXX")
mkdir "$STAGE/vsh" "$STAGE/kernel"
BASE="/workspace/build/${STAGE##*/}"
docker run --rm --platform linux/amd64 -v "$ROOT:/workspace" -w "$BASE/vsh" "$IMAGE" \
    make -f /workspace/src/vsh/Makefile all DIAGNOSTICS="$DIAGNOSTICS"
python3 "$ROOT/tools/check_vsh.py" "$STAGE/vsh/battery_level.prx" --mode "$MODE"
docker run --rm --platform linux/amd64 -v "$ROOT:/workspace" -w "$BASE/kernel" "$IMAGE" \
    make -f /workspace/src/bootstrap/Makefile all DIAGNOSTICS="$DIAGNOSTICS" VSH_PAYLOAD="$BASE/vsh/battery_level.prx"
python3 "$ROOT/tools/check_build.py" "$STAGE/kernel/battery_level.prx" \
    --elf "$STAGE/kernel/battery_level.elf" --vsh "$STAGE/vsh/battery_level.prx" --mode "$MODE"
OUTPUT="$ROOT/build/$MODE"
mkdir -p "$OUTPUT"
mv "$STAGE/kernel/battery_level.prx" "$OUTPUT/"
mv "$STAGE/kernel/battery_level.elf" "$OUTPUT/"
mv "$STAGE/vsh/battery_level.prx" "$OUTPUT/vsh-payload.prx"
shasum -a 256 "$OUTPUT/battery_level.prx"
