# Tool reference

Run commands from the repository root. Python entrypoints support `--help`. For the build/test workflow and diagnostic interpretation, see [development](../docs/development.md); for optional external inputs, see [dependencies](../docs/dependencies.md).

## Build and maintenance

| Command | Purpose |
| --- | --- |
| `sh tools/build.sh [release\|diagnostic]` | Build both components with pinned PSPDEV; default release |
| `sh tools/test.sh [--sanitize]` | Run host tests, optionally with ASan/UBSan on C executables |
| `python3 tools/format.py [--check\|--write]` | Check/apply pinned C/header and Python formatting; default check-only |
| `python3 tools/clean.py [--all]` | Remove known intermediates; `--all` also removes PRX/ELF/payload outputs |
| `python3 tools/clean.py --check-only` | Validate output directories without deleting |

The cleaner visits only `build/release/`, `build/diagnostic/` and their `kernel/` and `vsh/` children. It removes `*.o` and `exports.c`; `--all` adds `battery_level.prx`, `battery_level.elf` and `vsh-payload.prx`. It does not recurse, follow file links or clean evidence. All directory checks precede deletion, and existing build locks cause refusal.

## Binary checks

| Command | Purpose |
| --- | --- |
| `python3 tools/check_build.py [PRX] [--mode MODE]` | Check the installed kernel PRX, embedded payload and HOME callback ABI |
| `python3 tools/check_vsh.py [PAYLOAD] [--mode MODE]` | Check the internal user/VSH component |
| `python3 tools/inspect_deployed.py PRX [--reference PRX] [--mode MODE]` | Validate, hash and compare the bytes read from each PRX path |
| `python3 tools/prx_libraries.py PRX` | Inspect imports/exports; optionally use `--relocated-image`, `--provider`, `--provider-image` and `--all-import-nids` |

Default mode is release. The unified checker and inspector reference default to `build/release/battery_level.prx`; the VSH checker defaults to `build/release/vsh-payload.prx`. For diagnostics, pass the diagnostic paths and mode explicitly.

Unified checks need the companion `.elf` and `vsh-payload.prx` beside the candidate, or beside the reference for deployment inspection. Override these with `--elf PATH --vsh PATH`. `inspect_deployed.py` requires a path to inspect; it does not discover a USB mount or deploy files. Matching bytes do not prove runtime execution.

`prx_libraries.py` also supplies the shared PRX reader. `prx_checks.py` is a helper module for companion ELF and integer-only callback validation, not a CLI.

## Log summaries

| Command | Purpose |
| --- | --- |
| `python3 tools/summarize_log.py [--power] LOG` | Summarize VSH snapshots, observed completions and optional power/visibility changes |
| `python3 tools/summarize_runtime.py LOG` | Summarize bootstrap/GAME snapshots by build, context and session start |

Both readers accept ASCII logs up to 8 MiB and report incomplete records. Their formats and session rules differ; use the reader for the corresponding log. Retention, budgets and interpretation limits are covered under [diagnostics](../docs/development.md#diagnostics).

## Firmware analysis

Commands below are relative to `tools/analysis/`. They inspect locally obtained inputs without installing plugins or writing flash0. Persistent outputs must be new paths under `build/analysis/`.

| Tool | Purpose |
| --- | --- |
| `resolve_prx_rel2.py INPUT IMAGE REPORT` | Relocate an authenticated module at base zero and emit a hash manifest |
| `prx_string_xrefs.py PRX IMAGE` | Find candidate string references with Capstone; supports `--pattern` and `--context` |
| `inspect_paf.py` | Inspect PAF/VSH instructions, direct callers, imports and fields; supports `--module`, `--range`, `--caller`, `--import-stub`, `--field` and `--word` |
| `decompress_rco_rlz.py INPUT OUTPUT` | Decode the authenticated standard indicator resource's tables |
| `inspect_battery_resource.py` | Inspect the standard battery image's format and alpha bounds |
| `verify_home.py` | Check all 175 maintained Impose instruction/relocation guards |
| `verify_assets.py` | Authenticate the Sony resources and compare all 101 sprites with the approved series hash |
| `build_rcomage.py` | Build the recorded macOS RCOMage tool from authenticated archives and the local patch |
| `dump_rco.py INPUT OUTPUT` | Dump the authenticated resource with the recorded RCOMage binary/data |

`common.py` supplies input/output boundaries and firmware identities; it is a helper module, not a command. `requirements.txt` pins Capstone, and `rcomage.patch` retains the third-party patch and notices. Interface details and reproduction examples are in [native analysis](../docs/analysis.md).
