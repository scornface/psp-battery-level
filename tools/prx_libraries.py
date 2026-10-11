#!/usr/bin/env python3
"""Read PSP PRX module import/export tables and optionally pair imports with exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


PT_LOAD = 1
MAX_IMAGE = 32 * 1024 * 1024


def bounded_read(path, maximum):
    if not path.is_file():
        raise ValueError(f"Not a regular input file: {path}")
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"Input exceeds {maximum} bytes: {path}")
    return data


@dataclass(frozen=True)
class Prx:
    path: Path
    image: bytes
    phdrs: tuple[tuple[int, ...], ...]
    name: str
    gp: int
    ent_top: int
    ent_end: int
    stub_top: int
    stub_end: int
    info_address: int
    entry: int

    @classmethod
    def open(cls, path: Path, relocated_image: Path | None = None) -> "Prx":
        elf = bounded_read(path, MAX_IMAGE * 2)
        relocated = None
        if relocated_image:
            relocated = bounded_read(relocated_image, MAX_IMAGE)
            manifest = json.loads(bounded_read(relocated_image.with_suffix(relocated_image.suffix + ".json"), 4096))
            if not isinstance(manifest, dict) or type(manifest.get("load_base")) is not int \
                    or manifest.get("load_base") != 0 or manifest.get("input_sha256") != hashlib.sha256(elf).hexdigest() \
                    or manifest.get("image_sha256") != hashlib.sha256(relocated).hexdigest():
                raise ValueError("Relocated image manifest does not match source/base/image")
        return cls.parse(elf, path, relocated)

    @classmethod
    def parse(cls, elf: bytes, path: Path = Path("<memory>"), relocated: bytes | None = None) -> "Prx":
        if len(elf) > MAX_IMAGE * 2:
            raise ValueError("ELF file exceeds supported input bound")
        if len(elf) < 52 or elf[:7] != b"\x7fELF\x01\x01\x01":
            raise ValueError(f"{path}: expected ELF32 little-endian PRX")
        header = struct.unpack_from("<16sHHIIIIIHHHHHH", elf)
        if header[1] != 0xffa0 or header[2] != 8 or header[3] != 1 or header[8] != 52:
            raise ValueError(f"{path}: unsupported ELF type/machine/version/header")
        phoff, phentsize, phnum = header[5], header[9], header[10]
        if phentsize != 32 or not 1 <= phnum <= 16 or phoff < 52 or phoff + phentsize * phnum > len(elf):
            raise ValueError(f"{path}: invalid program-header table")
        phdrs = tuple(
            struct.unpack_from("<IIIIIIII", elf, phoff + i * phentsize)
            for i in range(phnum)
        )
        loads = [p for p in phdrs if p[0] == PT_LOAD]
        if not loads:
            raise ValueError("No load segments")
        image_size = max(p[2] + p[5] for p in loads)
        if not 0 < image_size <= MAX_IMAGE:
            raise ValueError("Image exceeds supported address span")
        ranges = []
        for p in loads:
            _, offset, vaddr, _, filesz, memsz, _, align = p
            if not memsz or filesz > memsz or offset + filesz > len(elf) or vaddr & 3 \
                    or align not in (0, 1) and align & (align - 1):
                raise ValueError(f"{path}: invalid PT_LOAD segment")
            if any(vaddr < end and start < vaddr + memsz for start, end in ranges):
                raise ValueError("Overlapping load segments")
            ranges.append((vaddr, vaddr + memsz))
        if relocated is not None:
            image = relocated
            if len(image) != image_size:
                raise ValueError("Relocated image size does not match load segments")
        else:
            mutable = bytearray(image_size)
            for p in loads:
                _, offset, vaddr, _, filesz, memsz, _, _ = p
                if offset + filesz > len(elf) or filesz > memsz:
                    raise ValueError(f"{path}: invalid PT_LOAD segment")
                mutable[vaddr : vaddr + filesz] = elf[offset : offset + filesz]
            image = bytes(mutable)

        # For PSP ET_SCE_PRX files with no section table, p_paddr of the first PT_LOAD
        # identifies SceModuleInfo in the file, as used by the PPSSPP ELF loader.
        info_offset = loads[0][3] & 0x7FFFFFFF
        info_ranges = [p for p in loads if p[1] <= info_offset and info_offset + 52 <= p[1] + p[4]]
        if len(info_ranges) != 1:
            raise ValueError(f"{path}: module info is not in file-backed load memory")
        info_address = info_offset - info_ranges[0][1] + info_ranges[0][2]
        attr, major, minor, name, gp, ent_top, ent_end, stub_top, stub_end = struct.unpack_from(
            "<HBB28sIIIII", image, info_address
        )
        del attr, major, minor
        if b"\0" not in name:
            raise ValueError("Unterminated module name")
        module = cls(
            path,
            image,
            phdrs,
            name.split(b"\0", 1)[0].decode("ascii"),
            gp,
            ent_top,
            ent_end,
            stub_top,
            stub_end,
            info_address,
            header[4],
        )
        for start, end in ((ent_top, ent_end), (stub_top, stub_end)):
            if start & 3 or end & 3 or end < start or end - start > 65536:
                raise ValueError("Invalid import/export table range")
            if end > start:
                module.require_range(start, end - start)
        if module.entry & 3:
            raise ValueError("Unaligned module entry")
        module.require_range(module.entry, 4, executable=True)
        return module

    def require_range(self, address: int, size: int, executable: bool = False) -> None:
        if size < 0 or address < 0 or not any(
            p[0] == PT_LOAD and p[2] <= address and size <= (p[4] if executable else p[5])
            and address - p[2] <= (p[4] if executable else p[5]) - size and (not executable or p[6] & 1)
            for p in self.phdrs
        ):
            raise ValueError(f"{self.name}: unmapped range {address:#x}+{size:#x}")

    def u32(self, address: int) -> int:
        if address & 3:
            raise ValueError("Unaligned word")
        self.require_range(address, 4)
        return struct.unpack_from("<I", self.image, address)[0]

    def cstr(self, address: int) -> str:
        self.require_range(address, 1)
        end = self.image.find(b"\0", address, min(len(self.image), address + 256))
        if end < 0:
            raise ValueError("Unterminated library name")
        self.require_range(address, end + 1 - address)
        return self.image[address:end].decode("ascii")

    def imports(self) -> list[dict[str, object]]:
        records = []
        pos = self.stub_top
        while pos < self.stub_end:
            if pos + 20 > self.stub_end:
                raise ValueError(f"{self.name}: truncated import record at 0x{pos:x}")
            self.require_range(pos, 20)
            nameptr, version, attr, words, var_count, func_count, nidptr, stubptr = struct.unpack_from(
                "<IHHBBHII", self.image, pos
            )
            size = words * 4
            if words not in (5, 6) or pos + size > self.stub_end or func_count > 4096 or (var_count and words != 6):
                raise ValueError(f"{self.name}: invalid import record length {words} at 0x{pos:x}")
            name = self.cstr(nameptr) if nameptr else "<unnamed>"
            self.require_range(nidptr, func_count * 4)
            self.require_range(stubptr, func_count * 8, executable=True)
            varstubptr = self.u32(pos + 20) if words == 6 else 0
            if var_count:
                self.require_range(varstubptr, var_count * 8)
            nids = [self.u32(nidptr + i * 4) for i in range(func_count)]
            stubs = [stubptr + i * 8 for i in range(func_count)]
            records.append(
                {
                    "name": name,
                    "version": version,
                    "words": words,
                    "attribute": attr,
                    "var_count": var_count,
                    "varstubptr": varstubptr,
                    "func_count": func_count,
                    "nids": nids,
                    "stubs": stubs,
                    "nidptr": nidptr,
                    "stubptr": stubptr,
                    "address": pos,
                }
            )
            pos += size
        if pos != self.stub_end:
            raise ValueError(f"{self.name}: import records end at 0x{pos:x}, expected 0x{self.stub_end:x}")
        return records

    def exports(self) -> list[dict[str, object]]:
        records = []
        pos = self.ent_top
        while pos < self.ent_end:
            if pos + 16 > self.ent_end:
                raise ValueError(f"{self.name}: truncated export record at 0x{pos:x}")
            self.require_range(pos, 16)
            nameptr, version, attr, words, var_count, func_count, tableptr = struct.unpack_from(
                "<IHHBBHI", self.image, pos
            )
            size = words * 4
            if words != 4 or pos + size > self.ent_end or func_count + var_count > 4096:
                raise ValueError(f"{self.name}: invalid export record length {words} at 0x{pos:x}")
            name = self.cstr(nameptr) if nameptr else "<module-table>"
            total = var_count + func_count
            nids = [self.u32(tableptr + i * 4) for i in range(total)]
            addresses = [self.u32(tableptr + (total + i) * 4) for i in range(total)]
            records.append(
                {
                    "name": name,
                    "version": version,
                    "attribute": attr,
                    "var_count": var_count,
                    "func_count": func_count,
                    "nids": nids,
                    "addresses": addresses,
                    "tableptr": tableptr,
                    "address": pos,
                }
            )
            pos += size
        if pos != self.ent_end:
            raise ValueError(f"{self.name}: export records end at 0x{pos:x}, expected 0x{self.ent_end:x}")
        return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prx", type=Path)
    parser.add_argument("--relocated-image", type=Path)
    parser.add_argument("--provider", type=Path, action="append", default=[])
    parser.add_argument("--provider-image", type=Path, action="append", default=[])
    parser.add_argument("--all-import-nids", action="store_true")
    args = parser.parse_args()
    if len(args.provider_image) not in (0, len(args.provider)):
        parser.error("provide one --provider-image per --provider, or none")

    try:
        module = Prx.open(args.prx, args.relocated_image)
        providers = [
            Prx.open(path, args.provider_image[i] if args.provider_image else None)
            for i, path in enumerate(args.provider)
        ]
        imports = module.imports()
        if len({provider.name for provider in providers}) != len(providers):
            raise ValueError("Duplicate provider module name")
        exports = {provider.name: provider.exports() for provider in providers}
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"module={module.name} gp=0x{module.gp:08x}")
    print(f"exports=0x{module.ent_top:08x}-0x{module.ent_end:08x} imports=0x{module.stub_top:08x}-0x{module.stub_end:08x}")
    for library in imports:
        print(
            f"\nimport {library['name']} version=0x{library['version']:04x} "
            f"functions={library['func_count']} variables={library['var_count']} "
            f"nids=0x{library['nidptr']:08x} stubs=0x{library['stubptr']:08x}"
        )
        candidates = []
        for provider in providers:
            for record in exports[provider.name]:
                if record["name"] == library["name"]:
                    by_nid = {
                        nid: address
                        for nid, address in zip(record["nids"][:record["func_count"]], record["addresses"][:record["func_count"]])
                    }
                    candidates.append((provider.name, by_nid))
        for i, (nid, stub) in enumerate(zip(library["nids"], library["stubs"])):
            resolved = [f"{provider}+0x{by_nid[nid]:08x}" for provider, by_nid in candidates if nid in by_nid]
            if args.all_import_nids or resolved or i < 20:
                suffix = " -> " + ", ".join(resolved) if resolved else ""
                print(f"  {i:03d} NID=0x{nid:08x} stub=0x{stub:08x}{suffix}")

    if providers:
        print("\nprovider export libraries:")
        for provider in providers:
            libraries = [r for r in exports[provider.name] if r["name"] != "<module-table>"]
            print(f"  {provider.name}: " + ", ".join(f"{r['name']}({r['func_count']}f/{r['var_count']}v)" for r in libraries))


if __name__ == "__main__":
    main()
