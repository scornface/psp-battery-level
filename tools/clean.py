#!/usr/bin/env python3
"""Clean local build intermediates; --all also removes PRX/ELF outputs."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_directories():
    # Only the two known build directories belong to this command. In particular
    # never walk third-party sources, firmware/evidence, or a mounted console.
    build = ROOT / "build"
    if build.is_symlink() or (build.exists() and build.resolve().parent != ROOT.resolve()):
        raise ValueError("Refusing redirected build directory")
    # Validate both modes before deleting anything; one bad mode must not leave
    # the other partially cleaned. No symlinked/mounted directory is traversed.
    for mode in ("release", "diagnostic"):
        directory = build / mode
        if directory.is_symlink() or directory.is_mount() \
                or (directory.exists() and directory.resolve().parent != build.resolve()):
            raise ValueError(f"Refusing redirected build mode: {mode}")
    if build.is_mount():
        raise ValueError("Refusing mounted build directory")


def clean_builds(all_outputs=False):
    validate_directories()
    if any((ROOT / "build" / f".build-{mode}.lock").exists() for mode in ("release", "diagnostic")):
        raise ValueError("Refusing cleanup while a build lock exists")
    for mode in ("release", "diagnostic"):
        directory = ROOT / "build" / mode
        paths = list(directory.glob("*.o")) + [directory / "exports.c"]
        if all_outputs:
            paths += [directory / "battery_level.prx", directory / "battery_level.elf"]
        for path in paths:
            if path.is_file() and not path.is_symlink():
                path.unlink()
                print(f"removed {path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Also remove compiled plugin outputs")
    parser.add_argument("--check-only", action="store_true", help="Validate output directories without deleting")
    args = parser.parse_args()
    try:
        if args.check_only:
            validate_directories()
        else:
            clean_builds(args.all)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
