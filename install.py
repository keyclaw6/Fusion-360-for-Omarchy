#!/usr/bin/env python3
"""Install the one pinned Fusion route; application data stays outside this repo."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

APP = "fusion360-for-omarchy"
SOURCE = Path(__file__).resolve().parent
COMMANDS = (APP, APP + "-auth", APP + "-browser")
SUPPORT_FILES = (*("bin/" + c for c in COMMANDS), "lib/fusion360_omarchy.py",
                 "install.py", "maintenance.py", "compatibility-lock.json")
OPTIONAL_SUPPORT = ("lib/fusion360_hyprland.py", "runtime-patches/manifest.json",
                    "runtime-patches/build-overlay.py", "runtime-patches/compile.sh",
                    "runtime-patches/test-constant-alpha.py", "runtime-patches/test-present-wait.py",
                    "runtime-patches/owned-tool-windows.patch",
                    "runtime-patches/argb-input-shape.patch")
OVERLAY_TARGET = "files/lib/wine/x86_64-unix/winex11.so"
OVERLAY_TARGETS_V2 = (OVERLAY_TARGET, "files/lib/wine/x86_64-unix/win32u.so")
OVERLAY_ENVIRONMENT = {
    "WINE_X11_ARGB_SHAPE_INPUT": "1",
    "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
    "QSG_RHI_BACKEND": "opengl",
}
OVERLAY_ENVIRONMENT_V2 = {
    "WINE_X11_ARGB_SHAPE_INPUT": "1",
    "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
    "WINE_X11_VULKAN_PRESENT_WAIT": "1",
    "QSG_RHI_BACKEND": "d3d11",
}
OVERLAY_ENVIRONMENT_V3 = {**OVERLAY_ENVIRONMENT_V2, "QSG_RHI_BACKEND": "opengl"}
# Configuration revisions keep their exact environment for recovery receipts.
OVERLAY_PAIR_ENVIRONMENTS = {
    "ge-proton11-7-omarchy-x11-v2": OVERLAY_ENVIRONMENT_V2,
    "ge-proton11-7-omarchy-x11-v3": OVERLAY_ENVIRONMENT_V3,
}
SCHEMES = {"x-scheme-handler/adskidmgr": APP + "-auth.desktop",
           "x-scheme-handler/fusion360": APP + ".desktop"}


class InstallError(Exception):
    pass


@dataclass(frozen=True)
class Locations:
    state: Path
    cache: Path
    data_home: Path
    config_home: Path
    bin_home: Path

    @classmethod
    def from_args(cls, args):
        data = Path(args.data_home or os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        state = Path(args.state or os.environ.get("FUSION360_STATE", SOURCE if
                     (SOURCE / "install-manifest.json").is_file() else data / APP)).expanduser()
        saved = {}
        if (state / "install-manifest.json").is_file():
            try:
                record = json.loads((state / "install-manifest.json").read_text())
                if record.get("application_id") == APP:
                    saved = record.get("paths", {})
            except (ValueError, OSError):
                pass  # load_manifest will explain the malformed record.
        return cls(*(Path(os.path.abspath(Path(p).expanduser())) for p in (
            state,
            args.cache or saved.get("cache") or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP,
            args.data_home or saved.get("data_home") or data,
            args.config_home or saved.get("config_home") or os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"),
            args.bin_home or saved.get("bin_home") or Path.home() / ".local/bin")))

    @property
    def prefix(self):
        return self.state / "prefix"

    @property
    def manifest(self):
        return self.state / "install-manifest.json"

    def environment(self):
        return dict(os.environ, FUSION360_STATE=str(self.state),
                    XDG_DATA_HOME=str(self.data_home), XDG_CONFIG_HOME=str(self.config_home))


def add_locations(parser):
    for option in ("state", "cache", "data-home", "config-home", "bin-home"):
        parser.add_argument("--" + option, metavar="PATH")


def digest(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def reject_symlink(path):
    if path.is_symlink():
        raise InstallError(f"Refusing a symbolic link at {path}.")


def private_directory(path):
    reject_symlink(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, data, mode=0o600):
    reject_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".fusion-install-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + "\n").encode())


def check_locations(loc):
    # A source checkout is never an appropriate place for a logged-in prefix.
    for parent in (SOURCE, *SOURCE.parents):
        if (parent / ".git").exists():
            if loc.state.resolve().is_relative_to(parent) or loc.cache.resolve().is_relative_to(parent):
                raise InstallError("Installation state and cache must be outside the source repository.")
            break
    for path in (loc.state, loc.cache, loc.data_home, loc.config_home, loc.bin_home,
                 loc.prefix, loc.state / "bin", loc.state / "lib",
                 loc.data_home / "applications", loc.manifest):
        for parent in (path, *path.parents):
            reject_symlink(parent)


@contextmanager
def maintenance_lock(loc):
    check_locations(loc)
    private_directory(loc.state)
    path = loc.state / ".maintenance.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise InstallError("Another install or maintenance command is running.") from None
        yield
    finally:
        os.close(fd)


def read_lock(source=SOURCE):
    lock = json.loads((source / "compatibility-lock.json").read_text())
    if lock.get("schema") != 1 or lock["runner"]["name"] != "GE-Proton11-7-x86_64":
        raise InstallError("This installer supports only the reviewed GE-Proton11-7 lock.")
    for entry in (lock["runner"], lock["autodesk_installer"], lock["steam_runtime"]):
        parsed = urllib.parse.urlsplit(entry["url"])
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
            raise InstallError("The compatibility lock has an invalid URL or checksum.")
    overlay = overlay_spec(lock)
    if overlay:
        manifest = json.loads((source / overlay["manifest"]).read_text())
        if manifest.get("schema") != overlay_schema(overlay) or any(manifest.get(key) != value for key, value in overlay.items()
                                               if key != "manifest"):
            raise InstallError("The runtime overlay provenance does not match the compatibility lock.")
    return lock


def overlay_spec(lock):
    overlay = lock.get("runner_overlay")
    if overlay is None:
        return None
    common = {"id", "required_environment", "manifest"}
    if not isinstance(overlay, dict) or overlay.get("manifest") != "runtime-patches/manifest.json":
        raise InstallError("The locked runtime overlay is unsupported or malformed.")
    if overlay.get("id") == "ge-proton11-7-omarchy-x11-v1":
        valid = (set(overlay) == common | {"target", "original_sha256", "sha256"}
                 and overlay.get("target") == OVERLAY_TARGET
                 and overlay.get("required_environment") == OVERLAY_ENVIRONMENT)
        modules = [overlay]
    elif isinstance(overlay.get("id"), str) and overlay["id"] in OVERLAY_PAIR_ENVIRONMENTS:
        modules = overlay.get("modules")
        valid = (set(overlay) == common | {"modules"}
                 and overlay.get("required_environment") == OVERLAY_PAIR_ENVIRONMENTS[overlay["id"]]
                 and isinstance(modules, list) and len(modules) == 2
                 and all(isinstance(item, dict)
                         and set(item) == {"target", "original_sha256", "sha256"}
                         and isinstance(item.get("target"), str) for item in modules)
                 and sorted(item.get("target", "") for item in modules) == sorted(OVERLAY_TARGETS_V2))
    else:
        valid, modules = False, []
    if (not valid or not all(isinstance(item.get(key), str)
                            and re.fullmatch(r"[0-9a-f]{64}", item[key])
                            for item in modules for key in ("original_sha256", "sha256"))):
        raise InstallError("The locked runtime overlay is unsupported or malformed.")
    return overlay


def overlay_schema(overlay):
    return 2 if "modules" in overlay else 1


def overlay_modules(overlay):
    """Normalize for iteration only; retain the exact legacy receipt/lock bytes."""
    if "modules" in overlay:
        return sorted(overlay["modules"], key=lambda item: item["target"])
    return [{key: overlay[key] for key in ("target", "original_sha256", "sha256")}]


def require_overlay_migration(loc, lock):
    selected = lock.get("runner_overlay")
    current_path = loc.state / "compatibility-lock.json"
    reject_symlink(current_path)
    current = json.loads(current_path.read_text()).get("runner_overlay") if current_path.exists() else None
    receipt_path = loc.state / "runner-overlay.json"
    reject_symlink(receipt_path)
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if ((current and current != selected)
            or (receipt.get("phase") in {"prepared", "active"} and receipt.get("overlay") != selected)):
        raise InstallError("Roll back the current runtime overlay before installing a different one; the prefix can be reused.")


def run(command, loc, **kwargs):
    return subprocess.run(command, env=loc.environment(), check=True, **kwargs)


def ensure_packages(loc, install=True):
    if not shutil.which("pacman"):
        raise InstallError("The tested package route requires an Arch/Omarchy host.")
    missing = [p for p in ("umu-launcher", "mesa-utils", "xdg-utils")
               if subprocess.run(["pacman", "-Q", p], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL).returncode]
    if missing:
        if not install or not shutil.which("omarchy"):
            raise InstallError("Required native packages are missing: " + ", ".join(missing))
        run(["omarchy", "pkg", "add", *missing], loc)
    result = subprocess.run(["pacman", "-Q", "umu-launcher"], check=True,
                            capture_output=True, text=True)
    installed = result.stdout.strip().split()[-1].rsplit("-", 1)[0]
    if installed != read_lock()["launcher"]["version"]:
        raise InstallError("umu-launcher differs from the reviewed lock; validate it before changing the lock.")
    for command in ("umu-run", "xdg-mime", "glxinfo"):
        if not shutil.which(command):
            raise InstallError(f"Required executable is missing: {command}")


def fetch_verified(entry, destination):
    reject_symlink(destination)
    if destination.exists():
        if digest(destination) != entry["sha256"]:
            raise InstallError(f"Cached download checksum differs from the lock: {destination.name}")
        return destination
    private_directory(destination.parent)
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
    try:
        request = urllib.request.Request(entry["url"], headers={"User-Agent": APP + "/0.1"})
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(request, timeout=60) as response:
            if urllib.parse.urlsplit(response.url).scheme != "https":
                raise InstallError("A download redirected outside HTTPS.")
            shutil.copyfileobj(response, output, 1024 * 1024)
        if digest(temporary) != entry["sha256"]:
            raise InstallError("A download checksum differs from the compatibility lock.")
        os.replace(temporary, destination)
        return destination
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def safe_members(archive, top):
    members = archive.getmembers()
    seen = set()
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != top
                or path in seen or not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
            raise InstallError("Runner archive contains an unsafe or duplicate member.")
        seen.add(path)
        if member.issym() or member.islnk():
            base = str(path.parent) if member.issym() else ""
            target = PurePosixPath(posixpath.normpath(posixpath.join(base, member.linkname)))
            if target.is_absolute() or not target.parts or target.parts[0] != top or ".." in target.parts:
                raise InstallError("Runner archive contains an escaping link.")
    return members


def install_runner(archive_path, loc, lock):
    name = lock["runner"]["name"]
    target = loc.state / name
    reject_symlink(target)
    overlay = overlay_spec(lock)
    exceptions = {item["target"]: item for item in overlay_modules(overlay)} if overlay else {}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = safe_members(archive, name)
        if target.exists():
            # Adopt an already extracted runner only after checking its actual files.
            for member in members:
                path = loc.state / member.name
                if member.issym():
                    good = path.is_symlink() and os.readlink(path) == member.linkname
                elif member.isdir():
                    good = path.is_dir() and not path.is_symlink()
                else:
                    extracted = archive.extractfile(member)
                    good = (path.is_file() and not path.is_symlink() and extracted is not None
                            and path.resolve().is_relative_to(target.resolve()))
                    if good:
                        with extracted:
                            archive_digest = hashlib.file_digest(extracted, "sha256").hexdigest()
                        actual_digest = digest(path)
                        exception = exceptions.get(member.name.removeprefix(name + "/"))
                        if exception:
                            if archive_digest != exception["original_sha256"]:
                                raise InstallError("The overlay base module does not match the official runner archive.")
                            good = actual_digest in {archive_digest, exception["sha256"]}
                        else:
                            good = actual_digest == archive_digest
                if not good:
                    raise InstallError("Existing runner differs from its verified archive; it was left untouched.")
            return
        stage = Path(tempfile.mkdtemp(prefix=".runner-", dir=loc.state))
        try:
            archive.extractall(stage, members=members, filter="data")
            if not (stage / name / "proton").is_file():
                raise InstallError("Verified archive does not contain the expected Proton launcher.")
            os.rename(stage / name, target)
        finally:
            shutil.rmtree(stage)


def current_overlay_modules(loc, lock):
    overlay = overlay_spec(lock)
    runner = loc.state / lock["runner"]["name"]
    result = []
    for item in overlay_modules(overlay) if overlay else ():
        target = runner / item["target"]
        reject_symlink(target)
        if not target.is_file() or not target.resolve().is_relative_to(runner.resolve()):
            raise InstallError("A required runner module is missing or outside the production runner.")
        actual = digest(target)
        if actual not in {item["original_sha256"], item["sha256"]}:
            raise InstallError("A production runner module is unrecognized; all modules were left untouched.")
        result.append((item, target, actual))
    return result


def require_overlay_installed(loc, lock):
    if any(actual != item["sha256"] for item, _, actual in current_overlay_modules(loc, lock)):
        raise InstallError("The required pinned runtime overlay is missing or mismatched. Run a full install after closing Fusion.")


def read_overlay_artifacts(overlay, artifact):
    root = Path(artifact)
    reject_symlink(root)
    result = {}
    for item in overlay_modules(overlay):
        candidate = root / Path(item["target"]).name if overlay_schema(overlay) == 2 else root
        reject_symlink(candidate)
        if not candidate.is_file():
            raise InstallError("The overlay artifact set is incomplete; no production module was changed.")
        data = candidate.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise InstallError("An overlay artifact differs from the reviewed hash; no production module was changed.")
        result[item["target"]] = (data, candidate.stat().st_mode & 0o777)
    return result


def overlay_artifact(loc, lock, archive_path, supplied=None, install_packages=True, supplied_dir=None):
    overlay = overlay_spec(lock)
    if not overlay:
        if supplied or supplied_dir:
            raise InstallError("The compatibility lock does not select a runtime overlay.")
        return None
    version = overlay_schema(overlay)
    if (supplied and (version != 1 or supplied_dir)) or (supplied_dir and version != 2):
        raise InstallError("Use --overlay-file only for v1, or --overlay-dir containing the reviewed module pair.")
    bundle = loc.cache / overlay["id"]
    reject_symlink(bundle)
    cache = bundle if version == 2 else bundle / "winex11.so"
    items = overlay_modules(overlay)
    # Preflight every supplied/cached file before writing any cache entry.
    buffers = read_overlay_artifacts(overlay, Path(supplied or supplied_dir).expanduser().resolve()) if supplied or supplied_dir else None
    complete = True
    for item in items:
        target = bundle / Path(item["target"]).name
        reject_symlink(target)
        if target.exists():
            if not target.is_file() or digest(target) != item["sha256"]:
                raise InstallError("A cached runtime overlay differs from the lock; it was left untouched.")
        else:
            complete = False
    if complete:
        return cache
    if buffers is None:
        installed = loc.state / lock["runner"]["name"]
        if all((installed / item["target"]).is_file() and not (installed / item["target"]).is_symlink()
               and digest(installed / item["target"]) == item["sha256"] for item in items):
            source = installed / (str(Path(OVERLAY_TARGET).parent) if version == 2 else OVERLAY_TARGET)
            buffers = read_overlay_artifacts(overlay, source)
    if buffers is None:
        # Compiler/header versions belong to the pinned SDK, not native packages.
        missing = [package for package in ("git", "bubblewrap", "patch", "autoconf", "automake", "libtool")
                   if subprocess.run(["pacman", "-Q", package], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL).returncode]
        if missing:
            if not install_packages or not shutil.which("omarchy"):
                raise InstallError("Overlay build packages are missing: " + ", ".join(missing))
            run(["omarchy", "pkg", "add", *missing], loc)
        builder = SOURCE / "runtime-patches/build-overlay.py"
        if not builder.is_file():
            raise InstallError("The pinned overlay build recipe is unavailable.")
        private_directory(loc.cache)
        nonce = uuid.uuid4().hex[:8]
        work = loc.cache / (overlay["id"] + "-build-" + nonce)
        stage = loc.cache / (overlay["id"] + "-candidate-" + nonce)
        output = stage if version == 2 else stage / "winex11.so"
        try:
            run([sys.executable, str(builder), "--runner-archive", str(archive_path),
                 "--output-dir" if version == 2 else "--output", str(output), "--work-dir", str(work)], loc)
            buffers = read_overlay_artifacts(overlay, output)
        finally:
            if stage.is_dir() and not stage.is_symlink():
                shutil.rmtree(stage)
    private_directory(bundle)
    for item in items:
        target = bundle / Path(item["target"]).name
        if not target.exists():
            data, mode = buffers[item["target"]]
            atomic_write(target, data, mode)
    read_overlay_artifacts(overlay, cache)
    return cache


def prepare_overlay(loc, lock, archive_path):
    """Persist complete originals and the previous lock before any promotion."""
    overlay = overlay_spec(lock)
    if not overlay:
        return None
    require_overlay_migration(loc, lock)
    receipt_path = loc.state / "runner-overlay.json"
    current = current_overlay_modules(loc, lock)
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("overlay") == overlay and receipt.get("phase") in {"prepared", "active"}
                and receipt.get("runner") == lock["runner"]["name"]
                and receipt.get("base_runner_sha256") == lock["runner"]["sha256"]):
            validate_overlay_recovery(loc, receipt)
            return receipt
    if overlay_schema(overlay) == 2 and any(actual != item["original_sha256"] for item, _, actual in current):
        raise InstallError("A two-module promotion without a matching recovery receipt requires both original modules.")
    originals = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {item.name: item for item in safe_members(archive, lock["runner"]["name"])}
        for item, _, _ in current:
            member = members.get(lock["runner"]["name"] + "/" + item["target"])
            if member is None or not member.isfile():
                raise InstallError("The original runner archive lacks an overlay base module.")
            with archive.extractfile(member) as original:
                data = original.read()
            if hashlib.sha256(data).hexdigest() != item["original_sha256"]:
                raise InstallError("An original module does not match the overlay provenance.")
            originals[item["target"]] = data
    previous_path = loc.state / "compatibility-lock.json"
    if previous_path.is_file():
        previous_bytes = previous_path.read_bytes()
        previous = json.loads(previous_bytes)
        if (previous.get("runner", {}).get("name") != lock["runner"]["name"]
                or previous.get("runner", {}).get("sha256") != lock["runner"]["sha256"]):
            raise InstallError("The installed compatibility lock describes a different base runner.")
    else:
        previous = dict(lock)
        previous.pop("runner_overlay", None)
        previous_bytes = (json.dumps(previous, indent=2) + "\n").encode()
    if previous.get("runner_overlay"):
        # A legacy adoption still recovers to official bytes, never to a lock
        # requiring patched bytes. Migration between overlays is always explicit.
        previous.pop("runner_overlay")
        previous_bytes = (json.dumps(previous, indent=2) + "\n").encode()
    recovery_root = loc.state / "runner-recovery"
    private_directory(recovery_root)
    recovery = recovery_root / (overlay["id"] + "-" + uuid.uuid4().hex[:8])
    recovery.mkdir(mode=0o700)
    sync_directory(recovery_root)
    for item, target, _ in current:
        atomic_write(recovery / Path(item["target"]).name, originals[item["target"]], target.stat().st_mode & 0o777)
    atomic_write(recovery / "compatibility-lock.json", previous_bytes)
    receipt = {"schema": overlay_schema(overlay), "application_id": APP, "runner": lock["runner"]["name"],
               "base_runner_sha256": lock["runner"]["sha256"],
               "overlay": overlay, "phase": "prepared", "recovery": str(recovery.relative_to(loc.state)),
               "previous_lock_sha256": hashlib.sha256(previous_bytes).hexdigest()}
    validate_overlay_recovery(loc, receipt)
    write_json(receipt_path, receipt)
    return receipt


def validate_overlay_recovery(loc, receipt):
    if (receipt.get("application_id") != APP or receipt.get("runner") != "GE-Proton11-7-x86_64"
            or receipt.get("phase") not in {"prepared", "active", "rolled_back"}):
        raise InstallError("The runtime overlay recovery record is invalid.")
    # Receipt validation intentionally does not read today's build manifest.
    overlay = overlay_spec({"runner_overlay": receipt.get("overlay")})
    if not overlay or receipt.get("schema") != overlay_schema(overlay):
        raise InstallError("The runtime overlay recovery identity is missing or invalid.")
    relative = PurePosixPath(receipt.get("recovery", ""))
    if (relative.is_absolute() or len(relative.parts) != 2 or relative.parts[0] != "runner-recovery"
            or ".." in relative.parts):
        raise InstallError("The runtime recovery directory is outside its dedicated location.")
    recovery = loc.state / str(relative)
    for path in (recovery.parent, recovery, recovery / "compatibility-lock.json"):
        reject_symlink(path)
    for item in overlay_modules(overlay):
        original = recovery / Path(item["target"]).name
        reject_symlink(original)
        if not original.is_file() or digest(original) != item["original_sha256"]:
            raise InstallError("Runtime recovery modules failed verification; no module was changed.")
    if digest(recovery / "compatibility-lock.json") != receipt.get("previous_lock_sha256"):
        raise InstallError("The runtime recovery lock failed verification; no module was changed.")
    previous = json.loads((recovery / "compatibility-lock.json").read_text())
    if (previous.get("runner_overlay") or previous.get("runner", {}).get("name") != receipt["runner"]
            or previous.get("runner", {}).get("sha256") != receipt.get("base_runner_sha256")):
        raise InstallError("The recovery lock does not describe the original production runner.")
    return recovery


def activate_overlay(loc, lock, artifact, receipt):
    overlay = overlay_spec(lock)
    if not overlay:
        return
    if (receipt.get("overlay") != overlay or receipt.get("phase") not in {"prepared", "active"}
            or receipt.get("runner") != lock["runner"]["name"]
            or receipt.get("base_runner_sha256") != lock["runner"]["sha256"]):
        raise InstallError("The overlay activation does not match its recovery receipt.")
    validate_overlay_recovery(loc, receipt)
    buffers = read_overlay_artifacts(overlay, artifact)
    current = current_overlay_modules(loc, lock)
    guard_path = loc.state / "compatibility-lock.json"
    reject_symlink(guard_path)
    guard = json.loads(guard_path.read_text()) if guard_path.is_file() else {}
    if (guard.get("runner_overlay") != overlay
            or guard.get("runner", {}).get("name") != lock["runner"]["name"]
            or guard.get("runner", {}).get("sha256") != lock["runner"]["sha256"]):
        raise InstallError("Install the matching required-overlay lock before activating its modules.")
    # All candidates/current files were checked before the first replacement.
    # A stopped process between replacements leaves a deliberately unlaunchable
    # mixed pair under the new lock; the matching receipt permits a safe retry.
    for item, target, actual in current:
        if actual != item["sha256"]:
            atomic_write(target, buffers[item["target"]][0], target.stat().st_mode & 0o777)
    require_overlay_installed(loc, lock)
    receipt["phase"] = "active"
    write_json(loc.state / "runner-overlay.json", receipt)


def verify_runtime_files(runtime, version):
    manifest = runtime / "VERSIONS.txt"
    if not manifest.is_file():
        raise InstallError("The Steam runtime has no version manifest.")
    lines = [line.split() for line in manifest.read_text().splitlines() if line.startswith("depot\t")]
    if not lines or len(lines[0]) < 2 or lines[0][1] != version:
        raise InstallError("Steam runtime build differs from the compatibility lock; review it before proceeding.")
    verifier = runtime / "pressure-vessel/bin/pv-verify"
    files = runtime / ("steamrt4_platform_" + version) / "files"
    if not verifier.is_file() or not files.is_dir():
        raise InstallError("The pinned Steam runtime is incomplete.")
    result = subprocess.run([str(verifier), "--quiet", "--minimized-runtime", str(files)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise InstallError("Steam runtime mtree verification failed; existing files were left untouched.")


def install_runtime(loc, lock):
    """Seed umu's exact runtime snapshot before umu can choose a newer first bootstrap."""
    entry = lock["steam_runtime"]
    runtime = loc.data_home / "umu/steamrt4"
    reject_symlink(runtime)
    if runtime.exists():
        verify_runtime_files(runtime, entry["version"])
        return
    archive_path = fetch_verified(entry, loc.cache / ("SteamLinuxRuntime_4-" + entry["version"] + ".tar.xz"))
    runtime.parent.mkdir(parents=True, exist_ok=True)
    # Coordinate with umu 1.4.4's own Runtime lock as well as our app lock.
    fd = os.open(runtime.parent / "umu.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if runtime.exists():
            verify_runtime_files(runtime, entry["version"])
            return
        stage = Path(tempfile.mkdtemp(prefix=".fusion-runtime-", dir=runtime.parent))
        try:
            with tarfile.open(archive_path, "r:xz") as archive:
                archive.extractall(stage, members=safe_members(archive, "SteamLinuxRuntime_4"), filter="data")
            extracted = stage / "SteamLinuxRuntime_4"
            verify_runtime_files(extracted, entry["version"])
            (extracted / "umu").symlink_to("_v2-entry-point")
            atomic_write(extracted / ".installed.ok", b"ok\n")
            os.rename(extracted, runtime)
        finally:
            shutil.rmtree(stage)
    finally:
        os.close(fd)


def load_manifest(loc):
    if not loc.manifest.exists():
        return {"schema": 1, "application_id": APP,
                "paths": {k: str(getattr(loc, k)) for k in ("state", "cache", "data_home", "config_home", "bin_home")},
                "files": {}, "associations": {}}
    manifest = json.loads(loc.manifest.read_text())
    expected = {k: str(getattr(loc, k)) for k in ("state", "cache", "data_home", "config_home", "bin_home")}
    if (manifest.get("schema") != 1 or manifest.get("application_id") != APP
            or manifest.get("paths") != expected):
        raise InstallError("Installation paths differ from the existing private manifest.")
    return manifest


def file_record(path):
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if path.is_file():
        return {"kind": "file", "sha256": digest(path)}
    return None


def desktop_quote(value):
    # Desktop Entry Exec quoting is distinct from shell quoting. No shell runs.
    if any(ord(c) < 32 for c in value):
        raise InstallError("Installation paths may not contain control characters.")
    value = value.replace("%", "%%")
    return '"' + re.sub(r'([\\"`$])', r'\\\1', value) + '"'


def is_runtime_source(relative):
    path = PurePosixPath(relative)
    return (len(path.parts) == 2 and path.parts[0] == "runtime-patches"
            and (path.name in {"manifest.json", "build-overlay.py", "compile.sh", "test-constant-alpha.py",
                              "test-present-wait.py", "README.md"}
                 or path.suffix == ".patch" or path.name.startswith("LICENSE.")))


def support_files(source=SOURCE):
    files = list(SUPPORT_FILES)
    files.extend(p for p in OPTIONAL_SUPPORT if (source / p).is_file())
    directory = source / "runtime-patches"
    if directory.is_dir():
        manifest_path = directory / "manifest.json"
        if manifest_path.is_file():
            recipe = json.loads(manifest_path.read_text())
            required = {"manifest.json", "build-overlay.py", "compile.sh", "test-constant-alpha.py", "README.md"}
            if recipe.get("schema") == 2:
                required.add("test-present-wait.py")
            for patch in recipe["patches"]:
                for name in (patch["file"], patch["notice"]):
                    if len(PurePosixPath(name).parts) != 1 or not is_runtime_source("runtime-patches/" + name):
                        raise InstallError("The runtime recipe references a file outside its source directory.")
                    required.add(name)
                if not (directory / patch["file"]).is_file() or digest(directory / patch["file"]) != patch["sha256"]:
                    raise InstallError("A required runtime source patch is missing or differs from its manifest.")
            if any(not (directory / name).is_file() for name in required):
                raise InstallError("The runtime build recipe is incomplete; its scripts, patches and licenses must ship together.")
        files.extend(str(path.relative_to(source)) for path in sorted(directory.iterdir())
                     if path.is_file() and is_runtime_source(str(path.relative_to(source))))
    return list(dict.fromkeys(files))


def integration_payloads(loc, source=SOURCE):
    payloads = {}
    for relative in support_files(source):
        path = source / relative
        payloads[loc.state / relative] = (path.read_bytes(), 0o755 if relative.startswith("bin/")
                                        or relative in {"install.py", "maintenance.py"} else 0o600)
    common = "[Desktop Entry]\nType=Application\nTerminal=false\nCategories=Graphics;Engineering;\nIcon=applications-engineering\n"
    start = (common + "Name=Fusion 360 for Omarchy\nComment=Fusion with pinned GE-Proton and umu\n"
             + "Exec=/usr/bin/python3 " + desktop_quote(str(loc.state / "bin" / APP)) + " launch %u\n"
             + "MimeType=x-scheme-handler/fusion360;\nStartupNotify=true\nStartupWMClass=steam_app_fusion360\n")
    auth = (common + "Name=Autodesk Fusion sign-in\nNoDisplay=true\n"
            + "Exec=/usr/bin/python3 " + desktop_quote(str(loc.state / "bin" / (APP + "-auth"))) + " %u\n"
            + "MimeType=x-scheme-handler/adskidmgr;\n")
    applications = loc.data_home / "applications"
    payloads[applications / (APP + ".desktop")] = (start.encode(), 0o644)
    payloads[applications / (APP + "-auth.desktop")] = (auth.encode(), 0o644)
    return payloads


def install_integration(loc, manifest, source=SOURCE, register=True):
    payloads = integration_payloads(loc, source)
    links = {loc.bin_home / name: loc.state / "bin" / name for name in COMMANDS}
    links[loc.bin_home / (APP + "-maintenance")] = loc.state / "maintenance.py"
    planned = {p: {"kind": "file", "sha256": hashlib.sha256(b).hexdigest()}
               for p, (b, _) in payloads.items()}
    planned.update({p: {"kind": "symlink", "target": str(t)} for p, t in links.items()})
    for path, record in planned.items():
        existing = file_record(path)
        if path.exists() and existing is None:
            raise InstallError(f"An unrelated directory occupies an integration path: {path}")
        if existing and existing not in (record, manifest["files"].get(str(path))):
            raise InstallError(f"An unrelated or edited file occupies an integration path: {path}")
    for path, (data, mode) in payloads.items():
        if path.is_symlink():
            raise InstallError(f"Refusing to replace an integration symlink with a file: {path}")
        atomic_write(path, data, mode)
        manifest["files"][str(path)] = planned[path]
        write_json(loc.manifest, manifest)
    loc.bin_home.mkdir(parents=True, exist_ok=True)
    for path, target in links.items():
        if path.is_symlink() and os.readlink(path) != str(target):
            path.unlink()
        if not path.is_symlink():
            path.symlink_to(target)
        manifest["files"][str(path)] = planned[path]
        write_json(loc.manifest, manifest)
    if register:
        if not shutil.which("xdg-mime"):
            raise InstallError("xdg-mime is required for desktop callback registration.")
        loc.config_home.mkdir(parents=True, exist_ok=True)
        reject_symlink(loc.config_home / "mimeapps.list")
        for scheme, desktop in SCHEMES.items():
            if scheme not in manifest["associations"]:
                previous = run(["xdg-mime", "query", "default", scheme], loc,
                               capture_output=True, text=True).stdout.strip()
                manifest["associations"][scheme] = {"previous": previous if previous != desktop else "",
                                                     "desktop": desktop}
                write_json(loc.manifest, manifest)
            run(["xdg-mime", "default", desktop, scheme], loc)
            selected = run(["xdg-mime", "query", "default", scheme], loc,
                           capture_output=True, text=True).stdout.strip()
            if selected != desktop:
                raise InstallError("The desktop still selects a different handler for " + scheme
                                   + "; inspect desktop-specific MIME defaults before signing in.")
    if shutil.which("update-desktop-database"):
        run(["update-desktop-database", str(loc.data_home / "applications")], loc,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def core(source=SOURCE):
    spec = importlib.util.spec_from_file_location("fusion360_installed_core", source / "lib/fusion360_omarchy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def focus_rules(source=SOURCE):
    path = source / "lib/fusion360_hyprland.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("fusion360_installed_hyprland", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_focus_rule(loc):
    config = loc.config_home / "hypr/hyprland.lua"
    if not config.is_file():
        return
    module = focus_rules()
    if module is None:
        raise InstallError("The required Fusion focus-rule helper is unavailable.")
    try:
        module.install_focus_rule(config, loc.state)
    except module.FocusRuleError as error:
        raise InstallError(str(error)) from None


def runtime_paths(loc, module):
    return module.Paths(loc.state.resolve(), (loc.data_home / "umu/steamrt4").resolve())


def require_closed(loc, module=None, proc_root=Path("/proc")):
    module = module or core()
    paths = runtime_paths(loc, module)
    if module.active_bus(paths):
        raise InstallError("Close Fusion and Identity Manager before maintenance. If only the idle runtime remains, run fusion360-for-omarchy stop-idle-runtime.")
    try:
        processes = module.prefix_processes(paths, proc_root=proc_root)
    except (module.LauncherError, OSError):
        raise InstallError("Fusion process identity could not be verified; no maintenance was performed.") from None
    if processes:
        raise InstallError("A process still uses this prefix. Close Fusion and its helpers before maintenance.")


def verify_runtime_build(loc, lock, required=True):
    path = loc.data_home / "umu/steamrt4/VERSIONS.txt"
    if not path.is_file():
        if required:
            raise InstallError("umu did not install the required Steam runtime.")
        return
    lines = [line.split() for line in path.read_text().splitlines() if line.startswith("depot\t")]
    if not lines or len(lines[0]) < 2 or lines[0][1] != lock["steam_runtime"]["version"]:
        raise InstallError("Steam runtime build differs from the compatibility lock; review it before proceeding.")


def seed_renderer(prefix):
    path = prefix / "drive_c/users/steamuser/AppData/Roaming/Autodesk/Neutron Platform/Options/NMachineSpecificOptions.xml"
    reject_symlink(path)
    if not path.resolve().is_relative_to(prefix.resolve()):
        raise InstallError("Fusion preferences resolve outside the dedicated prefix.")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    old = path.read_bytes() if path.exists() else None
    try:
        root = ET.fromstring(old, parser=parser) if old else ET.Element("OptionGroups")
    except ET.ParseError:
        raise InstallError("Fusion preferences are malformed; they were left untouched.") from None
    if root.tag != "OptionGroups":
        raise InstallError("Unknown Fusion preference format; it was left untouched.")
    group = root.find("BootstrapOptionsGroup")
    if group is None:
        group = ET.SubElement(root, "BootstrapOptionsGroup", SchemaVersion="2", UserName="Bootstrap")
    option = group.find("driverOptionId")
    if option is not None and option.get("Value") == "VirtualDeviceDx11":
        return
    if option is None:
        option = ET.SubElement(group, "driverOptionId", UserName="Graphics driver")
    option.set("Value", "VirtualDeviceDx11")
    if old:
        # A private one-time original is recovery data, never source material.
        backup = path.with_name(path.name + ".before-fusion360-for-omarchy")
        if not backup.exists():
            atomic_write(backup, old)
    encoding = "utf-16" if old and old.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    atomic_write(path, ET.tostring(root, encoding=encoding, xml_declaration=True))


def finish_prefix(loc, module, lock):
    paths = runtime_paths(loc, module)
    require_closed(loc, module)
    verify_runtime_build(loc, lock)
    try:
        module.resolve_targets(paths)
        seed_renderer(loc.prefix)
        result = module.configure_browser(paths, str(loc.state / "bin" / (APP + "-browser")))
    except module.LauncherError as error:
        raise InstallError(str(error)) from None
    if result:
        raise InstallError("WineBrowser registration failed; retry installation after closing Fusion.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_locations(parser)
    parser.add_argument("--no-packages", action="store_true", help="Require packages to exist instead of installing them")
    parser.add_argument("--integration-only", action="store_true", help="Install launchers only; do not download or change the prefix")
    parser.add_argument("--no-register", action="store_true", help="Leave desktop protocol defaults unchanged")
    parser.add_argument("--overlay-file", metavar="PATH", help="Use a verified local v1 winex11.so artifact")
    parser.add_argument("--overlay-dir", metavar="PATH", help="Use a verified local winex11.so and win32u.so pair")
    args = parser.parse_args(argv)
    loc = Locations.from_args(args)
    try:
        with maintenance_lock(loc):
            lock = read_lock()
            manifest = load_manifest(loc)
            receipt = artifact = None
            if not args.integration_only:
                require_overlay_migration(loc, lock)
                ensure_packages(loc, not args.no_packages)
                module = core()
                require_closed(loc, module)
                verify_runtime_build(loc, lock, required=False)
                archive = fetch_verified(lock["runner"], loc.cache / (lock["runner"]["name"] + ".tar.gz"))
                install_runner(archive, loc, lock)
                install_runtime(loc, lock)
                artifact = overlay_artifact(loc, lock, archive, args.overlay_file, not args.no_packages, args.overlay_dir)
                receipt = prepare_overlay(loc, lock, archive)
            else:
                if args.overlay_file or args.overlay_dir:
                    raise InstallError("An overlay may only be activated by a full install with Fusion closed.")
                current_path = loc.state / "compatibility-lock.json"
                if current_path.is_file():
                    current_overlay = json.loads(current_path.read_text()).get("runner_overlay")
                    if current_overlay and current_overlay != lock.get("runner_overlay"):
                        raise InstallError("Integration-only installation cannot change an active runtime overlay. Use explicit rollback or a full install.")
                require_overlay_installed(loc, lock)
            install_integration(loc, manifest, register=not args.no_register)
            if receipt:
                activate_overlay(loc, lock, artifact, receipt)
            if overlay_spec(lock):
                install_focus_rule(loc)
            if not args.integration_only:
                try:
                    module.resolve_targets(runtime_paths(loc, module))
                    installed = True
                except module.LauncherError:
                    installed = False
                if not installed:
                    installer = fetch_verified(lock["autodesk_installer"], loc.cache / "Fusion Client Downloader.exe")
                    try:
                        result = module.install_exe(runtime_paths(loc, module), str(installer))
                    except module.LauncherError as error:
                        raise InstallError(str(error)) from None
                    if result:
                        raise InstallError("The official Fusion installer did not finish successfully.")
                finish_prefix(loc, module, lock)
            print("Desktop integration installed. Run fusion360-for-omarchy status --json to inspect it.")
            return 0
    except (InstallError, OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as error:
        print("Installation stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
