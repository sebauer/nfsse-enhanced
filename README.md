# NFS SE Enhanced

Unofficial patch for **The Need for Speed Special Edition** (DOS, 1996).

Thirty years after the original, I was tired of barely making out the traffic ahead: without a
proper CRT monitor, 640×480 on a modern screen turns oncoming cars into a few blurry pixels until
it is almost too late. So this is a gently modernised version that stays true to the retro charm
of the original. Races run in **1024×768** or **1280×960** with longer view and draw distances,
cars that appear further ahead, a tuned traffic window and more responsive keyboard steering.
HUD and cockpits are adapted to the new resolution. No new artwork, no remastered textures:
everything is rescaled from the game's own files.

> Not affiliated with or endorsed by Electronic Arts. "Need for Speed" is a trademark of
> Electronic Arts. This repository contains **no game files**: all graphics are generated
> from the user's own installation.

**Status: v0.9.** Generators and the patcher are done; a browser version is planned.

## Installation

Download the zip from the [latest release](https://github.com/sebauer/nfsse-enhanced/releases),
unpack it anywhere and start the launcher. You need **Python 3.9 or newer**.

- **Windows:** double-click `nfsse-patcher.bat` (or drag the game folder onto it).
- **macOS / Linux:** `sh nfsse-patcher.sh` in the unpacked folder.

The first run sets up a private Python environment (`.venv` next to the launcher; numpy, scipy,
Pillow). The patcher then asks for the game folder, resolution(s), keyboard steering and view
distance, writes the new files next to the originals and prints the DOSBox-X settings.
[`docs/USER_README.txt`](docs/USER_README.txt) (`README.txt` in the zip) has the details.

### From source

```
python3 -m pip install -r requirements.txt
python3 patcher.py                                       # asks for everything
python3 patcher.py "<game folder>" -y                    # both resolutions, release options
python3 patcher.py "<game folder>" --res 1280 --steer 1   # 1280x960 only, original steering
python3 patcher.py "<game folder>" --check                # only check the installation
```

Options: `--res 1024 1280`, `--steer 1..4` (keyboard steering factor, default 2),
`--view extended|original` (view distance, car visibility, traffic window; default extended),
`-y` (no questions, defaults for options not given), `--jobs N` (parallel jobs, default half the
CPU cores), `--out DIR` (write elsewhere, for testing). The patcher verifies `NFS.EXE` (both known
variants, see `docs/EXE.md`), checks that the installation is complete, builds cockpits and the
title screen for every installed language and prints the required DOSBox-X settings. Generating
both resolutions takes about 15 s on a 12-core machine (about 70 s with `--jobs 1`).

## Releasing

Set the version in `nfsse/version.py` (it is also stamped on the title screen), commit, tag the
commit `v<version>` and push the tag. The release workflow checks that tag and version match,
smoke-tests the patcher, builds the zip and creates a draft release to review and publish.

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
- DOSBox-X (`memsize = 64` for 1280×960, plus the VESA settings in the user README). The patch
  is tested mainly with DOSBox-X; other DOSBox versions may work but are untested.

See [`docs/USER_README.txt`](docs/USER_README.txt) for the full player documentation.

## Documentation

- [`docs/EXE.md`](docs/EXE.md): executable layout, every patch site, rejected experiments
- [`docs/FORMATS.md`](docs/FORMATS.md): FSH, QFS, Huffman, BAMF, FNTF, directory layout

## Support

If the patch brings back some 1996 racing memories, you can
[buy me a coffee ☕](https://buymeacoffee.com/sebauer). Entirely optional, and thanks for racing! 🏁

## License

MIT (see `LICENSE`) for the code in this repository.
