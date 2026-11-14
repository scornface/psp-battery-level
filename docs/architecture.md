# Architecture

The installed kernel PRX selects one backend for its execution context: a user-mode XMB component in VSH, or a kernel Impose backend in GAME HOME. POPS is rejected. The backends do not share renderer state, native pointers, synchronization or teardown.

## Source map

| Component | Responsibility |
| --- | --- |
| `src/bootstrap/main.c`, `context.h` | Environment checks, context selection and parent lifecycle |
| `src/bootstrap/vsh.c` | Loading and owning the embedded user module |
| `src/vsh/main.c` | VSH worker, discovery, readiness retries and power sampling |
| `src/vsh/xmb.c`, `xmb.h` | Native Text ownership, callback-driven layout, recovery and cleanup |
| `src/vsh/native.c`, `native.h` | Module discovery, memory/signature guards, Sony calls and style |
| `src/vsh/*_policy.h` | Pure layout, recovery and timeout decisions |
| `src/vsh/abi.S`, `ark-imports.S` | Sony scalar-float ABI adapter and ARK import stubs |
| `src/home/backend.c`, `callback.c`, `hook.S` | GAME worker, native guards and pre/Sony/post callback wrapper |
| `src/home/bar_*.h`, `binding_policy.h` | Strip geometry, transfers and pixel ownership |
| `src/home/assets.c`, `pgf.c`, `sprite.c` | Asset authentication, bounded font decoding and sprite preparation |
| `src/home/power_worker.c`, `power_frames.h` | Power sampling and two-frame publication |
| `src/bootstrap/diagnostics.c`, `src/vsh/diagnostics.c` | Optional worker-side logging |

`src/vsh/Makefile` builds the user payload independently. `src/bootstrap/Makefile` embeds it and links the GAME backend into the installed PRX. Each module owns its exports.

Read `bootstrap/main.c` and `bootstrap/vsh.c` first, then follow the selected backend. `home/backend.h` is the bootstrap-facing GAME interface; `home/backend_internal.h` is private to that backend. `vsh/xmb.h` is not a cross-backend API.

## Bootstrap and module ownership

The bootstrap checks the model, firmware, key configuration and ARK API versions before selecting a backend. Version checks alone are insufficient: each backend must also validate the native code and objects it uses. Exact interfaces are documented in [native analysis](analysis.md).

In VSH, the bootstrap loads the embedded PRX into user memory partitions. It owns that module even if startup partially fails. Parent unload requires successful child stop and unload; a loaded child must never be abandoned on a failure path.

In GAME, the bootstrap worker runs the HOME backend. Hook publication and parent stop use the same interrupt exclusion. Once the hook is published, unload is refused without stopping the active renderer. A failed or stopped instance must be unloaded and freshly loaded, not restarted with stale state.

## VSH backend

### Installation and callback context

The VSH worker discovers PAF/VSH through KUBridge, checks module signatures and retries readiness for up to 30 seconds per startup phase. Installation validates the standard page, baseline geometry and both event slots before writing either hook. Text construction waits for a verified Sony callback.

The worker publishes the desired percentage and copies diagnostic state under the native PAF lightweight mutex. Power calls and file I/O remain outside it. Only verified callbacks create, style, reposition or destroy native nodes. Both original Sony callbacks run first.

The clock update event is 100; the size/layout event is `0x2000c`. Sony's reflow can invoke the layout callback recursively. The `reflowing` guard prevents applying the correction again during that nested call.

### Text and layout

`shown_node` is the visible front and `new_node` is the reusable back. At most two Text nodes exist. A percentage change sets the back's UTF-16 string and waits for Sony to prepare it while the front remains visible.

Commit requires valid backend flags and two identical width/box samples. Readiness flags bracket repeated metric reads to reject observed changes; this does not establish Sony's complete publication protocol. Node ranges, vtables, parent/vector membership and backend identity are checked before native calls, including destruction.

Layout uses the measured native box: `shift = box + 7`, with the percentage's right anchor at X=236. Battery and shadow move from captured baseline positions. Sony's reflow routine positions the clock and hold/mute icons. Geometry and front/back visibility change under the same lock.

Never subtract a shift from already shifted coordinates. Sony can reset the clock during date/time size changes; recognize only the verified reset positions and reapply the current shift from baseline.

### Recovery and USB

Invalid power samples or a hidden battery Plane hide the percentage and restore the bar. The front retains its string and metrics so it can be restored without setting the string or waiting for font preparation again. A changed percentage prepares a new back while that cached front remains visible.

The Plane visibility flag does not indicate whether its page is visible. USB storage can hide the page and suspend preparation while leaving the flag set. The update callback queries `USBStor_Driver`; state 1 pauses preparation/commit and clears the metric wait budget and stability samples. Nodes remain allocated. Normal preparation resumes after USB; outside USB, ten non-ready attempts cause a fault. A ready back waiting for the icon does not consume that timeout.

### Failure and cleanup

Guard failures request cleanup in a verified callback rather than invoking native operations from an arbitrary thread. Lock failures and callbacks without a verified context publish only a single-word deferred request. The next valid callback records the request and performs cleanup; synchronized fault details remain latched. The periodic event slot is resolved again on each callback.

Cleanup restores baseline geometry, destroys owned Text nodes, checks the original child counts and restores both callbacks. Uncertain ownership or a partially constructed object prevents destruction. A teardown latch and retired-address tokens prevent double destruction or a later false report of success.

VSH stop waits up to three seconds for worker/cleanup completion and uses a bounded thread-end handshake. The unload check uses a try-lock and refuses recursive unload from the PAF owner. Remaining workers, hooks, nodes or teardown faults prevent unload; unsafe native failures require a reboot.

## GAME HOME backend

### Startup and callback wrapper

Startup reads only `flash0:/kd/resource/impose.rsc` and `flash0:/font/ltn8.pgf`. Both files have bounded reads and exact size/hash checks before decoding. Scratch storage is reclaimed after preparing owned assets. Missing or mismatched inputs prevent hook installation; there is no replacement font, bundled Sony asset or fallback overlay.

Installation requires all 175 instruction/relocation guards, expected module ranges and the one-block FPL allocation with its exact cached/uncached aliases. The wrapper preserves Sony's arguments and results around integer-only pre/post helpers. A per-invocation token pairs granted pre/post phases; nested or expired calls cannot consume another invocation's work.

Only verified callbacks under CPU interrupt exclusion access the native strip at x=250..477, y=5..21. Interrupt exclusion does not make display scanout atomic. Callbacks perform no file I/O, power calls, allocation or glyph preparation.

### Pixel ownership and recovery

`canonical` stores the unmodified Sony strip; `presentation` stores the last plugin output. Clean callbacks access no pixels. Power-only changes first compare the complete old presentation, then compose from canonical pixels. They never shift an already shifted image.

Before Sony performs a partial battery update, restore the canonical strip only when the binding, boundary and entire old presentation match. A verified native full rebuild needs no stale restoration because it clears the owned strip itself.

Suspension retains ownership of any residual output. Recovery must precede both the wait gate and Sony's partial update. It requires the same binding/boundary and complete pixel equality; a mismatch forbids writing. Only verified restoration or completion of a native full clear discharges that ownership. A rejected scene or an incomplete rebuild does not.

### Sprites and power publication

Sprites preserve the original digits and 11×11 `%`, with a compact shadow and one blank bright column between digits and percent. Width includes the shadow. Composition uses `shift = width + 4` and `percent_x = 478 - width`; date/time and battery move together from canonical pixels. Old tails are cleared within the same strip. Accepted native-left boundaries remain 301..450.

Sony retains control of animations and cache scheduling. The plugin does not force redraws or store native cache flags.

The worker normally samples power once per second and prepares the inactive of two owned frames. Interrupt exclusion covers front-index/validity publication and the callback's entire front read; no pointer survives that read. Invalid power publishes invalidity instead of clamping or inventing a percentage. Workers never write Sony pixels, and logging budgets do not limit rendering or sampling lifetime.

## Development boundaries

Keep pure policies independent of PSP services. Share operations within a backend when their ownership contracts match, but do not merge PAF locking, interrupt exclusion or teardown into a generic controller. Repeated volatile readiness reads are intentional. Keep measured offsets numeric when their meaning is not established rather than inventing Sony field names.

Build, diagnostics, testing and release procedures are in [development](development.md). Host tests and structural checks cannot establish correct Sony rendering, scanout behavior or every unload path.
