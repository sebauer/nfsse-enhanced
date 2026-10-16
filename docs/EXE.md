# NFS.EXE internals and patch catalogue

Reference for the DOS executable of *The Need for Speed Special Edition* (English/German
release, `NFS_DOS.EXE` on the CD, dated 1996-06-19) and for every change `nfsse/exe.py` makes.

## Supported input executables

| SHA-256 | Source | Note |
|---|---|---|
| `7d2104a9eae01ca7b74807ab66334e3ce806d7a9ca3057a9f886932533c6f815` | CD `NFS_DOS.EXE` = clean install `NFS.EXE` | English and German installs use the same EXE; language comes from `NFS.CFG` |
| `86f80829727fd311387a69c55613a3332de4a2df27a350502d9bce1d1011df6a` | an installed copy seen in the wild | differs in one byte: file 0x607e6 (code 0x341e6, video player mode set) `push 0` → `push 8`. Origin unknown. All in-game testing so far used this variant. |

Both are 1,254,591 bytes. Other releases (other languages, re-releases) are untested and
should be refused by the patcher.

## Layout

- DOS stub + **LE** executable (DOS4GW). LE header at file offset `0x2c80`.
- Object 1 (code): vaddr `0x10000`; file offset = `0x3c600 + v - 0x10000` (`le.cfo`).
  Slack at the end of obj1: `0xba9fd..0xbb000` (0x603 bytes, zero, currently unused).
- Object 4 (data): vaddr `0xE0000 + raw`; file offset = `0xE9600 + v - 0xE0000` (`le.dfo`).
  Virtual size `0x89a10`; the initial stack top equals it. Zero-initialised memory can be
  appended above it (`exe.add_obj4_block`).
- At runtime code is loaded at `v + 0x1E9000` (useful with the DOSBox-X debugger).
- Compiler: Watcom C/C++32 (1995). Sound library build string: `Mar 07 1996`.

### Fixups

Absolute references go through LE fixup records. **Never patch bytes that are fixup targets
or sources** — `exe.build` asserts against the fixup source set. To move a table, retarget
its fixups with `exe.relocate_target(d, old_obj4_offset, new_obj4_offset)`. Only 32-bit
target offsets can be retargeted; 16-bit ones (e.g. the detail table `0xd284`) cannot.

## Patch catalogue (`exe.build`)

Values in the left column are code vaddrs unless marked *data*.

### Resolution and video mode

| Site | Change |
|---|---|
| `0x5b9c1/0x5b9c6`, `0x2e9bc/0x2e9c1` | race mode width/height → W/H |
| `0x5ba5a` | `75 4a` → `nop nop` (accept the new mode) |
| *data* `0xf7d68 + 16*10` | VESA mode table: unused 1280×1024×15 entry → W×H×8, mode `0x22B` (1280 build only; 1024 uses the stock `0x105` entry) |
| `0x58082/0x580d6`, `0x58087/0x580db`, `0x5806d`, `0x580af`, `0x56ced`, `0x56d63` | pause menu / video mode switch back to 640×480 and restore |
| `0x1af80`, `0x1bfb4`, `0x3cf7a`, `0x3e2cc` | `je` → `nop nop`: menus/videos always switch mode |
| `0x49bd0` | `jle` → `jl` (4 KB table bound) |
| `0x2f9b0`, `0x2fac6`, `0x308d2` | `add reg,8` → `xor reg,8`: three tile loops that indexed a 640-wide table |
| `0x92ed3` | memory pool request 16 MB → 48 MB (`0x3000000`) |

The bank switch routine (`0x9d7f8`) honours the card's window granularity (`[0x1990c]`), so
real VESA cards with 4 KB granularity are fine.

### Screen layout (via `layout.L`)

The HUD keeps its original pixel size and is spread over the wider screen using the 1024×768
reference layout scaled to W×H. `L.SX = W/640`, `L.SY = (H-32)/448`, `L.DXR = W-640`,
`L.DY = H-480`; `L.my(y)` maps a 480-line cockpit y to the stretched cockpit.

| Site | Meaning |
|---|---|
| `0x2d913…0x2da3e` | acceleration display (F8) groups, `+k*DXR/4` |
| `0x2dd47`, `0x2dd99` | start-light step `×SX` |
| `0x2f8ef`, `0x2f90b`, `0x2f905`, `0x31619`, `0x31bc5`, `0x300e6`, `0x2fa19`, `0x3160e`, `0x31bbb`, `0x300dc` | map and gear strip anchored bottom-right |
| `0x2fdd9…0x2fdf8` | cockpit digital speedometer |
| `0x2d345`, `0x2d37a` | cockpit bottom strip / exterior frame height |
| `0x30ea3…0x30fa7` | HUD bar value positions (group deltas) |
| `0x3194b/0x31967`, `0x31950/0x3196c` | HUD clear rectangle |
| `0x5e505…0x5ff07`, `0x7f483…` | replay bar: 1×, bottom anchored; `0x5fd11` forces the full redraw path |
| `0x67018`, `0x67044`, `0x66ba9…0x66bff` | opponent markers above cars `×SX` |
| *data* `0xe8868`, `0xe88e0` | view records (viewport/buffer rectangles) |
| *data* `0xe8c80`, `0xe8cb4` | view configs |
| *data* `0xe8edc + 12*i` | per-car cockpit render heights → `L.my` |
| `0x4b0ec…0x4b1fa` | cockpit horizon quad x-guard ±1280 → ±2W (otherwise black/smeared area on the right) |

### Above 768 lines (1280×960 build)

- Column table `0x4df40` (one entry per screen column, room for 1024) is moved to a new
  obj4 block behind an enlarged stack (`grow_obj4_and_move_column_table`).
- Three polygon fillers (`0x90b30`, `0x91360`, `0xb5b50`) keep six per-scanline arrays of 768
  dwords on the stack (`esp + k*0xc00`). `stackfix.SITES` lists all 459 displacement fields;
  `stackfix.remap` rewrites them for 1024 rows. The table was generated with capstone
  (`stackfix.regen`) and is checked against the original bytes at patch time.
- Edge-table builders `0xa7814/0xa7964/0xa797a/0xa7a24`: `cmp ebx,0x300` → rows.
- Resolutions above 1024 lines would need these limits raised further.

### Asset names

Patched one letter so new files sit next to the originals:

| Site (*data*) | Original → new |
|---|---|
| `0xe0d75, 0xe0dd9, 0xe0e43…0xe0eb9` | cockpit `DH` → `D<tag>`, tickets/warnings `..H` → `..<tag>` |
| `0xe3651, 0xe3669, 0xe36ab` | `maskhi` → `maskh<tag>` (HUD FSH, blit lists) |
| `0xe368b` | `MASKHI.mmb` → `MASKH<tag>.mmb` |
| `0xe2974`, `0xe4454` | `title.qfs` → `titlee.qfs` (title screen with credit line) |

Tags: `J` = 1024×768, `K` = 1280×960.

### Optional: keyboard steering (`steer`)

`0x483e4` builds the digital steering angle towards ±0x1b0000. The step is the car's PBS value
at `+0x300` (4 for every car) × a speed factor. `steer=2` replaces the three loads
(`0x4840b`, `0x4841d`, `0x48425`) with `mov edi, 4*steer`. 2× was chosen in testing; 3×/4× scrub
too much speed in corners.

### Optional: car level of detail (`lod`)

`0x66d08` compares the car's view depth `[car+0x399]` with `0x1900` (ahead → low-poly),
`0xa00` (behind → low-poly), `0x2100` (behind → cull). Immediates at `0x66d5e`, `0x66d6a`,
`0x66d82` are multiplied by `lod` (release: 2).

### Optional: car visibility (`segs`, `cardepth`)

Cars ahead are only processed within 35 track segments (`cmp …,0x23` at `0x6839f`) and a
flag table `0x6e5d0[35]` that is directly followed by another table. `car_draw_segments` moves
the table to a new 0x80-byte block (fixups at `0x678ab`, `0x67916`, `0x6792a`, `0x683a1`), raises
the limit (release: 80) and replaces the global depth cull `0x5a00` (`0x66d26`; release:
`0x7fff0000` = off). Behind stays at 11 segments (`0x6e5c5`). The rear-view mirror is unchanged.

### Optional: track draw distance and detail (`draw`, `near`, `detail`)

- Draw distance `[0x56618]` is set from the immediate at `0x4f04e` (28 blocks). Max 32: the
  detail table has 32 entries per track type.
- Textured near zone: `cmp`/`mov` at `0x5a502`/`0x5a506` (4 blocks; release: 12).
- Detail table *data* `0xd284`: 8 track types × 32 dwords, original pattern hi×3, med, lo…;
  **entries 28..31 must stay 0** (crash otherwise). Walls and roadside objects only exist in the
  hi/med variants. `detail=6` → 5 hi + 1 med. Readers at `0x4f73f`, `0x4f851` (`shl 7`).
- Track vertex buffers `0x57434` (12 B), `0x58c58` (12 B), `0x5a47c` (8 B), 515 entries each, no
  overflow checks → moved to a new block with 4× capacity (`grow_track_vertex_buffers`).
- Scenery object window cap `0xb4` (180) at `0x597ee` → 440. Above the cap the engine drops
  *all* objects; the object vertex arrays hold 450 objects.
- An FPS-based auto-detail mechanism exists but is never enabled.

### Optional: traffic window (`traffic`)

`0x77f98`, per player segment s: spawn at `s + front + rand(0..10)` (front imm8 `0x77fb9`, 43),
inner rear `s - 12` (`0x77fbc`), outer front `+11` (`0x7808b`), outer rear `-8` (`0x7809f`).
Release: front 50, inner rear 6, outer rear 13 → recycled 19 behind. The police car is placed
at s−12/s−18, so the rear limit must stay ≥ 19. Six traffic cars (`0x36dd9 mov ecx,6`), only on
open-road tracks (`[0x4da12] ≤ 2`).

## Rejected / failed experiments

| Idea | Result |
|---|---|
| Draw distance > 32 via a code cave that builds a 64-entry detail table at track load and rewrites the 16-bit-fixup readers (`extend_detail_table`, still in the source, disabled) | crashed mid-race |
| Walls/objects detail 8 | stray grass polygons |
| Detail 9 / 12 | crash at race start (divide by zero at `0x83cdb`) |
| Traffic front +30 | visible pop-ins |
| Traffic rear −11 | police car never appears (placed at −12/−18) |
| More than 6 traffic cars | three car lists have only 9 slots (`0x5c224` draw, `0x5c274` rank, `0x5c298` order; `0x5c24c` has 10) — too risky |
| Larger horizon artwork | overflows an internal limit |
| Runtime cockpit scaling, in-game resolution menu | not pursued |
| AI-upscaled cockpit art | dropped for licensing/consistency; Lanczos from the original art only |

## Tools

- `le.dis(a, b)` / `python3 nfsse/le.py 2d5dc:2d6b4` — disassembly (needs capstone, dev only).
- `emu.py` — Unicorn harness that flat-loads the EXE with fixups applied and calls pure routines
  (dev only). Data globals are at `0xE0000 + raw` in emulation.
