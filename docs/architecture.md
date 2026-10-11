# Plugin architecture

The plugin adds a Sony PAF `Text` next to the battery. It does not draw to the
framebuffer, replace the clock string, or control Sony's charging animation.
The verified target is PSP-2004, Sony 6.61, ARK-4 4.20.69 r206, standard theme.

## Source map

| Component | Responsibility |
| --- | --- |
| `src/main.c` | Module lifecycle, environment checks, readiness retries, 1 Hz power sampling |
| `src/xmb.c` | Clock hooks, native Text ownership, measured layout, recovery and teardown |
| `src/native.c`, `native.h` | Module discovery, memory/signature guards, Sony ABI calls and style |
| `src/diagnostics.c`, `diagnostics.h` | Optional snapshot logger; absent from release |
| `src/xmb.h` | Internal shared-state and worker/controller contract |
| `src/*_policy.h` | Small platform-independent layout/recovery/timeout decisions |
| `src/abi.S` | Move scalar float argument bits into Sony's expected `f12` register |
| `src/ark-imports.S` | ARK KUBridge/SystemCtrl import stubs |

## Execution and ownership

The worker discovers PAF/VSH through KUBridge, validates the environment and
module signatures, and retries UI readiness for up to 30 seconds per phase.
Installation validates the standard page, geometry and both event slots before
writing either hook. Text construction is deferred to Sony's callback.

Once installed, the worker updates `status.desired` and copies diagnostic state
under the native PAF lightweight mutex. Power calls and logging are outside
that lock. Only verified clock callbacks create, style, reposition or destroy
native nodes. Both original Sony callbacks always run first.

The clock update hook uses event 100. The size/layout hook uses event `0x2000c`.
Native reflow can trigger the latter recursively; `reflowing` prevents applying
our correction again inside our own reflow.

## Text update state machine

`shown_node` is the committed front; `new_node` is the reusable back. At most
two Text nodes are created. An update sets the back's UTF-16 string and waits
for Sony to process it, keeping the old front visible.

The backend supplies fractional glyph width and a rounded native box. Commit
requires valid backend flags and two identical width/box samples. The layout uses
`shift = box + 7`, with the text right anchor at X=236. Battery and shadow move
from their captured baseline; the clock is repositioned through Sony's reflow
routine, which also places hold/mute icons. Swapping visibility and geometry
occurs under the same lock.

Readiness flags bracket repeated width/box reads. This rejects observed changes,
but does not prove Sony's backend publication protocol; hardware validation is
still required. Node addresses, vtables, parent/vector ownership and backend
identity are validated before virtual calls, including teardown.

Never accumulate shifts from the live coordinates. Sony can reset the clock
when its date/time size changes; recognize only the verified reset positions
and reapply the current shift from an unshifted baseline.

## Recovery and USB

Invalid power samples or a hidden battery Plane hide the percentage and restore
the bar. The front retains its string and measured box. Once valid again, the
callback can restore it without setting the string or repeating metric warmup.
A changed desired percentage prepares a new back while the cached front stays
visible. A ready back can wait for the icon without consuming a timeout.

The Plane flag does not represent page-level visibility. USB storage hides the
indicator page and can suspend text preparation while that flag remains set.
Each update callback directly queries `USBStor_Driver`; started (1) pauses
preparation/commit and clears the metric wait budget and stability samples.
Existing nodes remain intact. On exit, normal preparation resumes. Outside USB,
ten non-ready attempts still fault instead of waiting indefinitely.

## Failure and unload

Topology, vtables, callback ownership and expected geometry are checked before
native operations. Failure requests guarded cleanup; unexpected ownership or a
partially constructed object prevents unsafe destruction.

Cleanup restores geometry, destroys owned Text nodes, verifies original child
counts and restores both callbacks. `module_stop` requests this work instead
of performing it on a foreign thread. It waits up to three seconds and refuses
unload if the worker, hooks or nodes are still active. The thread-end handshake
adds at most 100 ms. A try-lock waits out active foreign callbacks without blocking
unload indefinitely; recursive unload from the PAF owner is refused.
Destruction failures retain a teardown latch/retired-address tokens and prevent
subsequent false success or double destruction. Such unsafe failures require a
reboot; they are not repaired by blindly retrying native operations.

Worker lock failures and callbacks lacking a verified context publish only a
single-word deferred request; a later verified callback records it (diagnostic
stage 7) and cleans up. The latest deferred code wins; first synchronized fault
details remain latched. The periodic event slot is re-resolved each time.

Important outcomes: -2 module/signature mismatch; -12 unsupported environment;
-20 callback context mismatch; -21 allocation preflight/allocation failure;
-22 unexpected constructed vtable; -23 child registration mismatch;
-24 style failure; -25 invalid percentage/setter failure; -26 hook ownership;
-27 teardown child-count mismatch; -30 unsupported initial geometry/topology;
-31 unexpected live geometry; -32 restoration mismatch; -33 metric timeout;
-34 unsafe Text membership. Discovery/readiness also use -1/-3/-4/-5/-7/-8/-9/
-10/-11 for module, lock, object and event checks.

## Release and diagnostics

Default: `sh tools/build.sh` (or `sh tools/build.sh release`). Optional logging:
`sh tools/build.sh diagnostic`. Docker builds use the pinned PSPDEV image;
direct SDK out-of-source builds are documented in [dependencies.md](dependencies.md).

All outputs are built directly in `build/release/` and `build/diagnostic/`;
`src/` contains only source/build definitions. Mode switches rebuild all objects,
because the shared-state layout differs between modes.

Release excludes diagnostic code, buffers, counters, timestamps and charging/AC
sampling. It imports no filesystem services. Required geometry caches, failure
handling, the power sampler and callback USB gate remain active. An offline
identity string identifies the PRX without a log: release `0001000a`, diagnostic
`0001000b`, module version 0.9. Numeric/text IDs derive from one token.

Diagnostic logging uses `ms0:/SEPLUGINS/battery-level.log`, hexadecimal fields,
at most 128 ordinary change snapshots per VSH session plus a terminal snapshot.
USB state is checked before writing and suppressed snapshots are retried later.
These checks are best-effort transition gating, not a USB/filesystem exclusion
lock. A newly started logging session truncates the previous file; archive a
trial before reboot/game launch. I/O uses copies,
never native pointers, outside the lock. Snapshot timestamps are not display
frame measurements. Parse with `python3 tools/summarize_log.py --power LOG`.

## Verification

Run `sh tools/test.sh` for C99 policy checks (`-Wall -Wextra -Werror`) and scoped
controller/guard tests and Python mutation/boundary tests. Build both modes and
run `tools/check_build.py` on their PRX files: bounded ELF ranges, exact import
NIDs/attributes, no variable/duplicate imports, mode identity and typed system
exports. Function/stub targets must be executable file-backed ranges. A checker
pass is structural evidence, not proof of correct rendering or unloading.

Host checks cannot validate Sony's renderer. Hardware checks cover startup,
percentage changes, date/time reflow, USB with changed percentage, standby and
return from a game. Stage a distinct versioned filename, compare bytes/hash and
imports, change only the resident plugin line, sync and reboot directly. For
release, verify the offline identity and file hash before/after the trial;
there is intentionally no runtime log identifying execution.

Hardware compatibility is limited to the target listed at the top of this
document. Host checks and structural PRX validation do not establish behavior on
other hardware, firmware, themes, or every unload path. For deployment, compare
the release PRX with its build, preserve other plugins, enable only one resident
copy, and reboot directly into the target environment.
