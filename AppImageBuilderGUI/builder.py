"""
Core AppImage build logic.
Generalised from the MikroTik WinBox AppImage build script.
"""

import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional

APPIMAGETOOL_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)
LINUXDEPLOY_URL = (
    "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/"
    "linuxdeploy-x86_64.AppImage"
)

# Libraries that should NOT be bundled — they must come from the host
DEFAULT_EXCLUDE_LIBS = [
    "libGL.so",
    "libEGL.so",
    "libGLX.so",
    "libGLdispatch.so",
    "libvulkan.so",
    "libdrm.so",
    "libwayland",
    "libc.so",
    "libm.so",
    "libpthread.so",
    "libdl.so",
    "librt.so",
    "ld-linux",
]

FREEDESKTOP_CATEGORIES = [
    "AudioVideo", "Audio", "Video", "Development", "Education",
    "Game", "Graphics", "Network", "Office", "Science",
    "Settings", "System", "Utility",
]

ICON_SIZES = ["16x16", "32x32", "64x64", "128x128", "256x256", "scalable"]


@dataclass
class AppImageConfig:
    """All configuration needed to build an AppImage."""
    binary_path: str = ""
    app_name: str = ""
    app_version: str = ""
    app_comment: str = ""
    app_description: str = ""
    icon_path: str = ""
    categories: List[str] = field(default_factory=lambda: ["Utility"])
    homepage_url: str = ""
    output_dir: str = ""
    use_terminal: bool = False
    exclude_libs: List[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_LIBS))
    extra_files: List[str] = field(default_factory=list)
    extra_env_vars: dict = field(default_factory=dict)
    reverse_domain: str = ""

    @property
    def safe_name(self) -> str:
        """Return app_name safe for filenames (no spaces/special chars)."""
        return re.sub(r"[^a-zA-Z0-9._-]", "", self.app_name.replace(" ", "-"))

    @property
    def rdns_id(self) -> str:
        """Reverse-DNS application ID."""
        if self.reverse_domain:
            return self.reverse_domain
        safe = re.sub(r"[^a-zA-Z0-9]", "", self.app_name)
        return f"org.appimage.{safe}"


class AppImageBuilder:
    """Builds an AppImage from a binary + config."""

    def __init__(self, config: AppImageConfig, log: Optional[Callable[[str], None]] = None):
        self.cfg = config
        self._log = log or (lambda msg: print(msg))
        self._tools_dir: Optional[Path] = None
        self._appdir: Optional[Path] = None

    # ── Public API ───────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty == OK)."""
        errors = []
        if not self.cfg.binary_path or not os.path.isfile(self.cfg.binary_path):
            errors.append("Binary path is invalid or file does not exist.")
        if not self.cfg.app_name.strip():
            errors.append("Application name is required.")
        if not self.cfg.app_version.strip():
            errors.append("Version is required.")
        if not self.cfg.output_dir or not os.path.isdir(self.cfg.output_dir):
            errors.append("Output directory does not exist.")
        if self.cfg.icon_path and not os.path.isfile(self.cfg.icon_path):
            errors.append("Icon file does not exist.")
        for cmd in ("ldd", "patchelf"):
            if not shutil.which(cmd):
                errors.append(f"Required tool '{cmd}' is not installed.")
        return errors

    def build(self, progress: Optional[Callable[[int, str], None]] = None) -> str:
        """
        Run the full AppImage build pipeline.
        *progress(percent, message)* is called to report status.
        Returns the path to the produced AppImage file.
        """
        prog = progress or (lambda p, m: None)

        prog(0, "Preparing tools …")
        self._prepare_tools()

        prog(10, "Creating AppDir structure …")
        self._create_appdir()

        prog(25, "Copying binary & assets …")
        self._copy_assets()

        prog(40, "Writing desktop & metadata files …")
        self._write_desktop_file()
        self._write_apprun()
        self._write_appdata()

        prog(55, "Bundling shared libraries …")
        self._bundle_libraries()

        prog(75, "Patching RPATH …")
        self._patch_rpath()

        prog(85, "Packaging AppImage …")
        output = self._package()

        prog(100, f"Done → {output}")
        return output

    # ── Auto-detection helpers ───────────────────────────────────────────

    @staticmethod
    def detect_version(binary_path: str) -> str:
        """Try to extract a version string from the binary."""
        try:
            raw = subprocess.check_output(
                ["strings", binary_path], stderr=subprocess.DEVNULL, timeout=30
            ).decode("utf-8", errors="replace")
        except Exception:
            return ""

        versions = re.findall(r"^(\d+\.\d+(?:\.\d+){0,2})$", raw, re.MULTILINE)
        if not versions:
            return ""
        # Sort and pick the highest
        versions.sort(key=lambda v: list(map(int, v.split("."))))
        return versions[-1]

    @staticmethod
    def detect_arch(binary_path: str) -> str:
        """Detect architecture from ELF binary."""
        try:
            out = subprocess.check_output(
                ["file", binary_path], stderr=subprocess.DEVNULL, timeout=10
            ).decode()
        except Exception:
            return "x86_64"
        if "x86-64" in out or "x86_64" in out:
            return "x86_64"
        if "aarch64" in out or "ARM aarch64" in out:
            return "aarch64"
        if "ARM" in out:
            return "armhf"
        if "80386" in out:
            return "i686"
        return "x86_64"

    @staticmethod
    def list_libraries(binary_path: str) -> List[str]:
        """Return a list of shared libraries the binary depends on."""
        try:
            out = subprocess.check_output(
                ["ldd", binary_path], stderr=subprocess.DEVNULL, timeout=30
            ).decode("utf-8", errors="replace")
        except Exception:
            return []
        libs = []
        for line in out.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[1] == "=>":
                path = parts[2]
                if path.startswith("/"):
                    libs.append(path)
        return libs

    # ── Private build steps ──────────────────────────────────────────────

    def _prepare_tools(self):
        self._tools_dir = Path(self.cfg.output_dir) / ".appimage-tools"
        self._tools_dir.mkdir(parents=True, exist_ok=True)

        self._appimagetool = self._tools_dir / "appimagetool-x86_64.AppImage"
        self._linuxdeploy = self._tools_dir / "linuxdeploy-x86_64.AppImage"

        for tool_path, url in [
            (self._appimagetool, APPIMAGETOOL_URL),
            (self._linuxdeploy, LINUXDEPLOY_URL),
        ]:
            if not tool_path.exists():
                self._log(f"Downloading {tool_path.name} …")
                urllib.request.urlretrieve(url, str(tool_path))
                tool_path.chmod(tool_path.stat().st_mode | stat.S_IEXEC)

    def _create_appdir(self):
        appdir = Path(self.cfg.output_dir) / f"{self.cfg.safe_name}.AppDir"
        if appdir.exists():
            shutil.rmtree(appdir)
        for sub in [
            "usr/bin",
            "usr/lib",
            "usr/share/applications",
            "usr/share/metainfo",
            "usr/share/pixmaps",
        ]:
            (appdir / sub).mkdir(parents=True, exist_ok=True)
        # icon directories
        for size in ICON_SIZES:
            (appdir / f"usr/share/icons/hicolor/{size}/apps").mkdir(parents=True, exist_ok=True)
        self._appdir = appdir

    def _copy_assets(self):
        appdir = self._appdir
        cfg = self.cfg

        # Binary
        dest_bin = appdir / "usr" / "bin" / cfg.safe_name
        shutil.copy2(cfg.binary_path, str(dest_bin))
        dest_bin.chmod(dest_bin.stat().st_mode | stat.S_IEXEC)

        # Icon
        if cfg.icon_path and os.path.isfile(cfg.icon_path):
            icon_ext = Path(cfg.icon_path).suffix.lower()
            icon_name = f"{cfg.safe_name.lower()}{icon_ext}"
            # root
            shutil.copy2(cfg.icon_path, str(appdir / icon_name))
            # pixmaps
            shutil.copy2(cfg.icon_path, str(appdir / "usr" / "share" / "pixmaps" / icon_name))
            # hicolor (put in 256x256 for raster, scalable for svg)
            if icon_ext == ".svg":
                target = appdir / "usr/share/icons/hicolor/scalable/apps" / icon_name
            else:
                target = appdir / "usr/share/icons/hicolor/256x256/apps" / icon_name
            shutil.copy2(cfg.icon_path, str(target))

        # Extra files → usr/share/<app>/
        if cfg.extra_files:
            share_data = appdir / "usr" / "share" / cfg.safe_name.lower()
            share_data.mkdir(parents=True, exist_ok=True)
            for fpath in cfg.extra_files:
                if os.path.isfile(fpath):
                    shutil.copy2(fpath, str(share_data / os.path.basename(fpath)))
                elif os.path.isdir(fpath):
                    shutil.copytree(fpath, str(share_data / os.path.basename(fpath)))

    def _desktop_icon_name(self) -> str:
        if self.cfg.icon_path:
            return self.cfg.safe_name.lower()
        return ""

    def _write_desktop_file(self):
        appdir = self._appdir
        cfg = self.cfg
        cats = ";".join(cfg.categories) + ";" if cfg.categories else ""
        content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            f"Name={cfg.app_name}\n"
            f"Comment={cfg.app_comment}\n"
            f"Exec={cfg.safe_name}\n"
            f"Icon={self._desktop_icon_name()}\n"
            "Type=Application\n"
            f"Categories={cats}\n"
            f"Terminal={'true' if cfg.use_terminal else 'false'}\n"
            "StartupNotify=true\n"
            f"X-AppImage-Version={cfg.app_version}\n"
        )
        desktop_file = appdir / f"{cfg.safe_name}.desktop"
        desktop_file.write_text(content)

    def _write_apprun(self):
        appdir = self._appdir
        cfg = self.cfg
        env_lines = ""
        for key, val in cfg.extra_env_vars.items():
            env_lines += f'export {key}="{val}"\n'

        content = (
            '#!/bin/bash\n'
            '# AppRun — generated by AppImage Builder GUI\n'
            '\n'
            'HERE="$(dirname "$(readlink -f "${0}")")"\n'
            '\n'
            'export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"\n'
            'export PATH="${HERE}/usr/bin:${PATH}"\n'
            'export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"\n'
            f'{env_lines}'
            '\n'
            f'BINARY="${{HERE}}/usr/bin/{cfg.safe_name}"\n'
            '\n'
            'if [[ ! -f "$BINARY" ]]; then\n'
            f'    echo "ERROR: {cfg.app_name} binary not found at: $BINARY" >&2\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'if [[ ! -x "$BINARY" ]]; then\n'
            '    chmod +x "$BINARY"\n'
            'fi\n'
            '\n'
            'exec "$BINARY" "$@"\n'
        )
        apprun = appdir / "AppRun"
        apprun.write_text(content)
        apprun.chmod(apprun.stat().st_mode | stat.S_IEXEC)

    def _write_appdata(self):
        appdir = self._appdir
        cfg = self.cfg
        build_date = date.today().isoformat()

        cats_xml = ""
        for cat in cfg.categories:
            cats_xml += f"    <category>{cat}</category>\n"

        description_p = cfg.app_description or cfg.app_comment or cfg.app_name
        homepage = ""
        if cfg.homepage_url:
            homepage = f'  <url type="homepage">{cfg.homepage_url}</url>\n'

        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<component type="desktop-application">\n'
            f'  <id>{cfg.rdns_id}</id>\n'
            f'  <name>{cfg.app_name}</name>\n'
            f'  <summary>{cfg.app_comment or cfg.app_name}</summary>\n'
            '  <description>\n'
            f'    <p>{description_p}</p>\n'
            '  </description>\n'
            f'{homepage}'
            '  <categories>\n'
            f'{cats_xml}'
            '  </categories>\n'
            '  <releases>\n'
            f'    <release version="{cfg.app_version}" date="{build_date}"/>\n'
            '  </releases>\n'
            '  <provides>\n'
            f'    <binary>{cfg.safe_name}</binary>\n'
            '  </provides>\n'
            '</component>\n'
        )
        meta_dir = appdir / "usr" / "share" / "metainfo"
        (meta_dir / f"{cfg.rdns_id}.appdata.xml").write_text(content)

    def _bundle_libraries(self):
        appdir = self._appdir
        cfg = self.cfg

        exclude_args = []
        for lib in cfg.exclude_libs:
            exclude_args += [f"--exclude-library={lib}*"]

        icon_args = []
        icon_name = self._desktop_icon_name()
        if icon_name:
            # find the icon file in appdir root
            for f in appdir.iterdir():
                if f.is_file() and f.stem == icon_name:
                    icon_args = ["--icon-file", str(f)]
                    break

        cmd = [
            str(self._linuxdeploy),
            "--appdir", str(appdir),
            "--executable", str(appdir / "usr" / "bin" / cfg.safe_name),
            "--desktop-file", str(appdir / f"{cfg.safe_name}.desktop"),
        ] + icon_args + exclude_args

        self._log(f"Running linuxdeploy …")
        env = os.environ.copy()
        env["NO_STRIP"] = "1"
        try:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=120
            )
            self._log(result.stdout[-2000:] if result.stdout else "")
            if result.returncode != 0:
                self._log(f"linuxdeploy warning (rc={result.returncode}), trying manual fallback …")
        except Exception as e:
            self._log(f"linuxdeploy failed: {e}. Falling back to manual copy …")

        # Manual fallback: copy libs that ldd reports
        self._log("Verifying bundled libraries …")
        for lib_path in self.list_libraries(cfg.binary_path):
            dest = appdir / "usr" / "lib" / os.path.basename(lib_path)
            if not dest.exists():
                self._log(f"  Copying: {lib_path}")
                shutil.copy2(lib_path, str(dest))

    def _patch_rpath(self):
        binary = self._appdir / "usr" / "bin" / self.cfg.safe_name
        try:
            subprocess.run(
                ["patchelf", "--set-rpath", "$ORIGIN/../lib:$ORIGIN/../../lib", str(binary)],
                capture_output=True, timeout=30,
            )
        except Exception as e:
            self._log(f"patchelf warning: {e}")

    def _package(self) -> str:
        cfg = self.cfg
        arch = self.detect_arch(cfg.binary_path)
        output = str(
            Path(cfg.output_dir) / f"{cfg.safe_name}-{cfg.app_version}-{arch}.AppImage"
        )

        env = os.environ.copy()
        env["ARCH"] = arch

        cmd = [str(self._appimagetool), str(self._appdir), output]
        self._log(f"Running appimagetool → {output}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"appimagetool failed (rc={result.returncode}):\n{result.stderr}"
            )
        self._log(result.stdout[-1000:] if result.stdout else "")
        return output
