# MikroTik WinBox — AppImage

Portable [WinBox](https://mikrotik.com/software) AppImage packaging for Linux x86_64.

The AppImage version is automatically detected from the bundled binary and embedded in the filename, desktop entry, and AppStream metadata — making it visible in tools like [Gear Lever](https://github.com/mijorus/gearlever).

## Repository structure

```
.
├── WinBox                  # WinBox executable (ELF 64-bit)
├── AppRun                  # AppImage entry point
├── WinBox.desktop          # Desktop entry (spec v1.0 + X-AppImage-Version)
├── winbox.appdata.xml      # AppStream metadata (version, release date)
├── build-appimage.sh       # Build script
└── assets/
    └── img/
        └── winbox.png      # Application icon
```

## Requirements

- Arch-based distro (CachyOS, Manjaro, EndeavourOS…)
- `patchelf`:
  ```bash
  sudo pacman -S patchelf
  ```
- `wget` and `ldd` (included by default on Arch)
- Internet access on first build (to download `appimagetool` and `linuxdeploy` into `./tools/`)

## Build

```bash
git clone https://github.com/MageInt/MikroTik-winbox-appimage
cd MikroTik-winbox-appimage
chmod +x build-appimage.sh
./build-appimage.sh
```

The version is auto-detected from the binary. You can also pass it explicitly:

```bash
./build-appimage.sh 4.0.1
```

The AppImage is generated at the project root:

```
WinBox-4.0.1-x86_64.AppImage
```

## Usage

```bash
chmod +x WinBox-4.0.1-x86_64.AppImage
./WinBox-4.0.1-x86_64.AppImage
```

Or double-click it in your file manager (requires `libfuse2` or FUSE support from your distro).

> **Note:** GPU libraries (`libGL`, `libEGL`, `libvulkan`…) and glibc are **not** bundled — they are provided by the host system to ensure compatibility with your graphics drivers.

## Bundled runtime dependencies

The build script automatically copies the following Qt/X11 libraries:

- `libxcb` and its extensions (xcb-glx, xkb, randr, render…)
- `libxkbcommon`, `libX11`, `libfreetype`, `libfontconfig`
- `libdbus-1`, `libglib-2.0`, `libharfbuzz`
- All their transitive dependencies

## License

WinBox is proprietary software by [MikroTik](https://mikrotik.com). This repository only provides the AppImage packaging.
