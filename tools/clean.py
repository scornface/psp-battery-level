#!/usr/bin/env python3
"""Clean local build intermediates; --all also removes PRX/ELF outputs."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_directories():
    # Fixed Docker outputs and documented native SDK directories only. Never
    # recursively walk build/: it also contains private hardware evidence.
    build = ROOT / "build"
    if build.is_symlink() or build.is_mount() or (build.exists() and not build.is_dir()):
        raise ValueError("Refusing redirected build directory")
    directories = []
    # Validate every directory before deleting anything; a bad native child must
    # not leave a different mode partially cleaned.
    for mode in ("release", "diagnostic"):
        for child in ("", "kernel", "vsh"):
            directory = build / mode / child
            if (
                directory.is_symlink()
                or directory.is_mount()
                or (directory.exists() and not directory.is_dir())
            ):
                raise ValueError(f"Refusing redirected build directory: {directory}")
            directories.append(directory)
    return directories


def clean_builds(all_outputs=False):
    directories = validate_directories()
    locks = [ROOT / "build" / f".build-{mode}.lock" for mode in ("release", "diagnostic")]
    if any(path.exists() or path.is_symlink() for path in locks):
        raise ValueError("Refusing cleanup while a build lock exists")
    for directory in directories:
        paths = list(directory.glob("*.o")) + [directory / "exports.c"]
        if all_outputs:
            paths += [
                directory / "battery_level.prx",
                directory / "battery_level.elf",
                directory / "vsh-payload.prx",
            ]
        for path in paths:
            if path.is_file() and not path.is_symlink():
                path.unlink()
                print(f"removed {path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Also remove compiled plugin outputs")
    parser.add_argument(
        "--check-only", action="store_true", help="Validate output directories without deleting"
    )
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
