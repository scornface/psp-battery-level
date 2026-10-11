#!/usr/bin/env python3
"""Reconstruct the optional macOS RCO research tool from authenticated archives."""
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from common import ROOT, outputs

ARCHIVES = {
    "pspdecrypt-1.0.tar.gz": {"736cfffcbc3858e6e294781f5a329bbe157b4023ff59afe1adfca4df39ffa58b"},
    "RCOMage-master.tar.gz": {
        "6b15161f8099cfe21f63ca56b42442a5cfea1f4183a0d56f176bdd1b6b295f79",
        "684106736f716e62ce9ee09d96093c264d99a765c402bfabae8d6cf3cc9ed209",
    },
}


def extract(archive, destination):
    with tarfile.open(archive) as source:
        for member in source:
            parts = Path(member.name).parts
            if member.isdir(): continue
            if not member.isfile() or ".." in parts or Path(member.name).is_absolute() or len(parts) < 2:
                raise ValueError("Unsupported archive entry")
            path = destination.joinpath(*parts[1:])
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as src, path.open("xb") as dst:
                shutil.copyfileobj(src, dst)


def main():
    if platform.system() != "Darwin":
        raise SystemExit("This recorded host recipe supports macOS")
    target = ROOT / "build/analysis/rcomage-tool"
    inputs = {}
    for name, hashes in ARCHIVES.items():
        archive = ROOT / ".deps" / name
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest not in hashes: raise SystemExit(f"Unexpected archive hash: {name}")
        inputs[name] = digest
        outputs(archive, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    patch = ROOT / "tools/analysis/rcomage.patch"
    with tempfile.TemporaryDirectory(prefix="rcomage-build-", dir=target.parent) as tmp:
        work = Path(tmp)
        for name in ARCHIVES:
            directory = work / ("pspdecrypt-1.0" if name.startswith("pspdecrypt") else "RCOMage-master")
            extract(ROOT / ".deps" / name, directory)
        source = work / "RCOMage-master"
        subprocess.run(["patch", "--batch", "-p1", "-i", str(patch)], cwd=source, check=True)
        sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "libxml-2.0", "zlib"], text=True))
        flags += ["-O2", "-fno-strict-aliasing", "-I" + str(source), "-I" + str(source / "src"), "-I" + sdk + "/usr/include/libxml2",
                  '-DDATADIR="' + str(target / "data") + '"']
        objects = []
        for file in sorted(source.glob("src/*.c")) + sorted(source.glob("7z/*.cc")):
            output = work / (file.stem + ".o")
            compiler = "clang++" if file.suffix == ".cc" else "clang"
            subprocess.run([compiler, *flags, "-c", str(file), "-o", str(output)], check=True)
            objects.append(str(output))
        published = work / "published"
        published.mkdir()
        libraries = shlex.split(subprocess.check_output(["pkg-config", "--libs", "libxml-2.0", "zlib"], text=True))
        subprocess.run(["clang++", *objects, *libraries, "-liconv", "-o", str(published / "rcomage")], check=True)
        shutil.copytree(source / "data", published / "data")
        metadata = {
            "archives": inputs, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "compiler": subprocess.check_output(["clang", "--version"], text=True).strip(),
            "binary_sha256": hashlib.sha256((published / "rcomage").read_bytes()).hexdigest(),
            "data": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (published / "data").iterdir() if p.is_file()},
        }
        (published / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
        published.rename(target)
    print(f"Authenticated RCOMage built at {target}")


if __name__ == "__main__":
    main()
