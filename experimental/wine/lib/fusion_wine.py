"""Direct host-Wine launch experiment. No desktop registration or prefix repair."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import xml.etree.ElementTree as ET

from fusion_wine_support import (IdentityReadiness, LauncherError, _inspect_prefix_process,
                                 process_argv0, read_registry, resolve_targets)

APP = "fusion360-for-omarchy-wine"
RUNNER = "fusion-wine-11.17"
SOURCE = Path(__file__).resolve().parent.parent
IDENTITY_ARGS = ["--process_name", "Autodesk.IDSDK.DefaultProcess-v2",
                 "--server_name", "Autodesk.IDSDK.DefaultServer-v2"]
QT_BACKENDS = {"default": {}, "opengl": {"QSG_RHI_BACKEND": "opengl"},
               "d3d11": {"QSG_RHI_BACKEND": "d3d11"}}
ALPHA_ENVIRONMENT = {"WINE_X11_ARGB_SHAPE_INPUT": "1", "WINE_X11_ARGB_CONSTANT_ALPHA": "1"}
NATIVE_COMPILER_LOCATION = {
    "registry_hive": "HKCU",
    "registry_key": r"Software\Wine\AppDefaults\Fusion360.exe\DllOverrides",
    "registry_value": "d3dcompiler_47", "override": "native,builtin",
    "relative_path": "d3dcompiler_v2/d3dcompiler_47.dll",
}
NATIVE_COMPILER_SYSTEM32 = "drive_c/windows/system32/d3dcompiler_47.dll"
PINNED_FILES = {"bin/wine", "bin/wineserver", *("lib/wine/x86_64-unix/" + name for name in
               ("ntdll.so", "win32u.so", "winex11.so", "opengl32.so", "winevulkan.so"))}


@dataclass(frozen=True)
class Paths:
    state: Path

    @property
    def prefix(self):
        return self.state / "prefix"

    @property
    def runner(self):
        return self.state / RUNNER

    @property
    def wine(self):
        return self.runner / "bin/wine"

    @property
    def wineserver(self):
        return self.runner / "bin/wineserver"

    @property
    def identity_log(self):
        return self.prefix / "drive_c/users/steamuser/AppData/Local/Autodesk/Identity Services/Log/IdServices.log"

    @property
    def session_file(self):
        return self.state / "session.json"


def compatibility_lock(paths):
    path = paths.state / "compatibility-lock.json"
    if not path.is_file():
        path = SOURCE / "compatibility-lock.json"
    try:
        lock = json.loads(path.read_text())
        runner = lock["runner"]
        if (lock["schema"] != 1 or lock["experiment"] != "standalone-host-wine"
                or runner["name"] != RUNNER or runner["version"] != "wine-11.17"
                or not re.fullmatch(r"[0-9a-f]{64}", runner["sha256"])
                or lock["windows_user"] != "steamuser"
                or lock["launch_environment"] not in QT_BACKENDS.values()
                or lock["runtime_environment"] not in ({}, ALPHA_ENVIRONMENT)
                or set(runner["files"]) != PINNED_FILES
                or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in runner["files"].values())
                or runner["executables"] != {name: runner["files"][name] for name in ("bin/wine", "bin/wineserver")}):
            raise ValueError
        native_compiler_spec(lock)
        return lock
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LauncherError("The standalone Wine compatibility lock is missing or invalid.") from None


def native_compiler_spec(lock):
    try:
        control = lock["native_compiler"]
        if (not isinstance(control, dict) or any(control.get(key) != value for key, value in NATIVE_COMPILER_LOCATION.items())
                or not isinstance(control["size"], int) or isinstance(control["size"], bool) or control["size"] <= 0
                or not re.fullmatch(r"[0-9a-f]{64}", control["sha256"])
                or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", control["file_version"])
                or control["system32_copy"] != {"relative_path": NATIVE_COMPILER_SYSTEM32,
                                                "size": control["size"], "sha256": control["sha256"]}):
            raise ValueError
        return control
    except (KeyError, TypeError, ValueError):
        raise LauncherError("The pinned native shader compiler control is missing or invalid.") from None


def validate_native_compiler(paths, lock):
    control = native_compiler_spec(lock)
    registry = read_registry(paths.prefix, hives=("user.reg",))
    if registry.get(control["registry_key"].casefold(), {}).get(control["registry_value"]) != control["override"]:
        raise LauncherError("Fusion's HKCU d3dcompiler_47 override must be native,builtin. Prepare the scoped override with Fusion closed; launch does not repair it.")
    application = resolve_targets(paths)["fusion"]
    target = application.parent / control["relative_path"]
    copy = control["system32_copy"]
    for candidate, root, expected, label in ((target, application.parent, control, "shipped native shader compiler"),
                                           (paths.prefix / copy["relative_path"], paths.prefix, copy, "private system32 shader compiler copy")):
        try:
            if (candidate.is_symlink() or not candidate.resolve().is_relative_to(root)
                    or not candidate.is_file() or candidate.stat().st_size != expected["size"]):
                raise ValueError
            with candidate.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected["sha256"]:
                    raise ValueError
        except (OSError, ValueError):
            raise LauncherError(f"Fusion's {label} is missing or differs from the lock. Review the explicit compiler preparation; no DLL was downloaded or replaced.") from None
    return target


def session_configuration(paths, lock, qt_backend=None):
    environment = {**lock["runtime_environment"],
                   **(lock["launch_environment"] if qt_backend is None else QT_BACKENDS[qt_backend])}
    compiler = native_compiler_spec(lock)
    identity = {"schema": 1, "runner": str(paths.runner), "prefix": str(paths.prefix),
                "runner_sha256": lock["runner"]["sha256"], "environment": environment,
                "runner_files": dict(lock["runner"]["files"]),
                "native_compiler": {key: compiler[key] for key in
                                    (*NATIVE_COMPILER_LOCATION, "size", "sha256", "system32_copy")},
                "windows_user": "steamuser"}
    identity["identity"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return identity


def read_session(paths, lock):
    try:
        if paths.session_file.is_symlink():
            raise ValueError
        record = json.loads(paths.session_file.read_text())
        environment = record["environment"]
        backend = next(name for name, value in QT_BACKENDS.items()
                       if {**lock["runtime_environment"], **value} == environment)
        expected = session_configuration(paths, lock, backend)
        if (any(record.get(key) != value for key, value in expected.items())
                or record.get("phase") not in {None, "starting", "dispatched", "failed"}
                or ("identity_ready" in record and not isinstance(record["identity_ready"], bool))):
            raise ValueError
        return record
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        raise LauncherError("The saved Wine session does not match this runtime. Close it before starting another experiment.") from None


def write_session(paths, record):
    if paths.session_file.is_symlink():
        raise LauncherError("Refusing a linked Wine session record.")
    descriptor, temporary = tempfile.mkstemp(prefix=".session-", dir=paths.state)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, paths.session_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def host_environment():
    env = dict(os.environ)
    for key in list(env):
        if (key.startswith(("WINE", "PROTON", "UMU", "STEAM", "Steam", "QT", "QSG_", "QML_", "DXVK", "VKD3D",
                            "LD_", "LIBGL", "GALLIUM", "MESA", "VK_", "__GLX", "FUSION360_"))
                or key in {"GAMEID", "RUNTIMEPATH", "DRI_PRIME", "WAYLAND_DISPLAY", "WAYLAND_SOCKET",
                           "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"}):
            env.pop(key, None)
    env["USER"] = pwd.getpwuid(os.getuid()).pw_name
    return env


def wine_environment(paths, configuration):
    env = host_environment()
    env.update({"WINEPREFIX": str(paths.prefix), "WINELOADER": str(paths.wine), "WINESERVER": str(paths.wineserver),
                "USER": "steamuser", "WINEDEBUG": "-all", "FUSION360_WINE_STATE": str(paths.state),
                "FUSION360_WINE_SESSION": configuration["identity"], **configuration["environment"]})
    return env


def validate_runtime(paths, lock, configuration):
    if (paths.prefix.is_symlink() or not (paths.prefix / "system.reg").is_file()
            or not (paths.prefix / "user.reg").is_file()
            or not (paths.prefix / "drive_c").resolve().is_relative_to(paths.prefix)):
        raise LauncherError("The dedicated copied Wine prefix is missing or points outside this installation.")
    for executable in (paths.wine, paths.wineserver):
        if not executable.is_file() or not os.access(executable, os.X_OK) or not executable.resolve().is_relative_to(paths.runner):
            raise LauncherError("The pinned Wine loader or wineserver is missing.")
    for relative, expected in lock["runner"]["files"].items():
        target = paths.runner / relative
        if not target.is_file() or not target.resolve().is_relative_to(paths.runner):
            raise LauncherError("A pinned Wine runtime file is missing or points outside this installation.")
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise LauncherError("A pinned Wine runtime file changed. Review the runtime before launching.")
    try:
        result = subprocess.run([str(paths.wine), "--version"], env=wine_environment(paths, configuration),
                                capture_output=True, text=True, timeout=10, check=False)
        if result.returncode or result.stdout.strip().split()[0] != lock["runner"]["version"]:
            raise ValueError
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        raise LauncherError("The Wine runtime version could not be verified.") from None


def session_processes(paths, configuration, proc_root=Path("/proc")):
    processes = []
    expected = {"WINELOADER": str(paths.wine), "WINESERVER": str(paths.wineserver), "USER": "steamuser",
                "WINEDEBUG": "-all", "FUSION360_WINE_SESSION": configuration["identity"]}
    def inspect(metadata, env):
        executable = Path(os.readlink(metadata / "exe")).resolve()
        compatible = executable.is_relative_to(paths.runner)
        compatible &= all(env.get(key.encode()) == value.encode() for key, value in expected.items())
        compatible &= env.get(b"QSG_RHI_BACKEND", b"") == configuration["environment"].get("QSG_RHI_BACKEND", "").encode()
        compatible &= all(env.get(key.encode(), b"") == configuration["environment"].get(key, "").encode()
                          for key in ALPHA_ENVIRONMENT)
        allowed = {b"QSG_RHI_BACKEND", *(key.encode() for key in ALPHA_ENVIRONMENT)}
        compatible &= not any(key not in allowed and key.startswith((b"WINE_X11_", b"WINE_LAYERED_", b"WINEQT_", b"QT_", b"QSG_", b"QML_"))
                              for key in env)
        compatible &= not any(env.get(key) for key in (b"DXVK_CONFIG", b"DXVK_CONFIG_FILE", b"WINEDLLOVERRIDES",
                                                       b"QT_WIDGETS_RHI", b"WINEQT_WIDGETS_RHI", b"PROTONPATH"))
        name = process_argv0(metadata).replace("\\", "/").rsplit("/", 1)[-1].strip('"').casefold()
        kind = "fusion" if name == "fusion360.exe" else "identity" if name == "adskidentitymanager.exe" else "helper"
        return {"kind": kind, "compatible": bool(compatible)}
    for proc in proc_root.iterdir():
        if proc.name.isdigit() and (info := _inspect_prefix_process(paths, proc, inspect)) is not None:
            processes.append({"pid": int(proc.name), **info})
    return processes


def require_compatible(processes):
    if any(not process["compatible"] for process in processes):
        raise LauncherError("Another runtime or rendering experiment still uses this prefix. Close it before continuing.")


@contextmanager
def startup_lock(paths):
    descriptor = os.open(paths.state / ".startup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LauncherError("Fusion is already starting.") from None
        yield
    finally:
        os.close(descriptor)


def wine_command(paths, target, arguments=()):
    return [str(paths.wine), str(target), *arguments]


def run_worker(paths, qt_backend=None, prestart_identity=True):
    lock = compatibility_lock(paths)
    configuration = session_configuration(paths, lock, qt_backend)
    validate_native_compiler(paths, lock)
    validate_runtime(paths, lock, configuration)
    with startup_lock(paths):
        processes = session_processes(paths, configuration)
        require_compatible(processes)
        if any(process["kind"] == "fusion" for process in processes):
            return 0
        targets = resolve_targets(paths)
        previous = read_session(paths, lock)
        record = {**configuration, "phase": "starting", "identity_ready": False}
        write_session(paths, record)
        environment = wine_environment(paths, configuration)
        try:
            if prestart_identity:
                identity = targets.get("identity")
                if not isinstance(identity, Path):
                    raise LauncherError("Identity Manager is missing from this Fusion build.")
                ready = (previous and previous.get("identity") == configuration["identity"]
                         and previous.get("identity_ready") and any(process["kind"] == "identity" for process in processes))
                if not ready:
                    cursor = IdentityReadiness.snapshot(paths.identity_log)
                    subprocess.Popen(wine_command(paths, identity, IDENTITY_ARGS), env=environment, cwd=identity.parent,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        current = session_processes(paths, configuration)
                        require_compatible(current)
                        if cursor.poll() and any(process["kind"] == "identity" for process in current):
                            ready = True
                            break
                        time.sleep(0.2)
                if not ready:
                    raise LauncherError("Identity Manager did not report fresh SSO readiness. Inspect the private prefix before retrying.")
                record["identity_ready"] = True
            fusion = targets["fusion"]
            process = subprocess.Popen(wine_command(paths, fusion), env=environment, cwd=fusion.parent,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            record["phase"] = "dispatched"
            write_session(paths, record)
        except (OSError, LauncherError):
            record["phase"] = "failed"
            write_session(paths, record)
            raise
        # Keep one worker through the loader's lifetime, including the brief
        # gap before Fusion appears in /proc. Callbacks do not take this lock.
        # systemd's ExitType=cgroup retains Wine if this initial loader exits.
        return process.wait()


def launch(paths, qt_backend=None, prestart_identity=True):
    lock = compatibility_lock(paths)
    configuration = session_configuration(paths, lock, qt_backend)
    validate_native_compiler(paths, lock)
    validate_runtime(paths, lock, configuration)
    processes = session_processes(paths, configuration)
    require_compatible(processes)
    if any(process["kind"] == "fusion" for process in processes):
        return 0
    systemd = shutil.which("systemd-run")
    if not systemd or not os.environ.get("DISPLAY"):
        raise LauncherError("A desktop X11 display and systemd user manager are required for ordinary launch.")
    command = [systemd, "--user", "--collect", "--quiet", "--service-type=exec", "--expand-environment=no",
               "--property=ExitType=cgroup", "--property=StandardOutput=null", "--property=StandardError=null",
               "--unit=fusion360-wine-" + uuid.uuid4().hex, "--description=Fusion standalone Wine"]
    for key in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "HOME"):
        if key in os.environ:
            command.append("--setenv=" + key + "=" + os.environ[key])
    command += ["--", sys.executable, "-B", str(Path(__file__).resolve()), "--state", str(paths.state), "_run"]
    if qt_backend is not None:
        command += ["--qt-backend", qt_backend]
    if not prestart_identity:
        command.append("--no-identity-prestart")
    return subprocess.run(command, env=host_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, check=False).returncode


def validate_auth_uri(uri):
    if len(uri) > 32768 or any(ord(char) <= 32 or ord(char) == 127 for char in uri):
        raise LauncherError("Invalid Autodesk authentication callback.")
    try:
        parsed = urlsplit(uri)
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=16)
        if (parsed.scheme != "adskidmgr" or parsed.netloc or parsed.path != "/login" or parsed.fragment
                or set(query) != {"code", "state"} or any(len(values) != 1 or not values[0]
                or any(ord(char) < 32 or ord(char) == 127 for char in values[0]) for values in query.values())):
            raise ValueError
    except ValueError:
        raise LauncherError("Invalid Autodesk authentication callback.") from None
    return uri


def authenticate(paths, uri):
    validate_auth_uri(uri)
    lock = compatibility_lock(paths)
    record = read_session(paths, lock)
    if record is None:
        raise LauncherError("Open the standalone Wine Fusion session before retrying sign-in.")
    validate_runtime(paths, lock, record)
    processes = session_processes(paths, record)
    require_compatible(processes)
    if not any(process["kind"] in {"fusion", "identity"} for process in processes):
        raise LauncherError("The standalone Wine Fusion session has closed. Open it before retrying sign-in.")
    target = resolve_targets(paths).get("identity")
    if not isinstance(target, Path):
        raise LauncherError("Identity Manager is missing from this Fusion build.")
    # Direct Wine has no atomic container attachment API. If the verified
    # session exits here, Wine may restart its SAME dedicated prefix server.
    # The exact loader, server and prefix still never fall back to Test 1/default.
    return subprocess.run(wine_command(paths, target, [uri]), env=wine_environment(paths, record), cwd=target.parent,
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          check=False).returncode


def open_browser(uri):
    if len(uri) > 32768 or any(ord(char) < 32 or ord(char) == 127 for char in uri):
        raise LauncherError("Invalid external browser URL.")
    try:
        parsed = urlsplit(uri)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
    except ValueError:
        raise LauncherError("Invalid external browser URL.") from None
    systemd = shutil.which("systemd-run")
    if not systemd:
        raise LauncherError("The host browser handoff requires the systemd user manager.")
    command = [systemd, "--user", "--collect", "--quiet", "--service-type=exec", "--expand-environment=no",
               "--property=StandardOutput=null", "--property=StandardError=null",
               "--unit=fusion360-wine-browser-" + uuid.uuid4().hex, "--description=Fusion external browser",
               "--", "/usr/bin/xdg-open", uri]
    return subprocess.run(command, env=host_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, check=False).returncode


def status(paths):
    report = {"experiment": "standalone-host-wine", "accepted": False, "runtime_ready": False,
              "running": False, "callback_ready": False, "native_compiler_prepared": False,
              "prefix": str(paths.prefix), "errors": []}
    try:
        lock = compatibility_lock(paths)
        record = read_session(paths, lock)
        configuration = record or session_configuration(paths, lock)
        validate_runtime(paths, lock, configuration)
        report["runtime_ready"] = True
        report["registered_fusion"] = str(resolve_targets(paths)["fusion"])
        processes = session_processes(paths, configuration)
        require_compatible(processes)
        report.update({"running": any(process["kind"] == "fusion" for process in processes),
                       "callback_ready": bool(record and any(process["kind"] in {"fusion", "identity"} for process in processes)),
                       "session_identity": configuration["identity"], "environment": configuration["environment"],
                       "processes": processes, "startup_phase": record.get("phase") if record else None})
        options = paths.prefix / "drive_c/users/steamuser/AppData/Roaming/Autodesk/Neutron Platform/Options/NMachineSpecificOptions.xml"
        if options.is_file():
            driver = ET.parse(options).find(".//BootstrapOptionsGroup/driverOptionId")
            report["native_renderer_preference"] = driver.get("Value") if driver is not None else None
        report["native_compiler_path"] = str(validate_native_compiler(paths, lock))
        report["native_compiler_prepared"] = True
    except (LauncherError, OSError, ET.ParseError) as error:
        report["errors"].append(str(error) if isinstance(error, LauncherError) else "Private installation metadata could not be read.")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("launch", "_run"):
        command = commands.add_parser(name, help="Start the pinned Wine application" if name == "launch" else "Internal detached startup worker")
        command.add_argument("--qt-backend", choices=QT_BACKENDS)
        command.add_argument("--no-identity-prestart", action="store_true")
    commands.add_parser("status").add_argument("--json", action="store_true")
    commands.add_parser("auth").add_argument("uri")
    commands.add_parser("browser").add_argument("uri")
    args = parser.parse_args(argv)
    state = args.state or Path(os.environ.get("FUSION360_WINE_STATE", Path.home() / ".local/share" / APP))
    paths = Paths(state.expanduser().resolve())
    try:
        if args.command == "browser":
            return open_browser(args.uri)
        if args.command == "status":
            report = status(paths)
            print(json.dumps(report, indent=2))
            return 0 if not report["errors"] else 1
        if args.command == "auth":
            return authenticate(paths, args.uri)
        function = launch if args.command == "launch" else run_worker
        return function(paths, args.qt_backend, not args.no_identity_prestart)
    except LauncherError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print("The standalone Wine launcher could not complete this operation.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
