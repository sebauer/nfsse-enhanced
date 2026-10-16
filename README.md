# NFS SE Enhanced

Unofficial high-resolution patch for **The Need for Speed Special Edition** (DOS, 1996).
Races run in **1024×768** or **1280×960** instead of 640×480, with an adapted HUD, rescaled
cockpits, optional faster keyboard steering, longer view distance and a tuned traffic window.

> Not affiliated with or endorsed by Electronic Arts. "Need for Speed" is a trademark of
> Electronic Arts. This repository contains **no game files**: all graphics are generated
> from the user's own installation.

**Status: v0.9 in development.** The generators are complete and verified; the end-user
patcher (`patcher.py`, later also a browser version) is the next step.

## How it works

The patch never ships EA data. A generator reads the user's own files and writes new ones
next to them (the originals stay untouched):

| Module | Input (user's installation) | Output |
|---|---|---|
| `nfsse/exe.py` | `NFS.EXE` | `NFS1024.EXE`, `NFS1280.EXE` |
| `nfsse/hud.py` | `SIMDATA/MISC/MASKHI(G).FSH` | `MASKHJ/K(G).FSH` |
| `nfsse/masks.py` | `SIMDATA/MISC/MASKHI.B00-B23, .MMB` | `MASKHJ/K.*` |
| `nfsse/cockpit.py` | `SIMDATA/(G)DASH/*DH.FSH/FMM` | `*DJ/DK.FSH/FMM` |
| `nfsse/tickets.py` | `SIMDATA/MISC/TICKET*/WARN*H.QFS` | `…J/K.QFS` |
| `nfsse/title.py` | `FRONTEND/(G)ART/TITLE.QFS` + game font | `TITLEE.QFS` |

Helpers: `fsh.py` (FSH archives), `qfs.py` (RefPack), `huff.py` (EA Huffman), `ffn.py`
(fonts), `layout.py`, `le.py` (LE executable/fixups), `stackfix.py`.

Runtime dependencies: Python 3, numpy, Pillow, scipy. `capstone` and `unicorn` are only used
by the analysis helpers (`le.dis`, `emu.py`, `stackfix.regen`).

## Requirements for players

- The **DOS** version, English or German, installed **completely** (setup → *Custom* → all
  components). The Windows 95 version is not supported.
- DOSBox-X (`memsize = 64` for 1280×960, plus the VESA settings in the user README).

See [`docs/USER_README.txt`](docs/USER_README.txt) for the full player documentation.

## Documentation

- [`docs/EXE.md`](docs/EXE.md) — executable layout, every patch site, rejected experiments
- [`docs/FORMATS.md`](docs/FORMATS.md) — FSH, QFS, Huffman, BAMF, FNTF, directory layout

## License

MIT (see `LICENSE`) for the code in this repository.
