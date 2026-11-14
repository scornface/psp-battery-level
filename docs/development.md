# Development

Run commands from the repository root. [Dependencies](dependencies.md) lists the required tools and optional research setup; [architecture](architecture.md) explains the runtime contracts.

## Build

```sh
sh tools/build.sh release
sh tools/build.sh diagnostic
```

Release excludes logging; diagnostic mode enables worker-side logs. The build uses a pinned Docker image, private staging and a per-mode lock. Both components pass their binary checks before outputs are copied into the mode directory. Do not remove a build lock while its build is running.

Each mode produces:

| File | Use |
| --- | --- |
| `build/MODE/battery_level.prx` | The only file installed on the console |
| `build/MODE/battery_level.elf` | Offline companion for symbols and callback-code checks |
| `build/MODE/vsh-payload.prx` | Embedded user component, retained for offline verification |

To recheck a candidate:

```sh
python3 tools/check_build.py build/release/battery_level.prx --mode release
python3 tools/check_build.py build/diagnostic/battery_level.prx --mode diagnostic
```

The checker validates build identity, exact imports/exports, the embedded payload and the integer-only HOME wrapper/helpers. It does not validate Sony rendering or unload behavior.

### Native SDK build

Install PSPDEV/PSPSDK and make sure `psp-config --pspsdk-path` works. Native builds require a checkout path without spaces and do not support command-line `CFLAGS` or `OBJS` overrides; use Docker when those constraints are unsuitable.

```sh
mkdir -p build/release/vsh build/release/kernel
make -C build/release/vsh -f ../../../src/vsh/Makefile DIAGNOSTICS=0
python3 tools/check_vsh.py build/release/vsh/battery_level.prx --mode release
make -C build/release/kernel -f ../../../src/bootstrap/Makefile DIAGNOSTICS=0 VSH_PAYLOAD="$PWD/build/release/vsh/battery_level.prx"
cp build/release/kernel/battery_level.prx build/release/kernel/battery_level.elf build/release/
cp build/release/vsh/battery_level.prx build/release/vsh-payload.prx
python3 tools/check_build.py build/release/battery_level.prx --mode release
```

For diagnostics, use `build/diagnostic`, `DIAGNOSTICS=1` and `--mode diagnostic` throughout. The Makefiles rebuild objects on each invocation so mode changes cannot reuse objects with incompatible shared-state layouts.

### Cleanup

`python3 tools/clean.py` removes known intermediates while preserving the three product files. Add `--all` to remove those products too. Cleanup is limited to the release/diagnostic directories and their native `kernel/` and `vsh/` children; it does not clean tests, analysis or hardware evidence. Do not run it concurrently with a native SDK build.

## Host tests

```sh
sh tools/test.sh
sh tools/test.sh --sanitize
```

Tests cover pure policies, pixel bounds, ownership/recovery, mocked PSP services, binary validation and tooling boundaries. They use Python and a C99 host compiler, with private products under `build/tests/`. Set `CC` to select a compiler with the required features.

Sanitizer mode enables ASan/UBSan for standalone C harnesses. Libraries loaded through ctypes remain uninstrumented because the Python process is not an ASan executable. LeakSanitizer is disabled on macOS. Test organization and fixture rules are in [tests](../tests/README.md).

## Formatting

```sh
python3 -m venv build/format-venv
build/format-venv/bin/python -m pip install -r tools/format-requirements.txt
. build/format-venv/bin/activate
python3 tools/format.py --check
python3 tools/format.py --write
```

The default is check-only. The runner requires the pinned versions and runs formatters only, not lint fixes. CI uses the same check. Normal host tests do not require formatters.

- C/headers in `src/` and `tests/`: clang-format 21.1.8, four spaces, approximately 100 columns, block-style multiline arguments and initializers, function braces on the next line and explicit control-statement braces. Continuation indentation is four spaces; long initializer lists remain packed. Labels remain at column zero, and nested preprocessor directives use four-space indentation. Include order is preserved. `DIAG` statement arguments retain their manual line breaks; macro and preprocessor boundaries require manual review because automatic brace insertion can skip them.
- Python in `tests/` and `tools/`: Ruff 0.14.5, four spaces and 100 columns. No import sorting or automatic lint corrections.
- Markdown: no column limit. Keep each prose paragraph on one line; use line breaks for Markdown structure, not text wrapping. Preserve quoted license text.
- Assembly, Makefiles, PSP exports, third-party patches, archives and generated files are outside automatic formatting.

Keep formatting changes separate from logic changes. For runtime formatting, compare C tokens/Python ASTs where applicable and require unchanged PRX/ELF/payload hashes after rebuilding both modes. For behavioral changes, add focused regression tests instead of treating formatting or compilation as validation.

## Diagnostics

Diagnostic builds produce two logs with different lifecycles:

| Path | Contents and retention |
| --- | --- |
| `ms0:/SEPLUGINS/battery-level.log` | VSH state/power snapshots; a new session truncates the previous log |
| `ms0:/SEPLUGINS/battery-level-runtime.log` | Appended bootstrap/GAME snapshots, separated by build/context/start key |

Copy logs before rebooting or launching another game, especially the VSH log. Parse the collected files locally:

```sh
python3 tools/summarize_log.py --power PATH_TO_VSH_LOG
python3 tools/summarize_runtime.py PATH_TO_RUNTIME_LOG
```

VSH logging permits at most 128 ordinary change snapshots plus terminal output per session. The outer logger permits 256 ordinary changes plus terminal output per instance. Failed USB/I/O attempts do not consume the budget; reaching the budget does not stop rendering or power sampling. USB state checks are best-effort write gating, not a filesystem exclusion lock. I/O uses copied state outside native synchronization.

Snapshots are not complete callback traces, and timestamps are not display latency. Zero GAME counters in a VSH record are normal. `terminal=1` marks bootstrap worker completion, not successful child unload. Release has no runtime log; identify it through the offline candidate and file hash, not old diagnostic logs left on the Memory Stick.

Raw fields use eight-digit hexadecimal values. Signed results use two's complement, so `fffffffe` is -2. Interpret codes in context: the outer `outcome` reports bootstrap/backend startup or worker completion, while GAME `fault` and `fault_site` describe callback failures. Consult [VSH startup](../src/vsh/main.c), the [VSH controller](../src/vsh/xmb.c), the [user loader](../src/bootstrap/vsh.c) or the [HOME callback](../src/home/callback.c) for the relevant failure path; the same number need not mean the same thing in each component.

## Hardware verification

Hardware coverage is limited to the [documented configuration](../README.md#compatibility). Release and diagnostic builds passed limited XMB → GAME HOME → XMB functional trials. This does not establish every transition, live-unload correctness or support for another configuration.

Before a trial:

1. Build and structurally check the candidate, retaining its PRX, ELF, payload, hashes and mode. Run the relevant host tests.
2. Confirm the actual USB mount and current plugin configuration. Preserve other plugins and inspect all applicable plugin entries.
3. Stage a distinct versioned PRX. Compare the bytes, hash and imports with the local candidate; `inspect_deployed.py` can validate the staged copy against the local reference and companions.
4. Change only this plugin's VSH/GAME entries, ensure only one copy is enabled, and sync writes.
5. Leave USB and reboot directly into the trial. Do not insert an intermediate plugin-disabled boot. Do not attempt GAME live unload after hook publication.

Exercise percentage changes and alignment, clock reflow, charging changes, USB entry/exit, standby and the VSH/GAME return path as relevant to the change. Record what was actually observed; do not describe unexercised cases as validated.

On return to USB, recheck the deployed PRX and configuration and collect diagnostics before overwriting them. A file comparison proves file identity, not execution identity. Diagnostic `build_id` identifies logged execution; release verification combines the retained candidate/readback with the observed trial. Keep raw evidence private and report hardware findings separately from host checks.

## Release workflow

The GitHub workflow checks formatting, runs host tests and builds the release with the pinned image. A manual run uploads artifacts without publishing. Package contents are `battery_level.prx`, `README.md`, `LICENSE` and `THIRD_PARTY_NOTICES.md`; ELF files, diagnostic builds and research inputs are not included.

Before publishing, review the changes, run the relevant checks and both build modes, and approve the intended release candidate on hardware. Set the repository variable `RELEASE_PRX_SHA256` to that approved PRX's SHA-256. A tag-triggered build must match it to proceed. Maintenance intended to preserve runtime behavior must retain the accepted artifact hashes.

Pushing an authorized `v*` tag publishes the PRX, `psp-battery-level.zip` and `SHA256SUMS`. A hyphen in the tag marks a prerelease. GitHub also supplies source archives for the tagged commit. Update the README's download availability when publishing the unified build; local acceptance or a manual workflow run alone does not make it a published release.
