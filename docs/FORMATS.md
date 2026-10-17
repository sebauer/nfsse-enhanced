# File formats

All formats below are handled by modules in `nfsse/`. Multi-byte values are little-endian
unless noted.

## FSH shape archive (`fsh.py`)

`SHPI` header: total size (u32 @4), entry count (u32 @8), directory id (4 bytes @12), then
`count × (name[4], offset u32)`. Each shape block starts with a 16-byte header:
`type u8, next u24 (offset of the next attachment, 0 = none), w, h, cx, cy, x, y (i16 each)`.

- Type `0x7b`: 8-bit indexed pixels, `w*h` bytes. Index 255 = transparent.
- Type `0x7a`: 4-bit pixels, two per byte, high nibble first (used by FFN font atlases).
- Attachments are chained via `next`: `0x22` palette (6-bit VGA, 768 bytes after a 16-byte
  header), `0x24` palette (8-bit), `0x7c` point list (`count u32 @4`, `count × (x i32, y i32)`).
- Global palettes are shapes named `!pal`.

`fsh.rebuild(d, {name: new_block})` rewrites an archive with replaced blocks.

### Cockpit archives (`SIMDATA/(G)DASH/<car>DH.FSH`)

The full-screen shape `dash` (640×480 at 0,0) carries a `0x7c` point list in 640×480 screen
coordinates. Points 0 and 1 are the **rear-view mirror rectangle**: top-left `(x0, y0)` and
bottom-right `(x1, y1)`, both **inclusive** (e.g. Corvette: `(546, 78)`–`(639, 120)`). The engine
renders the mirror view into this rectangle at runtime, so the mirror needs no EXE patch, and the
cockpit window mask (`<car>DH.FMM`) leaves it out. When scaling, the inclusive corner must map as
`round((x1 + 1) · SX) − 1` (and likewise for y via `L.my(y1 + 1) − 1`); scaling it like a plain
point makes the mirror view one pixel too small and it looks shifted up and left against its frame.
The remaining points sit near the top edge (e.g. `y ≈ 46` for the Corvette); their purpose is
not confirmed (probably positions of small indicator overlays).

## Track texture families (`*TRACKFM/*.FAM`)

`SIMDATA/NTRACKFM/<track>_{T,M,R}01.FAM` and `SIMDATA/ETRACKFM/<track>_001.FAM` (German:
`GTRACKFM`). A FAM is a `wwww` container (count u32, then absolute u32 offsets; entries follow each
other without padding) with four parts:

| Part | Content |
|---|---|
| 0 | `wwww` of FSH: road, terrain, wall, fence textures (80×40, 80×80, 32×96, 128×256, 179×89, ...) |
| 1 | `wwww` of FSH, one per roadside object: one `0x7b` shape `0000`, at most 128×128 |
| 2 | FSH with `!pal` (`0x22`) and `horz`, the horizon (640×110 or 640×130) |
| 3 | `wwww` with a small 3D object (`ORIP`) and its textures |

The `T`/`M`/`R` variants differ in colours; `ETRACKFM` is close to `R` except for some signs.
Object sprites use index 255 as transparent. Their palette is found in one of three places: a
`0x22` attachment behind the shape, listed `!pal`/`!PAL` shapes (`0x24`), or an unlisted `0x22`
block between the directory and the first shape.

Findings from an experiment with Coastal 1 (2× sprites, not part of the patch):

- **Every object FSH is a multiple of 4 bytes long**; the originals pad with a few bytes behind the
  directory. An unaligned FSH makes the game abort at race start with
  `reservemem - INVALID SIZE REQUESTED`.
- The engine sizes an object by its size in the world, not by its pixels: a sprite with twice the
  resolution is drawn at the same size.
- **Sprites larger than 128 pixels** in either dimension freeze the game at race start (black
  screen). DOSBox-X then logs `voodoo readd unaligned` endlessly: the game reads through a broken
  pointer into the address range of DOSBox-X's emulated Voodoo card. The limit sits somewhere in
  the object texture path of the EXE; a memory breakpoint on that range in the DOSBox-X debugger
  should find it.
- Within the limit there is little to gain: the objects that can grow are mostly seen from far
  away, while the blocky ones that come close are already 127–128 pixels tall.

## QFS / RefPack (`qfs.py`)

EA's LZ77 variant. Header `10 FB` (or `11 FB` with an extra 3-byte compressed size), then the
uncompressed size as a **big-endian u24**. Control codes: `0x00-0x7F` short copy, `0x80-0xBF`
medium, `0xC0-0xDF` long, `0xE0-0xFB` literal run (4..112 bytes), `0xFC-0xFF` end + 0..3
literals. `qfs.pack` is a greedy hash-chain encoder; `qfs.decode` dispatches on the header.

## EA Huffman (`huff.py`)

Types `30 FB` (plain), `31 FB` (+3-byte compressed size), `32 FB` (byte delta), `34 FB`
(double delta). Independent implementation, verified byte-identical against the game's decoder 
on all 33 Huffman files of the game. Structure: u24 BE size, clue byte (escape symbol), canonical
code-length counts and symbols (delta coded with a "used" bitmap), all integers in the game's
Elias-gamma-like `getnum`. The clue symbol introduces a run (`getnum` > 0: repeat last byte),
a literal byte (`0` + bit 0) or end of stream (`0` + bit 1). Note the decoder quirk for numbers
whose prefix has ≥ 16 zero bits (one extra value bit), kept for compatibility.

## BAMF blit lists (`masks.py`)

After rendering, the game copies the frame to banked VESA memory using precomputed lists:

```
'BAMF', size u32, banks u16, max_len u16, xstep u32 (16.16), ystep u32 (16.16),
per bank: count u16, count × (src u32, dst u16 (offset in 64K bank), len u16)
```

Lists with `xstep = 0x8000` are the half-resolution detail modes. Uncovered areas are holes
where the game draws directly to video memory (tachometer, map). Files:

- `SIMDATA/MISC/MASKHI.Bvp`: exterior views (v = view size 0..2, p = detail 0..3).
- `SIMDATA/MISC/MASKHI.MMB` and `SIMDATA/(G)DASH/<car>DH.FMM`: containers (`'wwww'`, count,
  offset table) of BAMF lists for the cockpit view; the cockpit window mask per car.

`masks.convert` re-pitches a 640-wide list to W (splitting at row ends and 64K banks);
`masks.build_list` builds a list from a predicate.

## FNTF fonts (`ffn.py`)

`'FNTF', size u32, version u16 (100), glyph count u16 @10, …, atlas offset u32 @0x1c`.
Glyph table at `0x20`, 11 bytes each: `code u16, w u8, h u8, x u16, y u16 (atlas position),
advance u8, x-offset i8, y-offset u8`. The atlas is an FSH shape of type `0x7a` (4-bit
coverage). `FRONTEND/(G)ART/FONTS/GRAVER18.FFN` is the small-caps font of the title credits.

## PBS car specs

`SIMDATA/CARSPECS/*.PBS` on the CD (Huffman/RefPack packed). Offset `0x300` = keyboard steering
base step (4 for every car).

## Directory layout by language

The EXE has two path sets, chosen by the language in `NFS.CFG`:

| English | German |
|---|---|
| `FRONTEND/ART`, `SHOW`, `SPEECH` | `FRONTEND/GART`, `GSHOW`, `GSPEECH` |
| `SIMDATA/DASH`, `SLIDES`, `ETRACKFM` | `SIMDATA/GDASH`, `GSLIDES`, `GTRACKFM` |

`SIMDATA/MISC` is shared; German variants there use a `G` prefix/suffix (`MASKHIG.FSH`,
`TICKEG*`, `GWARN*`). German cockpit art differs from the English one.
