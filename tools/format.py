#!/usr/bin/env python3
"""Check or apply the pinned C/header and Python formatters in maintained scope."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def formatter(name, version):
    executable = shutil.which(name)
    if not executable:
        raise ValueError(
            f"{name} not found; install tools/format-requirements.txt and activate the venv"
        )
    output = subprocess.check_output([executable, "--version"], text=True)
    found = re.search(r"\b\d+\.\d+\.\d+\b", output)
    if not found or found.group() != version:
        raise ValueError(f"Expected {name} {version}, got: {output.strip()}")
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check without writing (default)")
    mode.add_argument("--write", action="store_true", help="apply formatting, never lint fixes")
    args = parser.parse_args()

    pins = dict(
        line.split("==")
        for line in (ROOT / "tools/format-requirements.txt").read_text().splitlines()
        if line and not line.startswith("#")
    )
    clang = formatter("clang-format", pins["clang-format"])
    ruff = formatter("ruff", pins["ruff"])
    c_files = sorted(
        str(path.relative_to(ROOT))
        for directory in (ROOT / "src", ROOT / "tests")
        for path in directory.rglob("*")
        if path.is_file() and path.suffix in (".c", ".h")
    )

    c_options = ["-i"] if args.write else ["--dry-run", "--Werror"]
    python_options = [] if args.write else ["--check"]
    # Run both checks even when one fails, so a single invocation reports all drift.
    c_result = subprocess.run([clang, *c_options, *c_files], cwd=ROOT)
    python_result = subprocess.run([ruff, "format", *python_options, "tests", "tools"], cwd=ROOT)
    return int(bool(c_result.returncode or python_result.returncode))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
