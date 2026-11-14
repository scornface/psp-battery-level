#!/usr/bin/env python3
"""Bootstrap/user-payload boundary; exact imports, wrapper and integer helpers."""

import argparse
from pathlib import Path
import struct
from check_vsh import check_module, nid
from prx_checks import CompanionElf, hook_template, check_helper, target
from prx_libraries import Prx, bounded_read

IMPORTS = {
    "SystemCtrlForKernel": (0, 9, {0x1090A2E1, 0x5328B431, 0xB47C9D77}),
    "InitForKernel": (0x11, 9, {0x7233B5BC}),
    "SysMemForKernel": (0, 9, {0x7158CE7E, 0xC886B169, 0xC1A26C6F, 0xF12A62F7, 0x07C586A1}),
    "LoadCoreForKernel": (0, 9, {0xF6B1BF0F, 0x40972E6E}),
    "ThreadManForKernel": (
        0,
        9,
        {0x446D8DE6, 0xCEADEB47, 0x9FA03CD3, 0xD8199E4C, 0xF475845D, 0x278C0DF5},
    ),
    "InterruptManagerForKernel": (0, 9, {0x5F10D406, 0x092968F4, 0xFE28C6D9}),
    "ModuleMgrForKernel": (0, 9, {0x4E62C48A, 0x3FF74DF1, 0xE5D6087B, 0x387E3CA9}),
    "scePower_driver": (0, 9, {0x0AFD0D8B, 0x2085D15D}),
    "IoFileMgrForKernel": (0, 9, {0x810C4BC3, 0x109F50BC, 0x6A638D83}),
    "UtilsForKernel": (0, 9, {0x840259F1}),
}


def check(prx, elf, payload, diagnostic=False, module=None):
    module = module if module is not None else Prx.open(prx)
    data = bounded_read(payload, 512 * 1024)
    child = Prx.parse(data, payload)
    mode = "diagnostic" if diagnostic else "release"
    check_module(child, mode)
    identity = f"PSPBatteryRuntime {mode} " + ("00030004" if diagnostic else "00030003")
    if (
        module.name != "PSPBatteryRuntime"
        or module.u32(module.info_address) != 0xA1000
        or module.image.count(identity.encode() + b"\0") != 1
    ):
        raise ValueError("Unexpected bootstrap identity")

    expected = {key: (v, a, set(ns)) for key, (v, a, ns) in IMPORTS.items()}
    if diagnostic:
        v, a, ns = expected["IoFileMgrForKernel"]
        expected["IoFileMgrForKernel"] = (v, a, ns | {0x42EC03AC})
        v, a, ns = expected["ThreadManForKernel"]
        expected["ThreadManForKernel"] = (v, a, ns | {0x369ED59D})
        expected["sceUsb_driver"] = (0, 9, {0x112CC951})
    records = module.imports()
    if len(records) != len(expected) or {r["name"] for r in records} != set(expected):
        raise ValueError("Unexpected bootstrap libraries: " + ", ".join(r["name"] for r in records))
    for r in records:
        version, attr, nids = expected[r["name"]]
        if (r["words"], r["version"], r["attribute"], r["var_count"], r["func_count"]) != (
            5,
            version,
            attr,
            0,
            len(nids),
        ) or set(r["nids"]) != nids:
            raise ValueError("Unexpected bootstrap import: " + r["name"])

    exports = module.exports()
    if len(exports) != 1:
        raise ValueError("Expected system exports only")
    e = exports[0]
    if (
        e["name"] != "<module-table>"
        or e["attribute"] != 0x8000
        or e["version"]
        or e["func_count"] != 2
        or e["var_count"] != 1
        or set(e["nids"][:2]) != {nid("module_start"), nid("module_stop")}
        or e["nids"][2:] != [nid("module_info")]
        or e["addresses"][2] != module.info_address
    ):
        raise ValueError("Invalid bootstrap exports")
    for at in e["addresses"][:2]:
        if at & 3:
            raise ValueError("Unaligned system function")
        module.require_range(at, 4, executable=True)
    if e["addresses"][e["nids"].index(nid("module_start"))] != module.entry:
        raise ValueError("Wrong entrypoint")

    companion = CompanionElf.open(elf)
    syms = companion.symbols
    begin, end = syms["battery_vsh_image"], syms["battery_vsh_image_end"]
    module.require_range(begin, len(data))
    if begin & 63 or end - begin != len(data) or module.image[begin:end] != data:
        raise ValueError("Embedded user PRX mismatch/alignment")
    diagnostic_path = b"ms0:/SEPLUGINS/battery-level-runtime.log\0"
    if (diagnostic_path in module.image) != diagnostic:
        raise ValueError("Bootstrap diagnostics in wrong mode")
    for path in (b"flash0:/kd/resource/impose.rsc\0", b"flash0:/font/ltn8.pgf\0"):
        if module.image.count(path) != 1:
            raise ValueError("Missing/ambiguous startup asset path")

    helpers = {}
    for name in ("home_before", "home_after"):
        at, size = companion.function_extent(name)
        module.require_range(at, size, executable=True)
        if module.image[at : at + size] != companion.function_bytes(at, size):
            raise ValueError("Helper/ELF mismatch")
        check_helper(module, at, size)  # Interrupt primitives ONLY: no timing/I/O/power calls.
        helpers[name] = at

    words, refs = hook_template()
    address = syms["home_callback"]
    module.require_range(address, len(words) * 4, executable=True)
    actual = struct.unpack_from(f"<{len(words)}I", module.image, address)
    variables = {i for hi, lo, _ in refs for i in (hi, lo)}
    for i, (w, want) in enumerate(zip(actual, words)):
        if w & (0xFFFF0000 if i in variables else 0xFFFFFFFF) != want:
            raise ValueError("Changed Sony wrapper ABI")
    for hi, lo, name in refs:
        wanted = syms["home_original"] if name == "original" else helpers[name]
        if target(actual, hi, lo) != wanted:
            raise ValueError("Wrong wrapper reference")
    return mode


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "prx",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parents[1] / "build/release/battery_level.prx",
    )
    p.add_argument("--elf", type=Path)
    p.add_argument("--vsh", type=Path)
    p.add_argument("--mode", choices=("release", "diagnostic"), default="release")
    args = p.parse_args()
    args.elf = args.elf or args.prx.with_suffix(".elf")
    args.vsh = args.vsh or args.prx.parent / "vsh-payload.prx"
    try:
        check(args.prx, args.elf, args.vsh, args.mode == "diagnostic")
    except (OSError, ValueError, KeyError, struct.error) as error:
        raise SystemExit(str(error)) from error
    print(
        "Integrated "
        + args.mode
        + ": embedded user PRX exact; kernel imports/wrapper/integer helpers verified; hardware behavior requires separate evidence"
    )


if __name__ == "__main__":
    main()
