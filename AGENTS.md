# Agent instructions

## Repository and reading order

- `src/bootstrap/`: installed kernel PRX, context selection and embedded user-module ownership.
- `src/vsh/`: user-mode XMB backend and its private build definition.
- `src/home/`: GAME HOME worker, guarded callback and pure composition policies.
- `tests/`: host policies, C harnesses and tooling regressions. Keep generated products under `build/`.
- `tools/analysis/`: optional research. Use explicit `PSP_*_ROOT` inputs; never infer sibling laboratory paths.
- Read `docs/architecture.md` before changing runtime state, `docs/analysis.md` before changing native interfaces, and `docs/development.md` for build, validation and release procedures. Setup requirements are in `docs/dependencies.md`.

## Checks

- Run relevant host tests with `sh tools/test.sh`; use `sh tools/test.sh --sanitize` for C memory/ownership changes.
- Build with `sh tools/build.sh release` and `sh tools/build.sh diagnostic`. Each produces one installable PRX and offline ELF/payload companions.
- Check candidates with `python3 tools/check_build.py PATH --mode release` or `--mode diagnostic`.
- Run the pinned style check after code edits; setup is in `docs/development.md#formatting`.
- Separate host/structural results from hardware findings. For maintenance intended to preserve runtime behavior, compare both modes with the accepted artifact hashes. Consult local acceptance manifests/evidence when available; do not invent validation results when they are absent.

## Runtime constraints

- Keep modules focused, interfaces small and pure policies testable. Do not force shared abstractions across different backend contracts.
- Preserve Sony callbacks, measured layout and cached recovery. VSH node operations belong to verified callbacks under the PAF lock; worker power calls and diagnostic I/O stay outside it.
- HOME pixel access belongs to verified callbacks under interrupt exclusion. Preserve canonical/presentation ownership, exact restoration, actual-width anchoring, original digits/11×11 `%`, compact shadow and one-blank-column spacing.
- Do not substitute framebuffer overlays or fonts, weaken native signatures or write flash0. Scope is PSP-2004, Sony 6.61, ARK-4 4.20.69 r206, standard theme, VSH and GAME HOME only. POPS is unsupported. Version matches do not establish new support.
- Release excludes logging; its filesystem access is limited to bounded, read-only, authenticated GAME startup acquisition of `impose.rsc` and `ltn8.pgf`. Diagnostic I/O is opt-in and worker-only. No callback file I/O, periodic asset reads or configurable replacement assets.

## Code and documentation

- Use English. Explain contracts, ownership, synchronization, state transitions and reasons for native guards; avoid line-by-line narration.
- Follow `.clang-format` and `ruff.toml`; do not run automatic lint fixes as formatting.
- Markdown has no column limit. Keep each prose paragraph on one line and use line breaks for document structure. Preserve quoted license text.
- Document current behavior, not implementation history. Keep each subject in its primary document and link rather than repeat detailed explanations.

## Hardware operations

- Verify the mount and current configuration. Preserve other plugins; stage a distinct versioned PRX and compare bytes/hash/imports before changing only this plugin's entries and syncing.
- Reboot directly into the trial, without an intermediate plugin-disabled boot. Do not attempt GAME live unload after hook publication.
- On return to USB, recheck file/configuration and collect logs. Diagnostic `build_id` identifies logged execution; release uses offline identity/hash plus the observed trial, not a runtime log.
- Keep raw evidence private. Delete only files whose role is established. Deployment, commit, merge and publication require separate authorization.
