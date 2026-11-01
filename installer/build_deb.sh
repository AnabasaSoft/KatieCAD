#!/bin/sh
# Builds a .deb package from the PyInstaller output (dist/KatieCAD).
# Usage: installer/build_deb.sh <version> [arch]
set -e
VER="$1"; ARCH="${2:-amd64}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/build/deb/katiecad_${VER}_${ARCH}"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/katiecad" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -r "$ROOT/dist/KatieCAD/." "$PKG/opt/katiecad/"
ln -s /opt/katiecad/KatieCAD "$PKG/usr/bin/katiecad"
cp "$ROOT/KatieCAD.png" "$PKG/usr/share/icons/hicolor/256x256/apps/katiecad.png"
cat > "$PKG/usr/share/applications/io.github.merecete.KatieCAD.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=KatieCAD
GenericName=Electrical CAD
Comment=2D/3D CAD for electrical engineering
Exec=/opt/katiecad/KatieCAD %F
Icon=katiecad
Terminal=false
Categories=Graphics;Engineering;Electronics;
Keywords=CAD;electrical;schematic;switchgear;DXF;
StartupWMClass=KatieCAD
DESK
# AppStream metadata (software centres show licence, web site and description) and copyright file
mkdir -p "$PKG/usr/share/metainfo" "$PKG/usr/share/doc/katiecad"
sed -e "s/@VERSION@/$VER/" -e "s/@DATE@/$(date -u +%Y-%m-%d)/" \
    "$ROOT/installer/io.github.merecete.KatieCAD.metainfo.xml" \
    > "$PKG/usr/share/metainfo/io.github.merecete.KatieCAD.metainfo.xml"
cat > "$PKG/usr/share/doc/katiecad/copyright" <<COPY
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: KatieCAD
Source: https://github.com/Merecete/KatieCAD

Files: *
Copyright: 2026 Merecete
License: MIT
COPY
sed -n '/^Permission is hereby granted/,$p' "$ROOT/LICENSE" | sed -e 's/^$/./' -e 's/^/ /' \
    >> "$PKG/usr/share/doc/katiecad/copyright"
SIZE_KB=$(du -sk "$PKG" | cut -f1)        # shown as "installed size" by software centres
cat > "$PKG/DEBIAN/control" <<CTRL
Package: katiecad
Version: $VER
Section: graphics
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE_KB
Maintainer: Merecete <noreply@github.com>
Homepage: https://github.com/Merecete/KatieCAD
Description: 2D/3D CAD for electrical engineering (open source, MIT)
 KatieCAD is a free and open-source 2D/3D CAD program for electrical
 engineering: switchgear construction, distribution boards and building
 installation.
 .
 Wires, devices, cross references, terminals and cables, projects with
 several sheets, a symbol library, automatic documentation (device list,
 terminal plan, cable plan, parts list) and simple 3D modelling of control
 cabinets. Licensed under the MIT license.
CTRL
# refresh the software-centre catalogue after (un)installing, so licence and description show up at once
for T in postinst postrm; do
cat > "$PKG/DEBIAN/$T" <<'POST'
#!/bin/sh
set -e
if command -v appstreamcli >/dev/null 2>&1; then
  appstreamcli refresh-cache --force >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
POST
chmod 755 "$PKG/DEBIAN/$T"
done
mkdir -p "$ROOT/release"
dpkg-deb --build --root-owner-group "$PKG" "$ROOT/release/KatieCAD-${VER}-Linux-${ARCH}.deb"
