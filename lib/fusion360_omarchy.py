"""Small, pinned Fusion/umu launcher. No installation or desktop registration."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import parse_qs, unquote, urlsplit
import uuid
import xml.etree.ElementTree as ET


RUNNER = "GE-Proton11-7-x86_64"
OVERLAY_TARGET = "files/lib/wine/x86_64-unix/winex11.so"
OVERLAY_ENVIRONMENT = {
    "WINE_X11_ARGB_SHAPE_INPUT": "1",
    "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
    # Qt Quick descendants select the main window's RHI backend. Keep normal
    # QWidget palettes on their raster path; forcing QWidget RHI breaks alpha.
    "QSG_RHI_BACKEND": "opengl",
}
OVERLAY_TARGETS_V2 = {OVERLAY_TARGET, "files/lib/wine/x86_64-unix/win32u.so"}
OVERLAY_ENVIRONMENT_V2 = {
    "WINE_X11_ARGB_SHAPE_INPUT": "1",
    "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
    "WINE_X11_VULKAN_PRESENT_WAIT": "1",
    "QSG_RHI_BACKEND": "d3d11",
}
OVERLAY_ENVIRONMENT_V3 = {**OVERLAY_ENVIRONMENT_V2, "QSG_RHI_BACKEND": "opengl"}
OVERLAY_PAIR_ENVIRONMENTS = {
    "ge-proton11-7-omarchy-x11-v2": OVERLAY_ENVIRONMENT_V2,
    "ge-proton11-7-omarchy-x11-v3": OVERLAY_ENVIRONMENT_V3,
}
IDENTITY_ARGS = ["--process_name", "Autodesk.IDSDK.DefaultProcess-v2",
                 "--server_name", "Autodesk.IDSDK.DefaultServer-v2"]
_STRING = re.compile(r'(@|"(?:\\.|[^"\\])*")="((?:\\.|[^"\\])*)"')
_EXE = re.compile(r'^\s*(?:"([^"]+\.exe)"|([^\s"]+\.exe))(?:\s|$)', re.I)


class LauncherError(Exception):
    """A safe, static message suitable for a desktop notification or stderr."""


@dataclass(frozen=True)
class Paths:
    state: Path
    runtime: Path

    @classmethod
    def default(cls) -> "Paths":
        data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        state = Path(os.environ.get("FUSION360_STATE", str(data / "fusion360-for-omarchy")))
        return cls(state.expanduser().resolve(), (data / "umu/steamrt4").resolve())

    @property
    def prefix(self) -> Path:
        return (self.state / "prefix").resolve()

    @property
    def runner(self) -> Path:
        return self.state / RUNNER

    @property
    def client(self) -> Path:
        return self.runtime / "pressure-vessel/bin/steam-runtime-launch-client"

    @property
    def bus(self) -> str:
        # This is umu 1.4.4's pathname identity, not a security hash.
        identity = hashlib.md5(str(self.prefix).encode(), usedforsecurity=False).hexdigest()
        return "com.steampowered.App" + identity

    @property
    def identity_log(self) -> Path:
        return self.prefix / "drive_c/users/steamuser/AppData/Local/Autodesk/Identity Services/Log/IdServices.log"


@dataclass
class IdentityReadiness:
    """A private, read-only cursor: only newly written SSO readiness counts."""

    path: Path
    started_at: float
    inode: tuple[int, int] | None = None
    offset: int = 0
    sentinel: bytes = b""
    pending: bytes = b""
    ready: bool = False

    @classmethod
    def snapshot(cls, path: Path) -> "IdentityReadiness":
        cursor = cls(path, time.time())
        try:
            with path.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                cursor.inode = (stat.st_dev, stat.st_ino)
                cursor.offset = stat.st_size
                stream.seek(max(0, cursor.offset - 64))
                cursor.sentinel = stream.read(64)
        except FileNotFoundError:
            pass
        return cursor

    def poll(self) -> bool:
        if self.ready:
            return True
        try:
            with self.path.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                inode = (stat.st_dev, stat.st_ino)
                replaced = inode != self.inode or stat.st_size < self.offset
                if not replaced and self.sentinel:
                    stream.seek(self.offset - len(self.sentinel))
                    replaced = stream.read(len(self.sentinel)) != self.sentinel
                if replaced:
                    self.offset, self.pending = 0, b""
                self.inode = inode
                stream.seek(self.offset)
                chunk = stream.read(1024 * 1024)
                self.offset = stream.tell()
                stream.seek(max(0, self.offset - 64))
                self.sentinel = stream.read(min(self.offset, 64))
        except FileNotFoundError:
            return False
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        for line in lines:
            if b"SSO Server is ready" not in line:
                continue
            try:
                stamp = datetime.fromisoformat(line.split(b" ", 1)[0].decode("ascii"))
                if stamp.tzinfo is not None and stamp.timestamp() >= self.started_at:
                    self.ready = True
                    return True
            except (ValueError, UnicodeError):
                continue
        return False


def _unescape(value: str) -> str:
    escapes = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}
    return re.sub(r'\\([\\"nrt])', lambda m: escapes[m[1]], value)


def read_registry(prefix: Path) -> dict[str, dict[str, str]]:
    """Read string values only; HKCU takes precedence over HKLM."""
    result: dict[str, dict[str, str]] = {}
    for name in ("system.reg", "user.reg"):
        path = prefix / name
        if not path.is_file():
            continue
        section = ""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("[") and "]" in line:
                section = _unescape(line[1:line.index("]")]).casefold()
            elif section and (match := _STRING.fullmatch(line)):
                key = "@" if match[1] == "@" else _unescape(match[1][1:-1]).casefold()
                result.setdefault(section, {})[key] = _unescape(match[2])
    return result


def windows_executable(prefix: Path, command: str, expected: str) -> Path:
    """Resolve a registered executable; never execute registry command tails."""
    match = _EXE.match(command)
    if not match:
        raise LauncherError("The application registration has no valid executable.")
    windows = PureWindowsPath(match[1] or match[2])
    if windows.drive.casefold() != "c:" or not windows.root:
        raise LauncherError("The registered executable is outside this installation.")
    if windows.name.casefold() != expected.casefold() or ".." in windows.parts:
        raise LauncherError("The application registration has an unexpected target.")
    root = (prefix / "drive_c").resolve()
    path = root
    for part in windows.parts[1:]:
        candidate = path / part
        if not candidate.exists() and path.is_dir():
            matches = [p for p in path.iterdir() if p.name.casefold() == part.casefold()]
            if len(matches) == 1:
                candidate = matches[0]
        path = candidate
    path = path.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise LauncherError("The registered application executable is missing.")
    return path


def resolve_targets(paths: Paths) -> dict[str, Path | str]:
    registry = read_registry(paths.prefix)
    fusion_key = r"Software\Classes\f3d_file\shell\open\command".casefold()
    command = registry.get(fusion_key, {}).get("@")
    if not command:
        raise LauncherError("Fusion has not registered a current installation in this prefix.")
    fusion = windows_executable(paths.prefix, command, "Fusion360.exe")
    result: dict[str, Path | str] = {"fusion": fusion}
    identity_key = r"Software\Classes\adskidmgr\shell\open\command".casefold()
    identity_command = registry.get(identity_key, {}).get("@")
    if identity_command:
        result["identity"] = windows_executable(paths.prefix, identity_command, "AdskIdentityManager.exe")
        result["identity_source"] = "registered"
    else:
        # Identity Manager registers its protocol on first start. Stay in the
        # current registered Fusion build, even when older builds remain.
        identity = fusion.parent / "Autodesk Identity Manager/AdskIdentityManager.exe"
        if identity.is_file() and identity.resolve().is_relative_to(fusion.parent.resolve()):
            result["identity"] = identity.resolve()
            result["identity_source"] = "registered-fusion-build"
    launcher_key = r"Software\Classes\fusion360\shell\open\command".casefold()
    if launcher_command := registry.get(launcher_key, {}).get("@"):
        result["uri_launcher"] = windows_executable(paths.prefix, launcher_command, "NLauncher.exe")
    for section, values in registry.items():
        if "\\currentversion\\uninstall\\" not in section:
            continue
        if values.get("displayname") == "Autodesk Fusion":
            modify = values.get("modifypath", "")
            try:
                if windows_executable(paths.prefix, modify, "Fusion360.exe") == fusion:
                    result["version"] = values.get("displayversion", "unknown")
            except LauncherError:
                pass
    return result


def compatibility_lock(paths: Paths) -> dict:
    lock_path = paths.state / "compatibility-lock.json"
    if not lock_path.is_file():
        lock_path = Path(__file__).resolve().parent.parent / "compatibility-lock.json"
    try:
        lock = json.loads(lock_path.read_text())
        if (lock.get("schema") != 1 or lock["runner"]["name"] != RUNNER
                or not isinstance(lock["launcher"]["version"], str)
                or not isinstance(lock["steam_runtime"]["version"], str)):
            raise ValueError
        return lock
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LauncherError("The reviewed compatibility lock is missing or invalid.") from None


def overlay_modules(overlay: dict) -> list[dict]:
    """Normalize a validated legacy or two-module overlay without changing its identity."""
    if "modules" in overlay:
        return overlay["modules"]
    return [{key: overlay[key] for key in ("target", "original_sha256", "sha256")}]


def overlay_identity(overlay: dict) -> str:
    if "modules" not in overlay:
        return overlay["sha256"]
    identity = {"id": overlay["id"], "required_environment": overlay["required_environment"],
                "modules": sorted(({key: module[key] for key in ("target", "sha256")}
                                   for module in overlay_modules(overlay)), key=lambda item: item["target"])}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def runner_overlay(paths: Paths, lock: dict | None = None) -> dict | None:
    """Read the explicitly reviewed source manifest; never infer a patch from a filename."""
    lock = compatibility_lock(paths) if lock is None else lock
    if "runner_overlay" not in lock:
        return None
    overlay = lock["runner_overlay"]
    try:
        if not isinstance(overlay, dict) or overlay["manifest"] != "runtime-patches/manifest.json":
            raise ValueError
        if "modules" in overlay:
            keys = ("id", "modules", "required_environment")
            schema = 2
            if (set(overlay) != {*keys, "manifest"} or overlay["id"] not in OVERLAY_PAIR_ENVIRONMENTS
                    or overlay["required_environment"] != OVERLAY_PAIR_ENVIRONMENTS[overlay["id"]]
                    or not isinstance(overlay["modules"], list) or len(overlay["modules"]) != 2
                    or any(not isinstance(module, dict)
                           or set(module) != {"target", "original_sha256", "sha256"}
                           for module in overlay["modules"])
                    or {module["target"] for module in overlay["modules"]} != OVERLAY_TARGETS_V2):
                raise ValueError
        else:
            keys = ("id", "target", "original_sha256", "sha256", "required_environment")
            schema = 1
            if (set(overlay) != {*keys, "manifest"} or overlay["id"] != "ge-proton11-7-omarchy-x11-v1"
                    or overlay["target"] != OVERLAY_TARGET
                    or overlay["required_environment"] != OVERLAY_ENVIRONMENT):
                raise ValueError
        if any(not re.fullmatch(r"[0-9a-f]{64}", module[key])
               for module in overlay_modules(overlay) for key in ("original_sha256", "sha256")):
            raise ValueError
        manifest_path = paths.state / overlay["manifest"]
        if not manifest_path.is_file():
            manifest_path = Path(__file__).resolve().parent.parent / overlay["manifest"]
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("schema") != schema or any(manifest[key] != overlay[key] for key in keys):
            raise ValueError
        return overlay
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LauncherError("The reviewed runner overlay manifest is missing or invalid.") from None


def validate_overlay(paths: Paths, overlay: dict | None) -> None:
    if overlay is None:
        return
    try:
        for module in overlay_modules(overlay):
            target = paths.runner / module["target"]
            if target.is_symlink() or not target.resolve().is_relative_to(paths.runner.resolve()):
                raise ValueError
            with target.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != module["sha256"]:
                raise ValueError
    except (OSError, ValueError):
        raise LauncherError("The required Fusion runner overlay is missing or changed. Repair the installation before launching.") from None


def overlay_session_environment(overlay: dict | None) -> dict[str, str]:
    if overlay is None:
        return {}
    return {**overlay["required_environment"], "FUSION360_OVERLAY_ID": overlay["id"],
            "FUSION360_OVERLAY_SHA256": overlay_identity(overlay)}


def matches_overlay_environment(required: dict[str, str], actual: dict[bytes, bytes]) -> bool:
    # The tested pair uses DXVK's defaults. Older experiments must not retain
    # inline overrides or a file imposing a frame cap or other renderer option.
    if (required.get("FUSION360_OVERLAY_ID") in OVERLAY_PAIR_ENVIRONMENTS
            and any(actual.get(key) for key in (b"DXVK_CONFIG", b"DXVK_CONFIG_FILE"))):
        return False
    return all(actual.get(key.encode()) == value.encode() for key, value in required.items())


def clean_environment(paths: Paths) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        # Wine discards host QT_* variables but imports WINEQT_* after removing
        # the WINE prefix (ntdll/unix/env.c:get_initial_environment). Clear both
        # forms so host toolkit preferences cannot change Fusion's Windows Qt.
        if key.startswith(("WINE_X11_", "WINE_LAYERED_", "QT_", "WINEQT_", "QSG_")):
            env.pop(key)
    for key in (
        "LD_LIBRARY_PATH", "LD_PRELOAD", "LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER",
        "MESA_LOADER_DRIVER_OVERRIDE", "VK_ICD_FILENAMES", "VK_DRIVER_FILES",
        "__GLX_VENDOR_LIBRARY_NAME", "DXVK_ASYNC", "DXVK_CONFIG", "DXVK_CONFIG_FILE", "UMU_LOG", "UMU_NO_RUNTIME",
        "UMU_NO_PROTON", "UMU_USE_STEAM", "PROTON_VERB", "RUNTIMEPATH",
        "STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
        "STEAM_COMPAT_LAUNCHER_SERVICE", "SteamAppId", "SteamGameId",
        "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "QTWEBENGINE_CHROMIUM_FLAGS",
        "QTWEBENGINE_DISABLE_SANDBOX",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "FUSION360_OVERLAY_ID", "FUSION360_OVERLAY_SHA256",
    ):
        env.pop(key, None)
    env.update({
        "WINEPREFIX": str(paths.prefix),
        "PROTONPATH": str(paths.runner),
        "GAMEID": "umu-fusion360",
        "UMU_CONTAINER_NSENTER": "1",
        "UMU_RUNTIME_UPDATE": "0",
        "PROTON_USE_WINED3D": "0",
        "PROTON_USE_WAYLAND": "0",
        "PROTON_ENABLE_WAYLAND": "0",
        "PROTON_USE_XALIA": "0",
        "NO_AT_BRIDGE": "1",
        "WINEDLLOVERRIDES": "bcp47langs=",
        "PROTON_LOG": "0",
        "WINEDEBUG": "-all",
    })
    env.update(overlay_session_environment(runner_overlay(paths)))
    return env


def validate_runtime(paths: Paths, require_container: bool = True) -> None:
    umu = shutil.which("umu-run")
    if not umu:
        raise LauncherError("umu-launcher is not installed.")
    lock = compatibility_lock(paths)
    expected_umu = lock["launcher"]["version"]
    expected_runtime = lock["steam_runtime"]["version"]
    validate_overlay(paths, runner_overlay(paths, lock))
    try:
        result = subprocess.run([umu, "--version"], capture_output=True, text=True,
                                timeout=5, env=clean_environment(paths), check=False)
    except (OSError, subprocess.SubprocessError):
        raise LauncherError("The installed umu-launcher version could not be checked.") from None
    actual_umu = re.search(r"^umu-launcher version (\S+)", result.stdout)
    if result.returncode or not actual_umu or actual_umu[1] != expected_umu:
        raise LauncherError("umu-launcher differs from the reviewed version. Review the update before launching Fusion.")
    version = paths.runner / "version"
    if not version.is_file() or "GE-Proton11-7" not in version.read_text():
        raise LauncherError("The pinned GE-Proton11-7 runner is missing.")
    manifest = paths.runner / "toolmanifest.vdf"
    if not manifest.is_file() or '"4183110"' not in manifest.read_text():
        raise LauncherError("The runner does not declare Steam Linux Runtime 4.0.")
    if require_container and not paths.client.is_file():
        raise LauncherError("The required Steam Linux Runtime 4.0 is not installed.")
    runtime_versions = paths.runtime / "VERSIONS.txt"
    if require_container or runtime_versions.is_file():
        try:
            versions = dict((parts[0], parts[1]) for line in runtime_versions.read_text().splitlines()
                            if len(parts := line.split()) >= 2 and not line.startswith("#"))
        except OSError:
            raise LauncherError("The Steam runtime build could not be checked.") from None
        if versions.get("depot") != expected_runtime or versions.get("steamrt4") != expected_runtime:
            raise LauncherError("Steam Linux Runtime differs from the reviewed build. Review the update before launching Fusion.")


def active_bus(paths: Paths) -> bool:
    if not paths.client.is_file():
        return False
    try:
        result = subprocess.run([str(paths.client), "--list"], capture_output=True,
                                text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and f"--bus-name={paths.bus}" in result.stdout.splitlines()


def process_argv0(proc: Path) -> str:
    """Read just the executable field, never an authentication URL or other arguments."""
    first = bytearray()
    with (proc / "cmdline").open("rb") as stream:
        while len(first) < 4096:
            byte = stream.read(1)
            if byte in {b"", b"\0"}:
                return os.fsdecode(bytes(first))
            first.extend(byte)
    raise OSError("Process executable field is too long")


def process_metadata_root(proc: Path, excluded: set[Path] | None = None) -> Path:
    """A terminated group leader can still have live Wine threads and an mm."""
    excluded = excluded or set()
    try:
        status = (proc / "status").read_text().splitlines()
        if proc not in excluded and not any(line.startswith("State:") and line.split()[1] == "Z" for line in status):
            return proc
        for thread in (proc / "task").iterdir():
            if thread in excluded:
                continue
            try:
                state = (thread / "status").read_text().splitlines()
                if any(line.startswith("State:") and line.split()[1] != "Z" for line in state):
                    return thread
            except (FileNotFoundError, ProcessLookupError):
                continue
    except (FileNotFoundError, ProcessLookupError):
        pass
    return proc


def _inspect_prefix_process(paths: Paths, proc: Path, read):
    """Retry a vanished worker without forgetting a previously matched TGID."""
    matched = False
    excluded: set[Path] = set()
    for _ in range(3):
        metadata = None
        try:
            metadata = process_metadata_root(proc, excluded)
            env = dict(entry.split(b"=", 1) for entry in (metadata / "environ").read_bytes().split(b"\0")
                       if b"=" in entry)
            if metadata != proc and not env:
                raise FileNotFoundError("Worker environment disappeared")
            prefix = env.get(b"WINEPREFIX") or env.get(b"STEAM_COMPAT_DATA_PATH")
            if not prefix or Path(os.fsdecode(prefix)).resolve() != paths.prefix:
                if matched:
                    raise OSError("Process identity changed while reading metadata")
                return None
            matched = True
            result = read(metadata, env)
            if metadata != proc:
                state = (metadata / "status").read_text().splitlines()
                if not any(line.startswith("State:") and line.split()[1] != "Z" for line in state):
                    raise ProcessLookupError("Worker exited while reading metadata")
            return result
        except (OSError, ValueError, StopIteration) as error:
            if not proc.exists():
                return None  # The whole thread group exited, not only our reader.
            if not matched and not isinstance(error, (FileNotFoundError, ProcessLookupError)):
                return None
            if metadata is not None:
                excluded.add(metadata)
    if matched:
        raise LauncherError("A Fusion background process could not be checked; its runtime was left running.") from None
    return None


def active_processes(paths: Paths, proc_root: Path = Path("/proc")) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {"fusion": [], "identity": []}
    required = overlay_session_environment(runner_overlay(paths))
    def read(metadata: Path, env: dict[bytes, bytes]):
        name = (metadata / "comm").read_text().strip().casefold()
        # CEF renames Fusion's main thread CrBrowserMain. The Windows
        # executable in argv[0] remains usable; do not read/log other args.
        executable = process_argv0(metadata).replace("\\", "/").rsplit("/", 1)[-1].strip('"').casefold()
        kind = "fusion" if executable == "fusion360.exe" or name.startswith("fusion360") else (
            "identity" if executable == "adskidentitymanager.exe" or name.startswith("adskidentity") else None)
        runner = Path(os.fsdecode(env.get(b"PROTONPATH", b"/nonexistent"))).resolve()
        if (runner == paths.runner.resolve()
                and matches_overlay_environment(required, env)):
            return kind
        return None
    for proc in proc_root.iterdir():
        if not proc.name.isdigit():
            continue
        if kind := _inspect_prefix_process(paths, proc, read):
            result[kind].append(int(proc.name))
    return result


def mapped_file_identity(path: Path) -> tuple[int, int, int]:
    """Read the kernel's mapping identity, which can differ from stat() on Btrfs."""
    # Btrfs getattr returns a subvolume device while /proc/maps reports the
    # backing superblock device. Compare maps with maps, retaining device+inode
    # checks. ACCESS_COPY permits taking the address without modifying the file;
    # this maps one byte privately, executes nothing, and closes immediately.
    with path.open("rb") as stream:
        with mmap.mmap(stream.fileno(), 1, access=mmap.ACCESS_COPY) as mapping:
            address = ctypes.addressof(ctypes.c_ubyte.from_buffer(mapping))
            for line in Path("/proc/self/maps").read_text().splitlines():
                fields = line.split(None, 5)
                start, end = (int(part, 16) for part in fields[0].split("-"))
                if start <= address < end:
                    if (len(fields) < 6 or fields[5].endswith(" (deleted)")
                            or int(fields[4]) != os.fstat(stream.fileno()).st_ino):
                        break
                    major, minor = (int(part, 16) for part in fields[3].split(":"))
                    return major, minor, int(fields[4])
    raise OSError("The runner module mapping identity could not be verified")


def session_conflict(paths: Paths, proc_root: Path = Path("/proc")) -> bool:
    """Reject an older/experimental runtime even when it has the same prefix bus name."""
    overlay = runner_overlay(paths)
    required = overlay_session_environment(overlay)
    module_identities = {}
    if overlay:
        try:
            module_identities = {Path(module["target"]).name: mapped_file_identity(paths.runner / module["target"])
                                 for module in overlay_modules(overlay)}
        except (OSError, ValueError):
            return True
    def read(metadata: Path, env: dict[bytes, bytes]) -> bool:
        runner = Path(os.fsdecode(env.get(b"PROTONPATH", b"/nonexistent"))).resolve()
        if (runner != paths.runner.resolve()
                or not matches_overlay_environment(required, env)):
            return True
        if module_identities:
            # A replacement can have the correct pathname/hash on disk while
            # an existing process still maps the old inode. Never attach to it.
            for line in (metadata / "maps").read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) < 6 or "/x86_64-unix/" not in fields[5]:
                    continue
                module_identity = module_identities.get(Path(fields[5].removesuffix(" (deleted)")).name)
                if module_identity is None:
                    continue
                device = tuple(int(part, 16) for part in fields[3].split(":"))
                if (fields[5].endswith(" (deleted)")
                        or (*device, int(fields[4])) != module_identity):
                    return True
        return False
    for proc in proc_root.iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if _inspect_prefix_process(paths, proc, read):
                return True
        except LauncherError:
            return True
    return False


def require_compatible_session(paths: Paths) -> None:
    if session_conflict(paths):
        raise LauncherError("A different Fusion runtime is still active. Close Fusion and its runtime, then launch it again.")


def runtime_owner(paths: Paths, proc_root: Path = Path("/proc")) -> int:
    """Resolve the exact bus to its host PID and verify the container's initial environment."""
    busctl = shutil.which("busctl")
    if not busctl:
        raise LauncherError("The Fusion runtime owner cannot be verified because busctl is unavailable.")
    try:
        result = subprocess.run([busctl, "--user", "call", "org.freedesktop.DBus",
                                 "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                 "GetConnectionUnixProcessID", "s", paths.bus],
                                capture_output=True, text=True, timeout=5, check=False)
        match = re.fullmatch(r"u ([1-9][0-9]*)\s*", result.stdout)
        if result.returncode or not match:
            raise ValueError
        pid = int(match[1])
        proc = proc_root / str(pid)
        if Path(process_argv0(proc)).name != "x86_64-linux-gnu-srt-launcher-service":
            raise ValueError
        env = dict(entry.split(b"=", 1) for entry in (proc / "environ").read_bytes().split(b"\0")
                   if b"=" in entry)
        required = overlay_session_environment(runner_overlay(paths))
        if (Path(os.fsdecode(env.get(b"WINEPREFIX", b"/nonexistent"))).resolve() != paths.prefix
                or Path(os.fsdecode(env.get(b"PROTONPATH", b"/nonexistent"))).resolve() != paths.runner.resolve()
                or env.get(b"UMU_CONTAINER_NSENTER") != b"1"
                or not matches_overlay_environment(required, env)):
            raise ValueError
        return pid
    except (OSError, ValueError, subprocess.SubprocessError):
        raise LauncherError("The active Fusion runtime has an unverified owner. Close its runtime and launch again.") from None


def require_session(paths: Paths) -> None:
    validate_overlay(paths, runner_overlay(paths))
    require_compatible_session(paths)
    if not active_bus(paths) or not any(active_processes(paths).values()):
        raise LauncherError("No matching Fusion session is running. Open Fusion and retry sign-in.")


def validate_auth_uri(uri: str) -> str:
    if len(uri) > 32768 or any(ord(c) <= 32 or ord(c) == 127 for c in uri):
        raise LauncherError("Invalid Autodesk authentication callback.")
    try:
        parsed = urlsplit(uri)
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=16)
    except ValueError:
        raise LauncherError("Invalid Autodesk authentication callback.") from None
    if (parsed.scheme != "adskidmgr" or parsed.netloc or parsed.path != "/login"
            or parsed.fragment or set(query) != {"code", "state"}
            or any(len(values) != 1 or not values[0]
                   or any(ord(c) < 32 or ord(c) == 127 for c in values[0])
                   for values in query.values())):
        raise LauncherError("Invalid Autodesk authentication callback.")
    # URI content is passed as one argument, never interpolated or logged.
    return uri


def attach_command(paths: Paths, target: Path, arguments: list[str]) -> list[str]:
    overlay_options = ["--unset-env=DXVK_CONFIG", "--unset-env=DXVK_CONFIG_FILE",
                       *(f"--pass-env={key}" for key in overlay_session_environment(runner_overlay(paths)))]
    return [str(paths.client), f"--bus-name={paths.bus}",
            f"--directory={target.parent}", "--pass-env=PROTON_LOG",
            "--pass-env=WINEDEBUG", *overlay_options, "--", str(paths.runner / "proton"),
            "runinprefix", str(target), *arguments]


def attach(paths: Paths, target: Path, arguments: list[str]) -> int:
    require_session(paths)
    # Unlike umu's retry/fallback behavior, a vanished bus fails here; it can
    # never cause an authentication callback to launch a fresh container.
    return subprocess.call(attach_command(paths, target, arguments),
                           env=clean_environment(paths), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


def authenticate(paths: Paths, uri: str) -> int:
    validate_auth_uri(uri)
    validate_runtime(paths)
    targets = resolve_targets(paths)
    identity = targets.get("identity")
    if not isinstance(identity, Path):
        raise LauncherError("Identity Manager is not installed for the current Fusion build.")
    return attach(paths, identity, [uri])


def _focus(pids: list[int]) -> None:
    if pids and shutil.which("hyprctl"):
        try:
            result = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True,
                                    text=True, timeout=3, check=False)
            for client in json.loads(result.stdout):
                address = client.get("address", "")
                if client.get("pid") in pids and re.fullmatch(r"0x[0-9a-fA-F]+", address):
                    expression = 'hl.dispatch(hl.dsp.focus({window="address:' + address + '"}))'
                    subprocess.run(["hyprctl", "eval", expression],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=3, check=False)
                    return
        except (OSError, ValueError, subprocess.SubprocessError):
            pass


def windows_file_argument(paths: Paths, filename: str) -> str:
    if filename.casefold().startswith("file:"):
        # Desktop entries using %U receive local file URIs. Convert them here;
        # Fusion still receives the same verified C:/Z: path as a normal file.
        try:
            uri = urlsplit(filename)
            if (uri.netloc.casefold() not in {"", "localhost"} or not uri.path.startswith("/")
                    or "?" in filename or "#" in filename
                    or any(ord(char) < 32 or ord(char) == 127 for char in filename)):
                raise ValueError
            filename = unquote(uri.path, errors="strict")
            if any(ord(char) < 32 or ord(char) == 127 for char in filename):
                raise ValueError
        except (ValueError, UnicodeError):
            raise LauncherError("Only a local file URI without query or fragment is supported.") from None
    file = Path(filename).expanduser().resolve()
    if not file.is_file():
        raise LauncherError("The requested design file does not exist.")
    if any(re.search(r'[<>:"|?*\\]', part) for part in file.parts[1:]):
        raise LauncherError("The design filename contains characters Windows cannot address.")
    c_drive = (paths.prefix / "drive_c").resolve()
    if file.is_relative_to(c_drive):
        return str(PureWindowsPath("C:\\", *file.relative_to(c_drive).parts))
    z_drive = paths.prefix / "dosdevices/z:"
    if not z_drive.is_dir():
        raise LauncherError("The installation's Windows file mapping is unavailable.")
    z_root = z_drive.resolve()
    if not file.is_relative_to(z_root):
        raise LauncherError("The design file is outside the installation's Windows file mapping.")
    return str(PureWindowsPath("Z:\\", *file.relative_to(z_root).parts))


def _acquire_lock(path: Path, operation: int) -> int:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def launch_workspace() -> str | None:
    """Capture the invoking Hyprland workspace once, before slow startup work."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or not shutil.which("hyprctl"):
        return None
    try:
        result = subprocess.run(["hyprctl", "-j", "activeworkspace"], capture_output=True,
                                text=True, timeout=3, check=True)
        workspace = json.loads(result.stdout)
        name = workspace.get("name", "")
        if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
            return name
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def anchor_startup(paths: Paths, workspace: str | None) -> tuple[str, str] | None:
    """Temporary, silent placement for new Fusion windows only.

    Omarchy disables general launch workspace tracking. This named rule expires
    when a unique main window and its MessageTray map, or after two minutes if launch fails. Later
    children use the persistent same-process group hook. Existing Fusion windows
    anywhere cause this helper to leave compositor placement alone.
    """
    if workspace is None:
        return None
    name = "fusion360-startup-" + hashlib.sha256(str(paths.prefix).encode()).hexdigest()[:16]
    token = uuid.uuid4().hex
    expression = '''do
      _G.fusion360_startups = _G.fusion360_startups or {}
      local slots = _G.fusion360_startups
      if slots[NAME] then slots[NAME].finish() end
      local existing = hl.get_windows({class="steam_app_fusion360",mapped=true})
      if #existing > 0 then return end
      local rule = hl.window_rule({name=NAME,match={class="^steam_app_fusion360$",xwayland=true},workspace=WORKSPACE})
      local subscriptions, timer = {}, nil
      local slot = {token=TOKEN}
      local done = false
      local function finish()
        if done then return end
        done=true
        for _, subscription in ipairs(subscriptions) do subscription:remove() end
        if timer then timer:set_enabled(false) end
        -- A delayed callback must never disable a newer launch's named rule.
        if slots[NAME] == slot then rule:set_enabled(false);slots[NAME]=nil end
      end
      slot.finish=finish;slots[NAME]=slot
      local function ready(event, closing)
        if done or not event or not event.xwayland or event.class~="steam_app_fusion360" then return end
        local mains, tray = 0, false
        for _, window in ipairs(hl.get_windows({class="steam_app_fusion360",mapped=true})) do
          if window.mapped and window.xwayland and window.class=="steam_app_fusion360"
              and window.pid==event.pid and (not closing or window.address~=event.address) then
            local title=window.initial_title
            if type(title)=="string" then
              if title:match("^%s*(.-)%s*$")=="Autodesk Fusion" then mains=mains+1 end
              if title:match("^Msg:QTView:.*MessageTray$") then tray=true end
            end
          end
        end
        -- The splash and real main share a title and can coexist. A unique
        -- main plus its UI tray proves readiness without a whitespace guess.
        if mains==1 and tray then finish() end
      end
      subscriptions[1]=hl.on("window.open",function(w) ready(w, false) end)
      subscriptions[2]=hl.on("window.close",function(w) ready(w, true) end)
      timer=hl.timer(finish,{timeout=120000,type="oneshot"})
    end'''.replace("NAME", json.dumps(name)).replace("TOKEN", json.dumps(token)).replace("WORKSPACE", json.dumps(workspace + " silent"))
    result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True, timeout=5)
    if result.returncode or result.stdout.strip() != "ok":
        raise LauncherError("Fusion could not reserve its launch workspace; Hyprland rejected its startup rule.")
    return name, token


def release_startup_anchor(anchor: tuple[str, str] | None) -> None:
    if anchor is None:
        return
    name, token = anchor
    expression = ("do local slots=_G.fusion360_startups;local slot=slots and slots[" + json.dumps(name)
                  + "];if slot and slot.token==" + json.dumps(token) + " then slot.finish() end end")
    try:
        subprocess.run(["hyprctl", "eval", expression],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass # Compositor timer/reload also removes the temporary placement.


def launch(paths: Paths, argument: str | None = None, prestart_identity: bool = True) -> int:
    """Coordinate with prefix maintenance and serialize all cold startups."""
    origin = launch_workspace()
    validate_runtime(paths)
    try:
        maintenance_lock = _acquire_lock(paths.state / ".maintenance.lock", fcntl.LOCK_SH)
    except BlockingIOError:
        raise LauncherError("Fusion maintenance is in progress. Try launching again when it finishes.") from None
    def release_maintenance() -> None:
        nonlocal maintenance_lock
        if maintenance_lock is not None:
            os.close(maintenance_lock)
            maintenance_lock = None
    try:
        deadline = time.monotonic() + 45
        while True:
            try:
                startup_lock = _acquire_lock(paths.state / ".launch.lock", fcntl.LOCK_EX)
            except BlockingIOError:
                # Another launcher owns initialization. Once its Fusion process
                # exists, this call may focus/open a file in that session only.
                if active_processes(paths)["fusion"] and active_bus(paths):
                    return _launch(paths, argument, prestart_identity, allow_cold_start=False,
                                   on_session_ready=release_maintenance)
                if time.monotonic() >= deadline:
                    raise LauncherError("Fusion is already starting. Wait for it to finish starting.") from None
                time.sleep(0.2)
            else:
                anchor = None
                try:
                    if origin is not None and not active_processes(paths)["fusion"]:
                        anchor = anchor_startup(paths, origin)
                    return _launch(paths, argument, prestart_identity, on_session_ready=release_maintenance)
                finally:
                    release_startup_anchor(anchor)
                    os.close(startup_lock)
    finally:
        release_maintenance()


def _launch(paths: Paths, argument: str | None = None, prestart_identity: bool = True,
            *, allow_cold_start: bool = True, on_session_ready=None) -> int:
    validate_runtime(paths)
    require_compatible_session(paths)
    targets = resolve_targets(paths)
    fusion = targets["fusion"]
    assert isinstance(fusion, Path)
    target = fusion
    arguments: list[str] = []
    if argument:
        if argument.casefold().startswith("fusion360:"):
            if any(ord(c) < 32 for c in argument) or len(argument) > 32768:
                raise LauncherError("Invalid Fusion URI.")
            target = targets.get("uri_launcher", fusion)
            assert isinstance(target, Path)
            arguments = [argument]
        else:
            # Proton forwards application arguments unchanged. Give Fusion a
            # Windows path through the prefix's actual C:/Z: mappings.
            arguments = [windows_file_argument(paths, argument)]
    processes = active_processes(paths)
    if any(processes.values()):
        if not active_bus(paths):
            raise LauncherError("Fusion is running without its callback bridge. Close it and relaunch.")
        if on_session_ready:
            on_session_ready()
        if processes["fusion"] and not argument:
            _focus(processes["fusion"])
            return 0
        return attach(paths, target, arguments)
    if not allow_cold_start:
        raise LauncherError("The Fusion session closed while the file was being opened. Try again.")
    idle_runtime = active_bus(paths)
    if idle_runtime:
        runtime_owner(paths)
    env = clean_environment(paths)
    command = [shutil.which("umu-run") or "/usr/bin/umu-run", str(target), *arguments]
    if prestart_identity:
        identity = targets.get("identity")
        if not isinstance(identity, Path):
            raise LauncherError("Identity Manager is not installed for the current Fusion build.")
        readiness = IdentityReadiness.snapshot(paths.identity_log)
        identity_command = (attach_command(paths, identity, IDENTITY_ARGS) if idle_runtime else
                            [command[0], str(identity), *IDENTITY_ARGS])
        helper = subprocess.Popen(identity_command, env=env, cwd=identity.parent,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if readiness.poll() and active_bus(paths) and active_processes(paths)["identity"]:
                if on_session_ready:
                    on_session_ready()
                return attach(paths, target, arguments)
            if helper.poll() is not None:
                break
            time.sleep(0.2)
        if helper.poll() is None:
            helper.terminate()
        raise LauncherError("Identity Manager did not report that its SSO server is ready.")
    if idle_runtime:
        command = attach_command(paths, target, arguments)
    process = subprocess.Popen(command, env=env, cwd=target.parent,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if active_processes(paths)["fusion"] and active_bus(paths):
            if on_session_ready:
                on_session_ready()
            return process.wait()
        if process.poll() is not None:
            return process.returncode
        time.sleep(0.2)
    process.terminate()
    raise LauncherError("Fusion did not establish its runtime session.")


def install_exe(paths: Paths, installer: str) -> int:
    validate_runtime(paths, require_container=False)
    file = Path(installer).expanduser().resolve()
    if not file.is_file() or file.suffix.casefold() != ".exe":
        raise LauncherError("The Autodesk Windows installer was not found.")
    if active_bus(paths) or any(active_processes(paths).values()):
        raise LauncherError("Close this installation's Fusion session before maintenance.")
    return subprocess.call([shutil.which("umu-run") or "/usr/bin/umu-run", str(file)],
                           env=clean_environment(paths), cwd=file.parent,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def configure_browser(paths: Paths, helper_path: str) -> int:
    """Change only WineBrowser's Browsers value through Wine's registry API."""
    validate_runtime(paths)
    require_compatible_session(paths)
    resolve_targets(paths)
    helper = Path(helper_path).expanduser().resolve()
    if (not helper.is_file() or not os.access(helper, os.X_OK)
            or '"' in str(helper) or any(ord(c) < 32 for c in str(helper))):
        raise LauncherError("The executable host browser helper was not found.")
    target = paths.prefix / "drive_c/windows/system32/reg.exe"
    if not target.is_file():
        raise LauncherError("Wine's registry utility was not found in this prefix.")
    arguments = ["add", r"HKCU\Software\Wine\WineBrowser", "/v", "Browsers",
                 "/t", "REG_SZ", "/d", f'"{helper}"', "/f"]
    if any(active_processes(paths).values()):
        return attach(paths, target, arguments)
    if active_bus(paths):
        raise LauncherError("A Fusion runtime is still active without its application. Close its runtime and retry.")
    return subprocess.call([shutil.which("umu-run") or "/usr/bin/umu-run", str(target), *arguments],
                           env=clean_environment(paths), cwd=paths.prefix,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def configure_host_folders(paths: Paths, _: str = "") -> int:
    """Expose host Documents/Downloads and start local browsing in the host home.

    Run explicitly in this installation's verified live session. Export only
    the three affected preference keys before changing them; never replace
    Wine profile directories or move the user's files.
    """
    validate_runtime(paths)
    require_session(paths)
    home = Path.home().resolve()
    z_drive = paths.prefix / "dosdevices/z:"
    if not z_drive.is_dir() or z_drive.resolve() != Path("/"):
        raise LauncherError("Host folder setup requires the installation's Z: filesystem mapping.")
    def folder(kind: str) -> Path:
        candidate = home / {"DOCUMENTS": "Documents", "DOWNLOAD": "Downloads"}[kind]
        if shutil.which("xdg-user-dir"):
            result = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=5)
            selected = Path(result.stdout.strip())
            if not result.returncode and selected.is_absolute() and selected.is_dir():
                candidate = selected.resolve()
        return candidate if candidate.is_dir() else home
    def windows(directory: Path) -> str:
        if any(re.search(r'[<>:"|?*\\]', part) for part in directory.parts[1:]):
            raise LauncherError("A host folder cannot be addressed with a Windows path.")
        return str(PureWindowsPath("Z:\\", *directory.parts[1:]))
    personal, downloads = windows(folder("DOCUMENTS")), windows(folder("DOWNLOAD"))
    target = paths.prefix / "drive_c/windows/system32/reg.exe"
    if not target.is_file():
        raise LauncherError("Wine's registry utility was not found in this prefix.")
    base = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer"
    keys = [base + r"\Shell Folders", base + r"\User Shell Folders",
            r"HKCU\Software\QtProject\OrganizationDefaults\FileDialog"]
    recovery = paths.state / "host-folders"
    if recovery.is_symlink():
        raise LauncherError("Host-folder recovery directory must not be a symlink.")
    recovery.mkdir(mode=0o700, exist_ok=True)
    recovery.chmod(0o700)
    saved = recovery / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(time.monotonic_ns()))
    saved.mkdir(mode=0o700)
    for index, key in enumerate(keys):
        exported = saved / (str(index) + ".reg")
        code = attach(paths, target, ["export", key, windows(exported), "/y"])
        if code:
            raise LauncherError("Host-folder preference backup failed; no preferences were changed.")
        exported.chmod(0o600)
    values = [(key, name, value) for key in keys[:2]
              for name, value in [("Personal", personal), ("{374DE290-123F-4565-9164-39C4925E467B}", downloads)]]
    values.append((keys[2], "lastVisited", "file:///Z:" + home.as_posix()))
    for key, name, value in values:
        if attach(paths, target, ["add", key, "/v", name, "/t", "REG_SZ", "/d", value, "/f"]):
            raise LauncherError("Host-folder setup stopped; prior preferences are preserved under host-folders.")
    return 0


def browser_command(uri: str, host_root: Path = Path("/run/host")) -> list[str]:
    if len(uri) > 32768 or any(ord(c) < 32 or ord(c) == 127 for c in uri):
        raise LauncherError("Invalid external browser URL.")
    try:
        parsed = urlsplit(uri)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
    except ValueError:
        raise LauncherError("Invalid external browser URL.") from None
    # /usr inside pressure-vessel is the runtime. Run the host executable with
    # its matching loader/libraries when reaching the host systemd user manager.
    if (host_root / "usr/bin/systemd-run").is_file():
        loader = host_root / "usr/lib/ld-linux-x86-64.so.2"
        if not loader.is_file():
            raise LauncherError("The host browser handoff is unavailable.")
        libraries = ":".join(str(host_root / subdir) for subdir in ("usr/lib", "usr/lib/systemd"))
        command = [str(loader), "--library-path", libraries,
                   str(host_root / "usr/bin/systemd-run")]
    elif shutil.which("systemd-run"):
        command = [shutil.which("systemd-run") or "/usr/bin/systemd-run"]
    else:
        raise LauncherError("The host browser handoff is unavailable.")
    return [*command, "--user", "--collect", "--quiet",
            "--expand-environment=no", "--service-type=exec",
            f"--unit=fusion360-browser-{uuid.uuid4().hex}",
            "--description=Fusion external browser", "--property=StandardOutput=null",
            "--property=StandardError=null", "--", "/usr/bin/xdg-open", uri]


def open_browser(uri: str) -> int:
    command = browser_command(uri)
    env = dict(os.environ)
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        env.pop(key, None)
    if command[0] == "/run/host/usr/lib/ld-linux-x86-64.so.2" and env.get("DBUS_SESSION_BUS_ADDRESS"):
        # pressure-vessel exposes the session bus, not systemd's private socket.
        # systemd 261.2 explicitly falls back to that public bus when only its
        # child environment lacks XDG_RUNTIME_DIR. The host service keeps the
        # user manager's normal desktop environment.
        # https://github.com/systemd/systemd/blob/v261.2/src/shared/bus-util.c#L523-L532
        env.pop("XDG_RUNTIME_DIR", None)
    return subprocess.call(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def status(paths: Paths) -> dict:
    errors: list[str] = []
    try:
        targets = resolve_targets(paths)
    except LauncherError as error:
        targets = {}
        errors.append(str(error))
    try:
        validate_runtime(paths)
        runtime_ready = True
    except LauncherError as error:
        runtime_ready = False
        errors.append(str(error))
    overlay = None
    overlay_verified = False
    try:
        overlay = runner_overlay(paths)
        validate_overlay(paths, overlay)
        overlay_verified = overlay is not None
        processes = active_processes(paths)
        conflict = session_conflict(paths)
        if conflict:
            errors.append("A different Fusion runtime is still active; close it before relaunching.")
    except LauncherError as error:
        processes = {"fusion": [], "identity": []}
        conflict = True
        if str(error) not in errors:
            errors.append(str(error))
    bus = active_bus(paths)
    renderer = None
    options = paths.prefix / "drive_c/users/steamuser/AppData/Roaming/Autodesk/Neutron Platform/Options/NMachineSpecificOptions.xml"
    if options.is_file():
        try:
            tree = ET.parse(options)
            option = tree.find(".//BootstrapOptionsGroup/driverOptionId")
            renderer = option.get("Value") if option is not None else None
        except (ET.ParseError, OSError):
            errors.append("Fusion graphics preferences could not be read.")
    return {
        "schema_version": 1,
        "installed": bool(targets.get("fusion")),
        "running": bool(processes["fusion"]),
        "runtime_ready": runtime_ready,
        "session_attachment_ready": runtime_ready and bus and any(processes.values()) and not conflict,
        "session_conflict": conflict,
        "renderer": renderer,
        "runner": RUNNER,
        "runner_overlay": overlay["id"] if overlay else None,
        "runner_overlay_sha256": overlay_identity(overlay) if overlay else None,
        "runner_overlay_modules": {module["target"]: module["sha256"] for module in overlay_modules(overlay)} if overlay else {},
        "runner_overlay_verified": overlay_verified,
        "fusion_version": targets.get("version"),
        "prefix": str(paths.prefix),
        "registered_fusion": str(targets["fusion"]) if targets.get("fusion") else None,
        "registered_identity": str(targets["identity"]) if targets.get("identity") else None,
        "identity_source": targets.get("identity_source"),
        "process_ids": processes,
        "errors": errors,
    }


def notify_failure(message: str) -> None:
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "--app-name=Fusion 360", "Fusion 360", message],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
        except (OSError, subprocess.SubprocessError):
            pass


@dataclass(frozen=True)
class PrefixProcess:
    pid: int
    parent: int
    name: str
    argv0: str
    executable: Path
    mapped_executables: tuple[Path, ...] = ()
    zombie_leader: bool = False


def prefix_processes(paths: Paths, proc_root: Path = Path("/proc")) -> list[PrefixProcess]:
    """Private identity metadata only: no command arguments, URLs, or diagnostics output."""
    result = []
    for proc in proc_root.iterdir():
        if not proc.name.isdigit():
            continue
        def read(metadata: Path, _env):
            executable = Path(os.readlink(metadata / "exe"))
            argv0 = process_argv0(metadata)
            status = (proc / "status").read_text().splitlines()
            parent = next(int(line.split()[1]) for line in status if line.startswith("PPid:"))
            mapped = set()
            for line in (metadata / "maps").read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) == 6 and fields[5].casefold().endswith(".exe"):
                    mapped.add(Path(fields[5]))
            return PrefixProcess(int(proc.name), parent, (proc / "comm").read_text().strip(),
                                 argv0, executable, tuple(sorted(mapped)), metadata != proc)
        if process := _inspect_prefix_process(paths, proc, read):
            result.append(process)
    return result


def idle_wine_process(paths: Paths, process: PrefixProcess, fusion: Path) -> bool:
    executable = process.argv0.replace("\\", "/").casefold()
    name = executable.rsplit("/", 1)[-1]
    services = {"services.exe", "winedevice.exe", "svchost.exe", "plugplay.exe",
                "rpcss.exe", "explorer.exe", "tabtip.exe", "conhost.exe", "umu.exe"}
    if name in services and "/windows/" in executable:
        return any(paths.runner / "files/lib/wine" / arch / name in process.mapped_executables
                   for arch in ("x86_64-windows", "i386-windows"))
    if name == "adpclientservice.exe":
        # Autodesk's analytics daemon survives an ordinary quit. Permit only
        # the executable mapped from the currently registered Fusion build.
        return fusion.parent / "ADPClientService.exe" in process.mapped_executables
    if process.executable == paths.runner / "files/bin/wineserver":
        return name == "wineserver"
    return False


def idle_runtime_process(paths: Paths, process: PrefixProcess, ancestors: set[int], fusion: Path) -> bool:
    if idle_wine_process(paths, process, fusion):
        return True
    name = process.argv0.replace("\\", "/").casefold().rsplit("/", 1)[-1]
    runtime_tools = paths.runtime / "pressure-vessel/libexec/steam-runtime-tools-0"
    container_tools = Path("/usr/lib/pressure-vessel/from-host/libexec/steam-runtime-tools-0")
    if name in {"srt-bwrap", "pv-adverb", "x86_64-linux-gnu-srt-launcher-service"}:
        return process.executable in {runtime_tools / name, container_tools / name}
    if name == "steam-runtime-launch-client":
        return process.executable == paths.client
    if re.fullmatch(r"python3(?:\.[0-9]+)?", process.executable.name):
        # Only the umu/Proton ancestors which own the verified service may
        # survive. An unrelated Python child could be maintenance work.
        return (process.pid in ancestors and process.executable.parent == Path("/usr/bin")
                and process.name in {"umu-run", "python3", process.executable.name})
    return False


def _checked_idle_processes(paths: Paths, ancestors: set[int], fusion: Path) -> list[PrefixProcess]:
    require_compatible_session(paths)
    if any(active_processes(paths).values()):
        raise LauncherError("Fusion or Identity Manager is still running. Close Fusion and wait for Identity Manager to exit.")
    processes = prefix_processes(paths)
    if any(not idle_runtime_process(paths, process, ancestors, fusion) for process in processes):
        raise LauncherError("Fusion background application or update work is still active; its runtime was left running.")
    return processes


def _same_process_image(before: PrefixProcess, after: PrefixProcess) -> bool:
    return (before.pid == after.pid and before.argv0 == after.argv0
            and before.executable == after.executable
            and before.mapped_executables == after.mapped_executables)


@dataclass
class IdleProcessHandle:
    process: PrefixProcess
    descriptor: int
    signaled_at: float | None = None
    forced: bool = False


def stop_idle_runtime(paths: Paths) -> int:
    """Called only under the exclusive maintenance lock; never stop application/update work."""
    validate_runtime(paths)
    require_compatible_session(paths)
    if any(active_processes(paths).values()):
        raise LauncherError("Fusion or Identity Manager is still running. Close Fusion and wait for Identity Manager to exit.")
    processes = prefix_processes(paths)
    bus = active_bus(paths)
    if not bus and not processes:
        return 0
    fusion = resolve_targets(paths)["fusion"]
    assert isinstance(fusion, Path)
    ancestors: set[int] = set()
    if bus:
        owner = runtime_owner(paths)
        parents = {process.pid: process.parent for process in processes}
        parent = parents.get(owner)
        while parent in parents and parent not in ancestors:
            ancestors.add(parent)
            parent = parents[parent]
        # Ordinary launches are excluded by the maintenance lock. Recheck all
        # work, not just Fusion, immediately before terminating the exact bus.
        _checked_idle_processes(paths, ancestors, fusion)
        if runtime_owner(paths) != owner:
            raise LauncherError("Fusion runtime activity changed; its runtime was left running.")
        result = subprocess.run([str(paths.client), f"--bus-name={paths.bus}", "--terminate"],
                                env=clean_environment(paths), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=5, check=False)
        if result.returncode and active_bus(paths):
            raise LauncherError("The idle Fusion runtime could not be stopped. Try again after it finishes exiting.")
    handles: dict[int, IdleProcessHandle] = {}
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            bus = active_bus(paths)
            current = _checked_idle_processes(paths, ancestors, fusion)
            if not bus and not current:
                return 0
            if not bus:
                # The launcher protocol signals tracked process groups only;
                # daemonized Wine services can survive it. Pin each verified
                # service with a pidfd before rechecking the entire prefix.
                for process in current:
                    if process.pid in handles or not idle_wine_process(paths, process, fusion):
                        continue
                    try:
                        descriptor = os.pidfd_open(process.pid)
                    except ProcessLookupError:
                        continue
                    except (AttributeError, OSError):
                        raise LauncherError("An idle Fusion service could not be safely addressed; it was left running.") from None
                    handles[process.pid] = IdleProcessHandle(process, descriptor)
                for pid, handle in handles.items():
                    # A prior signal can change the process tree. Never share
                    # an idle snapshot across two signals, including escalation.
                    checked = _checked_idle_processes(paths, ancestors, fusion)
                    if active_bus(paths):
                        raise LauncherError("Fusion runtime activity changed; its services were left running.")
                    by_pid = {process.pid: process for process in checked}
                    process = by_pid.get(pid)
                    if process is None:
                        continue
                    if not _same_process_image(handle.process, process):
                        raise LauncherError("A Fusion service changed during shutdown; it was left running.")
                    server_present = any(item.executable == paths.runner / "files/bin/wineserver"
                                         for item in checked)
                    now = time.monotonic()
                    if handle.signaled_at is None:
                        signum = signal.SIGTERM
                        handle.signaled_at = now
                    else:
                        name = process.argv0.replace("\\", "/").casefold().rsplit("/", 1)[-1]
                        # Observed survivors after graceful shutdown: a stock
                        # device service, or ADP with a dead leader/live threads.
                        # Never force other services, analytics with a live leader,
                        # or any process while a Wine server still exists.
                        forceable = name == "winedevice.exe" or (
                            name == "adpclientservice.exe" and process.zombie_leader)
                        if (handle.forced or server_present or not forceable
                                or now - handle.signaled_at < 3):
                            continue
                        signum = signal.SIGKILL
                        handle.forced = True
                    try:
                        signal.pidfd_send_signal(handle.descriptor, signum)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        raise LauncherError("An idle Fusion service could not be stopped safely. Retry after it exits.") from None
            time.sleep(0.2)
    finally:
        for handle in handles.values():
            os.close(handle.descriptor)
    raise LauncherError("Fusion runtime services are still exiting. Run stop-idle-runtime again before maintenance.")


def _run_maintenance_cli(paths: Paths, operation, argument: str) -> int:
    """Public mutation commands must cooperate with install/backup/restore.

    Internal callers already hold this lock and invoke the operation directly.
    In particular, configuring WineBrowser is allowed in a live session; its
    own implementation still attaches only to the matching runtime.
    """
    try:
        descriptor = _acquire_lock(paths.state / ".maintenance.lock", fcntl.LOCK_EX)
    except BlockingIOError:
        raise LauncherError("Fusion maintenance is already in progress. Try again when it finishes.") from None
    try:
        return operation(paths, argument)
    finally:
        os.close(descriptor)


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's ordinary error includes unknown arguments, possibly URLs.
        self.exit(2, "Invalid command arguments. Use --help for usage.\n")


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description="Run Autodesk Fusion with pinned GE-Proton and umu.")
    sub = parser.add_subparsers(dest="command")
    start = sub.add_parser("launch", help="Launch or focus Fusion")
    start.add_argument("--no-prestart-identity", action="store_true")
    start.add_argument("file_or_uri", nargs="?")
    for name in ("status", "diagnostics"):
        report = sub.add_parser(name, help="Report installation/session status without account data")
        report.add_argument("--json", action="store_true")
    auth = sub.add_parser("auth", help="Deliver an Autodesk callback to the running session")
    auth.add_argument("uri")
    browser = sub.add_parser("browser", help="Open a URL in the host desktop browser")
    browser.add_argument("uri")
    installer = sub.add_parser("install-exe", help="Run the official installer in this prefix")
    installer.add_argument("file")
    configure = sub.add_parser("configure-browser", help="Set this prefix's WineBrowser helper")
    configure.add_argument("helper")
    sub.add_parser("configure-folders", help="Use host Documents/Downloads and home in local file dialogs")
    sub.add_parser("stop-idle-runtime", help="Stop this verified runtime only after application and update work exits")
    args = parser.parse_args(argv)
    paths = Paths.default()
    try:
        if args.command in {"status", "diagnostics"}:
            report = status(paths)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                for key, value in report.items():
                    print(f"{key}: {value}")
            return 0
        if args.command == "auth":
            code = authenticate(paths, args.uri)
            if code:
                raise LauncherError("Fusion could not receive the sign-in callback. Retry sign-in in Fusion.")
            return 0
        if args.command == "browser":
            code = open_browser(args.uri)
            if code:
                raise LauncherError("The desktop browser could not be opened.")
            return 0
        if args.command == "install-exe":
            code = _run_maintenance_cli(paths, install_exe, args.file)
        elif args.command == "configure-browser":
            code = _run_maintenance_cli(paths, configure_browser, args.helper)
        elif args.command == "configure-folders":
            code = _run_maintenance_cli(paths, configure_host_folders, "")
        elif args.command == "stop-idle-runtime":
            code = _run_maintenance_cli(paths, lambda item, _: stop_idle_runtime(item), "")
        else:
            code = launch(paths, getattr(args, "file_or_uri", None),
                          not getattr(args, "no_prestart_identity", False))
        if code:
            raise LauncherError("Fusion exited before completing the requested operation.")
        return code
    except LauncherError as error:
        print(str(error), file=sys.stderr)
        if args.command not in {"status", "diagnostics"}:
            notify_failure(str(error))
        return 1
    except (OSError, subprocess.SubprocessError):
        # Do not stringify these exceptions: command arguments may contain a
        # callback code. All CLI error output must remain independent of URLs.
        print("Fusion could not complete the requested operation.", file=sys.stderr)
        if args.command not in {"status", "diagnostics"}:
            notify_failure("Fusion could not complete the requested operation.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
