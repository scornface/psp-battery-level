# Dependencies

## Build and host checks

| Task | Requirements |
| --- | --- |
| Docker plugin build | Docker, Python 3.10+, POSIX shell and `shasum` |
| Native plugin build | PSPDEV/PSPSDK with `psp-config` on `PATH`, Python and a POSIX shell |
| Host tests | Python 3.10+ and a C99 compiler; `CC` selects the compiler |
| Formatting | clang-format 21.1.8 and Ruff 0.14.5 from `tools/format-requirements.txt` |

The Docker build uses `pspdev/pspdev@sha256:b22811072ea0721d7f6c666a5a279b6def2b0cd95892b819d9570f8ffc4452c0` on `linux/amd64`. If the local Docker client requires it, set `DOCKER_API_VERSION=1.41`. Native SDK versions are not pinned; compare their output with the candidate being validated rather than assuming binary equivalence.

Commands and formatter installation are in [development](development.md). Host tests need no Docker, PSP SDK, Sony firmware or mounted console.

## Runtime inputs

The plugin requires the ARK/Sony environment listed in [compatibility](../README.md#compatibility). It uses ARK KUBridge/SystemCtrl and Sony power, USB and native UI services. GAME startup additionally reads the exact standard 6.61 `flash0:/kd/resource/impose.rsc` and `flash0:/font/ltn8.pgf`, authenticating them before decoding. Neither file is modified or bundled.

PSPLink, libusb, Capstone, pspdecrypt and RCOMage are not runtime dependencies.

## Optional firmware research

These dependencies are needed only for the commands in `tools/analysis/`.

| Component | Required version or identity |
| --- | --- |
| Capstone | 5.0.6, installed in the configured package directory |
| pspdecrypt | 1.0, for updater extraction and authenticated `libLZR.c/.h` |
| RCOMage | Recorded 1.1.1 sources, built with `tools/analysis/rcomage.patch` |
| Sony firmware | Locally obtained standard non-Go 6.61 updater and extracted firmware |

### Input directories

Set the relevant variables to existing absolute directories outside generated `build/`. Tools do not infer a sibling laboratory layout or use a global package in place of a configured dependency. Commands with explicit input paths continue to use those paths.

| Variable | Contents |
| --- | --- |
| `PSP_CAPSTONE_ROOT` | Python package directory containing `capstone/` |
| `PSP_PSPDECRYPT_ROOT` | pspdecrypt 1.0 sources, with `libLZR.c/.h` directly inside |
| `PSP_ARCHIVES_ROOT` | Authenticated archives named below |
| `PSP_FIRMWARE_ROOT` | Extracted firmware root containing `F0/` |

Install Capstone into its configured directory:

```sh
python3 -m pip install --target "$PSP_CAPSTONE_ROOT" -r tools/analysis/requirements.txt
```

Keep shared inputs versioned and read-only. Changing a dependency requires verifying it against the supported inputs again.

### Archives and native tools

Download the recorded sources into `PSP_ARCHIVES_ROOT` and check their hashes before extraction:

```sh
curl -fL https://codeload.github.com/John-K/pspdecrypt/tar.gz/refs/tags/1.0 -o "$PSP_ARCHIVES_ROOT/pspdecrypt-1.0.tar.gz"
curl -fL https://codeload.github.com/kakaroto/RCOMage/tar.gz/54ca649a9a6aba150a1fbe423f4c3aec611ee913 -o "$PSP_ARCHIVES_ROOT/RCOMage-master.tar.gz"
shasum -a 256 "$PSP_ARCHIVES_ROOT/pspdecrypt-1.0.tar.gz" "$PSP_ARCHIVES_ROOT/RCOMage-master.tar.gz"
```

| Archive | SHA-256 |
| --- | --- |
| `pspdecrypt-1.0.tar.gz` | `736cfffcbc3858e6e294781f5a329bbe157b4023ff59afe1adfca4df39ffa58b` |
| `RCOMage-master.tar.gz` | `684106736f716e62ce9ee09d96093c264d99a765c402bfabae8d6cf3cc9ed209` |

Extract the authenticated pspdecrypt archive into `PSP_PSPDECRYPT_ROOT`, then run `make -C "$PSP_PSPDECRYPT_ROOT"`. Building it needs Clang/C++, zlib and OpenSSL (`libcrypto`). If necessary, point `CPATH` and `LIBRARY_PATH` at the local OpenSSL installation. No global pspdecrypt installation is required. Updater extraction commands and firmware identities are in [native analysis](analysis.md#inputs-and-reproduction).

The recorded RCOMage build recipe supports macOS and needs Command Line Tools, pkg-config, libxml2 and zlib. Run `python3 tools/analysis/build_rcomage.py`; it authenticates the archives, applies the patch in an isolated tree and records compiler, patch, binary and data identities. Autotools is not required. Use the resulting binary through `dump_rco.py`, which checks the input and recorded tool identities.

The separate LZR recipe is also macOS-specific. It authenticates `libLZR.c/.h` before compiling a temporary library. The legacy decoder does not bound its input; the wrappers therefore authenticate the complete supported resource before native execution. Neither recipe is a general-purpose safe decoder for arbitrary RCO files.

### Files and redistribution

Persistent analysis outputs must be new paths under `build/analysis/`; tools reject aliases, redirected/mounted output directories and overwrites. Relocated images require their generated source/image hash manifests. Do not use firmware or hardware evidence paths as output destinations.

Keep raw device logs, console configuration, firmware dumps and external research inputs out of source and binary releases. Generated analysis libraries and the patched RCOMage tool remain local build products. Their licenses and the notices required for PRX redistribution are in [third-party notices](../THIRD_PARTY_NOTICES.md).
