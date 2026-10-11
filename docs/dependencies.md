# Dependencies and local resources

## Build and tests

Plugin builds need PSPDEV/PSPSDK, Python 3.10+, a POSIX shell and `shasum`.
Docker supplies PSPDEV when using `sh tools/build.sh [release|diagnostic]`.
Host tests (`sh tools/test.sh`) need a C99 compiler and Python, not Docker/PSPDEV.

Pinned image:
`pspdev/pspdev@sha256:b22811072ea0721d7f6c666a5a279b6def2b0cd95892b819d9570f8ffc4452c0`,
`linux/amd64`. Builds are staged, mode-locked and checked before publishing PRX/ELF.
If the local Docker client requires it, prefix with `DOCKER_API_VERSION=1.41`.
The pinned image gives a recorded toolchain, not a universal reproducibility
guarantee across arbitrary environments; compare clean-build hashes.

For native builds install [PSPDEV](https://pspdev.github.io/), put its tools on
`PATH`, and ensure `psp-config --pspsdk-path` works:

```sh
mkdir -p build/release
make -C build/release -f ../../src/Makefile DIAGNOSTICS=0
python3 tools/check_build.py build/release/battery_level.prx --mode release
```

Use `build/diagnostic`, `DIAGNOSTICS=1` and `--mode diagnostic` for logging.
Native SDK versions are not pinned: record the toolchain and compare hashes.
Native checkout paths with spaces and CFLAGS/OBJS overrides are unsupported;
use Docker for such checkouts. Source lookup never searches generated objects.

## Release automation

`.github/workflows/release.yml` runs host tests and the pinned Docker release
build on GitHub Actions. A manual run uploads artifacts without publishing;
pushing a `v*` tag publishes the PRX, `psp-battery-level.zip` and `SHA256SUMS`.
Tags containing a hyphen are published as prereleases. GitHub also provides
source archives for the tagged commit. No diagnostic build or local research
inputs are packaged.

Before publishing `v0.9`, run the workflow manually: its PRX must match the
hardware-tested SHA-256. The same check gates the `v0.9` tag build. For subsequent
versions, update the manual-run reference hash after hardware validation.

## Runtime

The PRX uses ARK KUBridge/SystemCtrl, Sony power/USB services and guarded calls
into loaded PAF/VSH. PSPLink, libusb, Capstone, pspdecrypt and RCOMage are not
runtime dependencies. No external font or Sony firmware is bundled.

## Optional firmware research

| Component | Local location / purpose |
| --- | --- |
| Capstone 5.0.6 | `.deps/capstone-py/`, MIPS disassembly |
| pspdecrypt 1.0 | `.deps/pspdecrypt-1.0/`, OFW extraction and LZR source |
| RCOMage 1.1.1 | Authenticated archive in `.deps/`; recorded product in `build/analysis/rcomage-tool/` |

Normal plugin builds never download these. Install Capstone explicitly:

```sh
mkdir -p .deps
python3 -m pip install --target .deps/capstone-py -r tools/analysis/requirements.txt
```

Analysis scripts require that local package/version; they do not silently use a
different global installation. An upgrade needs verification of the known images.

### Reconstruct the research inputs

```sh
curl -fL https://codeload.github.com/John-K/pspdecrypt/tar.gz/refs/tags/1.0 -o .deps/pspdecrypt-1.0.tar.gz
curl -fL https://codeload.github.com/kakaroto/RCOMage/tar.gz/54ca649a9a6aba150a1fbe423f4c3aec611ee913 -o .deps/RCOMage-master.tar.gz
shasum -a 256 .deps/pspdecrypt-1.0.tar.gz .deps/RCOMage-master.tar.gz
```

Expected SHA-256: pspdecrypt
`736cfffcbc3858e6e294781f5a329bbe157b4023ff59afe1adfca4df39ffa58b`,
pinned RCOMage `684106736f716e62ce9ee09d96093c264d99a765c402bfabae8d6cf3cc9ed209`.
The recorded older RCOMage archive
`6b15161f8099cfe21f63ca56b42442a5cfea1f4183a0d56f176bdd1b6b295f79`
is also accepted. Do not extract an archive until its hash matches.

For OFW extraction, unpack pspdecrypt into `.deps/pspdecrypt-1.0` and run
`make -C .deps/pspdecrypt-1.0`. Its Makefile needs Clang/C++, zlib and OpenSSL
(`libcrypto`). Set local OpenSSL include/library search paths as needed: on
Homebrew, `CPATH` and `LIBRARY_PATH` can point to the installation's `include`
and `lib` directories. No global install of pspdecrypt is required.

For the optional macOS RCO tool, install Command Line Tools, pkg-config, libxml2
and zlib, then run `python3 tools/analysis/build_rcomage.py`. It authenticates the
archives, applies `tools/analysis/rcomage.patch` in an isolated source tree and
records archive/patch/binary/data hashes and Clang identity. The manual compiler
recipe lives in the script; autotools is not required. Legacy upstream warnings
do not make it a general-purpose safe decoder. Use only `dump_rco.py`, which
authenticates the standard indicator resource before starting the local tool.

The LZR wrapper also supports only this authenticated resource and checks
`libLZR.c/.h` hashes before compiling into a private `build/analysis/lzr-*`
directory. It does not claim to bound the legacy C decoder's input. Unknown
resources are rejected before C executes; temporary products are cleaned on
exit. Both recorded C build recipes are macOS-specific. Other hosts require
an independently verified recipe.

Relocation accepts only the three recorded standard modules, at base zero.
Consumers require the generated `.bin.json` source/image hash manifest. Analysis
outputs must be new paths in `build/analysis/`; remove only known generated
outputs before repeating a command. Evidence and firmware are never output paths.

## Directory boundaries and licenses

- `tools/`: maintained project scripts; `tools/analysis/`: optional research.
- `.deps/`: external archives, pspdecrypt sources and pinned Capstone package.
- `data/661/`: locally obtained standard (non-Go) Sony 6.61 updater.
- `data/ofw-661/`: extracted firmware; never shipped with the plugin.
- `data/evidence/`: optional local research data; never publish raw device logs,
  memory addresses, configuration, firmware dumps, or private material.
- `build/`: generated plugin, host-test and analysis outputs; safe to regenerate.

`.deps/`, `data/` and `build/` are ignored and must not be included in source or
binary releases. Third-party components retain their licenses: pspdecrypt GPLv3,
libLZR 0.11 by BenHur **CC BY-SA 3.0**, RCOMage
LGPL-2.1 notices and Capstone's component notices. MIT does not relicense them.
See [third-party notices](../THIRD_PARTY_NOTICES.md), including PSPSDK notices
to accompany PRX redistribution. Optional analysis binaries are not shipped.
