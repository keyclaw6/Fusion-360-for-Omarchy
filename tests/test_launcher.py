"""Boundary checks; no Wine process, browser, or desktop state is started."""

from contextlib import contextmanager, ExitStack, redirect_stderr
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fusion360_omarchy as fusion


def reg_escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


class LauncherBoundaries(unittest.TestCase):
    def setUp(self):
        isolated_env = patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": ""})
        isolated_env.start()
        self.addCleanup(isolated_env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = fusion.Paths(self.root / "state", self.root / "runtime")
        self.paths.prefix.mkdir(parents=True)
        (self.paths.state / "compatibility-lock.json").write_text(json.dumps({
            "schema": 1, "runner": {"name": fusion.RUNNER},
            "launcher": {"version": "1.4.4"},
            "steam_runtime": {"version": "4.0.20260914.260627"}}))
        self.build = self.paths.prefix / "drive_c/users/steamuser/AppData/Local/Autodesk/webdeploy/production/current"
        self.build.mkdir(parents=True)
        self.exe = self.build / "Fusion360.exe"
        self.exe.touch()
        self.idm = self.build / "Autodesk Identity Manager/AdskIdentityManager.exe"
        self.idm.parent.mkdir()
        self.idm.touch()
        self.windows = r"C:\users\steamuser\AppData\Local\Autodesk\webdeploy\production\current\Fusion360.exe"
        self.registry({r"Software\Classes\f3d_file\shell\open\command": {"@": f'"{self.windows}" "%1"'}})

    def registry(self, sections):
        lines = ["WINE REGISTRY Version 2", ""]
        for section, values in sections.items():
            lines.append(f"[{reg_escape(section)}] 1")
            for key, value in values.items():
                name = "@" if key == "@" else f'"{reg_escape(key)}"'
                lines.append(f'{name}="{reg_escape(value)}"')
            lines.append("")
        (self.paths.prefix / "user.reg").write_text("\n".join(lines))

    def test_registered_build_wins_over_old_executables(self):
        stale = self.build.parent / "000-old/Fusion360.exe"
        stale.parent.mkdir()
        stale.touch()
        targets = fusion.resolve_targets(self.paths)
        self.assertEqual(targets["fusion"], self.exe)
        self.assertEqual(targets["identity"], self.idm)

    def test_stale_registry_is_not_repaired_by_first_directory_match(self):
        self.exe.unlink()
        stale = self.build.parent / "old/Fusion360.exe"
        stale.parent.mkdir()
        stale.touch()
        with self.assertRaises(fusion.LauncherError):
            fusion.resolve_targets(self.paths)

    def test_registry_command_tail_is_never_executed(self):
        command = f'"{self.windows}" "%1" & cmd.exe /c malicious'
        self.assertEqual(fusion.windows_executable(self.paths.prefix, command, "Fusion360.exe"), self.exe)

    def test_registry_rejects_escape_and_wrong_executable(self):
        for command in (r'"Z:\tmp\Fusion360.exe"', r'"C:\..\Fusion360.exe"', r'"C:\windows\cmd.exe"'):
            with self.subTest(command=command), self.assertRaises(fusion.LauncherError):
                fusion.windows_executable(self.paths.prefix, command, "Fusion360.exe")

    def test_valid_auth_remains_one_literal_argument(self):
        uri = "adskidmgr:/login?code=%24%28touch%20%2Ftmp%2Fnever%29%3B%26&state=opaque"
        self.assertEqual(fusion.validate_auth_uri(uri), uri)
        command = fusion.attach_command(self.paths, self.idm, [uri])
        self.assertEqual(command[-1:], [uri])
        self.assertNotIn("bash", command)
        self.assertNotIn("sh", command)

    def test_invalid_callbacks_are_rejected_without_echoing_data(self):
        invalid = [
            "https://example.test/login?code=SECRET&state=x",
            "adskidmgr://attacker/login?code=SECRET&state=x",
            "adskidmgr:/logout?code=SECRET&state=x",
            "adskidmgr:/login?code=SECRET&state=",
            "adskidmgr:/login?code=SECRET&code=SECOND&state=x",
            "adskidmgr:/login?code=SECRET&state=x&redirect=somewhere",
            "adskidmgr:/login?code=SECRET&state=x#fragment",
            "adskidmgr:/login?code=SECRET%0A&state=x",
        ]
        for uri in invalid:
            with self.subTest(uri=uri), self.assertRaises(fusion.LauncherError) as error:
                fusion.validate_auth_uri(uri)
            self.assertNotIn("SECRET", str(error.exception))

    def test_exact_bus_is_required_not_prefix_or_other_instance(self):
        self.paths.client.parent.mkdir(parents=True)
        self.paths.client.touch()
        for lines, expected in (
            ([f"--bus-name={self.paths.bus}.Instance1"], False),
            (["--bus-name=com.steampowered.Appanother"], False),
            ([f"--bus-name={self.paths.bus}"], True),
        ):
            result = Mock(returncode=0, stdout="\n".join(lines))
            with patch.object(fusion.subprocess, "run", return_value=result):
                self.assertEqual(fusion.active_bus(self.paths), expected)

    def test_missing_session_never_launches_umu_or_proton(self):
        with patch.object(fusion, "active_bus", return_value=False), patch.object(fusion.subprocess, "call") as call:
            with self.assertRaises(fusion.LauncherError):
                fusion.attach(self.paths, self.idm, ["adskidmgr:/login?code=x&state=y"])
            call.assert_not_called()

    def test_vanished_bus_cannot_fall_back_to_new_container(self):
        with patch.object(fusion, "require_session"), patch.object(fusion.subprocess, "call", return_value=1) as call:
            self.assertEqual(fusion.attach(self.paths, self.idm, ["adskidmgr:/login?code=x&state=y"]), 1)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.args[0][0], str(self.paths.client))

    def test_process_match_checks_prefix_runner_and_cef_renamed_thread(self):
        proc_root = self.root / "proc"
        proc_root.mkdir()
        for pid, prefix, runner in ((100, self.paths.prefix, self.paths.runner),
                                    (101, self.root / "other", self.paths.runner),
                                    (102, self.paths.prefix, self.root / "wrong-runner")):
            proc = proc_root / str(pid)
            proc.mkdir()
            (proc / "comm").write_text("CrBrowserMain\n")
            (proc / "cmdline").write_bytes(str(self.exe).encode() + b"\0")
            (proc / "environ").write_bytes(f"WINEPREFIX={prefix}\0PROTONPATH={runner}\0".encode())
        self.assertEqual(fusion.active_processes(self.paths, proc_root), {"fusion": [100], "identity": []})

    def test_browser_handoff_never_uses_shell_and_rejects_other_schemes(self):
        uri = "https://accounts.autodesk.com/?state=$(touch%20no);echo"
        with patch.object(fusion.shutil, "which", return_value="/usr/bin/systemd-run"):
            command = fusion.browser_command(uri, self.root / "no-host")
        self.assertEqual(command[-2:], ["/usr/bin/xdg-open", uri])
        self.assertNotIn("-c", command)
        self.assertIn("--expand-environment=no", command)
        for uri in ("file:///tmp/private", "javascript:alert(1)", "https://user:pw@example.test/", "https://example.test/\n"):
            with self.assertRaises(fusion.LauncherError):
                fusion.browser_command(uri)

    def test_container_browser_uses_matching_host_systemd_library_directory(self):
        host = self.root / "host"
        (host / "usr/bin").mkdir(parents=True)
        (host / "usr/lib").mkdir()
        (host / "usr/bin/systemd-run").touch()
        (host / "usr/lib/ld-linux-x86-64.so.2").touch()
        command = fusion.browser_command("https://example.test/", host)
        self.assertEqual(command[:4], [str(host / "usr/lib/ld-linux-x86-64.so.2"),
                                      "--library-path",
                                      f"{host}/usr/lib:{host}/usr/lib/systemd",
                                      str(host / "usr/bin/systemd-run")])

    def test_container_browser_child_uses_public_bus_without_changing_parent(self):
        command = ["/run/host/usr/lib/ld-linux-x86-64.so.2", "--library-path", "placeholder"]
        desktop = {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/pressure-vessel/bus",
                   "XDG_RUNTIME_DIR": "/run/user/1000", "LD_LIBRARY_PATH": "wrong-proton-libs"}
        with (patch.dict(os.environ, desktop),
              patch.object(fusion, "browser_command", return_value=command),
              patch.object(fusion.subprocess, "call", return_value=0) as call):
            self.assertEqual(fusion.open_browser("https://example.test/"), 0)
            child = call.call_args.kwargs["env"]
            self.assertNotIn("XDG_RUNTIME_DIR", child)
            self.assertNotIn("LD_LIBRARY_PATH", child)
            self.assertEqual(child["DBUS_SESSION_BUS_ADDRESS"], desktop["DBUS_SESSION_BUS_ADDRESS"])
            self.assertEqual(os.environ["XDG_RUNTIME_DIR"], desktop["XDG_RUNTIME_DIR"])

    def test_host_browser_retains_regular_private_bus_environment(self):
        command = ["/usr/bin/systemd-run", "--user"]
        with (patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"}),
              patch.object(fusion, "browser_command", return_value=command),
              patch.object(fusion.subprocess, "call", return_value=0) as call):
            fusion.open_browser("https://example.test/")
            self.assertEqual(call.call_args.kwargs["env"]["XDG_RUNTIME_DIR"], "/run/user/1000")

    def test_environment_drops_software_renderer_wayland_and_debug_flags(self):
        bad = {"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe", "WAYLAND_DISPLAY": "wayland-1",
               "UMU_LOG": "debug", "PROTON_VERB": "destroyprefix", "QTWEBENGINE_CHROMIUM_FLAGS": "--bad",
               "QSG_RHI_BACKEND": "software", "QSG_INFO": "1", "QT_QUICK_BACKEND": "software",
               "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-gpu", "QT_WIDGETS_RHI": "1",
               "QT_WIDGETS_RHI_BACKEND": "d3d11", "QT_LOGGING_RULES": "*=true",
               "WINEQT_WIDGETS_RHI": "1", "WINEQT_WIDGETS_RHI_BACKEND": "opengl",
               "WINEQT_QPA_PLATFORM": "windows:verbose=2", "WINEQT_LOGGING_RULES": "*=true",
               "QT_FUTURE_BACKEND_OPTION": "host-setting", "WINEQT_FUTURE_BACKEND_OPTION": "host-setting",
               "QSG_FUTURE_BACKEND_OPTION": "host-setting", "QSG_RENDER_LOOP": "basic",
               "WINE_LAYERED_OVERLAY_ALPHA": "1", "WINE_LAYERED_OVERLAY_INPUT_SHAPE": "0",
               "WINE_X11_ARGB_SHAPE_INPUT": "0", "FUSION360_OVERLAY_ID": "old",
               "FUSION360_OVERLAY_SHA256": "old", "WINE_X11_ARGB_CONSTANT_ALPHA": "1"}
        with patch.dict(os.environ, bad):
            env = fusion.clean_environment(self.paths)
        for key in bad:
            self.assertNotIn(key, env)
        self.assertEqual(env["UMU_CONTAINER_NSENTER"], "1")
        self.assertEqual(env["UMU_RUNTIME_UPDATE"], "0")
        self.assertEqual(env["PROTONPATH"], str(self.paths.runner))

    def test_parser_errors_do_not_echo_uri(self):
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit):
            fusion.main(["auth", "--SECRET=credential"])
        self.assertNotIn("SECRET", output.getvalue())

    def readiness_line(self, seconds):
        timestamp = datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        return f"{timestamp} [AdskIdentityManager INFO] SSO Server is ready\n".encode()

    def test_identity_readiness_ignores_prior_session_and_partial_line(self):
        log = self.root / "identity.log"
        log.write_bytes(self.readiness_line(10))
        with patch.object(fusion.time, "time", return_value=20):
            cursor = fusion.IdentityReadiness.snapshot(log)
        self.assertFalse(cursor.poll())
        with log.open("ab") as stream:
            stream.write(b"new session has started\n")
        self.assertFalse(cursor.poll())
        fresh = self.readiness_line(21)
        with log.open("ab") as stream:
            stream.write(fresh[:-3])
        self.assertFalse(cursor.poll())
        with log.open("ab") as stream:
            stream.write(fresh[-3:])
        self.assertTrue(cursor.poll())

    def test_identity_readiness_handles_rotation_without_accepting_old_marker(self):
        log = self.root / "identity.log"
        log.write_bytes(b"existing unrelated data\n")
        with patch.object(fusion.time, "time", return_value=20):
            cursor = fusion.IdentityReadiness.snapshot(log)
        log.rename(self.root / "identity.log.old")
        log.write_bytes(self.readiness_line(10))
        self.assertFalse(cursor.poll())
        with log.open("ab") as stream:
            stream.write(self.readiness_line(21))
        self.assertTrue(cursor.poll())

    def test_identity_readiness_handles_truncate_and_regrow_past_previous_offset(self):
        log = self.root / "identity.log"
        log.write_bytes(b"existing log\n")
        with patch.object(fusion.time, "time", return_value=20):
            cursor = fusion.IdentityReadiness.snapshot(log)
        log.write_bytes(self.readiness_line(21) + b"further new log content\n")
        self.assertTrue(cursor.poll())

    def test_identity_readiness_can_start_before_log_exists(self):
        log = self.root / "new-identity.log"
        with patch.object(fusion.time, "time", return_value=20):
            cursor = fusion.IdentityReadiness.snapshot(log)
        self.assertFalse(cursor.poll())
        log.write_bytes(self.readiness_line(21))
        self.assertTrue(cursor.poll())

    def test_cold_launch_does_not_attach_until_fresh_sso_ready(self):
        readiness = Mock()
        readiness.poll.side_effect = [False, False, True]
        helper = Mock()
        helper.poll.return_value = None
        processes = [{"fusion": [], "identity": []}, {"fusion": [], "identity": [123]}]
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", side_effect=processes),
              patch.object(fusion, "active_bus", side_effect=[False, True]),
              patch.object(fusion.IdentityReadiness, "snapshot", return_value=readiness),
              patch.object(fusion.subprocess, "Popen", return_value=helper) as start,
              patch.object(fusion.time, "sleep"),
              patch.object(fusion, "attach", return_value=0) as attach):
            self.assertEqual(fusion.launch(self.paths), 0)
        self.assertEqual(readiness.poll.call_count, 3)
        self.assertEqual(start.call_args.args[0][-4:], fusion.IDENTITY_ARGS)
        attach.assert_called_once_with(self.paths, self.exe, [])

    def test_design_file_argument_uses_real_windows_drive_mapping(self):
        design = self.root / "Dansk ø design with spaces.f3d"
        design.write_bytes(b"test document")
        devices = self.paths.prefix / "dosdevices"
        devices.mkdir()
        (devices / "z:").symlink_to("/")
        expected = "Z:" + str(design).replace("/", "\\")
        self.assertEqual(fusion.windows_file_argument(self.paths, str(design)), expected)
        inside = self.build / "design.f3d"
        inside.touch()
        self.assertTrue(fusion.windows_file_argument(self.paths, str(inside)).startswith("C:\\users\\"))

    def test_file_open_delivers_windows_path_as_one_argument(self):
        design = self.root / "untrusted $(name); space.f3d"
        design.touch()
        devices = self.paths.prefix / "dosdevices"
        devices.mkdir()
        (devices / "z:").symlink_to("/")
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": []}),
              patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion, "attach", return_value=0) as attach):
            self.assertEqual(fusion.launch(self.paths, str(design)), 0)
        attach.assert_called_once_with(self.paths, self.exe, ["Z:" + str(design).replace("/", "\\")])

    def test_local_file_uri_decodes_once_and_uses_existing_drive_mapping(self):
        design = self.root / "ø model #1 percent%20.f3d"
        design.touch()
        devices = self.paths.prefix / "dosdevices"
        devices.mkdir()
        (devices / "z:").symlink_to("/")
        expected = "Z:" + str(design).replace("/", "\\")
        self.assertEqual(fusion.windows_file_argument(self.paths, design.as_uri()), expected)
        self.assertEqual(fusion.windows_file_argument(self.paths, design.as_uri().replace(
            "file:///", "file://localhost/", 1)), expected)
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": []}),
              patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion, "attach", return_value=0) as attach):
            self.assertEqual(fusion.launch(self.paths, design.as_uri()), 0)
        attach.assert_called_once_with(self.paths, self.exe, [expected])

    def test_file_uri_rejects_remote_authority_query_fragment_and_encoded_controls(self):
        for uri in ("file://remote.example/home/design.f3d", "file://user@localhost/home/design.f3d",
                    "file:///home/design.f3d?download=1", "file:///home/design.f3d?",
                    "file:///home/design.f3d#part", "file:///home/design.f3d#", "file:relative.f3d",
                    "file:///home/%00design.f3d", "file:///home/%0adesign.f3d", "file://[invalid/design.f3d"):
            with self.subTest(uri=uri), self.assertRaisesRegex(fusion.LauncherError, "local file URI"):
                fusion.windows_file_argument(self.paths, uri)

    def test_missing_or_restricted_z_drive_cannot_misaddress_local_file(self):
        design = self.root / "document.f3d"
        design.touch()
        with self.assertRaises(fusion.LauncherError):
            fusion.windows_file_argument(self.paths, str(design))
        devices = self.paths.prefix / "dosdevices"
        devices.mkdir()
        restricted = self.root / "other"
        restricted.mkdir()
        (devices / "z:").symlink_to(restricted)
        with self.assertRaises(fusion.LauncherError):
            fusion.windows_file_argument(self.paths, str(design))

    def test_maintenance_exclusive_lock_prevents_launch(self):
        with (self.paths.state / ".maintenance.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(fusion, "validate_runtime"), patch.object(fusion, "_launch") as launch:
                with self.assertRaisesRegex(fusion.LauncherError, "maintenance"):
                    fusion.launch(self.paths)
                launch.assert_not_called()

    def test_launch_holds_maintenance_lock_until_session_ready_then_releases(self):
        def during_launch(*args, **kwargs):
            with (self.paths.state / ".maintenance.lock").open("a") as maintenance:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(maintenance, fcntl.LOCK_EX | fcntl.LOCK_NB)
            kwargs["on_session_ready"]()
            with (self.paths.state / ".maintenance.lock").open("a") as maintenance:
                fcntl.flock(maintenance, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return 0
        with patch.object(fusion, "validate_runtime"), patch.object(fusion, "_launch", side_effect=during_launch):
            self.assertEqual(fusion.launch(self.paths), 0)
        with (self.paths.state / ".maintenance.lock").open("a") as maintenance:
            fcntl.flock(maintenance, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_concurrent_startup_cannot_launch_second_runtime(self):
        with (self.paths.state / ".launch.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (patch.object(fusion, "validate_runtime"),
                  patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": [123]}),
                  patch.object(fusion.time, "monotonic", side_effect=[0, 46]),
                  patch.object(fusion, "_launch") as launch):
                with self.assertRaisesRegex(fusion.LauncherError, "already starting"):
                    fusion.launch(self.paths)
                launch.assert_not_called()

    def test_concurrent_launch_can_attach_only_to_existing_session(self):
        with (self.paths.state / ".launch.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (patch.object(fusion, "validate_runtime"),
                  patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": [124]}),
                  patch.object(fusion, "active_bus", return_value=True),
                  patch.object(fusion, "_launch", return_value=0) as launch):
                self.assertEqual(fusion.launch(self.paths), 0)
                self.assertEqual(launch.call_args.args, (self.paths, None, True))
                self.assertIs(launch.call_args.kwargs["allow_cold_start"], False)
                self.assertTrue(callable(launch.call_args.kwargs["on_session_ready"]))

    def test_disappearing_concurrent_session_cannot_fall_back_to_cold_start(self):
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": []}),
              patch.object(fusion.subprocess, "Popen") as start,
              patch.object(fusion.subprocess, "call") as call):
            with self.assertRaisesRegex(fusion.LauncherError, "session closed"):
                fusion._launch(self.paths, allow_cold_start=False)
            start.assert_not_called()
            call.assert_not_called()

    def prepare_runtime(self):
        lock = {"schema": 1, "runner": {"name": fusion.RUNNER},
                "launcher": {"version": "1.4.4"},
                "steam_runtime": {"version": "4.0.20260914.260627"}}
        (self.paths.state / "compatibility-lock.json").write_text(json.dumps(lock))
        self.paths.runner.mkdir()
        (self.paths.runner / "version").write_text("1789520217 GE-Proton11-7\n")
        (self.paths.runner / "toolmanifest.vdf").write_text('"require_tool_appid" "4183110"\n')
        self.paths.client.parent.mkdir(parents=True)
        self.paths.client.touch()
        (self.paths.runtime / "VERSIONS.txt").write_text(
            "depot\t4.0.20260914.260627\nsteamrt4\t4.0.20260914.260627\tsteamrt4\n")

    def test_runtime_preflight_checks_actual_umu_and_runtime_against_lock(self):
        self.prepare_runtime()
        result = Mock(returncode=0, stdout="umu-launcher version 1.4.4 (Python)\n")
        with patch.object(fusion.shutil, "which", return_value="/usr/bin/umu-run"), patch.object(fusion.subprocess, "run", return_value=result):
            fusion.validate_runtime(self.paths)
            result.stdout = "umu-launcher version 1.4.5 (Python)\n"
            with self.assertRaisesRegex(fusion.LauncherError, "umu-launcher differs"):
                fusion.validate_runtime(self.paths)
            result.stdout = "umu-launcher version 1.4.4 (Python)\n"
            (self.paths.runtime / "VERSIONS.txt").write_text(
                "depot\t4.0.20260914.260627\nsteamrt4\t4.0.20261001.999999\tsteamrt4\n")
            with self.assertRaisesRegex(fusion.LauncherError, "Runtime differs"):
                fusion.validate_runtime(self.paths)

    def test_runtime_preflight_rejects_missing_versions_on_daily_launch(self):
        self.prepare_runtime()
        (self.paths.runtime / "VERSIONS.txt").unlink()
        result = Mock(returncode=0, stdout="umu-launcher version 1.4.4 (Python)\n")
        with patch.object(fusion.shutil, "which", return_value="/usr/bin/umu-run"), patch.object(fusion.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(fusion.LauncherError, "build could not be checked"):
                fusion.validate_runtime(self.paths)

    def prepare_overlay(self):
        self.prepare_runtime()
        payload = b"reviewed test module"
        overlay = {"id": "ge-proton11-7-omarchy-x11-v1", "target": fusion.OVERLAY_TARGET,
                   "original_sha256": "0" * 64, "sha256": hashlib.sha256(payload).hexdigest(),
                   "required_environment": dict(fusion.OVERLAY_ENVIRONMENT),
                   "manifest": "runtime-patches/manifest.json"}
        lock_path = self.paths.state / "compatibility-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["runner_overlay"] = overlay
        lock_path.write_text(json.dumps(lock))
        manifest = self.paths.state / overlay["manifest"]
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"schema": 1, **overlay}))
        target = self.paths.runner / overlay["target"]
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)
        return overlay, target

    def fake_process(self, pid, runner, extra=None, mapped_inode=None):
        root = self.root / "proc"
        proc = root / str(pid)
        proc.mkdir(parents=True)
        (proc / "comm").write_text("CrBrowserMain\n")
        (proc / "cmdline").write_bytes(str(self.exe).encode() + b"\0")
        env = {"WINEPREFIX": str(self.paths.prefix), "PROTONPATH": str(runner), **(extra or {})}
        (proc / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in env.items()))
        lines = ""
        if mapped_inode is not None:
            target = self.paths.runner / fusion.OVERLAY_TARGET
            major, minor, _ = fusion.mapped_file_identity(target)
            device = f"{major:x}:{minor:x}"
            lines = f"1000-2000 r-xp 0000 {device} {mapped_inode} {target}\n"
        (proc / "maps").write_text(lines)
        return root

    def prepare_overlay_v2(self):
        legacy, first = self.prepare_overlay()
        modules = [{key: legacy[key] for key in ("target", "original_sha256", "sha256")}]
        second = self.paths.runner / "files/lib/wine/x86_64-unix/win32u.so"
        second.write_bytes(b"reviewed presentation module")
        modules.append({"target": str(second.relative_to(self.paths.runner)), "original_sha256": "1" * 64,
                        "sha256": hashlib.sha256(second.read_bytes()).hexdigest()})
        overlay = {"id": "ge-proton11-7-omarchy-x11-v2", "modules": modules,
                   "required_environment": dict(fusion.OVERLAY_ENVIRONMENT_V2), "manifest": legacy["manifest"]}
        self.write_overlay_v2(overlay)
        return overlay, (first, second)

    def write_overlay_v2(self, overlay):
        path = self.paths.state / "compatibility-lock.json"
        lock = json.loads(path.read_text())
        lock["runner_overlay"] = overlay
        path.write_text(json.dumps(lock))
        (self.paths.state / "runtime-patches/manifest.json").write_text(json.dumps({"schema": 2, **overlay}))

    def prepare_overlay_v3(self):
        previous, targets = self.prepare_overlay_v2()
        overlay = {**previous, "id": "ge-proton11-7-omarchy-x11-v3",
                   "required_environment": dict(fusion.OVERLAY_ENVIRONMENT_V3)}
        self.write_overlay_v2(overlay)
        return overlay, targets

    def test_v3_requires_exact_environment_and_both_unchanged_reviewed_modules(self):
        overlay, targets = self.prepare_overlay_v3()
        self.assertEqual(fusion.runner_overlay(self.paths), overlay)
        fusion.validate_overlay(self.paths, overlay)
        for target in targets:
            original = target.read_bytes()
            target.write_bytes(b"unreviewed replacement")
            with self.subTest(target=target.name), self.assertRaises(fusion.LauncherError):
                fusion.validate_overlay(self.paths, overlay)
            target.write_bytes(original)
        invalid = [
            {**overlay, "id": "ge-proton11-7-omarchy-x11-v2"},
            {**overlay, "id": [overlay["id"]]},
            {**overlay, "required_environment": dict(fusion.OVERLAY_ENVIRONMENT_V2)},
            {**overlay, "required_environment": dict(fusion.OVERLAY_ENVIRONMENT)},
            {**overlay, "required_environment": {**overlay["required_environment"], "QT_WIDGETS_RHI": "1"}},
            {**overlay, "modules": [overlay["modules"][0]] * 2},
        ]
        for malformed in invalid:
            self.write_overlay_v2(malformed)
            with self.subTest(overlay=malformed), self.assertRaises(fusion.LauncherError):
                fusion.runner_overlay(self.paths)

    def test_v3_rejects_v2_session_despite_identical_runner_and_module_bytes(self):
        overlay, targets = self.prepare_overlay_v3()
        previous = {**overlay, "id": "ge-proton11-7-omarchy-x11-v2",
                    "required_environment": dict(fusion.OVERLAY_ENVIRONMENT_V2)}
        self.assertEqual(previous["modules"], overlay["modules"])
        self.assertNotEqual(fusion.overlay_identity(previous), fusion.overlay_identity(overlay))
        expected = {**fusion.overlay_session_environment(overlay), "UMU_CONTAINER_NSENTER": "1"}
        root = self.fake_process(123, self.paths.runner, expected)
        proc = root / "123"
        original = (proc / "environ").read_bytes()
        maps = []
        for index, target in enumerate(targets):
            major, minor, inode = fusion.mapped_file_identity(target)
            maps.append(f"{index + 1}000-{index + 2}000 r-xp 0000 {major:x}:{minor:x} {inode} {target}\n")
        (proc / "maps").write_text("".join(maps))
        self.assertFalse(fusion.session_conflict(self.paths, root))
        self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [123])
        stale_environments = [
            fusion.overlay_session_environment(previous),
            {**expected, "QSG_RHI_BACKEND": "d3d11"},
            {**expected, "FUSION360_OVERLAY_SHA256": fusion.overlay_identity(previous)},
        ]
        for stale in stale_environments:
            env = {**expected, **stale, "WINEPREFIX": str(self.paths.prefix), "PROTONPATH": str(self.paths.runner)}
            (proc / "environ").write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in env.items()))
            (proc / "cmdline").write_bytes(str(self.exe).encode() + b"\0")
            with self.subTest(stale=stale):
                self.assertTrue(fusion.session_conflict(self.paths, root))
                self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [])
                (proc / "cmdline").write_bytes(b"/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service\0")
                with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
                      patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0, stdout="u 123\n"))):
                    with self.assertRaisesRegex(fusion.LauncherError, "unverified owner"):
                        fusion.runtime_owner(self.paths, root)
        with (patch.object(fusion, "session_conflict", return_value=True),
              patch.object(fusion.subprocess, "call") as call):
            with self.assertRaisesRegex(fusion.LauncherError, "different Fusion runtime"):
                fusion.attach(self.paths, self.idm, ["adskidmgr:/login?code=fixture&state=fixture"])
            call.assert_not_called()
        (proc / "environ").write_bytes(original)
        with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0, stdout="u 123\n"))):
            self.assertEqual(fusion.runtime_owner(self.paths, root), 123)

    def test_v3_quiet_cold_identity_start_and_attachment_use_exact_environment(self):
        overlay, _ = self.prepare_overlay_v3()
        readiness, helper = Mock(), Mock()
        readiness.poll.return_value = True
        inherited = {"QSG_RHI_BACKEND": "d3d11", "WINEDEBUG": "+timestamp,+debugstr",
                     "DXVK_CONFIG": "dxgi.syncInterval = 0", "DXVK_CONFIG_FILE": "/tmp/old.conf"}
        with (patch.dict(os.environ, inherited),
              patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_conflict", return_value=False),
              patch.object(fusion, "active_processes", side_effect=[{"fusion": [], "identity": []},
                                                                    {"fusion": [], "identity": [123]}]),
              patch.object(fusion, "active_bus", side_effect=[False, True]),
              patch.object(fusion.IdentityReadiness, "snapshot", return_value=readiness),
              patch.object(fusion.subprocess, "Popen", return_value=helper) as start,
              patch.object(fusion, "attach", return_value=0)):
            self.assertEqual(fusion.launch(self.paths), 0)
        self.assertEqual(start.call_args.args[0][1], str(self.idm))
        environment = start.call_args.kwargs["env"]
        self.assertEqual(environment["WINEDEBUG"], "-all")
        for key, value in fusion.overlay_session_environment(overlay).items():
            self.assertEqual(environment[key], value)
            self.assertIn("--pass-env=" + key, fusion.attach_command(self.paths, self.exe, []))
        for key in ("DXVK_CONFIG", "DXVK_CONFIG_FILE"):
            self.assertNotIn(key, environment)
            self.assertIn("--unset-env=" + key, fusion.attach_command(self.paths, self.exe, []))

    def test_v3_refuses_inherited_dxvk_overrides_in_active_process_and_idle_owner(self):
        overlay, _ = self.prepare_overlay_v3()
        env = {**fusion.overlay_session_environment(overlay), "UMU_CONTAINER_NSENTER": "1"}
        root = self.fake_process(123, self.paths.runner, env)
        original = (root / "123/environ").read_bytes()
        for key, value in (("DXVK_CONFIG_FILE", "/tmp/unreviewed.conf"), ("DXVK_CONFIG", "dxgi.maxFrameRate = 1")):
            with self.subTest(key=key):
                (root / "123/environ").write_bytes(original + b"\0" + (key + "=" + value).encode())
                (root / "123/cmdline").write_bytes(str(self.exe).encode() + b"\0")
                self.assertTrue(fusion.session_conflict(self.paths, root))
                self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [])
                (root / "123/cmdline").write_bytes(b"/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service\0")
                with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
                      patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0, stdout="u 123\n"))):
                    with self.assertRaisesRegex(fusion.LauncherError, "unverified owner"):
                        fusion.runtime_owner(self.paths, root)

    def test_v2_requires_both_reviewed_modules_before_launch(self):
        overlay, targets = self.prepare_overlay_v2()
        self.assertEqual(fusion.runner_overlay(self.paths), overlay)
        fusion.validate_overlay(self.paths, overlay)
        for target in targets:
            original = target.read_bytes()
            target.write_bytes(b"unreviewed replacement")
            with self.subTest(target=target.name), self.assertRaises(fusion.LauncherError):
                fusion.validate_runtime(self.paths)
            target.write_bytes(original)
        targets[1].unlink()
        with self.assertRaises(fusion.LauncherError):
            fusion.validate_overlay(self.paths, overlay)
        targets[1].symlink_to(targets[0])
        with self.assertRaises(fusion.LauncherError):
            fusion.validate_overlay(self.paths, overlay)

    def test_v2_rejects_ambiguous_targets_extra_metadata_and_unreviewed_environment(self):
        overlay, _ = self.prepare_overlay_v2()
        invalid = [
            {**overlay, "modules": [overlay["modules"][0]] * 2},
            {**overlay, "modules": [overlay["modules"][0], {**overlay["modules"][1], "target": "../../outside.so"}]},
            {**overlay, "modules": [overlay["modules"][0], {**overlay["modules"][1], "sha256": "bad"}]},
            {**overlay, "modules": [overlay["modules"][0], {**overlay["modules"][1], "unreviewed": True}]},
            {**overlay, "target": fusion.OVERLAY_TARGET},
            {**overlay, "required_environment": {**overlay["required_environment"], "QSG_RHI_BACKEND": "opengl"}},
            {**overlay, "required_environment": {**overlay["required_environment"], "WINE_X11_VULKAN_PRESENT_WAIT": "0"}},
        ]
        for malformed in invalid:
            self.write_overlay_v2(malformed)
            with self.subTest(overlay=malformed), self.assertRaises(fusion.LauncherError):
                fusion.runner_overlay(self.paths)

    def test_v2_session_identity_covers_both_modules_and_environment(self):
        overlay, targets = self.prepare_overlay_v2()
        identity = fusion.overlay_identity(overlay)
        self.assertEqual(identity, fusion.overlay_identity({**overlay, "modules": list(reversed(overlay["modules"]))}))
        for index in range(2):
            changed = [dict(module) for module in overlay["modules"]]
            changed[index]["sha256"] = "f" * 64
            self.assertNotEqual(identity, fusion.overlay_identity({**overlay, "modules": changed}))
        expected = fusion.overlay_session_environment(overlay)
        root = self.fake_process(123, self.paths.runner, expected)
        maps = root / "123/maps"
        identities = [fusion.mapped_file_identity(target) for target in targets]
        def mappings(bad_index=None, deleted=False):
            return "".join(f"{i+1}000-{i+2}000 r-xp 0000 {major:x}:{minor:x} "
                           f"{inode + (i == bad_index and not deleted)} {target}"
                           + (" (deleted)" if i == bad_index and deleted else "") + "\n"
                           for i, (target, (major, minor, inode)) in enumerate(zip(targets, identities)))
        maps.write_text(mappings())
        self.assertFalse(fusion.session_conflict(self.paths, root))
        for index in range(2):
            for deleted in (False, True):
                maps.write_text(mappings(index, deleted))
                with self.subTest(index=index, deleted=deleted):
                    self.assertTrue(fusion.session_conflict(self.paths, root))
        maps.write_text(mappings())
        environ = root / "123/environ"
        environ.write_bytes(environ.read_bytes().replace(b"QSG_RHI_BACKEND=d3d11", b"QSG_RHI_BACKEND=opengl"))
        self.assertTrue(fusion.session_conflict(self.paths, root))

    def test_v2_environment_attachment_and_status_identify_complete_pair(self):
        overlay, _ = self.prepare_overlay_v2()
        with patch.dict(os.environ, {"WINE_X11_VULKAN_PRESENT_WAIT": "0", "QSG_RHI_BACKEND": "opengl",
                                     "DXVK_CONFIG": "dxgi.syncInterval = 4", "DXVK_CONFIG_FILE": "/tmp/other.conf"}):
            environment = fusion.clean_environment(self.paths)
        self.assertNotIn("DXVK_CONFIG_FILE", environment)
        self.assertNotIn("DXVK_CONFIG", environment)
        for key, value in fusion.overlay_session_environment(overlay).items():
            self.assertEqual(environment[key], value)
            self.assertIn("--pass-env=" + key, fusion.attach_command(self.paths, self.exe, []))
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": []}),
              patch.object(fusion, "active_bus", return_value=False),
              patch.object(fusion, "session_conflict", return_value=False)):
            report = fusion.status(self.paths)
        self.assertEqual(report["runner_overlay_modules"], {m["target"]: m["sha256"] for m in overlay["modules"]})
        self.assertEqual(report["runner_overlay_sha256"], fusion.overlay_identity(overlay))

    def test_v2_refuses_runtime_file_overrides_and_unsets_them_on_attachment(self):
        overlay, _ = self.prepare_overlay_v2()
        env = {**fusion.overlay_session_environment(overlay), "UMU_CONTAINER_NSENTER": "1"}
        root = self.fake_process(123, self.paths.runner, env)
        original = (root / "123/environ").read_bytes()
        for key, value in (("DXVK_CONFIG_FILE", "/tmp/unreviewed.conf"), ("DXVK_CONFIG", "dxgi.maxFrameRate = 1")):
            with self.subTest(key=key):
                (root / "123/environ").write_bytes(original + b"\0" + (key + "=" + value).encode())
                (root / "123/cmdline").write_bytes(str(self.exe).encode() + b"\0")
                self.assertTrue(fusion.session_conflict(self.paths, root))
                self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [])
                (root / "123/cmdline").write_bytes(b"/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service\0")
                with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
                      patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0, stdout="u 123\n"))):
                    with self.assertRaisesRegex(fusion.LauncherError, "unverified owner"):
                        fusion.runtime_owner(self.paths, root)
        self.assertIn("--unset-env=DXVK_CONFIG_FILE", fusion.attach_command(self.paths, self.exe, []))
        self.assertIn("--unset-env=DXVK_CONFIG", fusion.attach_command(self.paths, self.exe, []))

    def test_required_overlay_hash_fails_closed_when_missing_or_modified(self):
        overlay, target = self.prepare_overlay()
        result = Mock(returncode=0, stdout="umu-launcher version 1.4.4 (Python)\n")
        with (patch.object(fusion.shutil, "which", return_value="/usr/bin/umu-run"),
              patch.object(fusion.subprocess, "run", return_value=result)):
            fusion.validate_runtime(self.paths)
            target.write_bytes(b"unreviewed build")
            with self.assertRaisesRegex(fusion.LauncherError, "overlay is missing or changed"):
                fusion.validate_runtime(self.paths)
            target.unlink()
            with self.assertRaisesRegex(fusion.LauncherError, "overlay is missing or changed"):
                fusion.validate_runtime(self.paths)

    def test_overlay_manifest_rejects_path_escape_unknown_flags_or_hash_disagreement(self):
        overlay, target = self.prepare_overlay()
        lock = fusion.compatibility_lock(self.paths)
        for key, value in (("target", "../../outside.so"),
                           ("required_environment", {"LD_PRELOAD": "unreviewed.so"}),
                           ("sha256", "f" * 64)):
            malformed = {**lock, "runner_overlay": {**overlay, key: value}}
            with self.subTest(key=key), self.assertRaisesRegex(fusion.LauncherError, "manifest"):
                fusion.runner_overlay(self.paths, malformed)

    def test_overlay_environment_overrides_inherited_values_and_is_passed_to_attachment(self):
        overlay, target = self.prepare_overlay()
        with patch.dict(os.environ, {"WINE_X11_ARGB_SHAPE_INPUT": "0", "FUSION360_OVERLAY_ID": "stale",
                                    "QSG_RHI_BACKEND": "d3d11", "WINE_LAYERED_OVERLAY_ALPHA": "1"}):
            env = fusion.clean_environment(self.paths)
        expected = fusion.overlay_session_environment(overlay)
        self.assertEqual(env["QSG_RHI_BACKEND"], "opengl")
        self.assertNotIn("WINE_LAYERED_OVERLAY_ALPHA", env)
        for key, value in expected.items():
            self.assertEqual(env[key], value)
            self.assertIn(f"--pass-env={key}", fusion.attach_command(self.paths, self.exe, []))

    def test_overlay_manifest_rejects_unreviewed_environment_even_when_lock_matches(self):
        overlay, target = self.prepare_overlay()
        expected = dict(fusion.OVERLAY_ENVIRONMENT)
        missing_qsg = {key: value for key, value in expected.items() if key != "QSG_RHI_BACKEND"}
        for environment in (missing_qsg, {**expected, "QSG_RHI_BACKEND": "d3d11"},
                            {**expected, "WINE_X11_UNREVIEWED_FLAG": "1"},
                            {**expected, "QT_WIDGETS_RHI": "1"}):
            malformed = {**overlay, "required_environment": environment}
            (self.paths.state / overlay["manifest"]).write_text(json.dumps({"schema": 1, **malformed}))
            lock = {**fusion.compatibility_lock(self.paths), "runner_overlay": malformed}
            with self.subTest(environment=environment), self.assertRaisesRegex(fusion.LauncherError, "manifest"):
                fusion.runner_overlay(self.paths, lock)

    def test_cold_identity_start_has_required_overlay_environment(self):
        overlay, target = self.prepare_overlay()
        readiness, helper = Mock(), Mock()
        readiness.poll.return_value = True
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_conflict", return_value=False),
              patch.object(fusion, "active_processes", side_effect=[{"fusion": [], "identity": []},
                                                                    {"fusion": [], "identity": [123]}]),
              patch.object(fusion, "active_bus", side_effect=[False, True]),
              patch.object(fusion.IdentityReadiness, "snapshot", return_value=readiness),
              patch.object(fusion.subprocess, "Popen", return_value=helper) as start,
              patch.object(fusion, "attach", return_value=0)):
            self.assertEqual(fusion.launch(self.paths), 0)
        for key, value in fusion.overlay_session_environment(overlay).items():
            self.assertEqual(start.call_args.kwargs["env"][key], value)

    def test_same_prefix_experimental_runtime_is_rejected(self):
        root = self.fake_process(123, self.root / "experimental-runner")
        self.assertTrue(fusion.session_conflict(self.paths, root))
        with (patch.object(fusion, "session_conflict", return_value=True),
              patch.object(fusion.subprocess, "call") as call):
            with self.assertRaisesRegex(fusion.LauncherError, "different Fusion runtime"):
                fusion.attach(self.paths, self.idm, ["adskidmgr:/login?code=SECRET&state=x"])
            call.assert_not_called()

    def test_overlay_session_requires_markers_and_current_mapped_module_inode(self):
        overlay, target = self.prepare_overlay()
        expected = fusion.overlay_session_environment(overlay)
        root = self.fake_process(123, self.paths.runner, expected, target.stat().st_ino)
        self.assertFalse(fusion.session_conflict(self.paths, root))
        self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [123])
        (root / "123/maps").write_text((root / "123/maps").read_text().replace(
            f" {target.stat().st_ino} ", f" {target.stat().st_ino + 1} "))
        self.assertTrue(fusion.session_conflict(self.paths, root))
        (root / "123/maps").write_text("")
        (root / "123/environ").write_bytes((root / "123/environ").read_bytes().replace(
            b"WINE_X11_ARGB_SHAPE_INPUT=1", b"WINE_X11_ARGB_SHAPE_INPUT=0"))
        self.assertTrue(fusion.session_conflict(self.paths, root))
        self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [])

    def test_qsg_backend_is_required_for_active_processes_and_runtime_reentry(self):
        overlay, target = self.prepare_overlay()
        expected = {**fusion.overlay_session_environment(overlay), "UMU_CONTAINER_NSENTER": "1"}
        root = self.fake_process(123, self.paths.runner, expected, target.stat().st_ino)
        proc = root / "123"
        approved = (proc / "environ").read_bytes()
        result = Mock(returncode=0, stdout="u 123\n")
        for actual in (approved.replace(b"QSG_RHI_BACKEND=opengl", b"QSG_RHI_BACKEND=d3d11"),
                       b"\0".join(item for item in approved.split(b"\0")
                                  if not item.startswith(b"QSG_RHI_BACKEND="))):
            with self.subTest(environment=actual):
                (proc / "environ").write_bytes(actual)
                self.assertTrue(fusion.session_conflict(self.paths, root))
                self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [])
                (proc / "cmdline").write_bytes(b"/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service\0")
                with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
                      patch.object(fusion.subprocess, "run", return_value=result)):
                    with self.assertRaisesRegex(fusion.LauncherError, "unverified owner"):
                        fusion.runtime_owner(self.paths, root)
                (proc / "cmdline").write_bytes(str(self.exe).encode() + b"\0")

    def test_session_accepts_btrfs_mapping_device_but_rejects_different_mapped_file(self):
        overlay, target = self.prepare_overlay()
        expected = fusion.overlay_session_environment(overlay)
        root = self.fake_process(123, self.paths.runner, expected, target.stat().st_ino)
        stat = target.stat()
        # Emulate Btrfs: the mapped superblock device differs from the device
        # returned by stat(), while the mapped module itself is unchanged.
        device = (os.major(stat.st_dev), os.minor(stat.st_dev) + 1)
        identity = (*device, stat.st_ino)
        maps = root / "123/maps"
        line = f"1000-2000 r-xp 0000 {device[0]:x}:{device[1]:x} {stat.st_ino} {target}\n"
        maps.write_text(line)
        with patch.object(fusion, "mapped_file_identity", return_value=identity):
            self.assertFalse(fusion.session_conflict(self.paths, root))
            maps.write_text(line.replace(f"{device[0]:x}:{device[1]:x}",
                                         f"{device[0]:x}:{device[1]+1:x}"))
            self.assertTrue(fusion.session_conflict(self.paths, root))
            maps.write_text(line.rstrip() + " (deleted)\n")
            self.assertTrue(fusion.session_conflict(self.paths, root))
        with patch.object(fusion, "mapped_file_identity", side_effect=OSError):
            self.assertTrue(fusion.session_conflict(self.paths, root))

    def test_status_identifies_overlay_without_claiming_conflicting_session_is_ready(self):
        overlay, target = self.prepare_overlay()
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": []}),
              patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion, "session_conflict", return_value=True)):
            report = fusion.status(self.paths)
        self.assertEqual(report["runner"], fusion.RUNNER)
        self.assertEqual(report["runner_overlay"], overlay["id"])
        self.assertTrue(report["runner_overlay_verified"])
        self.assertTrue(report["session_conflict"])
        self.assertFalse(report["session_attachment_ready"])

    def test_idle_bus_owner_requires_exact_service_prefix_runner_and_overlay(self):
        overlay, target = self.prepare_overlay()
        env = {**fusion.overlay_session_environment(overlay), "UMU_CONTAINER_NSENTER": "1"}
        root = self.fake_process(123, self.paths.runner, env)
        proc = root / "123"
        (proc / "cmdline").write_bytes(b"/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service\0")
        result = Mock(returncode=0, stdout="u 123\n")
        with (patch.object(fusion.shutil, "which", return_value="/usr/bin/busctl"),
              patch.object(fusion.subprocess, "run", return_value=result)):
            self.assertEqual(fusion.runtime_owner(self.paths, root), 123)
            (proc / "environ").write_bytes((proc / "environ").read_bytes().replace(
                b"WINE_X11_ARGB_SHAPE_INPUT=1", b"WINE_X11_ARGB_SHAPE_INPUT=0"))
            with self.assertRaisesRegex(fusion.LauncherError, "unverified owner"):
                fusion.runtime_owner(self.paths, root)

    def test_compatible_idle_runtime_restarts_identity_without_cold_umu_fallback(self):
        readiness, helper = Mock(), Mock()
        readiness.poll.return_value = True
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "runtime_owner", return_value=321) as owner,
              patch.object(fusion, "active_processes", side_effect=[{"fusion": [], "identity": []},
                                                                    {"fusion": [], "identity": [123]}]),
              patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion.IdentityReadiness, "snapshot", return_value=readiness),
              patch.object(fusion.subprocess, "Popen", return_value=helper) as start,
              patch.object(fusion, "attach", return_value=0)):
            self.assertEqual(fusion.launch(self.paths), 0)
        owner.assert_called_once_with(self.paths)
        command = start.call_args.args[0]
        self.assertEqual(command[0], str(self.paths.client))
        self.assertIn(f"--bus-name={self.paths.bus}", command)
        self.assertIn("runinprefix", command)
        self.assertEqual(command[-4:], fusion.IDENTITY_ARGS)

    def test_idle_bus_alone_is_never_sufficient_for_authentication(self):
        with (patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": []}),
              patch.object(fusion.subprocess, "Popen") as start,
              patch.object(fusion.subprocess, "call") as call):
            with self.assertRaisesRegex(fusion.LauncherError, "No matching Fusion session"):
                fusion.attach(self.paths, self.idm, ["adskidmgr:/login?code=SECRET&state=x"])
        start.assert_not_called()
        call.assert_not_called()

    def test_stop_idle_runtime_refuses_application_or_background_update_work(self):
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_bus", return_value=True),
              patch.object(fusion, "runtime_owner", return_value=321),
              patch.object(fusion.subprocess, "run") as terminate):
            with patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": []}):
                with self.assertRaisesRegex(fusion.LauncherError, "still running"):
                    fusion.stop_idle_runtime(self.paths)
            with (patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": []}),
                  patch.object(fusion, "prefix_processes", return_value=[fusion.PrefixProcess(
                      456, 321, "streamer.exe", r"C:\Autodesk\streamer.exe", Path("/wine"))])):
                with self.assertRaisesRegex(fusion.LauncherError, "update work"):
                    fusion.stop_idle_runtime(self.paths)
            terminate.assert_not_called()

    def test_stop_verified_idle_runtime_uses_only_exact_bus_and_waits_for_exit(self):
        service = [fusion.PrefixProcess(
            321, 1, "x86_64-linux-gn", "/run/pressure-vessel/x86_64-linux-gnu-srt-launcher-service",
            Path("/usr/lib/pressure-vessel/from-host/libexec/steam-runtime-tools-0/x86_64-linux-gnu-srt-launcher-service")),
            fusion.PrefixProcess(654, 321, "services.exe", r"C:\windows\system32\services.exe", Path("/wine"),
                                 (self.paths.runner / "files/lib/wine/x86_64-windows/services.exe",))]
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [], "identity": []}),
              patch.object(fusion, "active_bus", side_effect=[True, False]),
              patch.object(fusion, "runtime_owner", return_value=321),
              patch.object(fusion, "prefix_processes", side_effect=[service, service, []]),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0)) as terminate):
            self.assertEqual(fusion.stop_idle_runtime(self.paths), 0)
        self.assertEqual(terminate.call_args.args[0],
                         [str(self.paths.client), f"--bus-name={self.paths.bus}", "--terminate"])

    @contextmanager
    def idle_shutdown_fixture(self, processes, on_signal=None):
        clock = [0.0]
        with ExitStack() as stack:
            for name, value in (("validate_runtime", None), ("session_conflict", False),
                                ("active_processes", {"fusion": [], "identity": []}),
                                ("active_bus", False)):
                stack.enter_context(patch.object(fusion, name, return_value=value))
            read = stack.enter_context(patch.object(fusion, "prefix_processes", side_effect=lambda _: list(processes)))
            owner = stack.enter_context(patch.object(fusion, "runtime_owner"))
            command = stack.enter_context(patch.object(fusion.subprocess, "run"))
            opened = stack.enter_context(patch.object(fusion.os, "pidfd_open", side_effect=lambda pid: pid + 1000))
            sent = stack.enter_context(patch.object(fusion.signal, "pidfd_send_signal", side_effect=on_signal))
            closed = stack.enter_context(patch.object(fusion.os, "close"))
            stack.enter_context(patch.object(fusion.time, "monotonic", side_effect=lambda: clock[0]))
            stack.enter_context(patch.object(fusion.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
            yield {"clock": clock, "read": read, "owner": owner, "command": command,
                   "opened": opened, "sent": sent, "closed": closed}

    def stock_idle_service(self, pid, name):
        return fusion.PrefixProcess(pid, 1, name, f"C:\\windows\\system32\\{name}", Path("/wine"),
                                   (self.paths.runner / "files/lib/wine/x86_64-windows" / name,))

    def test_orphan_services_can_be_stopped_after_runtime_bus_has_already_exited(self):
        server = fusion.PrefixProcess(123, 1, "wineserver", "wineserver", self.paths.runner / "files/bin/wineserver")
        processes = [server, self.stock_idle_service(124, "services.exe")]
        def signal_process(descriptor, signum):
            self.assertEqual(signum, fusion.signal.SIGTERM)
            processes[:] = [process for process in processes if process.pid != descriptor - 1000]
        with self.idle_shutdown_fixture(processes, signal_process) as calls:
            self.assertEqual(fusion.stop_idle_runtime(self.paths), 0)
            self.assertEqual([call.args for call in calls["sent"].call_args_list],
                             [(1123, fusion.signal.SIGTERM), (1124, fusion.signal.SIGTERM)])
            calls["owner"].assert_not_called()
            calls["command"].assert_not_called()
            self.assertEqual(calls["closed"].call_count, 2)

    def test_shutdown_rechecks_all_prefix_work_after_opening_pidfds(self):
        processes = [self.stock_idle_service(124, "services.exe")]
        updater = fusion.PrefixProcess(999, 1, "streamer.exe", r"C:\Autodesk\streamer.exe", Path("/wine"))
        with self.idle_shutdown_fixture(processes) as calls:
            def opened(pid):
                processes.append(updater)
                return pid + 1000
            calls["opened"].side_effect = opened
            with self.assertRaisesRegex(fusion.LauncherError, "update work"):
                fusion.stop_idle_runtime(self.paths)
            calls["sent"].assert_not_called()
            calls["closed"].assert_called_once_with(1124)

    def test_shutdown_refuses_changed_runner_before_addressing_orphan_services(self):
        processes = [self.stock_idle_service(124, "services.exe")]
        with self.idle_shutdown_fixture(processes) as calls, patch.object(fusion, "session_conflict", return_value=True):
            with self.assertRaisesRegex(fusion.LauncherError, "different Fusion runtime"):
                fusion.stop_idle_runtime(self.paths)
            calls["opened"].assert_not_called()
            calls["sent"].assert_not_called()

    def test_shutdown_grace_then_forces_only_verified_device_and_dead_analytics_group(self):
        processes = [self.stock_idle_service(124, "winedevice.exe"),
                     fusion.PrefixProcess(125, 1, "ADPClientServic", str(self.build / "ADPClientService.exe"),
                                          Path("/wine"), (self.build / "ADPClientService.exe",), True)]
        def signal_process(descriptor, signum):
            if signum == fusion.signal.SIGKILL:
                self.assertGreaterEqual(calls["clock"][0], 3)
                processes[:] = [process for process in processes if process.pid != descriptor - 1000]
        with self.idle_shutdown_fixture(processes, signal_process) as calls:
            self.assertEqual(fusion.stop_idle_runtime(self.paths), 0)
            self.assertEqual([call.args for call in calls["sent"].call_args_list],
                             [(1124, fusion.signal.SIGTERM), (1125, fusion.signal.SIGTERM),
                              (1124, fusion.signal.SIGKILL), (1125, fusion.signal.SIGKILL)])
            self.assertEqual(calls["opened"].call_count, 2)

    def test_shutdown_never_forces_live_analytics_other_services_or_device_with_wineserver(self):
        analytics = fusion.PrefixProcess(125, 1, "ADPClientServic", str(self.build / "ADPClientService.exe"),
                                        Path("/wine"), (self.build / "ADPClientService.exe",))
        server = fusion.PrefixProcess(123, 1, "wineserver", "wineserver", self.paths.runner / "files/bin/wineserver")
        for processes in ([analytics], [self.stock_idle_service(126, "services.exe")],
                          [server, self.stock_idle_service(124, "winedevice.exe")]):
            with self.subTest(processes=processes), self.idle_shutdown_fixture(processes) as calls:
                with self.assertRaisesRegex(fusion.LauncherError, "still exiting"):
                    fusion.stop_idle_runtime(self.paths)
                self.assertTrue(calls["sent"].called)
                self.assertTrue(all(call.args[1] == fusion.signal.SIGTERM for call in calls["sent"].call_args_list))

    def test_shutdown_rechecks_application_activity_before_forcing_survivor(self):
        processes = [self.stock_idle_service(124, "winedevice.exe")]
        with self.idle_shutdown_fixture(processes) as calls:
            with patch.object(fusion, "active_processes", side_effect=lambda _: {
                    "fusion": [999] if calls["clock"][0] >= 3 else [], "identity": []}):
                with self.assertRaisesRegex(fusion.LauncherError, "still running"):
                    fusion.stop_idle_runtime(self.paths)
            self.assertEqual([call.args for call in calls["sent"].call_args_list],
                             [(1124, fusion.signal.SIGTERM)])

    def test_shutdown_rechecks_between_two_signals_when_application_or_updater_starts(self):
        for new_work in ("fusion", "updater"):
            processes = [self.stock_idle_service(124, "services.exe"),
                         self.stock_idle_service(125, "rpcss.exe")]
            started = [False]
            def signal_process(_descriptor, _signum):
                started[0] = True
                if new_work == "updater":
                    processes.append(fusion.PrefixProcess(999, 1, "streamer.exe",
                                                         r"C:\Autodesk\streamer.exe", Path("/wine")))
            with self.subTest(new_work=new_work), self.idle_shutdown_fixture(processes, signal_process) as calls:
                with patch.object(fusion, "active_processes", side_effect=lambda _: {
                        "fusion": [999] if started[0] and new_work == "fusion" else [], "identity": []}):
                    with self.assertRaisesRegex(fusion.LauncherError, "still running|update work"):
                        fusion.stop_idle_runtime(self.paths)
                self.assertEqual([call.args for call in calls["sent"].call_args_list],
                                 [(1124, fusion.signal.SIGTERM)])
                self.assertEqual(calls["closed"].call_count, 2)

    def test_shutdown_rechecks_bus_before_second_forced_signal(self):
        processes = [self.stock_idle_service(124, "winedevice.exe"),
                     self.stock_idle_service(125, "winedevice.exe")]
        new_bus = [False]
        def signal_process(_descriptor, signum):
            if signum == fusion.signal.SIGKILL:
                new_bus[0] = True
        with self.idle_shutdown_fixture(processes, signal_process) as calls:
            with patch.object(fusion, "active_bus", side_effect=lambda _: new_bus[0]):
                with self.assertRaisesRegex(fusion.LauncherError, "activity changed"):
                    fusion.stop_idle_runtime(self.paths)
            self.assertEqual([call.args for call in calls["sent"].call_args_list],
                             [(1124, fusion.signal.SIGTERM), (1125, fusion.signal.SIGTERM),
                              (1124, fusion.signal.SIGKILL)])

    def test_shutdown_does_not_reuse_numeric_pid_to_signal_replacement(self):
        original = self.stock_idle_service(124, "services.exe")
        processes = [original]
        replacement = self.stock_idle_service(124, "winedevice.exe")
        with self.idle_shutdown_fixture(processes) as calls:
            def opened(pid):
                processes[:] = [replacement]
                return pid + 1000
            calls["opened"].side_effect = opened
            with self.assertRaisesRegex(fusion.LauncherError, "changed during shutdown"):
                fusion.stop_idle_runtime(self.paths)
            calls["sent"].assert_not_called()
            calls["closed"].assert_called_once_with(1124)

    def test_zombie_leader_with_live_threads_remains_visible_to_all_identity_checks(self):
        overlay, target = self.prepare_overlay()
        root = self.fake_process(123, self.paths.runner, fusion.overlay_session_environment(overlay), target.stat().st_ino)
        proc = root / "123"
        (proc / "status").write_text("Name:\tFusion360\nState:\tZ (zombie)\nPPid:\t1\nThreads:\t2\n")
        live = proc / "task/124"
        live.mkdir(parents=True)
        (live / "status").write_text("Name:\tWorker\nState:\tS (sleeping)\nPPid:\t1\n")
        (live / "exe").symlink_to("/wine-preloader")
        for name in ("comm", "cmdline", "environ", "maps"):
            (live / name).write_bytes((proc / name).read_bytes())
        with (live / "maps").open("a") as stream:
            stream.write(f"3000-4000 r-xp 0000 00:00 1 {self.exe}\n")
        (proc / "environ").write_bytes(b"")
        (proc / "cmdline").write_bytes(b"")
        self.assertEqual(fusion.active_processes(self.paths, root)["fusion"], [123])
        self.assertFalse(fusion.session_conflict(self.paths, root))
        inspected = fusion.prefix_processes(self.paths, root)
        self.assertEqual(len(inspected), 1)
        self.assertEqual(inspected[0].pid, 123)
        self.assertTrue(inspected[0].zombie_leader)
        self.assertIn(self.exe, inspected[0].mapped_executables)
        (live / "environ").write_bytes((live / "environ").read_bytes().replace(
            b"QSG_RHI_BACKEND=opengl", b"QSG_RHI_BACKEND=d3d11"))
        self.assertTrue(fusion.session_conflict(self.paths, root))

    def zombie_workers_fixture(self):
        overlay, target = self.prepare_overlay()
        root = self.fake_process(123, self.paths.runner, fusion.overlay_session_environment(overlay), target.stat().st_ino)
        proc = root / "123"
        (proc / "status").write_text("Name:\tFusion360\nState:\tZ (zombie)\nPPid:\t1\nThreads:\t3\n")
        workers = [proc / "task/124", proc / "task/125"]
        for worker in workers:
            worker.mkdir(parents=True)
            (worker / "status").write_text("Name:\tWorker\nState:\tS (sleeping)\nPPid:\t1\n")
            (worker / "exe").symlink_to("/wine-preloader")
            for name in ("comm", "cmdline", "environ", "maps"):
                (worker / name).write_bytes((proc / name).read_bytes())
            with (worker / "maps").open("a") as stream:
                stream.write(f"3000-4000 r-xp 0000 00:00 1 {self.exe}\n")
        (proc / "environ").write_bytes(b"")
        (proc / "cmdline").write_bytes(b"")
        return root, proc, list((proc / "task").iterdir())

    def test_metadata_read_retries_another_worker_of_same_surviving_group(self):
        root, proc, workers = self.zombie_workers_fixture()
        original_read = Path.read_text
        for inspect in (fusion.prefix_processes, fusion.active_processes, fusion.session_conflict):
            reads = []
            def read_text(path, *args, **kwargs):
                reads.append(path)
                if path.parent == workers[0] and path.name in {"comm", "maps"}:
                    raise FileNotFoundError("Chosen worker exited during metadata read")
                return original_read(path, *args, **kwargs)
            with self.subTest(inspect=inspect.__name__), patch.object(Path, "read_text", read_text):
                result = inspect(self.paths, root)
            if inspect == fusion.prefix_processes:
                self.assertEqual([process.pid for process in result], [123])
                self.assertIn(self.exe, result[0].mapped_executables)
            elif inspect == fusion.active_processes:
                self.assertEqual(result["fusion"], [123])
            else:
                self.assertFalse(result)
            self.assertTrue(any(path.parent == workers[0] and path.name in {"comm", "maps"} for path in reads))
            self.assertTrue(any(path.parent == workers[1] and path.name in {"comm", "maps"} for path in reads))

    def test_matched_surviving_group_with_unreadable_workers_fails_closed(self):
        root, proc, workers = self.zombie_workers_fixture()
        original_read = Path.read_text
        def read_text(path, *args, **kwargs):
            if path.parent in workers and path.name in {"comm", "maps"}:
                raise FileNotFoundError("Worker identity is unavailable")
            return original_read(path, *args, **kwargs)
        for inspect in (fusion.prefix_processes, fusion.active_processes, fusion.session_conflict):
            with (self.subTest(inspect=inspect.__name__), patch.object(Path, "read_text", read_text),
                  patch.object(fusion, "process_metadata_root", wraps=fusion.process_metadata_root) as select):
                if inspect == fusion.session_conflict:
                    self.assertTrue(inspect(self.paths, root))
                else:
                    with self.assertRaisesRegex(fusion.LauncherError, "could not be checked"):
                        inspect(self.paths, root)
                self.assertEqual(select.call_count, 3)

    def test_process_executable_reader_stops_before_private_arguments(self):
        class ExecutableOnly(io.BytesIO):
            def read(self, size=-1):
                self.assert_read_size(size)
                return super().read(size)

            def assert_read_size(self, size):
                if size != 1 or self.tell() >= len(b"Fusion360.exe\0"):
                    raise AssertionError("Read reached private process arguments")

        with patch.object(Path, "open", return_value=ExecutableOnly(b"Fusion360.exe\0SECRET_CALLBACK")):
            self.assertEqual(fusion.process_argv0(Path("/proc/123")), "Fusion360.exe")

    def test_idle_cleanup_allows_only_registered_analytics_and_known_service_mappings(self):
        analytics = fusion.PrefixProcess(
            123, 321, "ADPClientServic", str(self.build / "ADPClientService.exe"), Path("/wine"),
            (self.build / "ADPClientService.exe",))
        self.assertTrue(fusion.idle_runtime_process(self.paths, analytics, set(), self.exe))
        for mapped in ((), (self.build.parent / "old/ADPClientService.exe",)):
            other = fusion.PrefixProcess(123, 321, analytics.name, analytics.argv0, analytics.executable, mapped)
            self.assertFalse(fusion.idle_runtime_process(self.paths, other, set(), self.exe))
        service = fusion.PrefixProcess(
            124, 321, "services.exe", r"C:\windows\system32\services.exe", Path("/wine"),
            (self.paths.runner / "files/lib/wine/x86_64-windows/services.exe",))
        self.assertTrue(fusion.idle_runtime_process(self.paths, service, set(), self.exe))
        substituted = fusion.PrefixProcess(124, 321, service.name, service.argv0, Path("/wine"),
                                          (self.build / "services.exe",))
        self.assertFalse(fusion.idle_runtime_process(self.paths, substituted, set(), self.exe))

    def test_idle_cleanup_python_allowance_is_only_for_verified_service_ancestors(self):
        python = fusion.PrefixProcess(123, 100, "python3", "python3", Path("/usr/bin/python3.13"))
        self.assertTrue(fusion.idle_runtime_process(self.paths, python, {123}, self.exe))
        self.assertFalse(fusion.idle_runtime_process(self.paths, python, {100}, self.exe))
        untrusted = fusion.PrefixProcess(123, 100, "python3", "python3", Path("/tmp/python3.13"))
        self.assertFalse(fusion.idle_runtime_process(self.paths, untrusted, {123}, self.exe))

    def test_stop_idle_cli_obeys_exclusive_maintenance_lock(self):
        with (self.paths.state / ".maintenance.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (patch.object(fusion.Paths, "default", return_value=self.paths),
                  patch.object(fusion, "stop_idle_runtime") as stop,
                  patch.object(fusion, "notify_failure"), redirect_stderr(io.StringIO())):
                self.assertEqual(fusion.main(["stop-idle-runtime"]), 1)
                stop.assert_not_called()

    def test_public_mutation_commands_respect_existing_maintenance_owner(self):
        with (self.paths.state / ".maintenance.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command, function in (("install-exe", "install_exe"), ("configure-browser", "configure_browser")):
                with (self.subTest(command=command),
                      patch.object(fusion.Paths, "default", return_value=self.paths),
                      patch.object(fusion, function, return_value=0) as operation,
                      patch.object(fusion, "notify_failure"),
                      redirect_stderr(io.StringIO())):
                    self.assertEqual(fusion.main([command, "/placeholder"]), 1)
                    operation.assert_not_called()

    def test_public_mutation_commands_hold_exclusive_lock_through_operation(self):
        def during_operation(paths, argument):
            self.assertEqual(paths, self.paths)
            with (self.paths.state / ".maintenance.lock").open("a") as contender:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(contender, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return 0
        for command, function in (("install-exe", "install_exe"), ("configure-browser", "configure_browser")):
            with (self.subTest(command=command),
                  patch.object(fusion.Paths, "default", return_value=self.paths),
                  patch.object(fusion, function, side_effect=during_operation) as operation):
                self.assertEqual(fusion.main([command, "/placeholder"]), 0)
                operation.assert_called_once_with(self.paths, "/placeholder")
            with (self.paths.state / ".maintenance.lock").open("a") as contender:
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_live_browser_configuration_does_not_require_closed_session(self):
        helper = self.root / "fusion360-for-omarchy-browser"
        helper.write_text("#!/bin/sh\nexit 0\n")
        helper.chmod(0o700)
        registry_utility = self.paths.prefix / "drive_c/windows/system32/reg.exe"
        registry_utility.parent.mkdir(parents=True)
        registry_utility.touch()
        with (patch.object(fusion.Paths, "default", return_value=self.paths),
              patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "active_processes", return_value={"fusion": [123], "identity": [124]}),
              patch.object(fusion, "attach", return_value=0) as attach):
            self.assertEqual(fusion.main(["configure-browser", str(helper)]), 0)
            self.assertEqual(attach.call_count, 1)
            self.assertEqual(attach.call_args.args[:2], (self.paths, registry_utility))


class StartupWorkspaceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lua"), "requires Lua for startup retry behavior")
    def test_old_timeout_and_cleanup_cannot_disable_a_retry(self):
        paths = fusion.Paths(Path("/tmp/fusion-tests/state"), Path("/tmp/fusion-tests/runtime"))
        with patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0, stdout="ok")) as run:
            first = fusion.anchor_startup(paths, "4")
            first_create = run.call_args.args[0][2]
            fusion.release_startup_anchor(first)
            first_release = run.call_args.args[0][2]
            second = fusion.anchor_startup(paths, "6")
            second_create = run.call_args.args[0][2]
            fusion.release_startup_anchor(second)
            second_release = run.call_args.args[0][2]
        harness = '''
local rules, timers, subscriptions, windows = {}, {}, {}, {}
hl = {
  get_windows=function() return windows end,
  window_rule=function(args)
    local r=rules[args.name] or {}
    r.enabled=true; r.workspace=args.workspace
    function r:set_enabled(value) self.enabled=value end
    rules[args.name]=r; return r
  end,
  on=function(event,callback)
    assert(event=="window.open" or event=="window.close")
    local s={event=event,callback=callback,removed=false}
    function s:remove() self.removed=true end
    subscriptions[#subscriptions+1]=s; return s
  end,
  timer=function(callback,args)
    assert(args.type=="oneshot" and args.timeout==120000)
    local t={callback=callback,enabled=true}
    function t:set_enabled(value) self.enabled=value end
    timers[#timers+1]=t; return t
  end
}
'''
        script = harness + first_create + '\n' + first_release + '''
assert(subscriptions[1].removed and subscriptions[2].removed and not timers[1].enabled)
''' + second_create + '''
local rule=next(rules) and select(2,next(rules))
assert(rule.enabled and rule.workspace=="6 silent")
timers[1].callback()
assert(rule.enabled, "old timeout disabled retry")
''' + first_release + '''
assert(rule.enabled, "old Python cleanup disabled retry")
assert(subscriptions[3].event=="window.open" and subscriptions[4].event=="window.close")
subscriptions[3].callback({mapped=true,xwayland=true,class="another-app",initial_title="Autodesk Fusion"})
assert(rule.enabled)
local splash={mapped=true,xwayland=true,class="steam_app_fusion360",pid=42,address="splash",initial_title="Autodesk Fusion"}
local main={mapped=true,xwayland=true,class="steam_app_fusion360",pid=42,address="main",initial_title="Autodesk Fusion "}
local tray={mapped=true,xwayland=true,class="steam_app_fusion360",pid=42,address="tray",initial_title="Msg:QTView:(102)MessageTray"}
windows={splash};subscriptions[3].callback(splash)
assert(rule.enabled, "splash ended anchor before separate main mapping")
windows={splash,main};subscriptions[3].callback(main)
assert(rule.enabled, "coexisting main and splash ended anchor")
windows={splash,main,tray};subscriptions[3].callback(tray)
assert(rule.enabled, "ambiguous owner ended anchor")
-- Close callbacks may still see the closing window in get_windows.
subscriptions[4].callback(splash)
assert(not rule.enabled and subscriptions[3].removed and subscriptions[4].removed and not timers[2].enabled)
''' + second_release + '\nwindows={}\n' + first_create + '''
assert(rule.enabled)
timers[3].callback()
assert(not rule.enabled and subscriptions[5].removed and subscriptions[6].removed and not timers[3].enabled)
''' + '\nwindows={}\n' + second_create + '''
windows={main};subscriptions[7].callback(main)
assert(rule.enabled, "main alone ended anchor before its UI exists")
local foreign_tray={mapped=true,xwayland=true,class="steam_app_fusion360",pid=99,address="foreign",initial_title="Msg:QTView:(102)MessageTray"}
windows={main,foreign_tray};subscriptions[7].callback(foreign_tray)
assert(rule.enabled, "another process ended anchor")
windows={main,tray};subscriptions[7].callback(tray)
assert(not rule.enabled and subscriptions[7].removed and subscriptions[8].removed and not timers[4].enabled)
'''
        result = subprocess.run([shutil.which("lua"), "-"], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_captures_workspace_without_shell_or_global_tracking_change(self):
        with patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "test"}), patch.object(fusion.shutil, "which", return_value="hyprctl"), patch.object(fusion.subprocess, "run", return_value=Mock(stdout='{"name":"4"}')) as run:
            self.assertEqual(fusion.launch_workspace(), "4")
            self.assertEqual(run.call_args.args[0], ["hyprctl", "-j", "activeworkspace"])

    def test_rejects_invalid_workspace_and_absent_compositor(self):
        with patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": ""}), patch.object(fusion.subprocess, "run") as run:
            self.assertIsNone(fusion.launch_workspace());run.assert_not_called()
        with patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "test"}), patch.object(fusion.shutil, "which", return_value="hyprctl"), patch.object(fusion.subprocess, "run", return_value=Mock(stdout='{"name":"4; os.execute()"}')):
            self.assertIsNone(fusion.launch_workspace())

    def test_anchor_has_silent_class_scope_automatic_cleanup_and_failure_cleanup(self):
        paths = fusion.Paths(Path("/tmp/fusion-tests/state"), Path("/tmp/fusion-tests/runtime"))
        with patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0,stdout="ok")) as run:
            name=fusion.anchor_startup(paths,"4")
            expression=run.call_args.args[0][2]
            self.assertIn('workspace="4 silent"', expression)
            self.assertIn('class="^steam_app_fusion360$",xwayland=true', expression)
            self.assertIn('if #existing > 0 then return end', expression)
            self.assertIn('timeout=120000,type="oneshot"', expression)
            self.assertIn('subscription:remove()', expression)
            fusion.release_startup_anchor(name)
            self.assertIn('slot.finish()',run.call_args.args[0][2])
            self.assertIn(name[1],run.call_args.args[0][2])
            self.assertNotIn('initial_workspace_tracking',expression)


class HostFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        for name in ("Documents", "Downloads"):
            (self.home / name).mkdir()
        self.paths = fusion.Paths(self.root / "state", self.root / "runtime")
        (self.paths.prefix / "dosdevices").mkdir(parents=True)
        (self.paths.prefix / "dosdevices/z:").symlink_to("/", target_is_directory=True)
        target = self.paths.prefix / "drive_c/windows/system32/reg.exe"
        target.parent.mkdir(parents=True)
        target.touch()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name in ("validate_runtime", "require_session"):
            stack.enter_context(patch.object(fusion, name))
        stack.enter_context(patch.object(fusion.Path, "home", return_value=self.home))
        stack.enter_context(patch.object(fusion.shutil, "which", return_value=None))
        self.calls = []

    def attach(self, paths, target, arguments):
        self.calls.append(arguments)
        if arguments[0] == "export":
            # Resolve the tested Z: path without creating a Wine process.
            Path(arguments[2][2:].replace("\\", "/")).write_text("backup fixture")
        return 0

    def test_backs_up_all_keys_before_setting_host_paths(self):
        with patch.object(fusion, "attach", side_effect=self.attach):
            self.assertEqual(fusion.configure_host_folders(self.paths), 0)
        self.assertEqual([call[0] for call in self.calls], ["export"] * 3 + ["add"] * 5)
        values = [call[call.index("/d") + 1] for call in self.calls[3:]]
        self.assertEqual(values[-1], "file:///Z:" + self.home.as_posix())
        self.assertIn(str(fusion.PureWindowsPath("Z:\\", *self.home.parts[1:], "Documents")), values)
        for file in (self.paths.state / "host-folders").glob("*/*.reg"):
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_missing_preference_key_stops_before_any_add(self):
        with patch.object(fusion, "attach", side_effect=[0, 1]) as attach:
            # Successful exports create their actual backup file.
            def fail_second(paths, target, arguments):
                if len(self.calls) == 1:
                    self.calls.append(arguments)
                    return 1
                return self.attach(paths, target, arguments)
            attach.side_effect = fail_second
            with self.assertRaisesRegex(fusion.LauncherError, "no preferences were changed"):
                fusion.configure_host_folders(self.paths)
        self.assertEqual([call[0] for call in self.calls], ["export", "export"])

    def test_add_failure_retains_private_backups(self):
        def fail_add(paths, target, arguments):
            if arguments[0] == "add":
                self.calls.append(arguments)
                return 1
            return self.attach(paths, target, arguments)
        with patch.object(fusion, "attach", side_effect=fail_add):
            with self.assertRaisesRegex(fusion.LauncherError, "prior preferences are preserved"):
                fusion.configure_host_folders(self.paths)
        self.assertEqual(len(list((self.paths.state / "host-folders").glob("*/*.reg"))), 3)
        self.assertEqual([call[0] for call in self.calls], ["export"] * 3 + ["add"])


if __name__ == "__main__":
    unittest.main()
