#!/usr/bin/env bash
# setup.sh — install all dependencies needed to build the poster.
# Run once after cloning, from the repo root.
# Supports macOS (Homebrew) and Debian/Ubuntu (apt).
set -eu

echo "=== ATLAS TileCal poster — environment setup ==="

OS="$(uname -s)"

install_macos() {
    if ! command -v brew &>/dev/null; then
        echo "ERROR: Homebrew not found. Install it first: https://brew.sh" >&2
        exit 1
    fi
    echo ":: macOS detected — installing via Homebrew"
    # mactex-no-gui is ~4 GB but ships tikzposter; basictex would need tlmgr top-ups
    brew install --cask mactex-no-gui || true
    brew install poppler imagemagick python || true
    # MacTeX drops binaries in /Library/TeX/texbin; add to PATH for this session
    export PATH="/Library/TeX/texbin:$PATH"
    echo ":: added /Library/TeX/texbin to PATH for this session"
    echo "   Add it to your shell profile to make it permanent:"
    echo "   echo 'export PATH=\"/Library/TeX/texbin:\$PATH\"' >> ~/.zshrc"
}

install_debian() {
    echo ":: Debian/Ubuntu detected — installing via apt"
    sudo apt-get update -q
    sudo apt-get install -y \
        texlive-latex-extra texlive-science texlive-fonts-extra \
        poppler-utils python3 python3-pip imagemagick
}

case "$OS" in
    Darwin) install_macos ;;
    Linux)  install_debian ;;
    *)
        echo "ERROR: unsupported OS '$OS'. Set up manually — see README.md." >&2
        exit 1
        ;;
esac

echo
echo ":: installing Python dependencies (Pillow, numpy)"
python3 -m pip install --quiet --user Pillow numpy

echo
echo ":: verifying build"
cd "$(dirname "$0")/build"
./build.sh

echo
echo "=== setup complete — ready to edit build/irradiation_poster.tex ==="
