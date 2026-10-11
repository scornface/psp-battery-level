#!/usr/bin/env python3
"""Dump only the authenticated standard indicator resource with recorded RCOMage."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from common import ROOT, outputs, run
from decompress_rco_rlz import authenticated_resource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    outputs(args.input, args.output)
    data = authenticated_resource(args.input)
    tool = ROOT / "build/analysis/rcomage-tool"
    metadata = json.loads((tool / "manifest.json").read_text())
    if hashlib.sha256((tool / "rcomage").read_bytes()).hexdigest() != metadata["binary_sha256"]:
        parser.error("RCOMage binary does not match recorded build")
    for name, digest in metadata["data"].items():
        if Path(name).name != name or hashlib.sha256((tool / "data" / name).read_bytes()).hexdigest() != digest:
            parser.error("RCOMage data identity mismatch")
    with tempfile.TemporaryDirectory(prefix="rco-dump-", dir=ROOT / "build/analysis") as tmp:
        source, output = Path(tmp) / "input.rco", Path(tmp) / "output.xml"
        source.write_bytes(data)
        subprocess.run([str(tool / "rcomage"), "dump", str(source), str(output), "--resdir", "-", "--no-decomp-warn"],
                       env={**os.environ, "RCOMAGE_DATADIR": str(tool / "data")}, check=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as destination:
            destination.write(output.read_bytes())


if __name__ == "__main__":
    run(main)
