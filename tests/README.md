# Test organization

Test commands, compiler selection and sanitizer coverage are documented in [development](../docs/development.md#host-tests). Tests use synthetic inputs and host PSP-service mocks, not firmware or a console.

| Location | Role |
| --- | --- |
| `c/` | Standalone C harnesses with named scenarios |
| `stubs/` | Host service declarations; not Sony ABI/layout evidence |
| `support.py` | Compilation, execution and private temporary products |
| `prx_fixture.py` | Independent user/kernel import contracts and synthetic ELF/PRX inputs |
| `pgf_fixture.py`, `home_types.py` | Synthetic PGF data and ctypes layouts |
| `*_test.py` | Python suites and C-harness entrypoints |

## Fixture rules

Keep expected results independent of production code. Do not derive expected imports from checker allowlists or expected pixels from the composer. Shared scene/tile inputs must not replace an independent oracle. Test modules must not import other test modules; reusable fixtures belong in support files.

Retain exhaustive HOME width/boundary combinations, both halfword lanes and complete mismatch checks in transfer tests. Keep residual-ownership recovery as a dedicated regression. Null-pointer clean-frame cases verify that rejected/idle paths do not access pixels.

Keep pure frame publication separate from worker service ordering, refresh tokens with the HOME hook ABI, and bootstrap lifecycle separate from logging. Preserve separate contracts for kernel/user binary checks and the two log formats.

Tooling tests cover snapshot consistency, path/archive boundaries, relocation handling and CLI behavior without external inputs. Positive synthetic analysis fixtures exercise the parser/verifier, not Sony firmware authentication. Host results do not establish renderer behavior, PSP scheduling or scanout atomicity.
