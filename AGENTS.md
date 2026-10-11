# Agent instructions

## Repository map
- `src/`: plugin C/Allegrex sources and SDK Makefile; keep generated files out.
- `tests/`: host policy and maintenance tests; `tools/`: build/verification helpers.
- `tools/analysis/`: optional firmware research. External inputs live in ignored
  `.deps/` and `data/`; outputs belong in ignored `build/`.
- Read `docs/architecture.md` before changing runtime state, `docs/analysis.md`
  before changing native offsets, and `docs/dependencies.md` for setup.

## Build and verify
- Host checks: `sh tools/test.sh`.
- PRX: `sh tools/build.sh` (release, no logging), `sh tools/build.sh diagnostic`.
- Verify a candidate: `python3 tools/check_build.py PATH --mode release` (or
  `diagnostic`). Native SDK build instructions are in `docs/dependencies.md`.
- Run relevant checks after changes. Compilation does not verify Sony rendering;
  report hardware validation separately. Do not claim new model/firmware support
  from matching version numbers alone.

## Code conventions
- Use English for code comments and documentation. Explain contracts, ownership,
  locking, state transitions and reasons for native guards; avoid line narration.
- Keep modules focused and interfaces small; retain testable pure policies.
- Preserve original Sony callbacks, measured native layout and cached recovery.
  Node operations belong to verified XMB callbacks under the PAF lock; worker
  power calls and diagnostic I/O remain outside it.
- Do not substitute framebuffer overlays/fonts, weaken native signatures or
  write flash0. Verified scope: PSP-2004, Sony 6.61, ARK-4 4.20.69 r206, standard
  theme, VSH only. Consult evidence before extending that scope.
- Release must exclude logging/filesystem imports; diagnostics are opt-in.

## Hardware deployment
- Verify the USB mount and current configuration. Stage a distinct versioned
  PRX, compare bytes/hash/imports, change only the resident plugin line and sync.
- Reboot directly into the trial; no intermediate plugin-off persistence boot.
- Recheck file/configuration on return to USB. Diagnostic logs identify execution
  by `build_id`; release has offline identity/hash, not a runtime log.
- Preserve other plugins. Only delete files whose role has been established.
