# Development tools

Run commands from the repository root. Python tools use the standard library
unless listed under firmware analysis.

| Tool | Purpose |
| --- | --- |
| `build.sh [release\|diagnostic]` | Pinned Docker/PSPDEV build; default release without logging |
| `test.sh` | Host policy tests and cleanup boundary tests |
| `check_build.py [PRX] [--mode MODE]` | Identity, imports, exports and release/diagnostic boundary |
| `inspect_deployed.py PRX [--reference PRX] [--mode MODE]` | Structural check, hash and comparison of the same read bytes |
| `summarize_log.py [--power] LOG` | Diagnostic log outcomes, transitions and counters |
| `prx_libraries.py PRX` | Shared ELF/PRX import/export reader; also used by build checks |
| `clean.py [--all]` | Clean plugin intermediates; optionally PRX/ELF, only under `build/` |

Builds go directly into `build/release/` and `build/diagnostic/`; host tests use
`build/tests/`. No build output belongs in `src/`. The checker and deployment
inspector's `--reference` default to `build/release/battery_level.prx`; the
inspector always requires a deployed path. Both default to release mode; specify
`--mode diagnostic` for diagnostic files. Equality does not establish mount,
configuration or runtime execution identity.

## Optional firmware analysis

`analysis/` contains tools for extending the verified native interface:

- `resolve_prx_rel2.py`: reconstruct the three authenticated 6.61 PRX images;
  zero-base only, with source/image hash manifests checked by consumers.
- `prx_string_xrefs.py`: identify references to strings (Capstone).
- `inspect_paf.py`: inspect instructions, callers and fields (Capstone).
- `decompress_rco_rlz.py`: decode the authenticated standard indicator resource;
  unknown resources never reach the input-unbounded legacy native decoder.
- `inspect_battery_resource.py`: verify standard battery image bounds.
- `build_rcomage.py`: reconstruct the recorded optional macOS tool from checked
  archives and the maintained LGPL patch. `dump_rco.py` authenticates its input,
  tool/data identities and uses an isolated copy of the resource.

Outputs must be new paths below `build/analysis/`; aliases/overwrites are rejected.
Disassembly results are heuristic candidates, not proof of complete call coverage.
The log parser reports partial records and measures observations only; timestamps
are not display latency.

The tools inspect locally obtained firmware copies; they do not install plugins or modify
flash0. Required inputs and optional dependencies are documented in
[`../docs/dependencies.md`](../docs/dependencies.md); technical evidence and
reproduction commands are in [`../docs/analysis.md`](../docs/analysis.md).
