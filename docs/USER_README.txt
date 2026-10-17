NFS SE Enhanced v0.9 by github.com/sebauer
==========================================
Unofficial patch for Need for Speed SE (DOS). Not affiliated with or endorsed by
Electronic Arts. "Need for Speed" is a trademark of Electronic Arts.

Thirty years after the original, I was tired of barely making out the traffic
ahead: without a proper CRT monitor, 640x480 on a modern screen turns oncoming
cars into a few blurry pixels until it is almost too late. So this is a gently
modernised version that stays true to the retro charm of the 1996 original:
higher resolution, longer view and draw distances, cars that appear further
ahead and more responsive keyboard steering. No new artwork, no remastered
textures: everything is rescaled from the game's own files.

Runs the race in 1024x768 or 1280x960 instead of 640x480. The original NFS.EXE
stays untouched; the patch adds new executables and new data files.


1. Installing the patch
-----------------------
Easiest: open https://sebauer.github.io/nfsse-enhanced/ in your browser,
select the game folder and choose the options. Nothing to install, nothing is
uploaded: the patcher runs locally in the browser. Chrome and Edge write the
new files straight into the game folder; other browsers give you a zip to
unpack into it.

The download version below does the same from the command line.
You need a FULL installation of the DOS game (see section 3) and Python 3.9
or newer (any current version is recommended; 3.9 is the minimum because
macOS still ships it). Unpack the patch zip anywhere; it does not have to be
in the game folder.

Windows:       double-click nfsse-patcher.bat, or drag the game folder onto it.
               No Python yet? Install it from https://www.python.org/downloads/
               and tick "Add python.exe to PATH" in the installer.
               Windows may warn about a file from the internet: confirm with
               "Run" (or "More info" > "Run anyway").
macOS / Linux: open a terminal in the unpacked folder and run
                   sh nfsse-patcher.sh

The first run sets up a private Python environment in the folder .venv next to
the launcher (downloads numpy, scipy and Pillow, about 100 MB, only once).
Then the patcher asks for the game folder and the options, writes the new
files next to the originals and shows the DOSBox-X settings you need. Run it
again at any time to change the options.

Command line options (optional): nfsse-patcher.bat --help (Windows) or
sh nfsse-patcher.sh --help (macOS / Linux), e.g. "<game folder>" --res 1280 -y

To remove the patch, delete the files listed in section 2 from the game
folder and delete the unpacked patch folder.


2. Files
--------
NFS1024.EXE     race in 1024x768
NFS1280.EXE     race in 1280x960
(by default both include the optional features of sections 5a/5b; the patcher
options --steer 1 and --view original turn them off)

Additional data files (the originals are not modified):
  SIMDATA\MISC\MASKHJ.*, MASKHJG.FSH      HUD / blit masks 1024x768
  SIMDATA\MISC\MASKHK.*, MASKHKG.FSH      HUD / blit masks 1280x960
  SIMDATA\DASH\*DJ.FSH / *DJ.FMM          cockpits 1024x768 (German: SIMDATA\GDASH)
  SIMDATA\DASH\*DK.FSH / *DK.FMM          cockpits 1280x960 (German: SIMDATA\GDASH)
  SIMDATA\MISC\TICKET*J/K.QFS, *WARN*J/K.QFS   ticket / warning screens
  FRONTEND\ART\TITLEE.QFS (German: GART)   title screen with the patch credit line

Start the game with NFS1024.EXE or NFS1280.EXE instead of NFS.EXE.


3. Requirements: installation and DOSBox-X configuration
--------------------------------------------------------
Installation: the patch needs a FULL installation of the DOS version.
In the setup program choose "Custom" and select ALL components. "Minimal" and
"Recommended" leave files on the CD that the patch has to convert (e.g. cockpits,
ticket screens), and the patched game would fail to load them.
English and German installations are both supported (German uses the folders
FRONTEND\GART and SIMDATA\GDASH, ...). The Windows 95 version (NFS_WIN.EXE)
is not supported.

The patch is tested mainly with DOSBox-X. Other DOSBox versions may work but
are untested.

Only the memory size needs changing in the DOSBox-X configuration:

[dosbox]
memsize = 64      (1280x960 needs 64 MB: its cockpits are ~5 MB each;
                   1024x768 runs with 32 MB; 16 MB is NOT enough)

Everything else can stay at the DOSBox-X defaults; both resolutions work
with them.


4. Requirements: in-game settings
---------------------------------
- Options > Graphic Details > Resolution must be set to 640x480.
  The 320x200 setting is not supported by the patch.
- All other graphic detail options work as in the original. The reduced-detail
  rendering modes (half-resolution 3D) are untested.


5. What changes
---------------
- 3D view, exterior and cockpit, in full resolution; the exterior view uses the
  whole screen.
- HUD bar, map, tachometer, start lights, acceleration display (F8) and replay
  bar are laid out for the wider screen.
- Cockpits are rescaled from the original artwork to fill the screen.
- Pause menu, end-of-race menus, checkpoint menu and videos switch to 640x480
  and are shown full screen.
- Ticket / warning screens are upscaled to the full resolution.
- Opponent markers above the cars scale with the resolution.
- The cockpit-view horizon is drawn across the full width (the original engine
  dropped horizon pieces beyond +-1280 pixels, which left a black/smeared area on
  the right side at high resolutions).
- The game's internal memory pool is raised from 16 MB to whatever is available
  (up to 48 MB), which the larger graphics need.


5a. Optional: faster keyboard steering
--------------------------------------
With digital input (keyboard) the original builds up the steering angle slowly,
especially at high speed, so correcting mid-corner often ends in the barrier.
These builds double the steering build-up rate (and the return to centre).
Analog input (joystick / wheel) is not affected. 2x was chosen in testing as the
best balance between responsiveness and speed lost to tyre scrub (3x/4x feel
quicker but scrub off noticeably more speed in corners).
Note: replays recorded with the original steering played back fine in
testing, but this is not guaranteed for every replay.
Do not mix different executables in network/modem races.


5b. Optional: extended view distance and traffic
-----------------------------------------------------------------
- Track drawn 32 blocks ahead instead of 28; detailed road textures (lane
  markings etc.) over 12 blocks instead of 4.
- Walls and roadside scenery appear from 6 blocks instead of 4 (more is not
  possible without deeper engine changes: 8 gives stray polygons, 12 crashes).
- Track vertex buffers enlarged 4x and the scenery-object limit raised from
  180 to 440 (the engine silently drops all scenery above the limit).
- Cars ahead are considered up to 80 track segments (was 35), without the
  original depth cut-off, so traffic and opponents no longer pop in late.
- Traffic: new traffic cars appear 50-60 track segments ahead (was 43-53), and
  overtaken cars are recycled 19 segments behind you (was 20). Same number of
  traffic cars, but fewer visible pop-ins and they come around a bit more often.
  (A tighter rear limit made traffic denser but suppressed the police car, which
  is placed 12-18 segments behind the player.)
- Cars switch to their low-poly model at twice the original distance (ahead:
  0x1900 -> 0x3200; mirror: 0xa00 -> 0x1400, hidden beyond 0x4200).


6. Known limitations
--------------------
- With the extended view distance, the rear-view mirror can render oddly while
  driving inside tunnels (only there).
- Horizons are still the original 640-pixel artwork (larger horizons overflow an
  internal limit; under investigation).
- The replay control bar flickers occasionally.
- Menus are rendered in 640x480 and scaled by DOSBox.
- Every engine limit found so far that was hard-wired to 768 screen lines has been
  raised to 1024 lines; resolutions above 1024 lines would need further work.


7. Support, questions, source code
----------------------------------
Questions, problems, source code and technical documentation:
https://github.com/sebauer/nfsse-enhanced

Enjoying the patch? You can buy me a coffee: https://buymeacoffee.com/sebauer
Entirely optional - thanks for racing!


8. Legal
--------
This patch modifies a commercial game. Do not redistribute NFS.EXE or the game
data. Distribute only the patch / generator and let users apply it to their own
copy.
