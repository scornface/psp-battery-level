"""Independent synthetic PRX contracts, not copied from checker allowlists.

Changes to production dependency policy must be reviewed against these fixtures.
The wrapper template is paired with an independent register-behavior test;
compiled PSP wrappers are checked by the normal build gate, not these host mocks.
"""

import hashlib
import struct
import sys
from support import ROOT

sys.path.insert(0, str(ROOT / "tools"))
from prx_checks import hook_template


def nid(name):
    return int.from_bytes(hashlib.sha1(name.encode()).digest()[:4], "little")


def user_prx(diagnostic=False):
    image = bytearray(4096)
    mode, build = ("diagnostic", "0001000b") if diagnostic else ("release", "0001000a")
    identity = f"PSPBatteryLevel {mode} {build}".encode() + b"\0"
    image[0x40 : 0x40 + len(identity)] = identity
    if diagnostic:
        markers = (
            b"build_id\0native_layout_calls\0clock_resyncs\0ms0:/SEPLUGINS/battery-level.log\0"
        )
        image[0x400 : 0x400 + len(markers)] = markers
    libraries = {
        "KUBridge": ["kuKernelFindModuleByName", "kuKernelGetModel", "kuKernelInitKeyConfig"],
        "SystemCtrlForUser": ["sctrlSEGetVersion", "sctrlHENGetVersion", "sctrlHENGetMinorVersion"],
        "scePower": ["scePowerGetBatteryLifePercent", "scePowerIsBatteryExist"],
        "sceUsb": ["sceUsbGetDrvState"],
        "Kernel_Library": [
            "sceKernelLockLwMutex",
            "sceKernelUnlockLwMutex",
            "sceKernelTryLockLwMutex",
        ],
        "SysMemUserForUser": ["sceKernelDevkitVersion", "sceKernelTotalFreeMemSize"],
        "ThreadManForUser": [
            "sceKernelCreateThread",
            "sceKernelStartThread",
            "sceKernelDeleteThread",
            "sceKernelWaitThreadEnd",
            "sceKernelDelayThread",
            "sceKernelGetThreadId",
        ],
        "UtilsForUser": ["sceKernelDcacheWritebackRange"],
    }
    if diagnostic:
        libraries["scePower"] += ["scePowerIsBatteryCharging", "scePowerIsPowerOnline"]
        libraries["ThreadManForUser"] += ["sceKernelGetSystemTimeLow"]
        libraries["IoFileMgrForUser"] = ["sceIoOpen", "sceIoWrite", "sceIoClose"]
    cursor = 0x600
    for i, (name, functions) in enumerate(libraries.items()):
        names = name.encode() + b"\0"
        nameptr = cursor
        image[cursor : cursor + len(names)] = names
        cursor = (cursor + len(names) + 3) & ~3
        nids = cursor
        for function in functions:
            struct.pack_into("<I", image, cursor, nid(function))
            cursor += 4
        stubs = cursor
        cursor += len(functions) * 8
        attr = 9 if name == "Kernel_Library" else 0x4008 if name == "SysMemUserForUser" else 0x4009
        struct.pack_into(
            "<IHHBBHII", image, 0x300 + i * 20, nameptr, 0, attr, 5, 0, len(functions), nids, stubs
        )
    struct.pack_into(
        "<HBB28sIIIII",
        image,
        0x100,
        0,
        9,
        0,
        b"PSPBatteryLevel",
        0,
        0x200,
        0x210,
        0x300,
        0x300 + len(libraries) * 20,
    )
    struct.pack_into("<IHHBBHI", image, 0x200, 0, 0, 0x8000, 4, 1, 2, 0x240)
    struct.pack_into(
        "<IIIIII",
        image,
        0x240,
        nid("module_start"),
        nid("module_stop"),
        nid("module_info"),
        0x80,
        0xA0,
        0x100,
    )
    elf = bytearray(96) + image
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into(
        "<16sHHIIIIIHHHHHH", elf, 0, ident, 0xFFA0, 8, 1, 0x80, 52, 0, 0, 52, 32, 1, 0, 0, 0
    )
    struct.pack_into("<IIIIIIII", elf, 52, 1, 96, 0, 96 + 0x100, len(image), len(image), 5, 16)
    return elf


# Recorded kernel boundary. Keep this independent of check_build.IMPORTS.
KERNEL_IMPORTS = {
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


class Runtime:
    name = "PSPBatteryRuntime"
    info_address = 0x100
    entry = 0x200

    def __init__(self, payload, diagnostic=False):
        self.image = bytearray(0x4000)
        struct.pack_into("<I", self.image, 0x100, 0xA1000)
        mode, build = ("diagnostic", "00030004") if diagnostic else ("release", "00030003")
        identity = f"PSPBatteryRuntime {mode} {build}".encode() + b"\0"
        self.image[0x120 : 0x120 + len(identity)] = identity
        self.image[0x1000 : 0x1000 + len(payload)] = payload
        if diagnostic:
            path = b"ms0:/SEPLUGINS/battery-level-runtime.log\0"
            self.image[0x900 : 0x900 + len(path)] = path
        for address, path in (
            (0xA00, b"flash0:/kd/resource/impose.rsc\0"),
            (0xB00, b"flash0:/font/ltn8.pgf\0"),
        ):
            self.image[address : address + len(path)] = path
        self.symbols = dict(
            battery_vsh_image=0x1000,
            battery_vsh_image_end=0x1000 + len(payload),
            home_callback=0x400,
            home_before=0x600,
            home_after=0x700,
            home_original=0x800,
        )
        words, refs = hook_template()
        for hi, lo, name in refs:
            words[lo] |= self.symbols["home_original" if name == "original" else name]
        self.image[0x400 : 0x400 + len(words) * 4] = struct.pack(f"<{len(words)}I", *words)
        for at in (0x600, 0x700):
            struct.pack_into("<I", self.image, at, 0x03E00008)
        imports = {name: (v, a, set(ns)) for name, (v, a, ns) in KERNEL_IMPORTS.items()}
        if diagnostic:
            imports["IoFileMgrForKernel"][2].add(0x42EC03AC)
            imports["ThreadManForKernel"][2].add(0x369ED59D)
            imports["sceUsb_driver"] = (0, 9, {0x112CC951})
        self.records = []
        stub = 0x3000
        for name, (version, attribute, nids) in imports.items():
            ns = sorted(nids)
            stubs = list(range(stub, stub + len(ns) * 8, 8))
            stub += len(ns) * 8
            self.records.append(
                dict(
                    name=name,
                    words=5,
                    version=version,
                    attribute=attribute,
                    var_count=0,
                    func_count=len(ns),
                    nids=ns,
                    stubs=stubs,
                )
            )
        self.system = dict(
            name="<module-table>",
            version=0,
            attribute=0x8000,
            func_count=2,
            var_count=1,
            nids=[nid("module_start"), nid("module_stop"), nid("module_info")],
            addresses=[0x200, 0x240, 0x100],
        )

    def imports(self):
        return self.records

    def exports(self):
        return [self.system]

    def u32(self, at):
        return struct.unpack_from("<I", self.image, at)[0]

    def require_range(self, address, size, executable=False):
        if address < 0 or size < 0 or address + size > len(self.image):
            raise ValueError("range")
        if executable and not (0x200 <= address and address + size <= 0x900):
            raise ValueError("executable range")
