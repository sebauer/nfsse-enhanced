# NFS.EXE internals and patch catalogue

Reference for the DOS executable of *The Need for Speed Special Edition* (English/German
release, `NFS_DOS.EXE` on the CD, dated 1996-06-19) and for every change `nfsse/exe.py` makes.

## Supported input executables

| SHA-256 | Source | Note |
|---|---|---|
| `7d2104a9eae01ca7b74807ab66334e3ce806d7a9ca3057a9f886932533c6f815` | CD `NFS_DOS.EXE` = clean install `NFS.EXE` | English and German installs use the same EXE; language comes from `NFS.CFG` |
| `86f80829727fd311387a69c55613a3332de4a2df27a350502d9bce1d1011df6a` | an installed copy seen in the wild | differs in one byte: file 0x607e6 (code 0x341e6, video player mode set) `push 0` → `push 8`. Origin unknown. All in-game testing so far used this variant. |

Both are 1,254,591 bytes. Other releases (other languages, re-releases) are untested and
are refused by the patcher.

The differing byte is the third argument of the mode-set call `0x84d74(w, h, bpp)` in the video
player `0x341a4` (320×200). `bpp = 0` means the default, 16 bpp (`0x84df1`), so the CD EXE asks for
320×200 hicolor; the 86f8 variant asks for 320×200×8, presumably a fix for cards without a
320×200×16 mode. `patcher.py` sets this byte on the CD EXE before patching, so both variants
produce byte-identical (tested) executables.

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
or sources**: `exe.build` asserts against the fixup source set. To move a table, retarget
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
reference layout scaled to W×H. `L.SX = W/640`, `L.DXR = W-640`, `L.DY = H-480`. The cockpit
(rows 32..479 of the 640×480 art) is scaled uniformly by `SX` and anchored at the bottom;
`L.my(y) = CY0 + (y-32)·SX` with `CY0 = H - 448·SX` maps a 480-line cockpit y. The rows between the
HUD bar and the cockpit (32 at 1280×960, 19 at 1024×768) are filled by `cockpit.fill_top`: a dark
neutral band, a fade to the desaturated average colour of the cockpit's first row, a fade into
that row. Up to v0.9 the cockpit was stretched to rows 32..H-1 instead (`L(W, H, uniform=False)`,
vertical scale `(H-32)/448`, about 3.6 % taller than wide at 1280×960).

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
| (none) | rear-view mirror: its viewport comes from the cockpit's `dash` point list, not from the EXE; see `docs/FORMATS.md` (cockpit archives) |
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

- Draw distance `[0x56618]`: originally 28 blocks, release 44. It is set at track load
  (immediate at `0x4f04e`) and **again at race start** (`0x5bbd3`) from the setting `[0x4d9d5]`:
  0 → 28 (immediate at `0x5bbe9`), 1 → 18, 2 → 13, via the pending value `[0x16b48]`. The F key
  (`0x480f2`) cycles the setting and sets 28/14/9 through `0x5b19c`, as does `0x633d2` (function
  `0x63304`). The options menu and the saved configuration use the same three-valued setting. In the
  patch the stages are 44 / 28 / 14 (key, `0x633d2`) and 44 / 28 / 18 (race start): immediates `0x48121`,
  `0x4812d`, `0x48139`, `0x633e2`, `0x633f8`, `0x63412`, `0x5bbe9`, `0x5bbfa`, `0x5bc0b`. In v0.9
  `draw=32` only patched the track-load site and therefore had no effect.
  See "Draw distance above 28" below.
- Textured near zone: `cmp`/`mov` at `0x5a502`/`0x5a506` (4 blocks; release: 12).
- Detail table *data* `0xd284`: 8 track types × 32 dwords, original pattern hi×3, med, lo…;
  entries 28..31 are 0 (see "Draw distance above 28"). Walls and roadside objects only exist in the
  hi/med variants. `detail=6` → 5 hi + 1 med. Readers at `0x4f73f`, `0x4f851` (`shl 7`).
- Track vertex buffers `0x57434` (12 B), `0x58c58` (12 B), `0x5a47c` (8 B), 515 entries each, no
  overflow checks → moved to a new block with 4× capacity (`grow_track_vertex_buffers`).
- Scenery object window cap `0xb4` (180) at `0x597ee` → 440. Above the cap the engine drops
  *all* objects. The object vertex arrays hold 900 vertices; emulation counts about 4 per object, so
  roughly 225 objects (not 450 as assumed when 440 was chosen). See the maxima below.
- An FPS-based adjustment (`0x5b0cc`, `0x5b17c`) exists, but its flag `[0x622dc]` is only ever cleared
  (single caller of `0x5b128`). `0x5b19c`, inside it, is also the entry used by the F key; limits 8..28.

### Optional: traffic window (`traffic`)

`0x77f98`, per player segment s: spawn at `s + front + rand(0..10)` (front imm8 `0x77fb9`, 43),
inner rear `s - 12` (`0x77fbc`), outer front `+11` (`0x7808b`), outer rear `-8` (`0x7809f`).
Release: front 50, inner rear 6, outer rear 13 → recycled 19 behind. The police car is placed
at s−12/s−18, so the rear limit must stay ≥ 19. Originally six traffic cars (`0x36dd9`, imm of `mov ecx,6`), only on
open-road tracks (`[0x4da12] ≤ 2`). Of the six, four are on the road at a time. Release:
`traffic_cars=7`, `traffic_active=7`, see "Car slots".

### Car slots

Read from the code (86f8) and checked with the Unicorn harness where noted. `traffic_cars=7`, `traffic_active=7`
are release options of the extended view and tested in game: noticeably more traffic (impression, not counted), new
replays work, loading an old replay crashes. Network games are untested. Addresses are *data* unless marked otherwise. Cars in an open-road race against one opponent: player (0),
opponent (1), police (always 2, pointer `0x5c254`), traffic from 3 on. Counts: `[0x4da30]` humans, `[0x4da2c]`
racers, `[0x4da34]` police, `[0x4da3c]` traffic, `[0x4da38]` total = racers + police + traffic (computed at code
`0x496f7` / `0x499a8` through a pointer to the race description `0x4da0c`, 0x348 bytes, which is also what a network
game sends and a replay file stores). The loops over the cars use the total, not a constant. Cars themselves are
heap blocks of 0x79a bytes (`0x513b1`); the car number is at `+0x516` and `+0x47d`.

**How many traffic cars are on the road.** Six slots exist (`0x36dd9`), but `[0x7d2f0]` = 4 limits how many are
active: a car that leaves the traffic window gets state 6 (`+0x512`), a random delay and `[0x7d480]` (cars waiting)
is incremented (code `0x7cef5`); when the delay ends it only returns if `traffic - [0x7d2f0] < [0x7d480]` (code
`0x7e1ad`), so once two cars are waiting, two of the six stay parked and four drive. The 4 is the default written by `0x63f50` (immediate at
code `0x63fb1`, `mov [eax+0x34],4`; the struct is `0x7d2bc`). The parser for a `traffic.cfg` (code `0x7e20c`) that
would overwrite it is never called and the file does not exist.

**The engine is laid out for 10 cars**, one more than it uses: per-car palette ranges `0x16ea0` / `0x16ec8` /
`0x16ef0` (10 entries; car 9 = colours `0x90..0x97`), shape pointers `0x693a4` (10), the tables copied by code
`0x80ab0` / `0x80ad4` (10), `0x17798` (11), and a replay key frame has room for 2 x 10 list entries. Everything
else that is indexed by car number or list position has 9 slots:

| Table | Slots | Fixups | Behind it | `traffic_cars=7` |
|---|---|---|---|---|
| `0x5c224` drawn cars (count `[0x5c220]`) | 9 | 3 | `0x5c248`, a car pointer | moved, 16 slots |
| `0x5c24c` car pointers | 9 | 193, plus `0x5c250`..`0x5c268` addressed one by one | `0x5c270`, pointer to car 1 | grows in place over `0x5c270` |
| `0x5c270` pointer to car 1; also rank - 4 (code `0x51ea2`, `0x5d3af`) | | 6 | | moved, stays 4 bytes below the rank list |
| `0x5c274` rank (with `0x5c26c` = rank - 8, `0x5c278`, word `0x5c290`) | 9 | 13 | `0x5c298` | moved, 16 slots |
| `0x5c298` order (with `0x5c294` = order - 4, `0x5c29c`) | 9 | 20 | `0x5c2bc`, unrelated | moved, 16 slots |
| `0x4dce4` car models (inside the race description) | 9 | 14 | `0x4dd08` "police present", 14 fixups | `0x4dd08` moved, list grows in place |
| `0x6e5bc` bytes, palette entry per car | 9 | 10 | `0x6e5c5`, flags cleared every frame | moved |
| `0x4bd33` bytes, position per car (code `0x2e440`) | 9 | 2 | `0x4bd3c` | moved |
| records of 0x1d2 bytes from `0x6ea80` (times, position at `+0x1ca`); `0x6ea74`..`0x6ea7c` in front are variables *and* biased bases | 9 | 99 in `0x6ea74`..`0x6fadf`, 22 targets | `0x6fae2` (the fixup to `0x6fae0` is `word 0x6fae2` read as a dword) | moved as one range, 10 records |
| replay key frame (162 bytes, 20 from `0x63eec`): order at +0, rank at +0x24, next field at +0x50 | 9 + 9 | `0x63f10` reader, `0x63f0c` writer (base - 4) | | rank at +0x28 |
| replay key frame, cars that are not human: 8 x 0x172 bytes per key frame (stride `0xb90`, code `0x5d07c`, `0x5d28a`), 16 key frames, buffer `[0x16b98]` 0x15e00 bytes (code `0x5ddcb`, saved/loaded at `0x5c443` / `0x5c562`) | 8 | none | end of the heap block | stride `0xd02`, buffer 0x17520 |
| stack of code `0x7a040` (traffic AI): lane masks, one per list position, at `[esp]`, 8 lane counters at `[esp+0x24]`; the masks are read by `0x78c88` | 9 | none | the counters | frame 0x9c -> 0xc4, masks at `[esp+0x9c]` |
| `0x7d490` AI data pointers (cleared for every car at code `0x7dec5`) | 9 | 9, base - 4 mixed with the variable `0x7d48c` | `0x7d4b4`, written once before that loop and never read | left alone: the tenth zero lands on `0x7d4b4` |
| `0x693a4`, `0x16ea0`, `0x16ec8`, `0x16ef0`, `0x17798`, tables in `0x80ab0` / `0x80ad4` | 10 or 11 | | | fit |

Only indexed by racers or humans (at most 8), so not affected: participants `0x4da48 + 0x4b*i`, `0x4dca0`, `0x4dcc0`,
`0x5c194` (9, constant loop), `0x4d950`, the dots of the track map `0x5d5e8`, result records `0x7cb68 + 0x95*i`,
the replay data of human cars. Traffic cars read past some of them (`0x4da53 + 0x4b*i` at code `0x51290`), which
they already do today; nothing is written there.

`exe.more_traffic` (build option `traffic_cars`, 6 = off, 7 = maximum) makes the changes in the last column and sets
the count at `0x36dd9`. All moves are fixup retargets (169 fixups, 36 targets) into two new obj4 blocks; code
changes: `0x36dd9`, `0x5c444`, `0x5c563`, `0x5d07e`, `0x5d28c`, `0x5ddcc`, `0x7a048`, `0x7aeab` (immediates),
`0x7a0bb`..`0x7a0d5` (the loop offset `edx` starts at 0x9c instead of 0) and `0x7abda`..`0x7abf4` (argument set-up
for `0x78c88`, rewritten shorter with the mask pointer `esp+0x9c`). `traffic_active` (4 = off) patches `0x63fb1`
and works without `traffic_cars` too: `traffic_active=6` alone is a one-byte change.

Emulated with the built EXE and 10 cars: list sort `0x518c0`, key frame snapshot and restore (frames 0, 15, 19),
the position loop `0x2e40e`, model selection `0x653a4` (7 different traffic models out of 12), the per-car replay
record `0x5d0e4` (last byte written = buffer size), the first loop of `0x7a040` (masks and counters separate, saved
registers intact). No fixup is left that points into a vacated range.

Known consequences and open points:

- Replay files and network games are not compatible between an EXE with `traffic_cars=7` and any other: the key
  frame layout, the replay buffer size and the car count differ. Loading an old replay crashes (tested). Network games are
  untested. "Police present" (`0x4dd08`) is no longer part of
  the race description, so a replay loaded from a file takes it from the last race of the session.
- Not analysed in the code beyond the tables above: limits inside the renderer (polygons, sprites, shadows for one more car),
  per-car sound, memory for the tenth car model, the palette range `0x90..0x97` on every track.
- Car 9 is released by the start logic a little later than car 8 (code `0x7e19d`: leading racer past segment
  `16*n + 15`).

### Track rendering internals

Read from the code unless marked otherwise. A block is 4 track segments. Addresses in brackets are *data*.

**Per frame** (around `0x5bd00`..`0x5bf31`):

| Step | Function |
|---|---|
| apply a pending draw distance (`[0x16b48]`, -1 = none) and invalidate the block list | `0x5bcf5`, `0x5004c` (sets `[0x56610]` and `[0x56614]` to -1) |
| load blocks around the car; requeue if the car's block changed or the list is invalid | `0x50070` (calls `0x4ee30`, then `0x4ffbc`) |
| queue `draw + 1` blocks: `draw - 1` with 4 rows, one more with 4 rows, one with a single row | `0x4ffbc` → `0x4f7d4` per block |
| transform the queued vertices; copy them to `0x62578` and clamp the near ones | `0x59a74` (copy at `0x59b76`) |
| draw: far, flat blocks from the back to the near zone, then the textured near zone | `0x5a4f0`, far part `0x59d3c` |

The detail index of a block is its distance from the car, so `0x4f7d4` also reads entry `draw` of the
detail table (index 28 at the stock distance).

**Data:**

| Address | Content |
|---|---|
| `[0x57430]` | segment table, 36 bytes per segment; byte +7 of a block's first segment = track type (row of the detail table) |
| `[0x5bb88]`, `[0x5bb90]` | masks for segment and block numbers |
| `[0x565e8]` | decoded block ring: 64 slots of 540 bytes = 12-byte header + 4 rows of 11 vertices of 12 bytes; slot = block mod 64 |
| `[0x565ec]`, `[0x565f8]`, `[0x565f4]` | streaming state; blocks ahead (30); that + 5 |
| `0x56604`, `0x56608` | pointers to the packed track data and its block table (per-block offsets from +0x2c; loader at `0x4edbe`) |
| `[0x5bb74]` / `[0x5bb78]` | write index / total of the queued track vertices |
| `0x56620` | 6 bytes per block: detail value u8 (+0), first vertex u16 (+2), vertex count u16 (+4); written at `0x4fe94` |
| `[0x565c4]`, `[0x565c0]` | scenery object vertex and object counters (buffers `0x4f540`/`0x51f70`/`0x549a0`) |
| `0x60cd8` | texture pointers, indexed by the ids in the block headers (header use: from emulation) |
| `0x61ed8` | 256 pointers, read only (looks like a per-vertex buffer, but is not) |
| `[0x63df4]` | current view object; first dword = field of view, halved and passed to `0x83c5b` |

**Detail structures:** the values of the detail table (*data* `0xd284`) index 76-byte structures at `0x161d4`,
three per track type: hi/med/lo = 5/6/7 (type 0), 13/14/15 (1), 8/9/10 (2), 0/1/2 (3 and 6), 4/11/12 (4 and 5),
16/17/18 (7). They start with one list of vertex indices per row, each ended by `0xff`. Low detail has 11 vertices
per block, high detail 36 (types 4, 5 and 7: 44).

Track vertices per frame, counted from these lists (515 fit into the original buffers):

| Stock, 28 blocks | `detail=6`, 28 blocks | `detail=6`, 32 blocks, entries 28..31 = 0 |
|---|---|---|
| 403..427 | 453..493 | 597..637 |

### Draw distance above 28 (`draw` > 28, `exe.far_track`)

Why raising `[0x56618]` alone fails (static reading, confirmed with the Unicorn harness on the real track files):

1. **Streaming window.** Track blocks are decoded into a ring of 64 slots (`[0x565e8]`, 540 bytes each) by
   `0x4ee30`; `[0x565f8]` = 30 (immediate at `0x4f0f5`) blocks ahead of the car and `[0x565f4]` = that + 5 behind
   are kept loaded, i.e. blocks car-5..car+29. `0x4ffbc` queues blocks car..car+draw, so from `draw` = 30 on the
   farthest blocks are stale ring slots: uninitialised memory at race start (bad texture ids in the block header
   -> `convertshapedepth`), later the block 64 before (stretched polygons).
2. **11 vertices per far block.** `0x5a52e` (and `0x5a0b7`) compute the first vertex of the textured near zone as
   `total - 11 - (draw - near) * 11`. Detail entries 28..31 are 0 = structure 0, the 36-vertex high-detail
   variant of types 3/6; at `draw` = 29 block 28 gets it and the near zone reads 25 vertices too far (broken
   polygons close to the camera). At 28 only its first row (11 vertices in every structure) is used.
3. **View vertex copy** `0x62578`: 515 entries, followed by the camera globals; more vertices overwrite them
   (divide by zero at `0x83cdb`).
4. **Other setters.** The F key (`0x48120`) and a second routine (`0x633e1`, in function `0x63304`) set the
   distance for setting 0 through `0x5b19c` with their own immediate 28. Earlier test builds did not patch them;
   "clean after the first pause menu" most likely meant: back at 28 (which of the two runs after the pause menu
   was not traced).
5. Texture level by block distance: table `0x14708` has 32 entries (readers `0x59d76`, `0x5a068`).

Symptoms seen in the game while the causes were unknown (Coastal 1, 1280×960), useful for recognising them:

| Build | Result | Matches |
|---|---|---|
| 29 blocks | starts, huge stretched terrain near the camera until the first pause menu | 2, 4 |
| 30 and 32 blocks | divide by zero at `0x83cdb` (view object overwritten, field of view 0) | 3 |
| 32, entries 28..31 = own low detail | `convertshapedepth - SOURCE SHAPE TYPE UNRECOGNIZED ($20)` | 1 |
| 29, only `0x62578` moved | same as 29 | 2, 4 |
| 32 (both variants), only `0x62578` moved | runs, sometimes broken polygons or `convertshapedepth` ($00, $30) at race start | 1, 2 |

The matches are conclusions from the analysis, the individual crashes were not traced in a debugger.

`far_track(d, draw)` therefore patches: all distance immediates (`0x4f04e`, `0x5bbe9`, `0x48121`, `0x633e2`,
limits `0x5b0d9/dd`, `0x5b19e/1a6`, `0x5b1bd/1c5`); the window `0x4f0f5` = `draw + 2`; the detail reader
`0x4f83e..0x4f855` rewritten in place so that the distance index is clamped to 27 (own-type low detail; no
fixup byte touched); the two texture-level readers (`0x59d67`, `0x5a055`) clamped to index 31; `0x62578` moved
to a new block (4 fixups); the block loader `0x4edf2` returns 0 for a block without the `TRKD` tag instead of
waiting for a key (past the end of an open road).

Limits, `DRAW_MAX` = 44:

- Scenery-object vertex buffers `0x4f540`/`0x51f70`/`0x549a0` hold 900 entries. Maximum over all 17 tracks and
  every car block: 651 at 32 blocks, 795 at 40, 847 at 44, 919 at 48.
- Open roads: the race length is `blocks*4 - 181` segments (`0x63959`), the finish line is 45 blocks before the
  end of the data. With the car at block b the queue needs blocks up to b + draw; behind the finish line the
  farthest blocks do not exist (stale slots are drawn). Stock has 15 blocks of margin there, 44 has none.
- Ring: 64 slots >= 5 + draw + 2. Block offset table: 600 entries (longest track 578 blocks).

Emulated (scratch scripts, not in the repo): the game's own streaming + queueing over every car block of every
track with the built EXEs (no stale slot inside the track, 11 vertices for every block >= 12, counts above) and
its polygon emission `0x5a4f0` with stubbed draw calls: 10 flat polygons per block for every distance 12..draw-1,
texture level 3 from distance 21 on. Nothing in `0x59d3c` limits the distance; the projection `0x94c80`
normalises z. Tested in game with 44 blocks and the stages 44/28/medium.

## Rejected / failed experiments

| Idea | Result |
|---|---|
| Draw distance > 32 via a code cave that builds a 64-entry detail table at track load and rewrites the 16-bit-fixup readers (`extend_detail_table`, still in the source, disabled) | crashed mid-race; superseded by the index clamp in `far_track` |
| Walls/objects detail 8 | stray grass polygons |
| Detail 9 / 12 | crash at race start (divide by zero at `0x83cdb`) |
| Traffic front +30 | visible pop-ins |
| Traffic rear −11 | police car never appears (placed at −12/−18) |
| More than 7 traffic cars | not tried; would need the 10-entry tables and the replay key frame format extended, see "Car slots" |
| Larger horizon artwork | overflows an internal limit |
| Runtime cockpit scaling, in-game resolution menu | not pursued |
| AI-upscaled cockpit art | dropped for licensing/consistency; Lanczos from the original art only |

## Tools

- `le.dis(a, b)` / `python3 nfsse/le.py 2d5dc:2d6b4`: disassembly (needs capstone, dev only).
- `emu.py`: Unicorn harness that flat-loads the EXE with fixups applied and calls pure routines
  (dev only). Data globals are at `0xE0000 + raw` in emulation.
