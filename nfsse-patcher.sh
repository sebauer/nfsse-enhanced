#!/bin/sh
# NFS SE Enhanced patcher - launcher for macOS and Linux.
# The first run sets up a private Python environment in .venv next to this script (needs internet,
# about 100 MB); nothing is installed system-wide. Delete the folder to remove everything.
# Usage: sh nfsse-patcher.sh ["<game folder>"] [options]   (options: sh nfsse-patcher.sh --help)
DIR=$(cd "$(dirname "$0")" && pwd)
VENV="$DIR/.venv"

if [ ! -f "$VENV/installed.ok" ]; then
    if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
        echo "The patcher needs Python 3.9 or newer (python3)."
        echo "  macOS: run 'xcode-select --install' (Command Line Tools include Python 3), or get it from python.org"
        echo "  Linux: install python3 with your package manager"
        exit 1
    fi
    echo "First run: setting up a Python environment in $VENV"
    echo "(downloads numpy, scipy and Pillow, about 100 MB; only needed once)"
    rm -rf "$VENV"
    if ! python3 -m venv "$VENV"; then
        echo "Could not create the Python environment."
        echo "  Debian/Ubuntu: sudo apt install python3-venv"
        exit 1
    fi
    "$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$DIR/requirements.txt" || {
        echo "Installing the Python packages failed (internet connection?). Run the script again to retry."
        exit 1
    }
    touch "$VENV/installed.ok"
    echo
fi
exec "$VENV/bin/python" "$DIR/patcher.py" "$@"
