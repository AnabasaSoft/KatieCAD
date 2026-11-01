#!/bin/sh
# Builds a single-file AppImage from the PyInstaller output (dist/KatieCAD).
# Usage: installer/build_appimage.sh <version> [arch]      (arch: x86_64 (default) or aarch64)
# Needs: dist/KatieCAD (run PyInstaller first), curl. appimagetool is downloaded if it is not
# found in PATH or via the APPIMAGETOOL variable. No FUSE needed (extract-and-run).
set -e
VER="$1"; ARCH="${2:-x86_64}"
[ -n "$VER" ] || { echo "Usage: $0 <version> [arch]"; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -x "$ROOT/dist/KatieCAD/KatieCAD" ] || { echo "dist/KatieCAD/KatieCAD missing - run PyInstaller first"; exit 1; }
APPDIR="$ROOT/build/KatieCAD.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/katiecad" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$ROOT/dist/KatieCAD/." "$APPDIR/usr/lib/katiecad/"
cp "$ROOT/KatieCAD.png" "$APPDIR/katiecad.png"
cp "$ROOT/KatieCAD.png" "$APPDIR/.DirIcon"
cp "$ROOT/KatieCAD.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/katiecad.png"
cat > "$APPDIR/katiecad.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=KatieCAD
Comment=2D CAD and electrical CAD
Exec=KatieCAD %F
Icon=katiecad
Terminal=false
Categories=Graphics;Engineering;
StartupWMClass=KatieCAD
DESK
cp "$APPDIR/katiecad.desktop" "$APPDIR/usr/share/applications/katiecad.desktop"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/katiecad/KatieCAD" "$@"
RUN
chmod +x "$APPDIR/AppRun"

TOOL="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
if [ -z "$TOOL" ]; then
  TOOL="$ROOT/build/appimagetool-$ARCH.AppImage"
  if [ ! -x "$TOOL" ]; then
    curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
  fi
fi
mkdir -p "$ROOT/release"
OUT="$ROOT/release/KatieCAD-${VER}-Linux-${ARCH}.AppImage"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
chmod +x "$OUT"
echo "Done: $OUT"
