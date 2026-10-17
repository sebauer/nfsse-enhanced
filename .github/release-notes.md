Unofficial hi-res patch for **The Need for Speed Special Edition** (DOS): races in 1024×768 or
1280×960, longer view and draw distances, more responsive keyboard steering. The patcher generates
everything from your own installation; no game files are included.

**Easiest:** use the [web patcher](https://sebauer.github.io/nfsse-enhanced/) right in your browser, no installation needed.

## Install the download version

You need a **full** DOS installation of the game (setup → *Custom* → all components) and
**Python 3.9 or newer** (any current version is recommended; 3.9 is the minimum because macOS still
ships it). Download `nfsse-enhanced-<version>.zip` below and unpack it anywhere.

**Windows:** double-click `nfsse-patcher.bat` (or drag the game folder onto it). If Python is
missing, get it from [python.org](https://www.python.org/downloads/) and tick *Add python.exe to PATH*.

**macOS / Linux:** in a terminal, run `sh nfsse-patcher.sh` inside the unpacked folder.

The first run sets up a private Python environment next to the launcher (downloads numpy, scipy
and Pillow, about 100 MB). The patcher then asks for the game folder and the options, writes the
new files next to the originals (which stay untouched) and shows the DOSBox-X settings you need.
See `README.txt` in the zip for details.

Questions or problems: [open an issue](https://github.com/sebauer/nfsse-enhanced/issues).
Enjoying it? [Buy me a coffee ☕](https://buymeacoffee.com/sebauer) (entirely optional).
