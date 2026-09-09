#!/bin/bash
# build-appimage.sh
# Builds a portable AppImage for MikroTik WinBox on Arch/CachyOS
# Run this script from your normal terminal (NOT inside VS Code Flatpak)
#
# Usage:
#   chmod +x build-appimage.sh
#   ./build-appimage.sh                    # build ./WinBox, auto-detect version
#   ./build-appimage.sh 4.0.1              # build ./WinBox, version forced
#   ./build-appimage.sh --download         # download the latest WinBox from MikroTik
#   ./build-appimage.sh --download 4.3     # download a specific WinBox version

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPDIR="${SCRIPT_DIR}/WinBox.AppDir"
DOWNLOAD_DIR="${SCRIPT_DIR}/downloads"

# Official MikroTik sources
MIKROTIK_LATEST_URL="${MIKROTIK_LATEST_URL:-https://download.mikrotik.com/routeros/winbox/LATEST.4}"
MIKROTIK_ZIP_URL_TEMPLATE="${MIKROTIK_ZIP_URL_TEMPLATE:-https://download.mikrotik.com/routeros/winbox/__APPVERSION__/WinBox_Linux.zip}"

DOWNLOAD=0
if [[ "$1" == "--download" || "$1" == "-d" ]]; then
    DOWNLOAD=1
    shift
fi

# Sources used to build the AppDir (overridden below when downloading)
WINBOX_BIN="${SCRIPT_DIR}/WinBox"
WINBOX_ICON="${SCRIPT_DIR}/assets/img/winbox.png"

# ── Version detection ────────────────────────────────────────────────────────

if [[ $DOWNLOAD -eq 1 ]]; then
    if [[ -n "$1" ]]; then
        APP_VERSION="$1"
        echo "==> Requested version: ${APP_VERSION}"
    else
        echo "==> Resolving latest WinBox version from MikroTik..."
        APP_VERSION=$(wget -qO- "$MIKROTIK_LATEST_URL" | awk 'NR==1{print $1}' | tr -d '[:space:]')
        if [[ -z "$APP_VERSION" ]]; then
            echo "ERROR: could not resolve the latest version from ${MIKROTIK_LATEST_URL}"
            exit 1
        fi
        echo "==> Latest version: ${APP_VERSION}"
    fi
elif [[ -n "$1" ]]; then
    APP_VERSION="$1"
    echo "==> Using provided version: ${APP_VERSION}"
else
    # Extract version from binary strings: prefer pattern matching WinBox major versions (4.x.y)
    APP_VERSION=$(strings "${WINBOX_BIN}" 2>/dev/null \
        | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' \
        | sort -V \
        | grep -E '^4\.' \
        | tail -1)

    if [[ -z "$APP_VERSION" ]]; then
        # Fallback: highest version-like string that is not a known lib version
        APP_VERSION=$(strings "${WINBOX_BIN}" 2>/dev/null \
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

REQUIRED_CMDS=(wget ldd patchelf)
[[ $DOWNLOAD -eq 1 ]] && REQUIRED_CMDS+=(unzip)

for cmd in "${REQUIRED_CMDS[@]}"; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' is not installed."
        echo "Install it with your package manager (e.g. sudo pacman -S $cmd / sudo apt-get install $cmd)"
        exit 1
    fi
done

# ── 1b. Download WinBox from MikroTik ────────────────────────────────────────

if [[ $DOWNLOAD -eq 1 ]]; then
    ZIP_URL="${MIKROTIK_ZIP_URL_TEMPLATE//__APPVERSION__/${APP_VERSION}}"
    ZIP_PATH="${DOWNLOAD_DIR}/WinBox_Linux-${APP_VERSION}.zip"
    EXTRACT_DIR="${DOWNLOAD_DIR}/${APP_VERSION}"

    mkdir -p "$DOWNLOAD_DIR"

    if [[ ! -f "$ZIP_PATH" ]]; then
        echo "==> Downloading ${ZIP_URL}..."
        wget -O "${ZIP_PATH}.part" "$ZIP_URL"
        mv "${ZIP_PATH}.part" "$ZIP_PATH"
    else
        echo "==> Using cached archive: ${ZIP_PATH}"
    fi

    rm -rf "$EXTRACT_DIR"
    mkdir -p "$EXTRACT_DIR"
    unzip -q -o "$ZIP_PATH" -d "$EXTRACT_DIR"

    WINBOX_BIN="${EXTRACT_DIR}/WinBox"
    [[ -f "${EXTRACT_DIR}/assets/img/winbox.png" ]] && WINBOX_ICON="${EXTRACT_DIR}/assets/img/winbox.png"

    if [[ ! -f "$WINBOX_BIN" ]]; then
        echo "ERROR: no WinBox binary found in ${ZIP_PATH}"
        exit 1
    fi
    chmod +x "$WINBOX_BIN"
fi

# ── 2. Download tools if needed ──────────────────────────────────────────────

mkdir -p "${SCRIPT_DIR}/tools"

if [[ ! -x "$APPIMAGETOOL" ]]; then
    echo "==> Downloading appimagetool..."
    wget -O "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

if [[ ! -x "$LINUXDEPLOY" ]]; then
    echo "==> Downloading linuxdeploy..."
    wget -O "$LINUXDEPLOY" "$LINUXDEPLOY_URL"
    chmod +x "$LINUXDEPLOY"
fi

# ── 3. Build AppDir ──────────────────────────────────────────────────────────

echo "==> Building AppDir at ${APPDIR}..."
rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy executable
cp "${WINBOX_BIN}" "${APPDIR}/usr/bin/WinBox"
chmod +x "${APPDIR}/usr/bin/WinBox"

# Copy icon
cp "${WINBOX_ICON}" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/winbox.png"
cp "${WINBOX_ICON}" "${APPDIR}/winbox.png"

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
        base=$(basename "$libpath")
        # Never bundle host-provided libs (GPU drivers, glibc...), even as fallback
        skip=0
        for lib in "${EXCLUDE_LIBS[@]}"; do
            [[ "$base" == "$lib"* ]] && { skip=1; break; }
        done
        [[ $skip -eq 1 ]] && continue
        dest="${APPDIR}/usr/lib/${base}"
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
