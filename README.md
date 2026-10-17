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

**Status: v0.9, first release in preparation.**

## ✨ What changes

### 🖥️ Resolution and display

- The race runs in **1024×768** or **1280×960** instead of 640×480, exterior and cockpit view.
  The exterior view uses the whole screen.
- HUD bar, map, tachometer, start lights, acceleration display (F8) and replay bar are laid out
  for the wider screen.
- Cockpits are rescaled from the original artwork, keeping their proportions.
- Ticket and warning screens are upscaled to the full resolution.
- Opponent markers above the cars scale with the resolution.
- The cockpit-view horizon is drawn across the full width. The original engine dropped horizon
  pieces beyond ±1280 pixels, which left a black or smeared area on the right side.
- Pause menu, end-of-race menus, checkpoint menu and videos switch to 640×480 and are shown full
  screen.
- The game's internal memory pool grows from 16 MB to whatever is available (up to 48 MB), which
  the larger graphics need.

### 🎮 Keyboard steering (optional)

With a keyboard, the original builds up the steering angle slowly, especially at high speed, so
correcting mid-corner often ends in the barrier. The default build **doubles** the steering
build-up rate (and the return to centre). Joystick and wheel are not affected.

2× turned out to be the best balance between responsiveness and speed lost to tyre scrub: 3× and
4× feel quicker but scrub off noticeably more speed in corners. Replays recorded with the
original steering played back fine in testing, but this is not guaranteed for every replay. Do
not mix different executables in network or modem races.

### 🛣️ View distance and traffic (optional)

- The track is drawn **32** blocks ahead instead of 28; detailed road textures (lane markings and
  so on) cover **12** blocks instead of 4.
- Walls and roadside scenery appear from **6** blocks instead of 4. More is not possible without
  deeper engine changes (8 gives stray polygons, 12 crashes).
- Track vertex buffers are 4× larger, and the scenery limit is raised from 180 to 440 objects
  (above the limit the engine silently drops all scenery).
- Cars ahead are considered up to **80** track segments away (was 35), without the original depth
  cut-off, so traffic and opponents no longer pop in late.
- New traffic cars appear 50-60 segments ahead (was 43-53), and overtaken cars are recycled 19
  segments behind you (was 20). Same number of traffic cars, fewer visible pop-ins, and they come
  around a bit more often. A tighter rear limit would make traffic denser but suppresses the
  police car, which is placed 12-18 segments behind the player.
- Cars switch to their low-poly model at twice the original distance.

### ⚠️ Known limitations

- With the extended view distance, the rear-view mirror can render oddly inside tunnels.
- Horizons are still the original 640-pixel artwork (larger horizons overflow an internal limit).
- The replay control bar flickers occasionally.
- Menus are rendered in 640×480 and scaled by DOSBox.
- Every engine limit found so far that was hard-wired to 768 screen lines has been raised to 1024
  lines; resolutions above 1024 lines would need further work.

## 🚀 Installation

Three ways, same result: new files next to the originals, which stay untouched. Afterwards start
the race with `NFS1024.EXE` or `NFS1280.EXE` instead of `NFS.EXE`.

### 🌐 Web patcher (easiest)

Open the [web patcher](https://sebauer.github.io/nfsse-enhanced/),
select your game folder and choose the options. Nothing to install; the patcher runs locally in
your browser and no game data is uploaded anywhere. Chrome and Edge write the new files straight
into the game folder, other browsers give you a zip to unpack into it.

### 📦 Download version

Download the zip from the
[latest release](https://github.com/sebauer/nfsse-enhanced/releases), unpack it anywhere and start
the launcher. You need **Python 3.9 or newer**; any current version is recommended (3.9 is the
minimum because macOS still ships it).

- **Windows:** double-click `nfsse-patcher.bat` (or drag the game folder onto it).
- **macOS / Linux:** `sh nfsse-patcher.sh` in the unpacked folder.

The first run sets up a private Python environment (`.venv` next to the launcher; numpy, scipy,
Pillow). The patcher then asks for the game folder, resolution(s), keyboard steering and view
distance, writes the new files next to the originals and prints the DOSBox-X settings.
[`docs/USER_README.txt`](docs/USER_README.txt) (`README.txt` in the zip) has the details.

### 🐍 From source

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

## 📋 Requirements

- The **DOS** version, English or German, installed **completely** (setup → *Custom* → all
  components). The Windows 95 version is not supported.
- DOSBox-X with the [settings below](#dosbox-x-settings). The patch is tested mainly with
  DOSBox-X; other DOSBox versions may work but are untested.
- In the game, *Options → Graphic Details → Resolution* must be set to 640×480.

See [`docs/USER_README.txt`](docs/USER_README.txt) for the full player documentation.

<a id="dosbox-x-settings"></a>

## 🕹️ DOSBox-X settings

Only the memory size needs changing in `dosbox-x.conf` (the patcher prints the same at the end):

```ini
[dosbox]
# 1280x960 needs 64 MB (its cockpits are ~5 MB each); 1024x768 runs with 32 MB; 16 MB is not enough
memsize = 64
```

Everything else can stay at the DOSBox-X defaults; both resolutions work with them.

## 📚 Documentation

- [`docs/USER_README.txt`](docs/USER_README.txt): player documentation (installation, DOSBox-X
  settings, all changes)
- [`docs/EXE.md`](docs/EXE.md): executable layout, every patch site, rejected experiments
- [`docs/FORMATS.md`](docs/FORMATS.md): FSH, QFS, Huffman, BAMF, FNTF, directory layout

## 🔧 How it works

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

`patcher.py` runs these generators as parallel jobs. The web patcher (`web/`) runs the same
Python code unchanged in [Pyodide](https://pyodide.org) web workers.

Runtime dependencies: Python 3, numpy, Pillow, scipy. `capstone` and `unicorn` are only used
by the analysis helpers (`le.dis`, `emu.py`, `stackfix.regen`).

## ☕ Support

If the patch brings back some 1996 racing memories, you can
[buy me a coffee ☕](https://buymeacoffee.com/sebauer). Entirely optional, and thanks for racing! 🏁

## 📄 License

MIT (see `LICENSE`) for the code in this repository.
