"""Read-only helpers adapted from Fusion 360 for Omarchy, commit c92f298.

Registry target discovery, fresh SSO readiness and process-metadata race handling
are copied from that local experiment; no Proton/umu integration is imported.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path, PureWindowsPath
import re
import time

_STRING = re.compile(r'(@|"(?:\\.|[^"\\])*")="((?:\\.|[^"\\])*)"')


_EXE = re.compile(r'^\s*(?:"([^"]+\.exe)"|([^\s"]+\.exe))(?:\s|$)', re.I)


class LauncherError(Exception):
    """A safe, static message suitable for a desktop notification or stderr."""


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


def read_registry(prefix: Path, *, hives=("system.reg", "user.reg")) -> dict[str, dict[str, str]]:
    """Read string values; callers may request HKCU-only configuration evidence."""
    result: dict[str, dict[str, str]] = {}
    for name in hives:
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
