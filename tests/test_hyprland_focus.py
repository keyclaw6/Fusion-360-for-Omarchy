"""Focus-rule ownership checks use temporary files, never the live compositor."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import fusion360_hyprland as focus

FROZEN_LEGACY_BLOCK = (
    b'-- BEGIN fusion360-for-omarchy focus rule\n'
    b'o.window({ class = "^steam_app_fusion360$", xwayland = true }, { focus_on_activate = false })\n'
    b'o.window({ class = "^steam_app_fusion360$", title = "^Msg:QTView:.*MessageTray$", xwayland = true }, { border_size = 0 })\n'
    b'-- END fusion360-for-omarchy focus rule\n'
)


@unittest.skipUnless(shutil.which("luac"), "requires the real Lua syntax checker")
class FocusRuleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fusion-focus-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config/hypr/hyprland.lua"
        self.config.parent.mkdir(parents=True)
        self.original = b'-- personal settings\nrequire("default.hypr.omarchy")'
        self.config.write_bytes(self.original)
        self.config.chmod(0o640)
        self.state = self.root / "private state"

    def install(self):
        return focus.install_focus_rule(self.config, self.state)

    def remove(self):
        return focus.remove_focus_rule(self.config, self.state)

    def frozen_legacy_install(self):
        """The deployed record shape, independent of today's install function."""
        self.assertEqual(focus.LEGACY_BLOCK, FROZEN_LEGACY_BLOCK)
        directory = self.state / "hyprland-focus"
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        installed = self.original + b"\n" + FROZEN_LEGACY_BLOCK
        self.config.write_bytes(installed)
        backup = directory / "before-install-frozen.lua"
        backup.write_bytes(self.original)
        backup.chmod(0o600)
        record = {"schema": 1, "application_id": "fusion360-for-omarchy", "config_path": str(self.config),
                  "block_sha256": focus._hash(FROZEN_LEGACY_BLOCK), "original_sha256": focus._hash(self.original),
                  "installed_sha256": focus._hash(installed), "original_mode": 0o640,
                  "original_backup": backup.name, "status": "installed", "legacy_note": "preserve this verbatim"}
        raw = (json.dumps(record, indent=4) + "\n").encode()
        (directory / "record.json").write_bytes(raw)
        (directory / "record.json").chmod(0o600)
        return directory, raw, installed

    def frozen_monitor_install(self, prepared=False):
        self.assertEqual(focus._hash(focus.MONITOR_BLOCK),
                         'f67ad6bc9e2cf463d2c576142679a984eb5b4b2838915df6b3001f993c45b778')
        directory, legacy_raw, legacy_config = self.frozen_legacy_install()
        installed = legacy_config.replace(FROZEN_LEGACY_BLOCK, focus.MONITOR_BLOCK)
        record = {
            'schema': 1, 'application_id': 'fusion360-for-omarchy', 'config_path': str(self.config),
            'block_sha256': focus._hash(focus.MONITOR_BLOCK), 'original_sha256': focus._hash(self.original),
            'installed_sha256': focus._hash(installed), 'original_mode': 0o640,
            'original_backup': 'before-install-monitor-frozen.lua',
            'status': 'install-prepared' if prepared else 'installed',
            'upgrade': {'record_backup': 'before-upgrade-record-frozen.json',
                        'record_sha256': focus._hash(legacy_raw),
                        'config_backup': 'before-upgrade-config-frozen.lua',
                        'config_sha256': focus._hash(legacy_config)},
        }
        (directory / record['original_backup']).write_bytes(self.original)
        (directory / record['upgrade']['record_backup']).write_bytes(legacy_raw)
        (directory / record['upgrade']['config_backup']).write_bytes(legacy_config)
        raw = (json.dumps(record, indent=2) + '\n').encode()
        (directory / 'record.json').write_bytes(raw)
        self.config.write_bytes(legacy_config if prepared else installed)
        return directory, raw, installed

    def test_idempotent_install_and_exact_removal_keep_bytes_mode_and_private_backup(self):
        self.assertTrue(self.install())
        self.assertFalse(self.install())
        self.assertEqual(self.config.read_bytes().count(focus.BLOCK), 1)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        directory = self.state / "hyprland-focus"
        record = json.loads((directory / "record.json").read_bytes())
        self.assertEqual(record["original_mode"], 0o640)
        backup = directory / record["original_backup"]
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual((directory / "record.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.remove())
        self.assertFalse(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        self.assertTrue(backup.exists())

    def test_deployed_group_revision_upgrades_and_rolls_back_exactly(self):
        self.assertEqual(focus._hash(focus.GROUP_BLOCK),
                         "9239f81b3ad92a9ca2460f5f85d71ff4fd934fd6ec1ff4fda37c428b10341ae2")
        with mock.patch.object(focus, "BLOCK", focus.GROUP_BLOCK):
            self.install()
        previous = self.config.read_bytes()
        record_path = self.state / "hyprland-focus/record.json"
        previous_record = record_path.read_bytes()
        self.install()
        self.assertIn(focus.BLOCK, self.config.read_bytes())
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual(self.config.read_bytes(), previous)
        self.assertEqual(record_path.read_bytes(), previous_record)
        self.remove()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_deployed_workspace_revision_upgrades_and_rolls_back_exactly(self):
        self.assertEqual(focus._hash(focus.WORKSPACE_BLOCK),
                         "800c9fb153ff57f321769a47cd641e0767a78138fc9f1fe37b5bf7b81aa93fa1")
        with mock.patch.object(focus, "BLOCK", focus.WORKSPACE_BLOCK):
            self.install()
        previous = self.config.read_bytes()
        self.install()
        self.assertIn(focus.DRAG_RULE, self.config.read_bytes())
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual(self.config.read_bytes(), previous)

    def test_removal_preserves_user_edits_outside_block_and_current_mode(self):
        self.install()
        edited = b'-- newly added before\n' + self.config.read_bytes() + b'-- newly added after\n'
        self.config.write_bytes(edited)
        self.config.chmod(0o600)
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), edited.replace(focus.BLOCK, b""))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_edited_block_is_never_replaced_or_removed(self):
        self.install()
        installed = self.config.read_bytes()
        for old, new in ((b"focus_on_activate = false", b"focus_on_activate = true"),
                         (b"border_size = 0", b"border_size = 1"),
                         (b'window.initial_title == "Fusion360"', b'window.initial_title == "other"')):
            with self.subTest(effect=old):
                edited = installed.replace(old, new)
                self.config.write_bytes(edited)
                for operation in (self.install, self.remove):
                    with self.assertRaises(focus.FocusRuleError):
                        operation()
                    self.assertEqual(self.config.read_bytes(), edited)

    @unittest.skipUnless(shutil.which("lua"), "requires Lua for the isolated rule contract")
    def test_rule_payload_scopes_activation_border_and_utility_animations(self):
        # Execute only our constant block, with a recording stub, never user config.
        capture = b'''hl = {on = function(name, callback)
            assert((name == "window.move_to_workspace" or name == "window.open" or name == "window.active" or name == "window.fullscreen")
                and type(callback) == "function")
        end}
        o = { window = function(match, effects)
            assert(match.xwayland == true)
            assert(match.class ~= nil)
            for key, value in pairs(match) do
                assert(key == "class" or key == "title" or key == "initial_title" or key == "xwayland")
            end
            local count = 0
            for key, value in pairs(effects) do
                count = count + 1
                io.write(match.class, "\\t", match.title or match.initial_title or "", "\\t", key, "\\t", tostring(value), "\\n")
            end
            assert(count == 1)
        end }\n'''
        result = subprocess.run([shutil.which("lua"), "-"], input=capture + focus.BLOCK,
                                capture_output=True, check=True, timeout=10)
        self.assertEqual(result.stdout.decode().splitlines(), [
            "^steam_app_fusion360$\t\tfocus_on_activate\tfalse",
            "^steam_app_fusion360$\t^Msg:QTView:.*MessageTray$\tborder_size\t0",
            "^steam_app_fusion360$\t^Fusion360$\tno_anim\ttrue",
        ])
        title = result.stdout.decode().splitlines()[1].split("\t")[1]
        self.assertIsNotNone(re.fullmatch(title, "Msg:QTView:(102)MessageTray"))
        for other_title in ("Fusion360", "Autodesk Fusion", "MessageTray",
                            "Msg:QTView:(102)MessageTray other"):
            self.assertIsNone(re.fullmatch(title, other_title))

    def test_unowned_or_duplicate_block_is_preserved(self):
        self.config.write_bytes(self.original + b"\n" + focus.BLOCK)
        with self.assertRaises(focus.FocusRuleError):
            self.install()
        self.assertFalse(self.remove())
        self.config.write_bytes(self.original)
        self.install()
        duplicated = self.config.read_bytes() + focus.BLOCK
        self.config.write_bytes(duplicated)
        with self.assertRaises(focus.FocusRuleError):
            self.remove()
        self.assertEqual(self.config.read_bytes(), duplicated)

    def test_invalid_lua_never_changes_config_and_valid_lua_is_not_executed(self):
        self.config.write_bytes(b"local bad = {\n")
        with self.assertRaises(focus.FocusRuleError):
            self.install()
        self.assertEqual(self.config.read_bytes(), b"local bad = {\n")
        executed = self.root / "must-not-exist"
        self.config.write_text('io.open("' + str(executed) + '", "w"):close()\n')
        self.install()
        self.assertFalse(executed.exists())

    def test_symbolic_link_and_agent_dot_files_paths_are_refused(self):
        link = self.root / "linked-config.lua"
        link.symlink_to(self.config)
        with self.assertRaises(focus.FocusRuleError):
            focus.install_focus_rule(link, self.state)
        directory = self.root / "linked-directory"
        directory.symlink_to(self.config.parent)
        with self.assertRaises(focus.FocusRuleError):
            focus.install_focus_rule(directory / "hyprland.lua", self.state)
        forbidden = self.root / "agent-dot-files/hyprland.lua"
        forbidden.parent.mkdir()
        forbidden.write_bytes(self.original)
        with self.assertRaises(focus.FocusRuleError):
            focus.install_focus_rule(forbidden, self.state)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertEqual(forbidden.read_bytes(), self.original)

    def test_configuration_change_during_validation_is_not_overwritten(self):
        validate = focus._validate_candidate
        edited = self.original + b"\n-- simultaneous user edit\n"

        def concurrent_edit(directory, data):
            validate(directory, data)
            self.config.write_bytes(edited)

        with mock.patch.object(focus, "_validate_candidate", side_effect=concurrent_edit):
            with self.assertRaises(focus.FocusRuleError):
                self.install()
        self.assertEqual(self.config.read_bytes(), edited)

    def test_private_state_cannot_be_created_inside_a_git_repository(self):
        repository = self.root / "source"
        repository.mkdir()
        (repository / ".git").mkdir()
        with self.assertRaises(focus.FocusRuleError):
            focus.install_focus_rule(self.config, repository / "state")
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_reinstall_after_user_removes_block_and_record_tampering(self):
        self.install()
        self.config.write_bytes(self.original + b"\n-- retained user setting\n")
        self.assertTrue(self.install())
        record_path = self.state / "hyprland-focus/record.json"
        record = json.loads(record_path.read_bytes())
        record["original_backup"] = "../unrelated"
        record_path.write_text(json.dumps(record))
        existing = self.config.read_bytes()
        with self.assertRaises(focus.FocusRuleError):
            self.remove()
        self.assertEqual(self.config.read_bytes(), existing)

    def test_prepared_record_recovers_when_final_record_write_fails(self):
        write_record = focus._record_write

        def fail_final_record(directory, record):
            if record["status"] == "installed":
                raise OSError("simulated record write failure")
            write_record(directory, record)

        with mock.patch.object(focus, "_record_write", side_effect=fail_final_record):
            with self.assertRaises(OSError):
                self.install()
        self.assertIn(focus.BLOCK, self.config.read_bytes())
        self.assertFalse(self.install())
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_missing_lua_validator_preserves_config(self):
        with mock.patch.object(focus.shutil, "which", return_value=None):
            with self.assertRaises(focus.FocusRuleError):
                self.install()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_frozen_legacy_record_can_be_removed_without_upgrade(self):
        self.frozen_legacy_install()
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_legacy_upgrade_archives_exact_record_config_and_original_then_uninstalls(self):
        directory, raw, installed = self.frozen_legacy_install()
        self.assertTrue(self.install())
        self.assertFalse(self.install())
        record = json.loads((directory / "record.json").read_bytes())
        self.assertEqual((directory / record["upgrade"]["record_backup"]).read_bytes(), raw)
        self.assertEqual((directory / record["upgrade"]["config_backup"]).read_bytes(), installed)
        self.assertEqual((directory / "before-install-frozen.lua").read_bytes(), self.original)
        self.assertEqual(record["status"], "installed")
        self.assertEqual(self.config.read_bytes(), installed.replace(FROZEN_LEGACY_BLOCK, focus.BLOCK))
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))

    def test_upgrade_and_removal_preserve_edits_before_and_after_upgrade(self):
        self.frozen_legacy_install()
        before = b'-- added before migration\n' + self.config.read_bytes() + b'-- later setting\n'
        self.config.write_bytes(before)
        self.install()
        self.config.write_bytes(self.config.read_bytes() + b'-- added after migration\n')
        self.config.chmod(0o600)
        self.remove()
        self.assertEqual(self.config.read_bytes(), before.replace(FROZEN_LEGACY_BLOCK, b'') + b'-- added after migration\n')
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_rollback_restores_exact_legacy_record_and_preserves_surrounding_edits(self):
        directory, raw, before = self.frozen_legacy_install()
        self.install()
        extra = b'-- after upgrade\n'
        self.config.write_bytes(self.config.read_bytes() + extra)
        self.config.chmod(0o600)
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual((directory / 'record.json').read_bytes(), raw)
        self.assertEqual(self.config.read_bytes(), before + extra)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), before.replace(FROZEN_LEGACY_BLOCK, b'') + extra)

    def test_unowned_or_edited_legacy_block_is_never_migrated(self):
        self.config.write_bytes(self.original + b'\n' + FROZEN_LEGACY_BLOCK)
        with self.assertRaises(focus.FocusRuleError):
            self.install()
        directory, raw, before = self.frozen_legacy_install()
        changed = before.replace(b'border_size = 0', b'border_size = 1')
        self.config.write_bytes(changed)
        for operation in (self.install, self.remove):
            with self.assertRaises(focus.FocusRuleError):
                operation()
            self.assertEqual(self.config.read_bytes(), changed)
            self.assertEqual((directory / 'record.json').read_bytes(), raw)

    def test_prepared_upgrade_retries_after_config_write_failure(self):
        directory, raw, before = self.frozen_legacy_install()
        with mock.patch.object(focus, '_replace_config', side_effect=OSError('simulated config write failure')):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(self.config.read_bytes(), before)
        record = json.loads((directory / 'record.json').read_bytes())
        self.assertEqual(record['status'], 'install-prepared')
        self.assertEqual((directory / record['upgrade']['record_backup']).read_bytes(), raw)
        self.assertTrue(self.install())
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_prepared_upgrade_refuses_changed_config_but_can_be_cancelled(self):
        directory, raw, before = self.frozen_legacy_install()
        with mock.patch.object(focus, '_replace_config', side_effect=OSError('simulated config write failure')):
            with self.assertRaises(OSError):
                self.install()
        edited = before + b'-- concurrent edit\n'
        self.config.write_bytes(edited)
        with self.assertRaises(focus.FocusRuleError):
            self.install()
        self.assertEqual(self.config.read_bytes(), edited)
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual((directory / 'record.json').read_bytes(), raw)
        self.assertEqual(self.config.read_bytes(), edited)

    def test_upgrade_final_record_failure_recovers_without_duplicate_migration(self):
        directory, _, _ = self.frozen_legacy_install()
        write = focus._record_write

        def fail_installed(directory, record):
            if record['status'] == 'installed':
                raise OSError('simulated final record failure')
            write(directory, record)

        with mock.patch.object(focus, '_record_write', side_effect=fail_installed):
            with self.assertRaises(OSError):
                self.install()
        before = sorted(directory.glob('before-upgrade-*'))
        self.assertFalse(self.install())
        self.assertEqual(sorted(directory.glob('before-upgrade-*')), before)
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))

    def test_rollback_recovers_after_restoring_config_before_record_write(self):
        directory, raw, before = self.frozen_legacy_install()
        self.install()
        write = focus._write

        def fail_old_record(path, data, mode=0o600):
            if path == directory / 'record.json' and data == raw:
                raise OSError('simulated old record restore failure')
            write(path, data, mode)

        with mock.patch.object(focus, '_write', side_effect=fail_old_record):
            with self.assertRaises(OSError):
                focus.rollback_focus_rule(self.config, self.state)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(json.loads((directory / 'record.json').read_bytes())['status'], 'rollback-prepared')
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual((directory / 'record.json').read_bytes(), raw)
        self.assertTrue(self.remove())
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_corrupt_archived_record_blocks_upgrade_removal_and_rollback(self):
        directory, _, _ = self.frozen_legacy_install()
        self.install()
        before = self.config.read_bytes()
        record = json.loads((directory / 'record.json').read_bytes())
        (directory / record['upgrade']['record_backup']).write_bytes(b'altered recovery data')
        for operation in (self.install, self.remove, lambda: focus.rollback_focus_rule(self.config, self.state)):
            with self.assertRaises(focus.FocusRuleError):
                operation()
            self.assertEqual(self.config.read_bytes(), before)

    def test_monitor_upgrade_rolls_back_one_exact_version_at_a_time_with_outside_edits(self):
        directory, monitor_raw, monitor_config = self.frozen_monitor_install()
        legacy_raw = (directory / 'before-upgrade-record-frozen.json').read_bytes()
        self.install()
        installed = json.loads((directory / 'record.json').read_bytes())
        self.assertEqual((directory / installed['upgrade']['record_backup']).read_bytes(), monitor_raw)
        extra = b'-- user edit after the second upgrade\n'
        self.config.write_bytes(self.config.read_bytes() + extra)
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual(self.config.read_bytes(), monitor_config + extra)
        self.assertEqual((directory / 'record.json').read_bytes(), monitor_raw)
        self.assertTrue(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual((directory / 'record.json').read_bytes(), legacy_raw)
        self.assertEqual(self.config.read_bytes(), monitor_config.replace(focus.MONITOR_BLOCK, FROZEN_LEGACY_BLOCK) + extra)
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))
        self.remove()
        self.assertEqual(self.config.read_bytes(), self.original + b'\n' + extra)

    def test_monitor_upgrade_uninstall_preserves_edits_without_restoring_an_old_block(self):
        self.frozen_monitor_install()
        extra = b'-- setting before the second upgrade\n'
        self.config.write_bytes(self.config.read_bytes() + extra)
        self.install()
        self.remove()
        self.assertEqual(self.config.read_bytes(), self.original + b'\n' + extra)
        self.assertNotIn(focus.BEGIN, self.config.read_bytes())

    def test_prepared_monitor_upgrade_completes_its_recorded_target_before_latest(self):
        directory, _, _ = self.frozen_monitor_install(prepared=True)
        replace = focus._replace_config
        targets = []

        def capture(config, previous, updated, info):
            targets.append(focus._find_block(updated))
            replace(config, previous, updated, info)

        with mock.patch.object(focus, '_replace_config', side_effect=capture):
            self.assertTrue(self.install())
        self.assertEqual(targets, [focus.MONITOR_BLOCK, focus.BLOCK])
        latest = json.loads((directory / 'record.json').read_bytes())
        previous = json.loads((directory / latest['upgrade']['record_backup']).read_bytes())
        self.assertEqual(previous['block_sha256'], focus._hash(focus.MONITOR_BLOCK))
        self.assertEqual(previous['status'], 'installed')
        self.remove()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_nested_upgrade_and_rollback_recover_at_both_config_record_boundaries(self):
        directory, monitor_raw, monitor_config = self.frozen_monitor_install()
        with mock.patch.object(focus, '_replace_config', side_effect=OSError('simulated config write failure')):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(self.config.read_bytes(), monitor_config)
        self.assertTrue(self.install())
        write = focus._write

        def fail_previous_record(path, data, mode=0o600):
            if path == directory / 'record.json' and data == monitor_raw:
                raise OSError('simulated record restore failure')
            write(path, data, mode)

        with mock.patch.object(focus, '_write', side_effect=fail_previous_record):
            with self.assertRaises(OSError):
                focus.rollback_focus_rule(self.config, self.state)
        self.assertEqual(self.config.read_bytes(), monitor_config)
        self.assertFalse(focus.rollback_focus_rule(self.config, self.state))
        self.assertEqual((directory / 'record.json').read_bytes(), monitor_raw)

    def test_nested_history_is_validated_and_non_decreasing_versions_are_rejected(self):
        directory, _, _ = self.frozen_monitor_install()
        self.install()
        before = self.config.read_bytes()
        nested = directory / 'before-upgrade-record-frozen.json'
        old_bytes = nested.read_bytes()
        nested.write_bytes(b'changed nested legacy recovery')
        for operation in (self.install, self.remove, lambda: focus.rollback_focus_rule(self.config, self.state)):
            with self.assertRaises(focus.FocusRuleError):
                operation()
            self.assertEqual(self.config.read_bytes(), before)
        nested.write_bytes(old_bytes)
        latest = json.loads((directory / 'record.json').read_bytes())
        prior_path = directory / latest['upgrade']['record_backup']
        prior = json.loads(prior_path.read_bytes())
        prior['block_sha256'] = latest['block_sha256']
        raw = (json.dumps(prior) + '\n').encode()
        prior_path.write_bytes(raw)
        latest['upgrade']['record_sha256'] = focus._hash(raw)
        (directory / 'record.json').write_text(json.dumps(latest))
        with self.assertRaises(focus.FocusRuleError):
            self.remove()
        self.assertEqual(self.config.read_bytes(), before)


@unittest.skipUnless(shutil.which("lua"), "requires Lua for the isolated event contract")
class LuaHookTests(unittest.TestCase):
    harness = "hyprland_monitor_contract.lua"
    block_name = "BLOCK"

    def run_hook(self, assertions):
        with tempfile.TemporaryDirectory(prefix="fusion-monitor-test-") as directory:
            block = Path(directory) / "owned-block.lua"
            block.write_bytes(getattr(focus, self.block_name))
            harness = Path(__file__).with_name(self.harness).read_bytes()
            result = subprocess.run([shutil.which("lua"), "-", str(block)], input=harness + assertions.encode(),
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())


class MonitorFollowTests(LuaHookTests):
    block_name = "GROUP_BLOCK"  # Keep the deployed monitor hook's contract covered.
    def test_only_matching_floating_children_follow_the_exact_main_and_destination(self):
        self.run_hook('''
local browser = child()
windows = {main, browser, child({pid = 99}), child({class = "other"}),
           child({initial_title = "Save"}), child({xwayland = false}),
           child({floating = false}), child({mapped = false}), child({workspace = destination})}
callback(child(), destination) -- A child move must not trigger another query.
callback(child({initial_title = "Autodesk Fusion other"}), destination)
assert(queries == 0)
recurse = true -- The real compositor also suppresses recursive subscriptions.
callback(main, destination)
assert(queries == 1 and #operations == 2)
assert(operations[1].args.window == browser and operations[1].args.workspace == destination)
assert(operations[2].args.window == browser and browser.size.x == 600 and browser.size.y == 400)
assert(main.monitor == old_monitor) -- The event fires before the owner's monitor changes.
''')

    def test_bidirectional_scaling_uses_fresh_children_and_preserves_physical_size(self):
        self.run_hook('''
local browser = child()
windows = {browser}
callback(main, destination)
assert(browser.size.x == 600 and browser.size.y == 400)
local comments = child({workspace = destination, monitor = new_monitor, size = {x = 120, y = 80}})
windows = {browser, comments} -- Discovered after registration and after the first event.
callback(main, old_workspace)
assert(queries == 2 and #operations == 6)
assert(browser.size.x == 300 and browser.size.y == 200)
assert(comments.size.x == 60 and comments.size.y == 40)
callback(main, old_workspace)
assert(#operations == 6) -- Same-workspace events never resize again.
''')

    def test_missing_destination_expired_windows_and_invalid_geometry_are_ignored(self):
        self.run_hook('''
windows = {child()}
callback(nil, destination)
callback(main, nil)
callback(main, {})
for _, scale in ipairs({0, -1, math.huge, 0/0, "1"}) do
  callback(main, {monitor = {scale = scale}})
end
assert(queries == 0 and #operations == 0)
windows = {{}, child({monitor = {scale = 0}}), child({size = {x = 0, y = 200}}),
           child({monitor = {scale = math.huge}}), child({size = {x = 0/0, y = 200}})}
callback(main, destination)
assert(#operations == 0)
''')

    def test_failed_move_or_disappearing_child_is_not_resized_and_no_repair_loop_runs(self):
        self.run_hook('''
windows = {child()}
fail_move = true
callback(main, destination)
assert(#operations == 1 and operations[1].kind == "move")
fail_move, expire_on_move = false, true
windows = {child()}
callback(main, destination)
assert(#operations == 2 and operations[2].kind == "move")
expire_on_move, fail_resize = false, true
windows = {child()}
callback(main, destination)
assert(#operations == 4 and operations[4].kind == "resize")
callback(main, destination)
assert(#operations == 4) -- No timer, retry, reassertion, or repeated scale adjustment.
fail_resize = false
windows = {child()}
callback(main, destination)
assert(#operations == 6 and windows[1].size.x == 600)
''')


class GroupFocusTests(LuaHookTests):
    harness = "hyprland_group_contract.lua"
    block_name = "DRAG_BLOCK"  # Frozen pre-modal behavior remains covered.

    def test_active_and_fullscreen_repair_only_false_members_using_fresh_typed_windows(self):
        self.run_hook('''
comments.allowed_over_fullscreen = true
local unknown = child()
unknown.allowed_over_fullscreen = nil
windows = {main, browser, comments, unknown, child({pid = 99}), child({workspace = other_workspace}),
           child({initial_title = "Save"}), child({xwayland = false}), child({floating = false})}
active = browser
on_active(browser)
assert(#operations == 2 and operations[1] == main and operations[2] == browser)
assert(active == browser)
on_fullscreen(main)
assert(#operations == 2) -- Already repaired members are left alone.
local reopened = child()
table.insert(windows, reopened)
on_fullscreen(main)
assert(#operations == 3 and operations[3] == reopened and active == browser)
''')

    def test_unrelated_active_window_missing_group_or_ambiguous_main_never_raise(self):
        self.run_hook('''
local zen = {mapped = true, xwayland = false, class = "zen", pid = 77}
active = zen
on_fullscreen(main)
assert(#operations == 0 and active == zen)
active = nil
on_active(main)
assert(#operations == 0 and active == nil)
active = main
on_active(child({workspace = other_workspace}))
assert(#operations == 0)
local second_main = child({initial_title = "Autodesk Fusion", floating = false})
table.insert(windows, second_main)
on_active(main)
assert(#operations == 0 and active == main)
windows = {browser, comments}
active = browser
on_active(browser)
assert(#operations == 0)
''')

    def test_native_active_window_change_stops_further_raises_without_restoring_focus(self):
        self.run_hook('''
local zen = {mapped = true, class = "zen", pid = 77}
switch_active = zen
on_active(main)
assert(#operations == 1 and operations[1] == main)
assert(active == zen and browser.allowed_over_fullscreen == false)
on_fullscreen(main)
assert(#operations == 1 and active == zen)
''')

    def test_shared_guard_blocks_cross_event_recursion_and_resets_after_dispatch_failure(self):
        self.run_hook('''
recurse = true
on_active(main)
assert(queries == 1 and #operations == 3 and active == main)
main.allowed_over_fullscreen, browser.allowed_over_fullscreen, comments.allowed_over_fullscreen = false, false, false
throw_raise = true
local ok, failure = pcall(on_active, main)
assert(not ok and failure:find("simulated Lua dispatch failure", 1, true))
assert(#operations == 4)
throw_raise, fail_raise = false, true
on_fullscreen(main)
assert(#operations == 5) -- A failed raise neither retries nor raises later members.
fail_raise = false
on_fullscreen(main)
assert(#operations == 8 and active == main)
''')


class WorkspaceGroupTests(LuaHookTests):
    harness = "hyprland_workspace_contract.lua"

    def test_child_move_carries_main_siblings_and_tray_without_recursive_moves(self):
        self.run_hook('''
move(browser,destination)
assert(main.workspace==destination and comments.workspace==destination and tray.workspace==destination)
assert(browser.workspace==old_workspace) -- Native move completes after this event.
assert(unrelated.workspace==old_workspace and #operations==5)
assert(comments.size.x==600 and comments.size.y==400)
''')

    def test_main_move_preserves_utility_physical_size_and_unrelated_windows(self):
        self.run_hook('''
move(main,destination)
assert(main.workspace==old_workspace and #operations==6)
assert(browser.workspace==destination and comments.workspace==destination and tray.workspace==destination)
assert(browser.size.x==600 and tray.size.y==400 and unrelated.workspace==old_workspace)
''')

    def test_opened_child_joins_existing_owner_without_following_focus(self):
        self.run_hook('''
browser.workspace,browser.monitor=destination,new_monitor
open(browser)
assert(browser.workspace==old_workspace and browser.size.x==150 and browser.size.y==100)
assert(main.workspace==old_workspace and #operations==2)
''')

    def test_ambiguous_owner_and_unrelated_windows_are_not_moved(self):
        self.run_hook('''
table.insert(windows,child({initial_title="Autodesk Fusion"}))
move(browser,destination)
assert(#operations==0)
table.remove(windows)
for _,w in ipairs({child({pid=99}),child({class="other"}),child({xwayland=false}),
    child({mapped=false})}) do
  move(w,destination)
  open(w)
end
assert(#operations==0)
''')

    def test_save_modal_and_other_same_process_windows_follow_unique_main(self):
        self.run_hook('''
save=child({initial_title="Save"})
other=child({initial_title="Other Fusion dialog"})
table.insert(windows,save);table.insert(windows,other)
move(save,destination)
assert(main.workspace==destination and other.workspace==destination)
assert(browser.workspace==destination and unrelated.workspace==old_workspace)
assert(save.workspace==old_workspace) -- Event's native operation completes next.
''')

    def test_failed_move_never_resizes_and_exception_releases_guard(self):
        self.run_hook('''
fail_move=true
move(main,destination)
assert(#operations==3 and browser.workspace==old_workspace)
fail_move=false
throw_move=true
assert(not pcall(move,main,destination))
throw_move=false
move(main,destination)
assert(#operations==9 and browser.workspace==destination)
''')




class ModalFocusTests(LuaHookTests):
    harness = "hyprland_group_contract.lua"

    def test_late_backdrop_open_reorders_an_already_eligible_save(self):
        self.run_hook('''
save=child({initial_title="Save"})
backdrop=child()
windows={main,save,browser,backdrop}
for _,window in ipairs(windows) do window.allowed_over_fullscreen=true end
on_open(save);on_open(backdrop)
assert(#timers==2 and not timers[1].enabled and #operations==0)
timers[1].callback();assert(#operations==0)
timers[2].callback()
assert(#operations==1 and operations[1]==save)
on_active(save);assert(#operations==1)
''')

    def test_disappearing_open_trigger_does_not_lose_a_live_dialog_repair(self):
        self.run_hook('''
save=child({initial_title="Save"})
backdrop=child()
windows={main,browser,save,backdrop}
for _,window in ipairs(windows) do window.allowed_over_fullscreen=true end
on_open(backdrop);backdrop.mapped=false
timers[1].callback()
assert(#operations==1 and operations[1]==save)
''')

    def test_workspace_repair_uses_the_main_current_workspace_after_native_move(self):
        self.run_hook('''
save=child({initial_title="Save"})
windows={main,browser,save}
for _,window in ipairs(windows) do window.allowed_over_fullscreen=true end
on_move(save,other_workspace)
for _,window in ipairs(windows) do window.workspace=other_workspace end
timers[1].callback()
assert(#operations==1 and operations[1]==save)
''')

    def test_open_ambiguous_main_or_foreign_process_does_not_replace_timer(self):
        self.run_hook('''
save=child({initial_title="Save"});windows={main,browser,save}
on_open(save);assert(#timers==1)
local alien=child({pid=99,workspace=workspace})
on_move(alien,workspace);assert(#timers==1 and timers[1].enabled)
table.insert(windows,child({initial_title="Autodesk Fusion",floating=false}))
on_move(save,workspace);assert(#timers==1 and timers[1].enabled)
''')

    def test_fullscreen_transition_reorders_already_eligible_surfaces_once(self):
        self.run_hook('''
save=child({initial_title="Save"})
backdrop=child()
windows={main,save,browser,backdrop};active=backdrop
for _,window in ipairs(windows) do window.allowed_over_fullscreen=true end
on_active(main)
assert(#operations==0)
recurse=true
on_fullscreen(main)
assert(#operations==0 and #timers==1)
timers[1].callback()
assert(#operations==1 and operations[1]==save)
on_active(save)
assert(#operations==1) -- Ordinary focus does not keep rebuilding the stack.
on_fullscreen(main) -- Restoring the main window needs the same ordering.
timers[#timers].callback()
assert(#operations==2 and operations[2]==save)
''')

    def test_deferred_repair_cancels_old_transition_and_respects_other_app(self):
        self.run_hook('''
save=child({initial_title="Save"})
windows={main,browser,save}
for _,window in ipairs(windows) do window.allowed_over_fullscreen=true end
on_fullscreen(main);on_fullscreen(main)
assert(#timers==2 and not timers[1].enabled)
timers[1].callback()
assert(#operations==0)
active={mapped=true,xwayland=true,class="other",pid=99}
timers[2].callback()
assert(#operations==0)
active=main
on_fullscreen(main)
save.mapped=false
timers[3].callback()
assert(#operations==0) -- A closed modal is never raised by a stale timer.
''')

    def test_modal_is_raised_after_backdrop_even_when_listed_first(self):
        self.run_hook('''
save=child({initial_title="Save"})
backdrop=child()
windows={main,save,browser,backdrop}
on_active(main)
assert(#operations==4 and operations[1]==main and operations[4]==save)
assert(save.allowed_over_fullscreen and backdrop.allowed_over_fullscreen)
on_active(main)
assert(#operations==4) -- No ongoing raise loop after eligibility is repaired.
''')

    def test_existing_eligible_modal_remains_above_a_newly_repaired_backdrop(self):
        self.run_hook('''
save=child({initial_title="Save Component Copy As",allowed_over_fullscreen=true})
windows={main,save,browser,comments}
on_active(browser)
assert(#operations==4 and operations[4]==save and active==main)
''')

    def test_modal_event_repairs_its_group_but_never_other_application(self):
        self.run_hook('''
save=child({initial_title="Save"})
windows={main,browser,comments,save};active=save
on_active(save)
assert(#operations==4 and operations[4]==save and active==save)
main.allowed_over_fullscreen=false
active={mapped=true,xwayland=true,class="other",pid=99}
on_fullscreen(main)
assert(#operations==4 and not main.allowed_over_fullscreen)
''')


if __name__ == "__main__":
    unittest.main()
