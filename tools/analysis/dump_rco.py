#!/usr/bin/env python3
"""Dump only the authenticated standard indicator resource with recorded RCOMage."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import re
from pathlib import Path
from common import ROOT, bounded_read, outputs, run
from decompress_rco_rlz import authenticated_resource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    outputs(args.input, args.output)
    data = authenticated_resource(args.input)
    tool = ROOT / "build/analysis/rcomage-tool"
    metadata = json.loads(bounded_read(tool / "manifest.json", 64 * 1024))
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("data"), dict)
        or not isinstance(metadata.get("binary_sha256"), str)
        or not re.fullmatch("[0-9a-f]{64}", metadata["binary_sha256"])
    ):
        raise ValueError("Invalid RCOMage build manifest")
    if (
        hashlib.sha256(bounded_read(tool / "rcomage", 32 * 1024 * 1024)).hexdigest()
        != metadata["binary_sha256"]
    ):
        parser.error("RCOMage binary does not match recorded build")
    for name, digest in metadata["data"].items():
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or not isinstance(digest, str)
            or not re.fullmatch("[0-9a-f]{64}", digest)
        ):
            raise ValueError("Invalid RCOMage data manifest")
        if (
            hashlib.sha256(bounded_read(tool / "data" / name, 8 * 1024 * 1024)).hexdigest()
            != digest
        ):
            parser.error("RCOMage data identity mismatch")
    with tempfile.TemporaryDirectory(prefix="rco-dump-", dir=ROOT / "build/analysis") as tmp:
        source, output = Path(tmp) / "input.rco", Path(tmp) / "output.xml"
        source.write_bytes(data)
        subprocess.run(
            [
                str(tool / "rcomage"),
                "dump",
                str(source),
                str(output),
                "--resdir",
                "-",
                "--no-decomp-warn",
            ],
            env={**os.environ, "RCOMAGE_DATADIR": str(tool / "data")},
            check=True,
        )
        result = bounded_read(output, 32 * 1024 * 1024)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as destination:
            destination.write(result)


if __name__ == "__main__":
    run(main)
