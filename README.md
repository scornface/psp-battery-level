# PSP Battery Level

A VSH plugin for ARK-4 that displays **0%–100% to the right of the battery icon**
using Sony's native XMB text renderer and style. Layout follows the measured
text width; date/time content and charging animation remain Sony-managed.

## Compatibility

Verified on **PSP-2004, Sony 6.61, ARK-4 4.20.69 r206, standard theme**.
The plugin checks model, environment, module signatures and native objects.
Other models, firmware versions and custom themes are not verified.

Current version: **0.9**. The release build has no diagnostic logging; the
diagnostic build is an optional troubleshooting variant.
Other ARK API versions and models are actively rejected; the regional suffix
and r206 revision are validation references, not values exposed by the guards.

**Community feedback welcome:** if you try this plugin on another PSP-2000
variant or ARK-4 revision, please [open an issue](https://github.com/scornface/psp-battery-level/issues)
with your PSP model, Sony firmware version, full ARK-4 version, theme, and observed
behavior—including correct operation, visual glitches, or failure to load.
Other PSP models and ARK API versions are currently rejected by the compatibility
guards; reports for those configurations are compatibility requests, not evidence
of support. Do not bypass the guards.

## Download

**[Download the latest release ZIP](https://github.com/scornface/psp-battery-level/releases/latest/download/psp-battery-level.zip)**

Contains the ready-to-install `battery_level.prx` (release, without logging),
installation instructions and license notices. No local build environment is needed.
Source archives are available on the [releases page](https://github.com/scornface/psp-battery-level/releases).

## Installation

1. Obtain or build `battery_level.prx` and copy it to `ms0:/SEPLUGINS/`.
2. Inspect ARK's plugin manager and applicable `PLUGINS.TXT` files in
   `ms0:/SEPLUGINS/` and the ARK installation/savedata directory (commonly
   `ms0:/PSP/SAVEDATA/ARK_01234/`). Preserve other plugins and **replace any
   existing battery-level entry**, rather than enabling a second version:

   ```text
   VSH, ms0:/SEPLUGINS/battery_level.prx, on
   ```

3. Leave USB mode and fully reboot into the supported ARK environment. Live ARK
   installations may require running ARK Loader again. No runtime configuration
   is needed. See [ARK plugin instructions](https://github.com/PSP-Archive/ARK-4/wiki/Plugins).

To disable/uninstall, set this entry to `off` or remove it, reboot, and remove the
PRX if desired. Only load it in VSH; it is not an in-game battery overlay.
Include [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md) in redistributions.

## Build

Requires Docker, Python 3.10+, a POSIX shell and `shasum`. The build uses a pinned
PSPDEV image and writes all generated files under `build/`.

```sh
sh tools/build.sh                 # release: no logging
sh tools/build.sh diagnostic      # optional diagnostic logger
```

Outputs: `build/release/battery_level.prx` and
`build/diagnostic/battery_level.prx`. Builds do not install anything on a console.
Native PSPDEV/PSPSDK builds and optional analysis dependencies are described in
[`docs/dependencies.md`](docs/dependencies.md).

Diagnostic builds write `ms0:/SEPLUGINS/battery-level.log`, checking USB state
before writes. A new logging session overwrites the previous log: copy a trial
log before rebooting or launching a game. Summarize with
`python3 tools/summarize_log.py --power LOG`.
Release excludes the logger and filesystem imports entirely.

If nothing appears, check the supported ARK version, standard theme, enabled
VSH-only entry, file paths and duplicate entries across configurations. Release
has no runtime log; diagnosis requires the explicit diagnostic build.

## Development

```sh
sh tools/test.sh
python3 tools/check_build.py build/release/battery_level.prx --mode release
python3 tools/clean.py            # remove plugin intermediates; keep PRX/ELF
```

Source is in `src/`, host tests in `tests/`, maintained scripts in `tools/`, and
optional firmware research in `tools/analysis/`. `.deps/`, `data/` and `build/`
are local-only directories and are not part of the distributed plugin.

- [Architecture and runtime contracts](docs/architecture.md)
- [Native interface evidence and reproduction](docs/analysis.md)
- [Dependencies and local resources](docs/dependencies.md)
- [Tool reference](tools/README.md)

## License and references

[MIT](LICENSE), copyright 2026 PSP Battery Level contributors. Third-party tools
retain their own licenses. [PSPSDK](https://github.com/pspdev/pspsdk),
[ARK-4](https://github.com/PSP-Archive/ARK-4) and
[DayViewer](https://github.com/PSP-Archive/Dayviewer) were technical references;
this plugin creates independent Text nodes rather than replacing the clock.
