#!/usr/bin/env python3
"""Identify a deployed PRX and compare it with the local resident candidate."""
import argparse
import hashlib
from check_build import check_module
from prx_libraries import Prx, bounded_read, MAX_IMAGE
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deployed", type=Path)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--reference", type=Path, default=root / "build/release/battery_level.prx")
    parser.add_argument("--mode", choices=("release", "diagnostic"), default="release")
    args = parser.parse_args()
    contents = []
    for path in (args.reference, args.deployed):
        if not path.is_file():
            parser.error(f"PRX not found: {path}")
        data = bounded_read(path, MAX_IMAGE * 2)
        contents.append(data)
        print(f"path={path} size={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
        try:
            print(f"identity={check_module(Prx.parse(data, path), args.mode)}")
        except ValueError as exc:
            parser.error(str(exc))
    reference, deployed = contents
    if reference != deployed:
        raise SystemExit("Deployed PRX differs from reference")
    print("Validated files are byte-identical; mount/configuration/runtime execution require separate checks")


if __name__ == "__main__":
    main()
