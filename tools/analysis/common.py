"""Explicit scope and filesystem boundaries for optional Sony 6.61 research."""
import hashlib
from pathlib import Path
import sys
import struct

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from prx_libraries import Prx, bounded_read

FIRMWARE = {
    "paf": "699413b667199732af0b3cc2379ea65df0c4e2daa7727c6d1bbb757df0160417",
    "vshmain": "dd283103f78db14a8bd08c8aa03ecc01807850baed54fb77b3c38ba7ffff712f",
    "dialogmain": "c3602b6c63f559318af51390bff21babbd68371cf505e6dffa20ad670ee86578",
}


def verified_source(path):
    data = bounded_read(path, 32 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() not in FIRMWARE.values():
        raise ValueError("Only the three verified Sony 6.61 analysis modules are supported")
    return data


def outputs(input_path, *destinations):
    for directory in (ROOT / "build", ROOT / "build/analysis"):
        if directory.is_symlink() or directory.is_mount():
            raise ValueError("Refusing redirected/mounted analysis directory")
    base = (ROOT / "build/analysis").resolve()
    paths = [Path(input_path).resolve()] + [Path(p).resolve() for p in destinations]
    if len(set(paths)) != len(paths):
        raise ValueError("Input/output paths collide")
    for i, path in enumerate(paths):
        for other in paths[i + 1:]:
            if path.exists() and other.exists() and path.samefile(other):
                raise ValueError("Input/output files alias")
    for path in paths[1:]:
        if not path.is_relative_to(base) or path == base:
            raise ValueError("Analysis outputs must be below build/analysis")
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to overwrite analysis output: {path}")


def analysis_module(source, image):
    verified_source(source)
    return Prx.open(source, image)


def capstone_module():
    sys.path.insert(0, str(ROOT / ".deps/capstone-py"))
    import capstone
    if capstone.__version__ != "5.0.6" or not Path(capstone.__file__).resolve().is_relative_to(ROOT / ".deps/capstone-py"):
        raise ValueError("Install the pinned local Capstone dependency")
    return capstone


def run(main):
    try:
        main()
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"Analysis failed: {exc}") from exc
