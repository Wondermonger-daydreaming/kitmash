#!/usr/bin/env bash
# install_houdini.sh — Install Houdini 21.0.729 from the downloaded tarball
# and verify headless hython works.
#
# Usage:
#   bash houdini/install_houdini.sh
#
# Expects: /tmp/houdini-install/houdini-21.0.729-linux_x86_64_gcc11.2.tar.gz
# Installs to: /opt/hfs21.0.729  (symlinked as /opt/hfs21.0)
# Run as a user with sudo access.

set -euo pipefail

TARBALL="/tmp/houdini-install/houdini-21.0.729-linux_x86_64_gcc11.2.tar.gz"
EXPECTED_MD5="96a5fef5753e33e16fce4804a258123d"
EXTRACT_DIR="/tmp/houdini-install/extracted"
INSTALL_ROOT="/opt"

# ── 1. Verify the download ────────────────────────────────────────────────────
echo "==> Verifying checksum..."
ACTUAL_MD5=$(md5sum "$TARBALL" | awk '{print $1}')
if [[ "$ACTUAL_MD5" != "$EXPECTED_MD5" ]]; then
  echo "ERROR: MD5 mismatch!"
  echo "  expected: $EXPECTED_MD5"
  echo "  actual:   $ACTUAL_MD5"
  exit 1
fi
echo "    OK ($ACTUAL_MD5)"

# ── 2. Extract ────────────────────────────────────────────────────────────────
echo "==> Extracting tarball to $EXTRACT_DIR ..."
mkdir -p "$EXTRACT_DIR"
tar -xzf "$TARBALL" -C "$EXTRACT_DIR" --strip-components=1
echo "    Done."

# ── 3. Run the installer (silent / headless) ──────────────────────────────────
echo "==> Running Houdini installer..."
# --no-menus       : skip the shell menu (houdini shell entry)
# --no-register    : skip SideFX phone-home registration
# --no-desktop-icon: no .desktop file
# HOUDINI_INSTALL_PATH: target directory
INSTALLER="$EXTRACT_DIR/houdini.install"
if [[ ! -x "$INSTALLER" ]]; then
  echo "ERROR: installer not found at $INSTALLER"
  exit 1
fi

sudo env \
  HOUDINI_INSTALL_PATH="$INSTALL_ROOT" \
  "$INSTALLER" \
    --no-menus \
    --no-register \
    --no-desktop-icon \
    --accept-EULA 2021-10-13 \
  || {
    # Some versions don't have --accept-EULA; fall back to expect
    echo "  (falling back to piped yes)"
    yes | sudo env HOUDINI_INSTALL_PATH="$INSTALL_ROOT" \
      "$INSTALLER" --no-menus --no-register --no-desktop-icon
  }

# ── 4. Locate the installed hfs directory ────────────────────────────────────
HFS=$(ls -d "$INSTALL_ROOT"/hfs21.0* 2>/dev/null | sort -V | tail -1)
if [[ -z "$HFS" ]]; then
  echo "ERROR: Installation did not produce an hfs21.0* directory under $INSTALL_ROOT"
  exit 1
fi
echo "==> Installed at: $HFS"

# ── 5. Convenience symlink ───────────────────────────────────────────────────
LINK="$INSTALL_ROOT/hfs21.0"
if [[ ! -L "$LINK" ]]; then
  sudo ln -sfn "$HFS" "$LINK"
  echo "==> Symlinked: $LINK -> $HFS"
fi

# ── 6. Source the environment and verify hython ───────────────────────────────
echo "==> Verifying hython..."
# shellcheck source=/dev/null
source "$HFS/houdini_setup"

hython - <<'PYEOF'
import hou
print(f"hython OK — Houdini {hou.applicationVersionString()}")
print(f"  Python  {hou.applicationPythonVersion()}")
print(f"  hfs     {hou.applicationVersionString()}")
PYEOF

echo ""
echo "══════════════════════════════════════════════════════════"
echo " Houdini installed.  Add this to your shell profile:"
echo "   source $HFS/houdini_setup"
echo " Or invoke hython directly:"
echo "   $HFS/bin/hython"
echo "══════════════════════════════════════════════════════════"
