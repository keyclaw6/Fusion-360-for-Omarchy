"""Isolated host-Wine boundary tests; never starts Wine, desktop services or browsers."""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fusion_wine as fusion
import fusion_wine_support as support


class HostWineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fusion-host-wine-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = fusion.Paths(self.root / "state with spaces")
        self.paths.prefix.mkdir(parents=True)
        self.build = self.paths.prefix / "drive_c/users/steamuser/AppData/Local/Autodesk/webdeploy/production/current"
        self.build.mkdir(parents=True)
        self.exe = self.build / "Fusion360.exe"
        self.exe.touch()
        self.idm = self.build / "Autodesk Identity Manager/AdskIdentityManager.exe"
        self.idm.parent.mkdir()
        self.idm.touch()
        self.windows = r"C:\users\steamuser\AppData\Local\Autodesk\webdeploy\production\current\Fusion360.exe"
        self.registry(self.windows)
        (self.paths.prefix / "system.reg").write_text("WINE REGISTRY Version 2\n")
        self.compiler = self.build / "d3dcompiler_v2/d3dcompiler_47.dll"
        self.compiler.parent.mkdir()
        self.compiler.write_bytes(b"Autodesk-shipped native compiler fixture")
        self.compiler_control = {**fusion.NATIVE_COMPILER_LOCATION, "file_version": "10.0.14393.33",
                                 "size": self.compiler.stat().st_size,
                                 "sha256": hashlib.sha256(self.compiler.read_bytes()).hexdigest()}
        self.compiler_control["system32_copy"] = {"relative_path": fusion.NATIVE_COMPILER_SYSTEM32,
                                                  "size": self.compiler_control["size"],
                                                  "sha256": self.compiler_control["sha256"]}
        self.compiler_copy = self.paths.prefix / fusion.NATIVE_COMPILER_SYSTEM32
        self.compiler_copy.parent.mkdir(parents=True)
        self.compiler_copy.write_bytes(self.compiler.read_bytes())
        self.compiler_override()
        files = {}
        for name in sorted(fusion.PINNED_FILES):
            path = self.paths.runner / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("fixture " + name).encode())
            path.chmod(0o755)
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.lock = {"schema": 1, "experiment": "standalone-host-wine", "windows_user": "steamuser",
                     "runner": {"name": fusion.RUNNER, "version": "wine-11.17", "sha256": "a" * 64,
                                "files": files, "executables": {key: files[key] for key in ("bin/wine", "bin/wineserver")}},
                     "native_compiler": self.compiler_control, "runtime_environment": {},
                     "launch_environment": {"QSG_RHI_BACKEND": "opengl"}}
        self.lock_path = self.paths.state / "compatibility-lock.json"
        self.lock_path.write_text(json.dumps(self.lock))
        self.configuration = fusion.session_configuration(self.paths, self.lock)
        self.proc = self.root / "proc"
        self.proc.mkdir()

    def registry(self, command):
        key = r"Software\Classes\f3d_file\shell\open\command".replace("\\", "\\\\")
        value = ('"' + command + '" "%1"').replace("\\", "\\\\").replace('"', '\\"')
        self.registry_base = f'WINE REGISTRY Version 2\n[{key}] 1\n@="{value}"\n'
        (self.paths.prefix / "user.reg").write_text(self.registry_base)

    def compiler_override(self, value="native,builtin", *, hive="user.reg", key=None, raw=None):
        (self.paths.prefix / "user.reg").write_text(self.registry_base)
        (self.paths.prefix / "system.reg").write_text("WINE REGISTRY Version 2\n")
        if value is not None or raw is not None:
            section = (key or fusion.NATIVE_COMPILER_LOCATION["registry_key"]).replace("\\", "\\\\")
            data = raw if raw is not None else '"' + value + '"'
            with (self.paths.prefix / hive).open("a") as stream:
                stream.write(f'\n[{section}] 1\n"d3dcompiler_47"={data}\n')

    def version_result(self):
        return Mock(returncode=0, stdout="wine-11.17\n")

    def fake_process(self, pid=123, name=None, configuration=None, overrides=None, executable=None):
        proc = self.proc / str(pid)
        proc.mkdir(parents=True, exist_ok=True)
        env = fusion.wine_environment(self.paths, configuration or self.configuration)
        env.update(overrides or {})
        (proc / "environ").write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in env.items()))
        (proc / "cmdline").write_bytes(str(name or self.exe).encode() + b"\0PRIVATE_UNREAD_ARGUMENT\0")
        (proc / "status").write_text("State:\tS (sleeping)\nPPid:\t1\n")
        (proc / "exe").symlink_to(executable or self.paths.wine)
        return proc

    def save_session(self, **updates):
        record = {**self.configuration, "phase": "dispatched", "identity_ready": True, **updates}
        fusion.write_session(self.paths, record)
        return record

    def test_current_registry_target_wins_and_command_tail_is_not_executed(self):
        stale = self.build.parent / "old/Fusion360.exe"
        stale.parent.mkdir()
        stale.touch()
        targets = support.resolve_targets(self.paths)
        self.assertEqual(targets["fusion"], self.exe)
        self.assertEqual(targets["identity"], self.idm)
        command = f'"{self.windows}" "%1" & cmd.exe /c unwanted'
        self.assertEqual(support.windows_executable(self.paths.prefix, command, "Fusion360.exe"), self.exe)
        self.exe.unlink()
        with self.assertRaises(fusion.LauncherError):
            support.resolve_targets(self.paths)

    def test_registry_target_cannot_escape_the_dedicated_prefix(self):
        for command in (r'"Z:\outside\Fusion360.exe"', r'"C:\..\Fusion360.exe"', r'"C:\windows\cmd.exe"'):
            with self.subTest(command=command), self.assertRaises(fusion.LauncherError):
                support.windows_executable(self.paths.prefix, command, "Fusion360.exe")
        self.exe.unlink()
        outside = self.root / "outside.exe"
        outside.touch()
        self.exe.symlink_to(outside)
        with self.assertRaises(fusion.LauncherError):
            support.resolve_targets(self.paths)

    def test_wine_children_have_exact_runtime_and_user_without_changing_home_or_parent(self):
        inherited = {"HOME": "/native/home", "USER": "native", "LOGNAME": "native", "DISPLAY": ":7",
                     "WINEPREFIX": "/foreign", "WINELOADER": "/usr/bin/wine", "WINESERVER": "/usr/bin/wineserver",
                     "WINEDEBUG": "+all", "WINEDLLOVERRIDES": "wrong", "WINE_X11_ARGB_SHAPE_INPUT": "1",
                     "PROTONPATH": "/foreign", "UMU_CONTAINER_NSENTER": "1", "SteamAppId": "1",
                     "QSG_RHI_BACKEND": "d3d11", "QT_WIDGETS_RHI": "1", "WINEQT_WIDGETS_RHI": "1",
                     "QTWEBENGINE_DISABLE_SANDBOX": "1", "DXVK_CONFIG": "dxgi.syncInterval = 0",
                     "DXVK_CONFIG_FILE": "/foreign", "VK_ICD_FILENAMES": "/software", "GALLIUM_DRIVER": "llvmpipe",
                     "LIBGL_ALWAYS_SOFTWARE": "1", "LD_PRELOAD": "/foreign", "FUSION360_OVERLAY_ID": "test1",
                     "WAYLAND_DISPLAY": "wayland-1"}
        with patch.dict(os.environ, inherited, clear=True):
            environment = fusion.wine_environment(self.paths, self.configuration)
            self.assertEqual(dict(os.environ), inherited)
        self.assertEqual(environment["HOME"], inherited["HOME"])
        self.assertEqual(environment["LOGNAME"], inherited["LOGNAME"])
        self.assertEqual(environment["USER"], "steamuser")
        self.assertEqual(environment["WINELOADER"], str(self.paths.wine))
        self.assertEqual(environment["WINESERVER"], str(self.paths.wineserver))
        self.assertEqual(environment["WINEPREFIX"], str(self.paths.prefix))
        self.assertEqual(environment["WINEDEBUG"], "-all")
        self.assertEqual(environment["QSG_RHI_BACKEND"], "opengl")
        for key in set(inherited) - {"HOME", "USER", "LOGNAME", "DISPLAY", "WINELOADER", "WINESERVER", "WINEPREFIX", "WINEDEBUG", "QSG_RHI_BACKEND"}:
            self.assertNotIn(key, environment, key)

    def test_backend_choices_are_explicit_and_change_session_identity(self):
        configurations = [fusion.session_configuration(self.paths, self.lock, value) for value in fusion.QT_BACKENDS]
        self.assertEqual(len({record["identity"] for record in configurations}), 3)
        self.assertEqual(self.configuration, configurations[1])
        with patch.dict(os.environ, {"QSG_RHI_BACKEND": "opengl"}):
            self.assertNotIn("QSG_RHI_BACKEND", fusion.wine_environment(self.paths, configurations[0]))
        for environment in ({"QSG_RHI_BACKEND": "software"}, {"WINEDEBUG": "+all"}, None):
            self.lock_path.write_text(json.dumps({**self.lock, "launch_environment": environment}))
            with self.subTest(environment=environment), self.assertRaises(fusion.LauncherError):
                fusion.compatibility_lock(self.paths)

    def test_runtime_checks_all_pinned_files_before_executing_version_probe(self):
        with patch.object(fusion.subprocess, "run", return_value=self.version_result()) as run:
            fusion.validate_runtime(self.paths, self.lock, self.configuration)
            self.assertEqual(run.call_args.args[0], [str(self.paths.wine), "--version"])
        for relative in sorted(fusion.PINNED_FILES):
            target = self.paths.runner / relative
            original = target.read_bytes()
            target.write_bytes(b"unreviewed")
            with self.subTest(relative=relative), patch.object(fusion.subprocess, "run") as run:
                with self.assertRaises(fusion.LauncherError):
                    fusion.validate_runtime(self.paths, self.lock, self.configuration)
                run.assert_not_called()
            target.write_bytes(original)

    def test_runtime_version_symlink_and_prefix_checks_fail_closed(self):
        for result in (Mock(returncode=1, stdout=""), Mock(returncode=0, stdout="wine-11.18\n")):
            with patch.object(fusion.subprocess, "run", return_value=result), self.assertRaises(fusion.LauncherError):
                fusion.validate_runtime(self.paths, self.lock, self.configuration)
        self.paths.wine.unlink()
        outside = self.root / "wine"
        outside.write_text("unreviewed")
        outside.chmod(0o755)
        self.paths.wine.symlink_to(outside)
        with patch.object(fusion.subprocess, "run") as run, self.assertRaises(fusion.LauncherError):
            fusion.validate_runtime(self.paths, self.lock, self.configuration)
        run.assert_not_called()
        self.paths.prefix.rename(self.root / "original-prefix")
        self.paths.prefix.symlink_to(self.root / "original-prefix")
        with self.assertRaises(fusion.LauncherError):
            fusion.validate_runtime(self.paths, self.lock, self.configuration)

    def test_native_compiler_requires_exact_hkcu_app_override_and_registered_build_file(self):
        before = {name: (self.paths.prefix / name).read_bytes() for name in ("user.reg", "system.reg")}
        self.assertEqual(fusion.validate_native_compiler(self.paths, self.lock), self.compiler)
        self.assertEqual({name: (self.paths.prefix / name).read_bytes() for name in before}, before)
        alternate = self.build.parent / "older/d3dcompiler_v2/d3dcompiler_47.dll"
        alternate.parent.mkdir(parents=True)
        alternate.write_bytes(self.compiler.read_bytes())
        self.compiler.unlink()
        with self.assertRaisesRegex(fusion.LauncherError, "shipped native shader compiler"):
            fusion.validate_native_compiler(self.paths, self.lock)

    def test_native_compiler_rejects_missing_global_other_application_or_nonstring_override(self):
        cases = [{"value": None}, {"value": "builtin"}, {"value": "builtin,native"}, {"value": "native"},
                 {"value": ""}, {"raw": "dword:00000001"}, {"hive": "system.reg"},
                 {"key": r"Software\Wine\DllOverrides"},
                 {"key": r"Software\Wine\AppDefaults\Other.exe\DllOverrides"}]
        for change in cases:
            self.compiler_override(**change)
            before = (self.paths.prefix / "user.reg").read_bytes()
            with self.subTest(change=change), self.assertRaisesRegex(fusion.LauncherError, "HKCU d3dcompiler_47"):
                fusion.validate_native_compiler(self.paths, self.lock)
            self.assertEqual((self.paths.prefix / "user.reg").read_bytes(), before)

    def test_native_compiler_rejects_wrong_bytes_wrong_size_and_symlink_escape(self):
        original = self.compiler.read_bytes()
        for payload in (b"X" * len(original), original[:-1]):
            self.compiler.write_bytes(payload)
            with self.subTest(size=len(payload)), self.assertRaisesRegex(fusion.LauncherError, "differs from the lock"):
                fusion.validate_native_compiler(self.paths, self.lock)
        self.compiler.unlink()
        outside = self.root / "other-compiler.dll"
        outside.write_bytes(original)
        self.compiler.symlink_to(outside)
        with self.assertRaises(fusion.LauncherError):
            fusion.validate_native_compiler(self.paths, self.lock)

    def test_missing_wrong_or_linked_system32_copy_blocks_launch_without_replacing_it(self):
        for payload in (None, b"unreviewed compiler", b"X" * self.compiler_control["size"]):
            self.compiler_copy.unlink(missing_ok=True)
            if payload is not None:
                self.compiler_copy.write_bytes(payload)
            with (self.subTest(payload=payload), patch.object(fusion.subprocess, "run") as run,
                  patch.object(fusion.subprocess, "Popen") as start,
                  self.assertRaisesRegex(fusion.LauncherError, "private system32 shader compiler copy")):
                fusion.launch(self.paths)
            run.assert_not_called()
            start.assert_not_called()
            self.assertEqual(self.compiler_copy.read_bytes() if self.compiler_copy.exists() else None, payload)
        self.compiler_copy.unlink()
        self.compiler_copy.symlink_to(self.compiler)
        with self.assertRaisesRegex(fusion.LauncherError, "private system32 shader compiler copy"):
            fusion.validate_native_compiler(self.paths, self.lock)
        self.assertTrue(self.compiler_copy.is_symlink())

    def test_native_compiler_lock_rejects_missing_or_malformed_controls(self):
        controls = [None, {}, {**self.compiler_control, "registry_hive": "HKLM"},
                    {**self.compiler_control, "registry_key": r"Software\Wine\DllOverrides"},
                    {**self.compiler_control, "override": "builtin,native"},
                    {**self.compiler_control, "relative_path": "../../compiler.dll"},
                    {**self.compiler_control, "size": True}, {**self.compiler_control, "sha256": "bad"}]
        for control in controls:
            self.lock_path.write_text(json.dumps({**self.lock, "native_compiler": control}))
            with self.subTest(control=control), self.assertRaisesRegex(fusion.LauncherError, "compiler control"):
                fusion.compatibility_lock(self.paths)

    def test_ordinary_and_detached_launch_refuse_missing_compiler_preparation_without_wine_or_repair(self):
        self.compiler_override(value=None)
        before = (self.paths.prefix / "user.reg").read_bytes()
        for launch in (fusion.launch, fusion.run_worker):
            with (self.subTest(launch=launch.__name__), patch.object(fusion.subprocess, "run") as run,
                  patch.object(fusion.subprocess, "Popen") as start,
                  self.assertRaisesRegex(fusion.LauncherError, "HKCU d3dcompiler_47")):
                launch(self.paths)
            run.assert_not_called()
            start.assert_not_called()
        self.assertFalse(self.paths.session_file.exists())
        self.assertFalse((self.paths.state / ".startup.lock").exists())
        self.assertEqual((self.paths.prefix / "user.reg").read_bytes(), before)

    def test_missing_render_preparation_is_reported_without_changing_running_callback_contract(self):
        self.save_session()
        self.compiler_override(value=None)
        processes = [{"pid": 123, "kind": "identity", "compatible": True}]
        with (patch.object(fusion, "validate_runtime"), patch.object(fusion, "session_processes", return_value=processes),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0))):
            self.assertEqual(fusion.authenticate(self.paths, "adskidmgr:/login?code=fixture&state=fixture"), 0)
            report = fusion.status(self.paths)
        self.assertTrue(report["callback_ready"])
        self.assertFalse(report["native_compiler_prepared"])
        self.assertIn("HKCU d3dcompiler_47", report["errors"][0])

    def test_runtime_environment_allows_only_disabled_or_the_exact_reviewed_alpha_pair(self):
        for environment in ({}, dict(fusion.ALPHA_ENVIRONMENT)):
            lock = {**self.lock, "runtime_environment": environment}
            self.lock_path.write_text(json.dumps(lock))
            self.assertEqual(fusion.compatibility_lock(self.paths)["runtime_environment"], environment)
            for backend in fusion.QT_BACKENDS:
                configuration = fusion.session_configuration(self.paths, lock, backend)
                self.assertEqual(configuration["environment"], {**environment, **fusion.QT_BACKENDS[backend]})
        for environment in ({"WINE_X11_ARGB_SHAPE_INPUT": "1"},
                            {**fusion.ALPHA_ENVIRONMENT, "WINE_X11_ARGB_CONSTANT_ALPHA": "0"},
                            {**fusion.ALPHA_ENVIRONMENT, "WINE_X11_VULKAN_PRESENT_WAIT": "1"},
                            {"LD_PRELOAD": "unreviewed"}, None):
            self.lock_path.write_text(json.dumps({**self.lock, "runtime_environment": environment}))
            with self.subTest(environment=environment), self.assertRaises(fusion.LauncherError):
                fusion.compatibility_lock(self.paths)

    def test_session_identity_covers_every_pinned_runtime_file_and_native_compiler(self):
        proc = self.fake_process()
        for name in fusion.PINNED_FILES:
            lock = {**self.lock, "runner": {**self.lock["runner"], "files": {**self.lock["runner"]["files"], name: "b" * 64}}}
            changed = fusion.session_configuration(self.paths, lock)
            with self.subTest(name=name):
                self.assertNotEqual(changed["identity"], self.configuration["identity"])
                self.assertFalse(fusion.session_processes(self.paths, changed, self.proc)[0]["compatible"])
        compiler = {**self.lock, "native_compiler": {**self.compiler_control, "sha256": "b" * 64,
                    "system32_copy": {**self.compiler_control["system32_copy"], "sha256": "b" * 64}}}
        self.assertNotEqual(fusion.session_configuration(self.paths, compiler)["identity"], self.configuration["identity"])
        self.assertTrue(proc.exists())

    def test_alpha_session_requires_both_flags_and_rejects_stray_test1_controls(self):
        lock = {**self.lock, "runtime_environment": dict(fusion.ALPHA_ENVIRONMENT)}
        selected = fusion.session_configuration(self.paths, lock)
        proc = self.fake_process(configuration=selected)
        self.assertTrue(fusion.session_processes(self.paths, selected, self.proc)[0]["compatible"])
        original = (proc / "environ").read_bytes()
        for key in fusion.ALPHA_ENVIRONMENT:
            (proc / "environ").write_bytes(original.replace((key + "=1").encode(), (key + "=0").encode()))
            with self.subTest(key=key):
                self.assertFalse(fusion.session_processes(self.paths, selected, self.proc)[0]["compatible"])
        for key in ("WINE_X11_VULKAN_PRESENT_WAIT", "WINE_LAYERED_OVERLAY_ALPHA", "WINEQT_WIDGETS_RHI", "QSG_INFO"):
            (proc / "environ").write_bytes(original + b"\0" + (key + "=1").encode())
            with self.subTest(stray=key):
                self.assertFalse(fusion.session_processes(self.paths, selected, self.proc)[0]["compatible"])
        baseline = fusion.wine_environment(self.paths, self.configuration)
        baseline["WINE_X11_ARGB_SHAPE_INPUT"] = "1"
        (proc / "environ").write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in baseline.items()))
        self.assertFalse(fusion.session_processes(self.paths, self.configuration, self.proc)[0]["compatible"])

    def test_old_session_without_runtime_file_identity_requires_explicit_closed_session_migration(self):
        legacy = {key: value for key, value in self.configuration.items() if key not in {"runner_files", "native_compiler", "identity"}}
        legacy["identity"] = hashlib.sha256(json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        fusion.write_session(self.paths, legacy)
        before = self.paths.session_file.read_bytes()
        with self.assertRaisesRegex(fusion.LauncherError, "saved Wine session"):
            fusion.read_session(self.paths, self.lock)
        self.assertEqual(self.paths.session_file.read_bytes(), before)

    def test_session_record_cannot_change_runtime_backend_or_point_outside_state(self):
        record = self.save_session()
        self.assertEqual(fusion.read_session(self.paths, self.lock), record)
        for changed in ({**record, "environment": {"QSG_RHI_BACKEND": "d3d11"}},
                        {**record, "runner": "/old-runtime"}, {**record, "prefix": "/old-prefix"}):
            self.paths.session_file.write_text(json.dumps(changed))
            with self.assertRaises(fusion.LauncherError):
                fusion.read_session(self.paths, self.lock)
        self.paths.session_file.unlink()
        self.paths.session_file.symlink_to(self.root / "elsewhere")
        with self.assertRaises(fusion.LauncherError):
            fusion.write_session(self.paths, record)

    def test_process_inventory_matches_prefix_runner_and_markers_not_only_executable_name(self):
        self.fake_process()
        self.assertEqual(fusion.session_processes(self.paths, self.configuration, self.proc),
                         [{"pid": 123, "kind": "fusion", "compatible": True}])
        self.fake_process(124, overrides={"WINEPREFIX": "/unrelated"})
        self.assertEqual(len(fusion.session_processes(self.paths, self.configuration, self.proc)), 1)
        self.fake_process(125, configuration=fusion.session_configuration(self.paths, self.lock, "d3d11"))
        with self.assertRaises(fusion.LauncherError):
            fusion.require_compatible(fusion.session_processes(self.paths, self.configuration, self.proc))

    def test_process_inventory_rejects_foreign_runtime_or_retained_dxvk_override(self):
        for index, change in enumerate(({"executable": Path("/usr/bin/python3")},
                                        {"overrides": {"DXVK_CONFIG_FILE": "/old.conf"}},
                                        {"overrides": {"WINESERVER": "/usr/bin/wineserver"}},
                                        {"overrides": {"WINEDLLOVERRIDES": "wrong"}})):
            self.fake_process(200 + index, **change)
        self.assertTrue(all(not process["compatible"] for process in fusion.session_processes(self.paths, self.configuration, self.proc)))

    def test_zombie_group_leader_does_not_hide_its_live_wine_worker(self):
        proc = self.fake_process()
        worker = proc / "task/124"
        worker.mkdir(parents=True)
        for name in ("environ", "cmdline"):
            (worker / name).write_bytes((proc / name).read_bytes())
        (worker / "status").write_text("State:\tS (sleeping)\n")
        (worker / "exe").symlink_to(self.paths.wine)
        (proc / "status").write_text("State:\tZ (zombie)\nPPid:\t1\n")
        (proc / "environ").write_bytes(b"")
        self.assertEqual(fusion.session_processes(self.paths, self.configuration, self.proc)[0]["kind"], "fusion")

    def test_readiness_requires_a_new_complete_timestamped_sso_line(self):
        log = self.paths.identity_log
        log.parent.mkdir(parents=True)
        log.write_bytes(b"2020-01-01T00:00:00+00:00 SSO Server is ready\n")
        cursor = fusion.IdentityReadiness.snapshot(log)
        self.assertFalse(cursor.poll())
        stamp = datetime.now(timezone.utc).isoformat().encode()
        with log.open("ab") as stream:
            stream.write(stamp + b" SSO Server is ready")
        self.assertFalse(cursor.poll())
        with log.open("ab") as stream:
            stream.write(b"\n")
        self.assertTrue(cursor.poll())

    def test_cold_worker_prestarts_identity_then_fusion_once_with_same_environment(self):
        identity, application = Mock(), Mock()
        application.wait.return_value = 0
        readiness = Mock()
        readiness.poll.return_value = True
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_processes", side_effect=[[], [{"pid": 1, "kind": "identity", "compatible": True}]]),
              patch.object(fusion.IdentityReadiness, "snapshot", return_value=readiness),
              patch.object(fusion.subprocess, "Popen", side_effect=[identity, application]) as start):
            self.assertEqual(fusion.run_worker(self.paths), 0)
        self.assertEqual(len(start.call_args_list), 2)
        self.assertEqual(start.call_args_list[0].args[0], fusion.wine_command(self.paths, self.idm, fusion.IDENTITY_ARGS))
        self.assertEqual(start.call_args_list[1].args[0], fusion.wine_command(self.paths, self.exe))
        self.assertEqual(start.call_args_list[0].kwargs["env"], start.call_args_list[1].kwargs["env"])
        self.assertTrue(fusion.read_session(self.paths, self.lock)["identity_ready"])

    def test_worker_stops_after_bounded_identity_failure_without_launching_fusion(self):
        with (patch.object(fusion, "validate_runtime"), patch.object(fusion, "session_processes", return_value=[]),
              patch.object(fusion.IdentityReadiness, "snapshot"), patch.object(fusion.time, "monotonic", side_effect=[0, 46]),
              patch.object(fusion.subprocess, "Popen") as start):
            with self.assertRaisesRegex(fusion.LauncherError, "fresh SSO readiness"):
                fusion.run_worker(self.paths)
        self.assertEqual(start.call_count, 1)
        self.assertEqual(fusion.read_session(self.paths, self.lock)["phase"], "failed")

    def test_verified_idle_identity_is_reused_without_another_readiness_cycle(self):
        self.save_session()
        process = Mock()
        process.wait.return_value = 0
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_processes", return_value=[{"pid": 123, "kind": "identity", "compatible": True}]),
              patch.object(fusion.IdentityReadiness, "snapshot") as readiness,
              patch.object(fusion.subprocess, "Popen", return_value=process) as start):
            self.assertEqual(fusion.run_worker(self.paths), 0)
        readiness.assert_not_called()
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0], fusion.wine_command(self.paths, self.exe))

    def test_worker_holds_startup_lock_until_dispatched_loader_exits(self):
        process = Mock()
        def while_running():
            with self.assertRaises(fusion.LauncherError):
                with fusion.startup_lock(self.paths):
                    self.fail("another worker raced the dispatched loader")
            return 0
        process.wait.side_effect = while_running
        with (patch.object(fusion, "validate_runtime"), patch.object(fusion, "session_processes", return_value=[]),
              patch.object(fusion.subprocess, "Popen", return_value=process)):
            self.assertEqual(fusion.run_worker(self.paths, prestart_identity=False), 0)

    def test_ordinary_launch_uses_detached_user_service_with_no_proton_or_shell(self):
        with (patch.object(fusion, "validate_runtime"), patch.object(fusion, "session_processes", return_value=[]),
              patch.object(fusion.shutil, "which", return_value="/usr/bin/systemd-run"),
              patch.dict(os.environ, {"DISPLAY": ":7", "HOME": "/native/home", "PROTONPATH": "/old", "WINEPREFIX": "/old"}),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0)) as run):
            self.assertEqual(fusion.launch(self.paths, "d3d11"), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/systemd-run")
        self.assertIn("--property=ExitType=cgroup", command)
        self.assertIn("--property=StandardOutput=null", command)
        self.assertIn("--property=StandardError=null", command)
        self.assertIn("--description=Fusion standalone Wine", command)
        self.assertIn("--setenv=HOME=/native/home", command)
        self.assertIn("--state", command)
        self.assertIn(str(self.paths.state), command)
        self.assertEqual(command[-2:], ["--qt-backend", "d3d11"])
        self.assertNotIn("PROTONPATH", run.call_args.kwargs["env"])
        self.assertNotIn("WINEPREFIX", run.call_args.kwargs["env"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_startup_lock_prevents_two_overlapping_workers(self):
        with fusion.startup_lock(self.paths):
            with self.assertRaisesRegex(fusion.LauncherError, "already starting"):
                with fusion.startup_lock(self.paths):
                    self.fail("second worker acquired lock")

    def test_callback_is_one_literal_argument_in_the_recorded_running_experiment(self):
        alternate = fusion.session_configuration(self.paths, self.lock, "d3d11")
        fusion.write_session(self.paths, alternate)
        uri = "adskidmgr:/login?code=%24%28touch%20%2Ftmp%2Fnever%29%3B%26&state=opaque"
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_processes", return_value=[{"pid": 123, "kind": "identity", "compatible": True}]),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0)) as run):
            self.assertEqual(fusion.authenticate(self.paths, uri), 0)
        self.assertEqual(run.call_args.args[0], [str(self.paths.wine), str(self.idm), uri])
        self.assertEqual(run.call_args.kwargs["env"]["QSG_RHI_BACKEND"], "d3d11")
        self.assertEqual(run.call_args.kwargs["env"]["WINEPREFIX"], str(self.paths.prefix))
        self.assertEqual(run.call_args.kwargs["env"]["WINESERVER"], str(self.paths.wineserver))
        self.assertEqual(run.call_args.kwargs["stdout"], fusion.subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stderr"], fusion.subprocess.DEVNULL)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_callback_refuses_missing_closed_conflicting_or_wrong_prefix_session(self):
        uri = "adskidmgr:/login?code=private&state=private"
        with patch.object(fusion.subprocess, "run") as run, self.assertRaises(fusion.LauncherError):
            fusion.authenticate(self.paths, uri)
        run.assert_not_called()
        self.save_session()
        for processes in ([], [{"pid": 1, "kind": "helper", "compatible": True}],
                          [{"pid": 2, "kind": "fusion", "compatible": False}]):
            with (self.subTest(processes=processes), patch.object(fusion, "validate_runtime"),
                  patch.object(fusion, "session_processes", return_value=processes),
                  patch.object(fusion.subprocess, "run") as run, self.assertRaises(fusion.LauncherError)):
                fusion.authenticate(self.paths, uri)
            run.assert_not_called()

    def test_callback_validation_and_errors_never_echo_private_uri(self):
        invalid = ["adskidmgr:/login?code=private", "adskidmgr://other/login?code=private&state=x",
                   "adskidmgr:/login?code=private&state=x&state=y", "adskidmgr:/login?code=private%0A&state=x",
                   "file:///private", "adskidmgr:/login?code=private&state=x\n"]
        for uri in invalid:
            output = io.StringIO()
            with self.subTest(uri=uri), redirect_stderr(output), patch.object(fusion.subprocess, "run") as run:
                self.assertEqual(fusion.main(["--state", str(self.paths.state), "auth", "--", uri]), 1)
                self.assertNotIn("private", output.getvalue())
                run.assert_not_called()

    def test_outgoing_browser_uses_clean_host_manager_and_literal_http_url(self):
        uri = "https://accounts.autodesk.com/login?state=%24%28never%29"
        with (patch.object(fusion.shutil, "which", return_value="/usr/bin/systemd-run"),
              patch.dict(os.environ, {"USER": "steamuser", "WINEPREFIX": str(self.paths.prefix), "LD_PRELOAD": "/bad"}),
              patch.object(fusion.subprocess, "run", return_value=Mock(returncode=0)) as run):
            self.assertEqual(fusion.open_browser(uri), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[-3:], ["--", "/usr/bin/xdg-open", uri])
        self.assertIn("--expand-environment=no", command)
        self.assertIn("--description=Fusion external browser", command)
        self.assertIn("--property=StandardOutput=null", command)
        self.assertIn("--property=StandardError=null", command)
        self.assertFalse(any(uri in argument for argument in command[:-1]))
        self.assertNotIn("WINEPREFIX", run.call_args.kwargs["env"])
        self.assertNotIn("LD_PRELOAD", run.call_args.kwargs["env"])
        self.assertNotEqual(run.call_args.kwargs["env"]["USER"], "steamuser")
        for invalid in ("file:///private", "https://user:password@example.com", "https:///missing", "https://example.com\n"):
            with self.subTest(uri=invalid), self.assertRaises(fusion.LauncherError):
                fusion.open_browser(invalid)

    def test_status_reports_live_configuration_without_certifying_acceptance(self):
        self.save_session()
        with (patch.object(fusion, "validate_runtime"),
              patch.object(fusion, "session_processes", return_value=[{"pid": 123, "kind": "fusion", "compatible": True}])):
            report = fusion.status(self.paths)
        self.assertTrue(report["runtime_ready"])
        self.assertTrue(report["running"])
        self.assertTrue(report["callback_ready"])
        self.assertFalse(report["accepted"])
        self.assertEqual(report["environment"], {"QSG_RHI_BACKEND": "opengl"})
        self.assertNotIn("PRIVATE_UNREAD_ARGUMENT", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
