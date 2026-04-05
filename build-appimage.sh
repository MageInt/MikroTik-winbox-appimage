#!/bin/bash
# build-appimage.sh
# Builds a portable AppImage for MikroTik WinBox on Arch/CachyOS
# Run this script from your normal terminal (NOT inside VS Code Flatpak)
#
# Usage:
#   chmod +x build-appimage.sh
#   ./build-appimage.sh              # auto-detect version from binary
#   ./build-appimage.sh 4.0.1        # override version manually

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPDIR="${SCRIPT_DIR}/WinBox.AppDir"

# ── Version detection ────────────────────────────────────────────────────────

if [[ -n "$1" ]]; then
    APP_VERSION="$1"
    echo "==> Using provided version: ${APP_VERSION}"
else
    # Extract version from binary strings: prefer pattern matching WinBox major versions (4.x.y)
    APP_VERSION=$(strings "${SCRIPT_DIR}/WinBox" 2>/dev/null \
        | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' \
        | sort -V \
        | grep -E '^4\.' \
        | tail -1)

    if [[ -z "$APP_VERSION" ]]; then
        # Fallback: highest version-like string that is not a known lib version
        APP_VERSION=$(strings "${SCRIPT_DIR}/WinBox" 2>/dev/null \
            | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' \
            | grep -vE '^(1\.6\.|3\.0\.|16\.|27\.|50\.|52\.|55\.)' \
            | sort -V | tail -1)
    fi

    if [[ -z "$APP_VERSION" ]]; then
        echo "WARNING: Could not detect version from binary. Pass it as argument: $0 <version>"
        APP_VERSION="unknown"
    else
        echo "==> Auto-detected version: ${APP_VERSION}"
    fi
fi

OUTPUT="${SCRIPT_DIR}/WinBox-${APP_VERSION}-x86_64.AppImage"

APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
LINUXDEPLOY_URL="https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"

APPIMAGETOOL="${SCRIPT_DIR}/tools/appimagetool-x86_64.AppImage"
LINUXDEPLOY="${SCRIPT_DIR}/tools/linuxdeploy-x86_64.AppImage"

# ── 1. Dependency check ──────────────────────────────────────────────────────

echo "==> Checking dependencies..."

for cmd in wget ldd patchelf; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' is not installed."
        echo "Install it with: sudo pacman -S $cmd"
        exit 1
    fi
done

# ── 2. Download tools if needed ──────────────────────────────────────────────

mkdir -p "${SCRIPT_DIR}/tools"

if [[ ! -x "$APPIMAGETOOL" ]]; then
    echo "==> Downloading appimagetool..."
    wget -q --show-progress -O "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

if [[ ! -x "$LINUXDEPLOY" ]]; then
    echo "==> Downloading linuxdeploy..."
    wget -q --show-progress -O "$LINUXDEPLOY" "$LINUXDEPLOY_URL"
    chmod +x "$LINUXDEPLOY"
fi

# ── 3. Build AppDir ──────────────────────────────────────────────────────────

echo "==> Building AppDir at ${APPDIR}..."
rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy executable
cp "${SCRIPT_DIR}/WinBox" "${APPDIR}/usr/bin/WinBox"
chmod +x "${APPDIR}/usr/bin/WinBox"

# Copy icon
cp "${SCRIPT_DIR}/assets/img/winbox.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/winbox.png"
cp "${SCRIPT_DIR}/assets/img/winbox.png" "${APPDIR}/winbox.png"

# Copy and patch desktop file: X-AppImage-Version for Gear Lever + other managers
BUILD_DATE=$(date +%Y-%m-%d)
sed "s/__APPVERSION__/${APP_VERSION}/g" "${SCRIPT_DIR}/WinBox.desktop" > "${APPDIR}/WinBox.desktop"

# Copy and patch AppStream metainfo with version and build date
mkdir -p "${APPDIR}/usr/share/metainfo"
sed -e "s/__APPVERSION__/${APP_VERSION}/g" \
    -e "s/__BUILDDATE__/${BUILD_DATE}/g" \
    "${SCRIPT_DIR}/winbox.appdata.xml" > "${APPDIR}/usr/share/metainfo/com.mikrotik.WinBox.appdata.xml"

cp "${SCRIPT_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# ── 4. Bundle shared libraries ───────────────────────────────────────────────

echo "==> Bundling shared libraries with linuxdeploy..."

# Exclude libs that must come from the host (GPU drivers, glibc, etc.)
EXCLUDE_LIBS=(
    "libGL.so"
    "libEGL.so"
    "libGLX.so"
    "libGLdispatch.so"
    "libvulkan.so"
    "libdrm.so"
    "libwayland"
    "libc.so"
    "libm.so"
    "libpthread.so"
    "libdl.so"
    "librt.so"
    "ld-linux"
)

EXCLUDE_ARG=""
for lib in "${EXCLUDE_LIBS[@]}"; do
    EXCLUDE_ARG="${EXCLUDE_ARG} --exclude-library=${lib}*"
done

# Run linuxdeploy to copy libraries
NO_STRIP=1 \
    "${LINUXDEPLOY}" \
    --appdir "${APPDIR}" \
    --executable "${APPDIR}/usr/bin/WinBox" \
    --desktop-file "${APPDIR}/WinBox.desktop" \
    --icon-file "${APPDIR}/winbox.png" \
    ${EXCLUDE_ARG} \
    2>&1 | tee /tmp/linuxdeploy.log || true

# Fallback: manually copy missing libs if linuxdeploy had issues
echo "==> Verifying bundled libraries..."
while IFS= read -r line; do
    libpath=$(echo "$line" | awk '{print $3}')
    libname=$(echo "$line" | awk '{print $1}')
    # Skip vdso and "not found" entries
    [[ "$libpath" == "(0x"* ]] && continue
    [[ -z "$libpath" ]] && continue
    [[ "$libpath" == "not" ]] && continue
    if [[ -f "$libpath" ]]; then
        dest="${APPDIR}/usr/lib/$(basename "$libpath")"
        if [[ ! -f "$dest" ]]; then
            echo "  Copying: $libpath"
            cp "$libpath" "$dest"
        fi
    fi
done < <(ldd "${APPDIR}/usr/bin/WinBox" 2>/dev/null)

# Fix RPATH so the AppImage finds its bundled libs at usr/lib/
patchelf --set-rpath '$ORIGIN/../lib:$ORIGIN/../../lib' "${APPDIR}/usr/bin/WinBox" 2>/dev/null || true

# ── 5. Package AppImage ──────────────────────────────────────────────────────

echo "==> Packaging AppImage..."
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT}"

echo ""
echo "✓ Done! WinBox ${APP_VERSION} AppImage created at:"
echo "  ${OUTPUT}"
echo ""
echo "Make it executable and run:"
echo "  chmod +x ${OUTPUT}"
echo "  ${OUTPUT}"
