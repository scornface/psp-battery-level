#!/usr/bin/env python3
"""Check the resident PRX's dependency boundary and unload export."""
import hashlib
import argparse
import re
import struct
from pathlib import Path
from prx_libraries import Prx


def nid(name):
    return int.from_bytes(hashlib.sha1(name.encode()).digest()[:4], "little")


def check_module(module, expected_mode=None):
    identities = re.findall(rb"PSPBatteryLevel (release|diagnostic) ([0-9a-f]{8})\0", module.image)
    if len(identities) != 1:
        raise ValueError("Missing or ambiguous build identity")
    mode, build_id = (part.decode() for part in identities[0])
    diagnostic = mode == "diagnostic"
    if expected_mode and mode != expected_mode:
        raise ValueError("Unexpected build mode")
    markers = (b"build_id\0", b"native_layout_calls\0", b"clock_resyncs\0",
               b"ms0:/SEPLUGINS/battery-level.log\0")
    if any((marker in module.image) != diagnostic for marker in markers):
        raise ValueError("Diagnostic code/markers do not match the build mode")
    records = module.imports()
    if len({r["name"] for r in records}) != len(records):
        raise ValueError("Duplicate import library")
    for r in records:
        expected_attr = 9 if r["name"] == "Kernel_Library" else 0x4008 if r["name"] == "SysMemUserForUser" else 0x4009
        if r["words"] != 5 or r["version"] or r["attribute"] != expected_attr or r["var_count"] \
                or len(set(r["nids"])) != r["func_count"]:
            raise ValueError("Unsupported import attributes/variables/duplicate NIDs")
    imports = {entry["name"]: set(entry["nids"]) for entry in records}
    allowed = {"KUBridge", "SystemCtrlForUser", "scePower", "sceUsb",
                "Kernel_Library", "SysMemUserForUser", "ThreadManForUser", "UtilsForUser"}
    if diagnostic:
        allowed.add("IoFileMgrForUser")
    if module.name != "PSPBatteryLevel" or set(imports) != allowed:
        raise ValueError("Unexpected module or imports")
    required = {
        "KUBridge": ["kuKernelFindModuleByName", "kuKernelGetModel", "kuKernelInitKeyConfig"],
        "SystemCtrlForUser": ["sctrlSEGetVersion", "sctrlHENGetVersion", "sctrlHENGetMinorVersion"],
        "scePower": ["scePowerGetBatteryLifePercent", "scePowerIsBatteryExist"],
        "sceUsb": ["sceUsbGetDrvState"],
        "Kernel_Library": ["sceKernelLockLwMutex", "sceKernelUnlockLwMutex", "sceKernelTryLockLwMutex"],
        "SysMemUserForUser": ["sceKernelDevkitVersion", "sceKernelTotalFreeMemSize"],
        "ThreadManForUser": ["sceKernelCreateThread", "sceKernelStartThread", "sceKernelDeleteThread",
                             "sceKernelWaitThreadEnd", "sceKernelDelayThread", "sceKernelGetThreadId"],
        "UtilsForUser": ["sceKernelDcacheWritebackRange"],
    }
    if diagnostic:
        required["scePower"] += ["scePowerIsBatteryCharging", "scePowerIsPowerOnline"]
        required["ThreadManForUser"] += ["sceKernelGetSystemTimeLow"]
        required["IoFileMgrForUser"] = ["sceIoOpen", "sceIoWrite", "sceIoClose"]
    for library, names in required.items():
        if imports[library] != {nid(name) for name in names}:
            raise ValueError(f"Unexpected {library} NIDs")
    exports = module.exports()
    if len(exports) != 1:
        raise ValueError("Expected one system export record")
    export = exports[0]
    if export["name"] != "<module-table>" or export["attribute"] != 0x8000 or export["version"] \
            or export["func_count"] != 2 or export["var_count"] != 1 \
            or set(export["nids"][:2]) != {nid("module_start"), nid("module_stop")} \
            or export["nids"][2:] != [nid("module_info")] \
            or export["addresses"][2] != module.info_address or module.u32(module.info_address) & 0xffff:
        raise ValueError("Invalid system start/stop/module-info export categories or identity")
    for address in export["addresses"][:2]:
        if address & 3:
            raise ValueError("Unaligned exported function")
        module.require_range(address, 4, executable=True)
    if export["addresses"][export["nids"].index(nid("module_start"))] != module.entry:
        raise ValueError("ELF entry does not match module_start export")
    return mode, build_id


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prx", nargs="?", type=Path, default=root / "build/release/battery_level.prx")
    parser.add_argument("--mode", choices=("release", "diagnostic"), default="release")
    args = parser.parse_args()
    try:
        mode, build_id = check_module(Prx.open(args.prx), args.mode)
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"PRX validation failed: {exc}") from exc
    detail = "" if mode == "diagnostic" else " (no filesystem imports)"
    print(f"PRX structure passed: {mode}{detail}, build_id={build_id}, exact import policy and system exports; hardware behavior is separate")


if __name__ == "__main__":
    main()
