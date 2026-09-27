"""Isolated installer/recovery tests. No live prefix, desktop defaults or network."""

from __future__ import annotations

import contextlib
import ast
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install
import maintenance


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fusion-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.loc = install.Locations(self.root / "state with spaces", self.root / "cache",
                                     self.root / "data", self.root / "config", self.root / "bin")
        self.loc.state.mkdir(mode=0o700)
        self.environment = mock.patch.dict(os.environ, {
            "XDG_CURRENT_DESKTOP": "", "DESKTOP_SESSION": "", "DE": "generic",
            "XDG_CONFIG_DIRS": str(self.root / "system-config"),
            "XDG_DATA_DIRS": str(self.root / "system-data")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.lock = {"runner": {"name": "GE-Proton11-7-x86_64", "sha256": "1" * 64},
                     "steam_runtime": {"version": "4.0.test", "sha256": "2" * 64,
                                       "url": "https://example.invalid/runtime.tar.xz"}}

    def archive(self, entries, name="runner.tar.gz", mode="w:gz"):
        path = self.root / name
        with tarfile.open(path, mode) as archive:
            for name, value, kind in entries:
                item = tarfile.TarInfo(name)
                item.mode = 0o755
                if kind == "file":
                    item.size = len(value)
                    archive.addfile(item, io.BytesIO(value))
                else:
                    item.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                    item.linkname = value
                    archive.addfile(item)
        return path

    def overlay_fixture(self):
        original = b"official X11 module fixture"
        patched = b"reviewed X11 module fixture"
        overlay = {"id": "ge-proton11-7-omarchy-x11-v1", "target": install.OVERLAY_TARGET,
                   "original_sha256": hashlib.sha256(original).hexdigest(),
                   "sha256": hashlib.sha256(patched).hexdigest(),
                   "required_environment": {"WINE_X11_ARGB_SHAPE_INPUT": "1",
                                            "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
                                            "QSG_RHI_BACKEND": "opengl"},
                   "manifest": "runtime-patches/manifest.json"}
        lock = dict(self.lock, runner_overlay=overlay)
        runner = self.lock["runner"]["name"]
        archive = self.archive([(runner + "/proton", b"proton", "file"),
                                (runner + "/" + install.OVERLAY_TARGET, original, "file"),
                                (runner + "/unchanged", b"unchanged", "file")])
        lock["runner"] = dict(lock["runner"], sha256=install.digest(archive))
        install.install_runner(archive, self.loc, lock)
        candidate = self.root / "candidate-winex11.so"
        candidate.write_bytes(patched)
        return lock, archive, candidate, original, patched

    def overlay_v2_fixture(self):
        self.loc.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        originals = {target: ("official " + Path(target).name).encode() for target in install.OVERLAY_TARGETS_V2}
        patched = {target: ("reviewed v2 " + Path(target).name).encode() for target in install.OVERLAY_TARGETS_V2}
        overlay = {"id": "ge-proton11-7-omarchy-x11-v2",
                   "modules": [{"target": target, "original_sha256": hashlib.sha256(originals[target]).hexdigest(),
                                "sha256": hashlib.sha256(patched[target]).hexdigest()}
                               for target in install.OVERLAY_TARGETS_V2],
                   "required_environment": {"WINE_X11_ARGB_SHAPE_INPUT": "1", "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
                                            "WINE_X11_VULKAN_PRESENT_WAIT": "1", "QSG_RHI_BACKEND": "d3d11"},
                   "manifest": "runtime-patches/manifest.json"}
        lock = dict(self.lock, runner_overlay=overlay)
        runner = lock["runner"]["name"]
        archive = self.archive([(runner + "/proton", b"proton", "file"),
                                *[(runner + "/" + target, data, "file") for target, data in originals.items()],
                                (runner + "/unchanged", b"unchanged", "file")])
        lock["runner"] = dict(lock["runner"], sha256=install.digest(archive))
        install.install_runner(archive, self.loc, lock)
        candidate = self.root / (self.loc.state.name + "-candidate")
        candidate.mkdir()
        for target, data in patched.items():
            (candidate / Path(target).name).write_bytes(data)
        return lock, archive, candidate, originals, patched

    def overlay_guard(self, lock):
        active = self.loc.state / "compatibility-lock.json"
        install.write_json(active, lock)
        manifest = install.load_manifest(self.loc)
        manifest["files"][str(active)] = install.file_record(active)
        install.write_json(self.loc.manifest, manifest)
        recipe = {key: value for key, value in lock["runner_overlay"].items() if key != "manifest"}
        install.write_json(self.loc.state / "runtime-patches/manifest.json", dict(recipe, schema=2))

    def assert_overlay_bytes(self, lock, expected):
        for target, data in expected.items():
            self.assertEqual((self.loc.state / lock["runner"]["name"] / target).read_bytes(), data)

    def test_download_verifies_before_use_and_preserves_bad_cache(self):
        data = b"verified installer fixture"
        response = io.BytesIO(data)
        response.url = "https://example.invalid/installer.exe"
        entry = {"url": response.url, "sha256": hashlib.sha256(data).hexdigest()}
        destination = self.loc.cache / "installer.exe"
        with mock.patch("urllib.request.urlopen", return_value=response):
            install.fetch_verified(entry, destination)
        self.assertEqual(destination.read_bytes(), data)
        destination.write_bytes(b"unexpected file")
        with self.assertRaises(install.InstallError):
            install.fetch_verified(entry, destination)
        self.assertEqual(destination.read_bytes(), b"unexpected file")

    def test_download_failure_does_not_leave_executable(self):
        response = io.BytesIO(b"wrong bytes")
        response.url = "https://example.invalid/installer.exe"
        destination = self.loc.cache / "installer.exe"
        with mock.patch("urllib.request.urlopen", return_value=response), self.assertRaises(install.InstallError):
            install.fetch_verified({"url": response.url, "sha256": "0" * 64}, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.loc.cache.iterdir()), [])

    def test_runner_rejects_traversal_and_escaping_links(self):
        runner = self.lock["runner"]["name"]
        for index, entry in enumerate(((runner + "/../../outside", b"bad", "file"),
                                       (runner + "/link", "../../outside", "symlink"),
                                       (runner + "/hard", "/etc/passwd", "hardlink"))):
            archive = self.archive([(runner + "/proton", b"ok", "file"), entry], f"bad-{index}.tar.gz")
            with self.subTest(entry=entry), self.assertRaises(install.InstallError):
                install.install_runner(archive, self.loc, self.lock)
            self.assertFalse((self.loc.state / runner).exists())
        self.assertFalse((self.root / "outside").exists())

    def test_runner_is_adopted_only_if_its_files_match(self):
        runner = self.lock["runner"]["name"]
        archive = self.archive([(runner + "/proton", b"runner", "file"),
                                (runner + "/shortcut", "proton", "symlink")])
        install.install_runner(archive, self.loc, self.lock)
        install.install_runner(archive, self.loc, self.lock)
        (self.loc.state / runner / "proton").write_bytes(b"modified")
        with self.assertRaises(install.InstallError):
            install.install_runner(archive, self.loc, self.lock)
        self.assertEqual((self.loc.state / runner / "proton").read_bytes(), b"modified")

    def test_runtime_bootstrap_uses_versioned_archive_and_verifies_tree(self):
        top = "SteamLinuxRuntime_4/"
        archive = self.archive([
            (top + "VERSIONS.txt", b"depot\t4.0.test\n", "file"),
            (top + "pressure-vessel/bin/pv-verify", b"#!/bin/sh\nexit 0\n", "file"),
            (top + "steamrt4_platform_4.0.test/files/fixture", b"runtime", "file"),
            (top + "_v2-entry-point", b"entry", "file"),
        ], "runtime.tar.xz", "w:xz")
        with mock.patch.object(install, "fetch_verified", return_value=archive) as fetch:
            install.install_runtime(self.loc, self.lock)
        self.assertEqual(fetch.call_args.args[0], self.lock["steam_runtime"])
        runtime = self.loc.data_home / "umu/steamrt4"
        self.assertEqual(os.readlink(runtime / "umu"), "_v2-entry-point")
        self.assertEqual((runtime / ".installed.ok").read_text(), "ok\n")
        (runtime / "VERSIONS.txt").write_text("depot\tnewer\n")
        with self.assertRaises(install.InstallError):
            install.install_runtime(self.loc, self.lock)
        self.assertEqual((runtime / "VERSIONS.txt").read_text(), "depot\tnewer\n")

    def test_renderer_edit_preserves_other_options_and_original(self):
        path = self.loc.prefix / "drive_c/users/steamuser/AppData/Roaming/Autodesk/Neutron Platform/Options/NMachineSpecificOptions.xml"
        path.parent.mkdir(parents=True)
        original = ('<?xml version="1.0" encoding="utf-16"?><OptionGroups><!--keep-->'
                    '<Network><CheckTLS Value="true"/></Network><BootstrapOptionsGroup>'
                    '<driverOptionId Value="VirtualDeviceGLCore"/><Other Value="42"/>'
                    '</BootstrapOptionsGroup></OptionGroups>').encode("utf-16")
        path.write_bytes(original)
        install.seed_renderer(self.loc.prefix)
        parsed = ET.parse(path)
        self.assertEqual(parsed.find(".//driverOptionId").get("Value"), "VirtualDeviceDx11")
        self.assertEqual(parsed.find(".//CheckTLS").get("Value"), "true")
        self.assertEqual(parsed.find(".//Other").get("Value"), "42")
        self.assertIn("<!--keep-->", path.read_text(encoding="utf-16"))
        self.assertEqual(path.with_name(path.name + ".before-fusion360-for-omarchy").read_bytes(), original)
        once = path.read_bytes()
        install.seed_renderer(self.loc.prefix)
        self.assertEqual(path.read_bytes(), once)
        path.write_text(path.read_text(encoding="utf-16").replace("VirtualDeviceDx11", "VirtualDeviceGLCore"),
                        encoding="utf-16")
        install.seed_renderer(self.loc.prefix)
        self.assertEqual(ET.parse(path).find(".//driverOptionId").get("Value"), "VirtualDeviceDx11")
        self.assertEqual(path.with_name(path.name + ".before-fusion360-for-omarchy").read_bytes(), original)
        path.write_bytes(b"broken XML")
        with self.assertRaises(install.InstallError):
            install.seed_renderer(self.loc.prefix)
        self.assertEqual(path.read_bytes(), b"broken XML")

    def test_any_process_using_prefix_blocks_backup(self):
        proc = self.root / "proc/12"
        proc.mkdir(parents=True)
        (proc / "environ").write_bytes(b"WINEPREFIX=" + os.fsencode(self.loc.prefix)
                                     + b"\0PROTONPATH=/experimental/other-runner\0")
        with self.assertRaises(install.InstallError):
            install.require_closed(self.loc, proc_root=proc.parent)
        (proc / "environ").write_bytes(b"WINEPREFIX=/unrelated/prefix\0")
        install.require_closed(self.loc, proc_root=proc.parent)

    def test_preflight_never_overwrites_unrelated_file(self):
        self.loc.bin_home.mkdir()
        conflict = self.loc.bin_home / install.APP
        conflict.write_text("unrelated launcher")
        with self.assertRaises(install.InstallError):
            install.install_integration(self.loc, install.load_manifest(self.loc), register=False)
        self.assertEqual(conflict.read_text(), "unrelated launcher")
        self.assertFalse((self.loc.state / "bin").exists())

    @unittest.skipUnless(shutil.which("xdg-mime"), "requires the real desktop MIME utility")
    def test_real_desktop_registration_reinstall_and_clean_uninstall(self):
        apps = self.loc.data_home / "applications"
        apps.mkdir(parents=True)
        self.loc.config_home.mkdir()
        legacy = apps / "adskidmgr.desktop"
        legacy.write_text("[Desktop Entry]\nType=Application\nName=Legacy\nExec=/bin/true %u\n"
                          "MimeType=x-scheme-handler/adskidmgr;\nNoDisplay=true\n")
        config = self.loc.config_home / "mimeapps.list"
        config.write_text("# unrelated comment\n[Default Applications]\ntext/plain=editor.desktop;\n")
        scheme = "x-scheme-handler/adskidmgr"
        install.run(["xdg-mime", "default", "adskidmgr.desktop", scheme], self.loc)
        self.loc.prefix.mkdir()
        design = self.loc.prefix / "unsynced-design"
        design.write_bytes(b"design fixture")
        manifest = install.load_manifest(self.loc)
        install.install_integration(self.loc, manifest)
        install.install_integration(self.loc, install.load_manifest(self.loc))
        installed = install.load_manifest(self.loc)
        self.assertEqual(installed["associations"][scheme]["previous"], "adskidmgr.desktop")
        selected = install.run(["xdg-mime", "query", "default", scheme], self.loc,
                               capture_output=True, text=True).stdout.strip()
        self.assertEqual(selected, install.APP + "-auth.desktop")
        self.assertEqual(self.loc.manifest.stat().st_mode & 0o777, 0o600)
        if shutil.which("desktop-file-validate"):
            subprocess.run(["desktop-file-validate", str(apps / (install.APP + ".desktop"))], check=True)
        # Symlink entry point finds its own installed modules, independently of the checkout.
        result = subprocess.run([str(self.loc.bin_home / (install.APP + "-maintenance")), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        maintenance.uninstall(self.loc, installed)
        current = install.run(["xdg-mime", "query", "default", scheme], self.loc,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(current, "adskidmgr.desktop")
        self.assertIn("text/plain=editor.desktop;", config.read_text())
        self.assertIn("# unrelated comment", config.read_text())
        self.assertNotIn(install.APP + ".desktop", config.read_text())
        self.assertNotIn(install.APP + "-auth.desktop", config.read_text())
        self.assertFalse(self.loc.manifest.exists())
        self.assertTrue(legacy.exists())
        self.assertEqual(design.read_bytes(), b"design fixture")

    def test_uninstall_preserves_modified_owned_files(self):
        manifest = install.load_manifest(self.loc)
        install.install_integration(self.loc, manifest, register=False)
        changed = self.loc.state / "bin" / install.APP
        changed.write_text("user edit")
        with self.assertRaises(install.InstallError):
            maintenance.uninstall(self.loc, manifest)
        self.assertEqual(changed.read_text(), "user edit")
        self.assertTrue(self.loc.manifest.exists())

    @unittest.skipUnless(shutil.which("gio"), "requires GLib's desktop entry launcher")
    def test_desktop_callback_delivers_one_literal_uri_with_spaces_in_helper_path(self):
        install.install_integration(self.loc, install.load_manifest(self.loc), register=False)
        # A harmless receipt helper tests the actual Desktop Entry argument parser.
        # It never calls Fusion, Autodesk, a browser or a shell.
        receipt = self.root / "receipt.json"
        helper = self.loc.state / "bin" / (install.APP + "-auth")
        helper.write_text("import json,sys\nfrom pathlib import Path\n"
                          + "Path(" + repr(str(receipt)) + ").write_text(json.dumps(sys.argv[1:]))\n")
        uri = "adskidmgr:///login?code=fixture%22%24%28%29&state=literal;$()"
        desktop = self.loc.data_home / "applications" / (install.APP + "-auth.desktop")
        install.run(["gio", "launch", str(desktop), uri], self.loc, capture_output=True)
        deadline = time.monotonic() + 3
        while not receipt.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(receipt.exists(), "The desktop callback did not reach the helper")
        self.assertEqual(json.loads(receipt.read_text()), [uri])

    @unittest.skipUnless(shutil.which("xdg-mime"), "requires the real desktop MIME utility")
    def test_uninstall_preserves_a_later_user_handler_choice(self):
        manifest = install.load_manifest(self.loc)
        install.install_integration(self.loc, manifest)
        apps = self.loc.data_home / "applications"
        (apps / "later-choice.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Later choice\nExec=/bin/true %u\n")
        scheme = "x-scheme-handler/adskidmgr"
        install.run(["xdg-mime", "default", "later-choice.desktop", scheme], self.loc)
        maintenance.uninstall(self.loc, manifest)
        chosen = install.run(["xdg-mime", "query", "default", scheme], self.loc,
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(chosen, "later-choice.desktop")

    def test_backup_restore_preserves_symlinks_and_pre_restore_state(self):
        self.loc.prefix.mkdir()
        design = self.loc.prefix / "design"
        design.write_bytes(b"before update")
        outside = self.root / "external-designs"
        outside.mkdir()
        (outside / "file").write_bytes(b"not copied through the link")
        (self.loc.prefix / "Documents").symlink_to(outside, target_is_directory=True)
        # umu can create an absolute pfx link back to the real dedicated prefix.
        (self.loc.prefix / "pfx").symlink_to(self.loc.prefix, target_is_directory=True)
        module = install.core()
        snapshot = maintenance.backup(self.loc, self.lock, module)
        self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
        self.assertTrue((snapshot / "prefix/Documents").is_symlink())
        self.assertEqual((snapshot / "prefix/pfx").readlink(), self.loc.prefix)
        self.assertEqual((snapshot / "prefix/design").read_bytes(), b"before update")
        design.write_bytes(b"failed update state")
        preserved = maintenance.restore(self.loc, snapshot, self.lock, module)
        self.assertEqual(design.read_bytes(), b"before update")
        self.assertEqual((preserved / "prefix/design").read_bytes(), b"failed update state")
        self.assertEqual((outside / "file").read_bytes(), b"not copied through the link")
        self.assertTrue((self.loc.prefix / "Documents").is_symlink())
        self.assertEqual((self.loc.prefix / "pfx").readlink(), self.loc.prefix)

    def test_update_failure_keeps_a_recoverable_snapshot(self):
        self.loc.prefix.mkdir()
        (self.loc.prefix / "design").write_bytes(b"valuable design fixture")
        lock = dict(self.lock, autodesk_installer={"url": "https://example.invalid/installer.exe", "sha256": "3" * 64})
        module = install.core()
        flags = ["--" + key.replace("_", "-") for key in ("state", "cache", "data_home", "config_home", "bin_home")]
        values = [str(getattr(self.loc, key)) for key in ("state", "cache", "data_home", "config_home", "bin_home")]
        args = [value for pair in zip(flags, values) for value in pair] + ["update"]
        with mock.patch.object(install, "read_lock", return_value=lock), \
             mock.patch.object(install, "core", return_value=module), \
             mock.patch.object(install, "ensure_packages"), \
             mock.patch.object(install, "verify_runtime_build"), \
             mock.patch.object(install, "fetch_verified", return_value=self.root / "installer.exe"), \
             mock.patch.object(module, "install_exe", return_value=1), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(maintenance.main(args), 1)
        snapshots = list((self.loc.state / "backups").glob("snapshot-*/snapshot.json"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual((snapshots[0].parent / "prefix/design").read_bytes(), b"valuable design fixture")
        self.assertFalse((self.loc.state / "last-update.json").exists())

    def test_overlay_activation_allows_only_exact_pinned_archive_difference(self):
        lock, archive, candidate, original, patched = self.overlay_fixture()
        cached = install.overlay_artifact(self.loc, lock, archive, candidate)
        receipt = install.prepare_overlay(self.loc, lock, archive)
        recovery = install.validate_overlay_recovery(self.loc, receipt)
        self.assertEqual(receipt["overlay"]["required_environment"], {
            "WINE_X11_ARGB_SHAPE_INPUT": "1", "WINE_X11_ARGB_CONSTANT_ALPHA": "1", "QSG_RHI_BACKEND": "opengl"})
        self.assertEqual((recovery / "winex11.so").read_bytes(), original)
        self.assertEqual(recovery.stat().st_mode & 0o777, 0o700)
        install.write_json(self.loc.state / "compatibility-lock.json", lock)
        install.activate_overlay(self.loc, lock, cached, receipt)
        target = self.loc.state / lock["runner"]["name"] / install.OVERLAY_TARGET
        self.assertEqual(target.read_bytes(), patched)
        install.require_overlay_installed(self.loc, lock)
        install.install_runner(archive, self.loc, lock)
        unrelated = self.loc.state / lock["runner"]["name"] / "unchanged"
        unrelated.write_bytes(b"unreviewed change")
        with self.assertRaises(install.InstallError):
            install.install_runner(archive, self.loc, lock)
        self.assertEqual(unrelated.read_bytes(), b"unreviewed change")
        self.assertEqual(install.digest(archive), lock["runner"]["sha256"])

    def test_overlay_unknown_artifact_or_base_hash_is_never_promoted(self):
        lock, archive, candidate, original, _ = self.overlay_fixture()
        candidate.write_bytes(b"unknown binary")
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive, candidate)
        self.assertFalse((self.loc.cache / lock["runner_overlay"]["id"] / "winex11.so").exists())
        bad_lock = dict(lock, runner_overlay=dict(lock["runner_overlay"], original_sha256="0" * 64))
        with self.assertRaises(install.InstallError):
            install.prepare_overlay(self.loc, bad_lock, archive)
        self.assertEqual((self.loc.state / lock["runner"]["name"] / install.OVERLAY_TARGET).read_bytes(), original)
        bad_environment = dict(lock, runner_overlay=dict(lock["runner_overlay"], required_environment={"LD_PRELOAD": "1"}))
        with self.assertRaises(install.InstallError):
            install.overlay_spec(bad_environment)

    def test_overlay_environment_requires_only_the_reviewed_three_settings(self):
        lock, _, _, _, _ = self.overlay_fixture()
        expected = lock["runner_overlay"]["required_environment"]
        self.assertEqual(install.overlay_spec(lock)["required_environment"], expected)
        invalid = [dict(expected, QSG_RHI_BACKEND="vulkan"),
                   dict(expected, QT_WIDGETS_RHI="1"),
                   dict(expected, WINE_X11_UNKNOWN_OVERRIDE="1"),
                   dict(expected, WINE_X11_ARGB_CONSTANT_ALPHA="0"),
                   {key: value for key, value in expected.items() if key != "QSG_RHI_BACKEND"}]
        for environment in invalid:
            with self.subTest(environment=environment), self.assertRaises(install.InstallError):
                install.overlay_spec(dict(lock, runner_overlay=dict(lock["runner_overlay"], required_environment=environment)))

    def test_overlay_rollback_restores_module_lock_and_ownership_after_interruption(self):
        lock, archive, candidate, original, patched = self.overlay_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        active_lock = self.loc.state / "compatibility-lock.json"
        install.write_json(active_lock, lock)
        manifest = install.load_manifest(self.loc)
        manifest["files"][str(active_lock)] = install.file_record(active_lock)
        install.write_json(self.loc.manifest, manifest)
        install.activate_overlay(self.loc, lock, candidate, receipt)
        self.loc.prefix.mkdir()
        design = self.loc.prefix / "design"
        design.write_bytes(b"preserved unsynced design")
        module = install.core()
        original_write = install.atomic_write

        def fail_lock_write(path, data, mode=0o600):
            if path == active_lock:
                raise OSError("simulated interruption")
            return original_write(path, data, mode)

        with mock.patch.object(install, "atomic_write", side_effect=fail_lock_write), self.assertRaises(OSError):
            maintenance.rollback_overlay(self.loc, module)
        target = self.loc.state / lock["runner"]["name"] / install.OVERLAY_TARGET
        self.assertEqual(target.read_bytes(), original)
        self.assertIn("runner_overlay", json.loads(active_lock.read_text()))
        with self.assertRaises(install.InstallError):
            install.require_overlay_installed(self.loc, lock)
        maintenance.rollback_overlay(self.loc, module)
        self.assertEqual(target.read_bytes(), original)
        self.assertNotIn("runner_overlay", json.loads(active_lock.read_text()))
        self.assertEqual(install.load_manifest(self.loc)["files"][str(active_lock)], install.file_record(active_lock))
        self.assertEqual(design.read_bytes(), b"preserved unsynced design")
        self.assertEqual(json.loads((self.loc.state / "runner-overlay.json").read_text())["phase"], "rolled_back")
        # A completed rollback is idempotent and keeps the verified recovery files.
        self.assertTrue(maintenance.rollback_overlay(self.loc, module).is_dir())

    def test_integration_only_refuses_required_overlay_that_is_not_installed(self):
        lock, _, _, _, _ = self.overlay_fixture()
        args = ["--state", str(self.loc.state), "--cache", str(self.loc.cache),
                "--data-home", str(self.loc.data_home), "--config-home", str(self.loc.config_home),
                "--bin-home", str(self.loc.bin_home), "--integration-only"]
        with mock.patch.object(install, "read_lock", return_value=lock), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(args), 1)
        self.assertFalse(self.loc.manifest.exists())
        self.assertFalse((self.loc.state / "bin").exists())

    def test_integration_only_cannot_drop_an_active_overlay_requirement(self):
        lock, _, _, _, _ = self.overlay_fixture()
        install.write_json(self.loc.state / "compatibility-lock.json", lock)
        original_lock = dict(lock)
        original_lock.pop("runner_overlay")
        args = ["--state", str(self.loc.state), "--cache", str(self.loc.cache),
                "--data-home", str(self.loc.data_home), "--config-home", str(self.loc.config_home),
                "--bin-home", str(self.loc.bin_home), "--integration-only"]
        with mock.patch.object(install, "read_lock", return_value=original_lock), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(args), 1)
        self.assertEqual(json.loads((self.loc.state / "compatibility-lock.json").read_text()), lock)
        self.assertFalse(self.loc.manifest.exists())

    def test_modified_recovery_module_cannot_be_restored(self):
        lock, archive, candidate, _, patched = self.overlay_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        recovery = install.validate_overlay_recovery(self.loc, receipt)
        install.write_json(self.loc.state / "compatibility-lock.json", lock)
        install.activate_overlay(self.loc, lock, candidate, receipt)
        (recovery / "winex11.so").write_bytes(b"damaged backup")
        with self.assertRaises(install.InstallError):
            maintenance.rollback_overlay(self.loc, install.core())
        self.assertEqual((self.loc.state / lock["runner"]["name"] / install.OVERLAY_TARGET).read_bytes(), patched)

    def test_v2_contract_accepts_only_the_complete_reviewed_pair_and_environment(self):
        lock, _, _, _, _ = self.overlay_v2_fixture()
        overlay = lock["runner_overlay"]
        module = install.core()
        self.assertEqual(install.OVERLAY_ENVIRONMENT_V2, module.OVERLAY_ENVIRONMENT_V2)
        self.assertEqual(install.overlay_modules(install.overlay_spec(lock)),
                         sorted(module.overlay_modules(overlay), key=lambda item: item["target"]))
        invalid = []
        for modules in ([], overlay["modules"][:1], overlay["modules"] * 2,
                        [overlay["modules"][0], overlay["modules"][0]], "not a list"):
            invalid.append(dict(overlay, modules=modules))
        for target in (None, "../../win32u.so", "files/lib/wine/i386-unix/win32u.so"):
            modules = [dict(item) for item in overlay["modules"]]
            modules[1]["target"] = target
            invalid.append(dict(overlay, modules=modules))
        for environment in (dict(install.OVERLAY_ENVIRONMENT),
                            dict(install.OVERLAY_ENVIRONMENT_V2, QSG_RHI_BACKEND="opengl"),
                            dict(install.OVERLAY_ENVIRONMENT_V2, WINE_X11_VULKAN_PRESENT_WAIT="0"),
                            dict(install.OVERLAY_ENVIRONMENT_V2, DXVK_CONFIG="dxgi.syncInterval = 0"),
                            dict(install.OVERLAY_ENVIRONMENT_V2, DXVK_CONFIG_FILE="unreviewed.conf"),
                            {key: value for key, value in install.OVERLAY_ENVIRONMENT_V2.items()
                             if key != "WINE_X11_VULKAN_PRESENT_WAIT"},
                            dict(install.OVERLAY_ENVIRONMENT_V2, LD_PRELOAD="unreviewed")):
            invalid.append(dict(overlay, required_environment=environment))
        invalid.append(dict(overlay, sha256="a" * 64))
        modules = [dict(item) for item in overlay["modules"]]
        modules[0]["sha256"] = 42
        invalid.append(dict(overlay, modules=modules))
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(install.InstallError):
                install.overlay_spec(dict(lock, runner_overlay=candidate))

    def test_v3_environment_is_separate_from_strict_v2_receipt_contract(self):
        lock, _, _, _, _ = self.overlay_v2_fixture()
        v2 = lock["runner_overlay"]
        v3 = {**v2, "id": "ge-proton11-7-omarchy-x11-v3",
              "required_environment": {"WINE_X11_ARGB_SHAPE_INPUT": "1", "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
                                       "WINE_X11_VULKAN_PRESENT_WAIT": "1", "QSG_RHI_BACKEND": "opengl"}}
        module = install.core()
        self.assertEqual(install.OVERLAY_ENVIRONMENT_V3, module.OVERLAY_ENVIRONMENT_V3)
        self.assertEqual(install.overlay_spec(dict(lock, runner_overlay=v3)), v3)
        self.assertEqual(install.overlay_spec(lock), v2)
        invalid = [dict(v2, required_environment=v3["required_environment"]),
                   dict(v3, required_environment=v2["required_environment"]),
                   dict(v3, required_environment=install.OVERLAY_ENVIRONMENT),
                   dict(v3, id=[v3["id"]]),
                   dict(v3, modules=v3["modules"][:1])]
        for key, value in (("DXVK_CONFIG", "dxgi.syncInterval = 0"), ("DXVK_CONFIG_FILE", "old.conf"),
                           ("QT_WIDGETS_RHI", "1"), ("WINE_X11_VULKAN_PRESENT_WAIT", "0")):
            invalid.append(dict(v3, required_environment={**v3["required_environment"], key: value}))
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(install.InstallError):
                install.overlay_spec(dict(lock, runner_overlay=candidate))

    def test_v3_migration_refuses_full_and_integration_installs_before_any_replacement(self):
        lock, archive, candidate, originals, patched = self.overlay_v2_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        self.overlay_guard(lock)
        install.activate_overlay(self.loc, lock, candidate, receipt)
        selected = {**lock, "runner_overlay": {**lock["runner_overlay"], "id": "ge-proton11-7-omarchy-x11-v3",
                                              "required_environment": dict(install.OVERLAY_ENVIRONMENT_V3)}}
        paths = (self.loc.state / "compatibility-lock.json", self.loc.state / "runner-overlay.json", self.loc.manifest)
        before = {path: path.read_bytes() for path in paths}
        args = ["--state", str(self.loc.state), "--cache", str(self.loc.cache),
                "--data-home", str(self.loc.data_home), "--config-home", str(self.loc.config_home),
                "--bin-home", str(self.loc.bin_home)]
        for mode in ([], ["--integration-only"]):
            with (self.subTest(mode=mode), mock.patch.object(install, "read_lock", return_value=selected),
                  mock.patch.object(install, "ensure_packages") as packages,
                  mock.patch.object(install, "install_integration") as integration,
                  contextlib.redirect_stderr(io.StringIO())):
                self.assertEqual(install.main(args + mode), 1)
                packages.assert_not_called()
                integration.assert_not_called()
            self.assert_overlay_bytes(lock, patched)
            self.assertEqual({path: path.read_bytes() for path in paths}, before)
        # Even after module restoration, the old required-overlay lock must be
        # explicitly rolled back before selecting a new environment revision.
        for target, data in originals.items():
            (self.loc.state / lock["runner"]["name"] / target).write_bytes(data)
        with self.assertRaisesRegex(install.InstallError, "Roll back"):
            install.prepare_overlay(self.loc, selected, archive)

    def test_frozen_v2_receipt_rolls_back_before_v3_then_preserves_exact_originals_and_prefix(self):
        old, archive, candidate, originals, patched = self.overlay_v2_fixture()
        baseline = {key: value for key, value in old.items() if key != "runner_overlay"}
        previous_bytes = (json.dumps(baseline, indent=4) + "\n").encode()
        recovery = self.loc.state / "runner-recovery/ge-proton11-7-omarchy-x11-v2-frozen"
        recovery.mkdir(parents=True)
        for target, data in originals.items():
            (recovery / Path(target).name).write_bytes(data)
            (self.loc.state / old["runner"]["name"] / target).write_bytes(patched[target])
        (recovery / "compatibility-lock.json").write_bytes(previous_bytes)
        # Frozen schema2 field layout and literal d3d11 environment from the
        # deployed v2 receipt; no current prepare function creates this record.
        receipt = {"schema": 2, "application_id": "fusion360-for-omarchy", "runner": old["runner"]["name"],
                   "base_runner_sha256": old["runner"]["sha256"],
                   "overlay": {"id": "ge-proton11-7-omarchy-x11-v2", "modules": old["runner_overlay"]["modules"],
                               "required_environment": {"WINE_X11_ARGB_SHAPE_INPUT": "1",
                                                        "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
                                                        "QSG_RHI_BACKEND": "d3d11", "WINE_X11_VULKAN_PRESENT_WAIT": "1"},
                               "manifest": "runtime-patches/manifest.json"},
                   "phase": "active", "recovery": str(recovery.relative_to(self.loc.state)),
                   "previous_lock_sha256": hashlib.sha256(previous_bytes).hexdigest()}
        install.write_json(self.loc.state / "runner-overlay.json", receipt)
        self.overlay_guard(old)
        archived_receipt = recovery / "receipt-before-migration.json"
        archived_receipt.write_bytes((self.loc.state / "runner-overlay.json").read_bytes())
        preserved = {path.name: path.read_bytes() for path in recovery.iterdir()}
        self.loc.prefix.mkdir()
        design = self.loc.prefix / "unsynced-design"
        design.write_bytes(b"private unsynced design fixture")
        selected = {**old, "runner_overlay": {**old["runner_overlay"], "id": "ge-proton11-7-omarchy-x11-v3",
                                             "required_environment": dict(install.OVERLAY_ENVIRONMENT_V3)}}
        self.assertEqual(selected["runner_overlay"]["modules"], old["runner_overlay"]["modules"])
        with self.assertRaisesRegex(install.InstallError, "Roll back"):
            install.prepare_overlay(self.loc, selected, archive)
        # New source/provenance may already exist. Rollback must rely only on
        # the frozen receipt and verified recovery files, not today's manifest.
        install.write_json(self.loc.state / "runtime-patches/manifest.json", {"schema": 2, **selected["runner_overlay"]})
        module = install.core()
        with mock.patch.object(install, "read_lock", side_effect=AssertionError("rollback read current source lock")):
            maintenance.rollback_overlay(self.loc, module)
        self.assert_overlay_bytes(old, originals)
        active_lock = self.loc.state / "compatibility-lock.json"
        self.assertEqual(active_lock.read_bytes(), previous_bytes)
        cached = install.overlay_artifact(self.loc, selected, archive, supplied_dir=candidate)
        self.assertEqual(cached.name, selected["runner_overlay"]["id"])
        prepared = install.prepare_overlay(self.loc, selected, archive)
        self.assertNotEqual(prepared["recovery"], receipt["recovery"])
        self.overlay_guard(selected)
        install.activate_overlay(self.loc, selected, cached, prepared)
        self.assert_overlay_bytes(selected, patched)
        paths = install.runtime_paths(self.loc, module)
        module.validate_overlay(paths, module.runner_overlay(paths, selected))
        maintenance.rollback_overlay(self.loc, module)
        self.assert_overlay_bytes(selected, originals)
        self.assertEqual(active_lock.read_bytes(), previous_bytes)
        self.assertEqual(install.load_manifest(self.loc)["files"][str(active_lock)], install.file_record(active_lock))
        self.assertEqual(design.read_bytes(), b"private unsynced design fixture")
        self.assertEqual({path.name: path.read_bytes() for path in recovery.iterdir()}, preserved)
        self.assertEqual(install.validate_overlay_recovery(self.loc, json.loads(archived_receipt.read_text())), recovery)
        self.assertEqual(install.digest(archive), selected["runner"]["sha256"])

    def test_v2_lock_requires_matching_schema2_manifest(self):
        fixture, _, _, _, _ = self.overlay_v2_fixture()
        lock = dict(fixture, schema=1,
                    runner=dict(fixture["runner"], url="https://example.invalid/runner.tar.gz"),
                    autodesk_installer={"url": "https://example.invalid/installer.exe", "sha256": "3" * 64})
        source = self.root / "lock-source"
        install.write_json(source / "compatibility-lock.json", lock)
        manifest = {key: value for key, value in lock["runner_overlay"].items() if key != "manifest"}
        path = source / "runtime-patches/manifest.json"
        install.write_json(path, dict(manifest, schema=2))
        self.assertEqual(install.read_lock(source), lock)
        for changed in (dict(manifest, schema=1),
                        dict(manifest, schema=2, required_environment=install.OVERLAY_ENVIRONMENT)):
            install.write_json(path, changed)
            with self.assertRaises(install.InstallError):
                install.read_lock(source)

    def test_v2_promotion_and_rollback_preserve_original_pair_and_exact_previous_lock(self):
        lock, archive, candidate, originals, patched = self.overlay_v2_fixture()
        baseline = dict(lock)
        baseline.pop("runner_overlay")
        previous = (json.dumps(baseline, indent=4) + "\n").encode()
        active = self.loc.state / "compatibility-lock.json"
        active.write_bytes(previous)
        cached = install.overlay_artifact(self.loc, lock, archive, supplied_dir=candidate)
        receipt = install.prepare_overlay(self.loc, lock, archive)
        self.assertEqual(receipt["schema"], 2)
        recovery = install.validate_overlay_recovery(self.loc, receipt)
        for target, original in originals.items():
            self.assertEqual((recovery / Path(target).name).read_bytes(), original)
        self.overlay_guard(lock)
        install.activate_overlay(self.loc, lock, cached, receipt)
        self.assert_overlay_bytes(lock, patched)
        install.install_runner(archive, self.loc, lock)
        module = install.core()
        paths = install.runtime_paths(self.loc, module)
        module.validate_overlay(paths, module.runner_overlay(paths, lock))
        self.loc.prefix.mkdir()
        (self.loc.prefix / "design").write_bytes(b"unsynced design")
        maintenance.rollback_overlay(self.loc, module)
        self.assert_overlay_bytes(lock, originals)
        self.assertEqual(active.read_bytes(), previous)
        self.assertEqual(install.load_manifest(self.loc)["files"][str(active)], install.file_record(active))
        self.assertEqual((self.loc.prefix / "design").read_bytes(), b"unsynced design")
        self.assertTrue(maintenance.rollback_overlay(self.loc, module).is_dir())
        self.assertEqual(active.read_bytes(), previous)
        self.assertEqual(install.digest(archive), lock["runner"]["sha256"])

    def test_v2_preflights_both_artifacts_and_production_modules_before_any_replacement(self):
        lock, archive, candidate, originals, patched = self.overlay_v2_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        self.overlay_guard(lock)
        second = install.overlay_modules(lock["runner_overlay"])[1]["target"]
        (candidate / Path(second).name).write_bytes(b"bad second artifact")
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive, supplied_dir=candidate)
        self.assertFalse((self.loc.cache / lock["runner_overlay"]["id"]).exists())
        with self.assertRaises(install.InstallError):
            install.activate_overlay(self.loc, lock, candidate, receipt)
        self.assert_overlay_bytes(lock, originals)
        (candidate / Path(second).name).write_bytes(patched[second])
        target = self.loc.state / lock["runner"]["name"] / second
        target.write_bytes(b"unknown production module")
        expected = dict(originals, **{second: b"unknown production module"})
        with self.assertRaises(install.InstallError):
            install.activate_overlay(self.loc, lock, candidate, receipt)
        self.assert_overlay_bytes(lock, expected)

    def test_v2_activation_requires_guard_and_partial_pair_requires_matching_receipt(self):
        lock, archive, candidate, originals, patched = self.overlay_v2_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        with self.assertRaises(install.InstallError):
            install.activate_overlay(self.loc, lock, candidate, receipt)
        self.assert_overlay_bytes(lock, originals)
        first = install.overlay_modules(lock["runner_overlay"])[0]["target"]
        (self.loc.state / lock["runner"]["name"] / first).write_bytes(patched[first])
        (self.loc.state / "runner-overlay.json").unlink()
        with self.assertRaises(install.InstallError):
            install.prepare_overlay(self.loc, lock, archive)

    def test_v2_interrupted_activation_never_accepts_a_mixed_pair_and_can_resume(self):
        for failure in ("first", "second", "receipt"):
            with self.subTest(failure=failure):
                self.loc = replace(self.loc, state=self.root / ("activation-" + failure))
                lock, archive, candidate, originals, patched = self.overlay_v2_fixture()
                receipt = install.prepare_overlay(self.loc, lock, archive)
                self.overlay_guard(lock)
                targets = [self.loc.state / lock["runner"]["name"] / item["target"]
                           for item in install.overlay_modules(lock["runner_overlay"])]
                fault = targets[0] if failure == "first" else targets[1] if failure == "second" else self.loc.state / "runner-overlay.json"
                original_write = install.atomic_write

                def interrupt(path, data, mode=0o600):
                    if path == fault:
                        raise OSError("simulated interruption")
                    return original_write(path, data, mode)

                with mock.patch.object(install, "atomic_write", side_effect=interrupt), self.assertRaises(OSError):
                    install.activate_overlay(self.loc, lock, candidate, receipt)
                module = install.core()
                paths = install.runtime_paths(self.loc, module)
                if failure != "receipt":
                    with self.assertRaises(module.LauncherError):
                        module.validate_overlay(paths, module.runner_overlay(paths, lock))
                else:
                    # Complete verified bytes are coherent even if the advisory
                    # receipt phase write was interrupted after both replacements.
                    module.validate_overlay(paths, module.runner_overlay(paths, lock))
                resumed = install.prepare_overlay(self.loc, lock, archive)
                install.activate_overlay(self.loc, lock, candidate, resumed)
                self.assert_overlay_bytes(lock, patched)
                self.assertEqual(json.loads((self.loc.state / "runner-overlay.json").read_text())["phase"], "active")

    def test_v2_rollback_preflights_all_recovery_and_current_bytes(self):
        lock, archive, candidate, _, patched = self.overlay_v2_fixture()
        receipt = install.prepare_overlay(self.loc, lock, archive)
        recovery = install.validate_overlay_recovery(self.loc, receipt)
        self.overlay_guard(lock)
        install.activate_overlay(self.loc, lock, candidate, receipt)
        second = install.overlay_modules(lock["runner_overlay"])[1]["target"]
        original = recovery / Path(second).name
        old = original.read_bytes()
        original.write_bytes(b"damaged second backup")
        with self.assertRaises(install.InstallError):
            maintenance.rollback_overlay(self.loc, install.core())
        self.assert_overlay_bytes(lock, patched)
        original.write_bytes(old)
        target = self.loc.state / lock["runner"]["name"] / second
        target.write_bytes(b"unrecognized second current file")
        with self.assertRaises(install.InstallError):
            maintenance.rollback_overlay(self.loc, install.core())
        self.assert_overlay_bytes(lock, dict(patched, **{second: b"unrecognized second current file"}))

    def test_v2_rollback_interruption_preserves_guard_until_both_originals_are_restored(self):
        for failure in ("second", "lock"):
            with self.subTest(failure=failure):
                self.loc = replace(self.loc, state=self.root / ("rollback-" + failure))
                lock, archive, candidate, originals, _ = self.overlay_v2_fixture()
                receipt = install.prepare_overlay(self.loc, lock, archive)
                self.overlay_guard(lock)
                install.activate_overlay(self.loc, lock, candidate, receipt)
                second = install.overlay_modules(lock["runner_overlay"])[1]["target"]
                active = self.loc.state / "compatibility-lock.json"
                fault = active if failure == "lock" else self.loc.state / lock["runner"]["name"] / second
                original_write = install.atomic_write

                def interrupt(path, data, mode=0o600):
                    if path == fault:
                        raise OSError("simulated interruption")
                    return original_write(path, data, mode)

                module = install.core()
                with mock.patch.object(install, "atomic_write", side_effect=interrupt), self.assertRaises(OSError):
                    maintenance.rollback_overlay(self.loc, module)
                self.assertEqual(json.loads(active.read_text())["runner_overlay"], lock["runner_overlay"])
                with self.assertRaises(module.LauncherError):
                    module.validate_overlay(install.runtime_paths(self.loc, module), lock["runner_overlay"])
                maintenance.rollback_overlay(self.loc, module)
                self.assert_overlay_bytes(lock, originals)
                self.assertNotIn("runner_overlay", json.loads(active.read_text()))

    def test_actual_legacy_receipt_shape_rolls_back_without_current_manifest_before_v2(self):
        lock, archive, candidate, originals, _ = self.overlay_v2_fixture()
        item = next(item for item in lock["runner_overlay"]["modules"] if item["target"] == install.OVERLAY_TARGET)
        legacy_bytes = b"legacy v1 runtime bytes"
        legacy = {"id": "ge-proton11-7-omarchy-x11-v1", "target": install.OVERLAY_TARGET,
                  "original_sha256": item["original_sha256"], "sha256": hashlib.sha256(legacy_bytes).hexdigest(),
                  "required_environment": {"WINE_X11_ARGB_SHAPE_INPUT": "1", "WINE_X11_ARGB_CONSTANT_ALPHA": "1",
                                           "QSG_RHI_BACKEND": "opengl"}, "manifest": "runtime-patches/manifest.json"}
        baseline = dict(lock)
        baseline.pop("runner_overlay")
        recovery = self.loc.state / "runner-recovery/ge-proton11-7-omarchy-x11-v1-legacy"
        recovery.mkdir(parents=True)
        (recovery / "winex11.so").write_bytes(originals[install.OVERLAY_TARGET])
        install.write_json(recovery / "compatibility-lock.json", baseline)
        # Frozen field layout from the original deployed schema1 receipt. No
        # call to prepare_overlay creates or migrates this recovery record.
        receipt = {"schema": 1, "application_id": install.APP, "runner": lock["runner"]["name"],
                   "base_runner_sha256": lock["runner"]["sha256"], "overlay": legacy, "phase": "active",
                   "recovery": str(recovery.relative_to(self.loc.state)),
                   "previous_lock_sha256": install.digest(recovery / "compatibility-lock.json")}
        install.write_json(self.loc.state / "runner-overlay.json", receipt)
        install.write_json(self.loc.state / "compatibility-lock.json", dict(lock, runner_overlay=legacy))
        (self.loc.state / lock["runner"]["name"] / install.OVERLAY_TARGET).write_bytes(legacy_bytes)
        with self.assertRaisesRegex(install.InstallError, "Roll back"):
            install.prepare_overlay(self.loc, lock, archive)
        install.write_json(self.loc.state / "runtime-patches/manifest.json", {"schema": 2, "unrelated": True})
        with mock.patch.object(install, "read_lock", side_effect=AssertionError("legacy rollback must not read today's manifest")):
            maintenance.rollback_overlay(self.loc, install.core())
        self.assert_overlay_bytes(lock, originals)
        self.assertTrue(recovery.is_dir())
        prepared = install.prepare_overlay(self.loc, lock, archive)
        self.assertEqual(prepared["schema"], 2)
        self.overlay_guard(lock)
        install.activate_overlay(self.loc, lock, candidate, prepared)
        self.assertTrue(recovery.is_dir())

    def test_v2_builder_uses_output_directory_and_rejects_incomplete_pair(self):
        lock, archive, _, originals, patched = self.overlay_v2_fixture()
        calls = []

        def build(command, _loc, **_kwargs):
            calls.append(command)
            directory = Path(command[command.index("--output-dir") + 1])
            directory.mkdir()
            for target, data in patched.items():
                (directory / Path(target).name).write_bytes(data)

        with mock.patch.object(install.subprocess, "run", return_value=mock.Mock(returncode=0)), \
             mock.patch.object(install, "run", side_effect=build):
            artifact = install.overlay_artifact(self.loc, lock, archive)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("--output", calls[0])
        self.assertEqual(set(install.read_overlay_artifacts(lock["runner_overlay"], artifact)), set(patched))
        self.assert_overlay_bytes(lock, originals)
        shutil.rmtree(artifact)

        def incomplete(command, _loc, **_kwargs):
            directory = Path(command[command.index("--output-dir") + 1])
            directory.mkdir()
            (directory / "winex11.so").write_bytes(patched[install.OVERLAY_TARGET])

        with mock.patch.object(install.subprocess, "run", return_value=mock.Mock(returncode=0)), \
             mock.patch.object(install, "run", side_effect=incomplete), self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive)
        self.assertFalse(artifact.exists())
        self.assert_overlay_bytes(lock, originals)

    def test_overlay_file_and_directory_arguments_are_version_specific(self):
        lock, archive, candidate, originals, _ = self.overlay_v2_fixture()
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive, supplied=candidate / "winex11.so")
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive, supplied=candidate / "winex11.so", supplied_dir=candidate)
        self.assert_overlay_bytes(lock, originals)
        self.loc = replace(self.loc, state=self.root / "legacy-state")
        self.loc.state.mkdir()
        legacy_lock, legacy_archive, _, _, _ = self.overlay_fixture()
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, legacy_lock, legacy_archive, supplied_dir=candidate)

    def test_v2_bad_cached_second_module_preserves_the_entire_cache(self):
        lock, archive, candidate, originals, _ = self.overlay_v2_fixture()
        items = install.overlay_modules(lock["runner_overlay"])
        cache = self.loc.cache / lock["runner_overlay"]["id"]
        cache.mkdir(parents=True)
        second = cache / Path(items[1]["target"]).name
        second.write_bytes(b"unrecognized cached bytes")
        with self.assertRaises(install.InstallError):
            install.overlay_artifact(self.loc, lock, archive, supplied_dir=candidate)
        self.assertEqual(second.read_bytes(), b"unrecognized cached bytes")
        self.assertFalse((cache / Path(items[0]["target"]).name).exists())
        self.assert_overlay_bytes(lock, originals)

    def test_require_closed_detects_live_worker_after_leader_exit_without_matching_overlay(self):
        proc = self.root / "proc/12"
        worker = proc / "task/13"
        worker.mkdir(parents=True)
        (proc / "status").write_text("State:\tZ (zombie)\nPPid:\t1\n")
        (proc / "environ").write_bytes(b"")
        (proc / "comm").write_text("old runtime\n")
        (worker / "status").write_text("State:\tS (sleeping)\n")
        (worker / "environ").write_bytes(b"WINEPREFIX=" + os.fsencode(self.loc.prefix)
                                        + b"\0PROTONPATH=/experimental/old-runner\0FUSION360_OVERLAY_ID=wrong\0")
        (worker / "exe").symlink_to("/experimental/old-runner/wine")
        (worker / "cmdline").write_bytes(b"C:\\windows\\system32\\winedevice.exe\0private argument not needed\0")
        (worker / "maps").write_text("")
        module = install.core()
        with self.assertRaises(install.InstallError):
            install.require_closed(self.loc, module, proc_root=proc.parent)
        (worker / "maps").unlink()
        with self.assertRaises(install.InstallError):
            install.require_closed(self.loc, module, proc_root=proc.parent)
        shutil.rmtree(worker)
        install.require_closed(self.loc, module, proc_root=proc.parent)

    def test_atomic_replacement_syncs_parent_after_rename(self):
        path = self.loc.state / "durable-lock"
        events = []
        real_sync, real_replace = os.fsync, os.replace

        def sync(fd):
            events.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
            return real_sync(fd)

        def rename(source, destination):
            events.append("rename")
            return real_replace(source, destination)

        with mock.patch.object(install.os, "fsync", side_effect=sync), mock.patch.object(install.os, "replace", side_effect=rename):
            install.atomic_write(path, b"durable contents")
        self.assertEqual(events, ["file", "rename", "directory"])
        self.assertEqual(path.read_bytes(), b"durable contents")

    def test_installed_builder_contains_all_local_dependencies_and_runs_independently(self):
        manifest = install.load_manifest(self.loc)
        install.install_integration(self.loc, manifest, register=False)
        directory = self.loc.state / "runtime-patches"
        recipe = json.loads((directory / "manifest.json").read_text())
        tree = ast.parse((directory / "build-overlay.py").read_text())
        # Derive direct local-file reads from the real builder, so a future new
        # dependency cannot silently disappear through a stale packaging list.
        scripts = {"build-overlay.py", "test-constant-alpha.py"}
        if recipe.get("schema") == 2:
            scripts.add("test-present-wait.py")
        required = scripts | {"README.md"}
        required.update(node.right.value for node in ast.walk(tree)
                        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                        and isinstance(node.left, ast.Name) and node.left.id == "HERE"
                        and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str))
        for patch in recipe["patches"]:
            required.update((patch["file"], patch["notice"]))
            self.assertEqual(install.digest(directory / patch["file"]), patch["sha256"])
        self.assertIn("compile.sh", required)
        for name in required:
            self.assertTrue((directory / name).is_file(), name)
            self.assertEqual(install.digest(directory / name), install.digest(install.SOURCE / "runtime-patches" / name))
        outside = self.root / "unrelated-working-directory"
        outside.mkdir()
        for script in sorted(scripts):
            result = subprocess.run([sys.executable, str(directory / script), "--help"], cwd=outside,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        if shutil.which("bash"):
            subprocess.run(["bash", "-n", str(directory / "compile.sh")], check=True)
        maintenance.uninstall(self.loc, manifest)
        self.assertTrue(all(not (directory / name).exists() for name in required))

    def test_incomplete_recipe_is_rejected_before_any_integration_write(self):
        source = self.root / "incomplete-source"
        for relative in install.support_files():
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(install.SOURCE / relative, destination)
        recipe = json.loads((source / "runtime-patches/manifest.json").read_text())
        names = ["compile.sh"] + (["test-present-wait.py"] if recipe.get("schema") == 2 else [])
        for name in names:
            with self.subTest(missing=name):
                path = source / "runtime-patches" / name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaises(install.InstallError):
                    install.install_integration(self.loc, install.load_manifest(self.loc), source=source, register=False)
                self.assertFalse(self.loc.manifest.exists())
                self.assertFalse((self.loc.state / "bin").exists())
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
