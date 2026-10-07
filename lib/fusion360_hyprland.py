"""Reversible Fusion-only Hyprland rules, monitor following and utility stacking."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid


APP = "fusion360-for-omarchy"
BEGIN = b"-- BEGIN fusion360-for-omarchy focus rule"
END = b"-- END fusion360-for-omarchy focus rule"
# Frozen bytes from the first installed rule, including its ownership markers.
LEGACY_BLOCK = (BEGIN + b"\n"
         b'o.window({ class = "^steam_app_fusion360$", xwayland = true }, '
         b"{ focus_on_activate = false })\n"
         b'o.window({ class = "^steam_app_fusion360$", '
         b'title = "^Msg:QTView:.*MessageTray$", xwayland = true }, '
         b"{ border_size = 0 })\n" + END + b"\n")
MONITOR_HOOK = b'''-- Fusion's Browser/Comments use this observed class/PID/initial-title convention.
-- Hyprland Lua exposes no X11 transient owner; this is not an ownership proof.
-- Subscriptions belong to this Lua config and are destroyed on compositor reload.
do
  local class = "steam_app_fusion360"
  local function positive(value)
    return type(value) == "number" and value > 0 and value < math.huge
  end
  hl.on("window.move_to_workspace", function(main, destination)
    if not main or not main.mapped or not main.xwayland or main.class ~= class then return end
    local title, pid = main.initial_title, main.pid
    if type(title) ~= "string" or title:match("^%s*(.-)%s*$") ~= "Autodesk Fusion"
        or not positive(pid) or not destination then return end
    -- The event precedes the main window's monitor update. Use its destination.
    local monitor = destination.monitor
    local new_scale = monitor and monitor.scale
    if not positive(new_scale) then return end
    -- Fresh typed references on every event; never retain addresses or PIDs.
    for _, child in ipairs(hl.get_windows({class = class, mapped = true, floating = true})) do
      if child ~= main and child.mapped and child.xwayland and child.floating
          and child.class == class and child.pid == pid and child.initial_title == "Fusion360" then
        local workspace, old_monitor, size = child.workspace, child.monitor, child.size
        local old_scale = old_monitor and old_monitor.scale
        if workspace and workspace ~= destination and positive(old_scale) and type(size) == "table"
            and positive(size.x) and positive(size.y) then
          local width, height = size.x * old_scale / new_scale, size.y * old_scale / new_scale
          if positive(width) and positive(height) then
            local moved = hl.dispatch(hl.dsp.window.move({window = child, workspace = destination, follow = false}))
            if moved and moved.ok and child.mapped and child.workspace == destination then
              hl.dispatch(hl.dsp.window.resize({window = child, x = width, y = height, relative = false}))
            end
          end
        end
      end
    end
  end)
end
'''
# Freeze the deployed monitor-only revision for exact upgrade and rollback.
MONITOR_BLOCK = LEGACY_BLOCK.removesuffix(END + b"\n") + MONITOR_HOOK + END + b"\n"
GROUP_FOCUS_HOOK = b'''-- Repair managed Fusion utility stacking only while its own group is active.
-- alter_zorder also runs native pointer handling; never dispatch focus or hide.
do
  local class, busy = "steam_app_fusion360", false
  local function fusion(window)
    return window and window.mapped and window.xwayland and window.class == class
        and type(window.pid) == "number" and window.pid > 0 and window.pid < math.huge
  end
  local function main_window(window)
    if not fusion(window) then return false end
    local title = window.initial_title
    return type(title) == "string" and title:match("^%s*(.-)%s*$") == "Autodesk Fusion"
  end
  local function child_window(window, main)
    return fusion(window) and window ~= main and window.pid == main.pid and window.floating
        and window.initial_title == "Fusion360" and window.workspace == main.workspace
  end
  local function repair(event)
    if busy or not fusion(event) or not event.workspace then return end
    if not main_window(event) and not (event.floating and event.initial_title == "Fusion360") then return end
    local workspace, main = event.workspace, nil
    local windows = hl.get_windows({class = class, mapped = true})
    for _, window in ipairs(windows) do
      if main_window(window) and window.pid == event.pid and window.workspace == workspace then
        if main and main ~= window then return end -- Ambiguous group: leave it alone.
        main = window
      end
    end
    if not main then return end
    local function member(window)
      return main.mapped and main.workspace == workspace and (window == main or child_window(window, main))
    end
    if not member(event) or not member(hl.get_active_window()) then return end
    busy = true
    local ok, failure = pcall(function()
      local function raise(window)
        if not member(hl.get_active_window()) then return false end
        if member(window) and window.allowed_over_fullscreen == false then
          local result = hl.dispatch(hl.dsp.window.alter_zorder({mode = "top", window = window}))
          return result and result.ok
        end
        return true
      end
      if not raise(main) then return end
      for _, window in ipairs(windows) do
        if child_window(window, main) and not raise(window) then return end
      end
    end)
    busy = false
    if not ok then error(failure) end
  end
  hl.on("window.active", repair)
  hl.on("window.fullscreen", repair)
end
'''
# Preserve the September deployment exactly for ownership checks and rollback.
GROUP_BLOCK = MONITOR_BLOCK.removesuffix(END + b"\n") + GROUP_FOCUS_HOOK + END + b"\n"
WORKSPACE_HOOK = b'''-- Keep observed Fusion utilities with their unique owning main window.
-- Browser/Comments have an X11 transient owner, unavailable in the Lua API.
-- Restrict the fallback to the observed class, PID and utility titles.
do
  local class, busy = "steam_app_fusion360", false
  local function positive(value)
    return type(value) == "number" and value > 0 and value < math.huge
  end
  local function fusion(window)
    return window and window.mapped and window.xwayland and window.class == class
        and positive(window.pid)
  end
  local function main_window(window)
    local title = window and window.initial_title
    return fusion(window) and type(title) == "string"
        and title:match("^%s*(.-)%s*$") == "Autodesk Fusion"
  end
  local function child_window(child, main)
    return fusion(child) and child ~= main and child.pid == main.pid and child.floating
        and (child.initial_title == "Fusion360"
          or (type(child.initial_title) == "string"
            and child.initial_title:match("^Msg:QTView:.*MessageTray$")))
  end
  local function owner(event, windows)
    local main
    for _, window in ipairs(windows) do
      if main_window(window) and window.pid == event.pid then
        if main then return nil end -- Multiple main windows: do not guess ownership.
        main = window
      end
    end
    if main and (event == main or child_window(event, main)) then return main end
  end
  local function together(event, destination, opening)
    if busy or not fusion(event) then return end
    local windows = hl.get_windows({class = class, mapped = true})
    local main = owner(event, windows)
    if not main then return end
    if opening then destination = main.workspace end
    if not destination then return end
    local new_scale = destination.monitor and destination.monitor.scale
    busy = true
    local ok, failure = pcall(function()
      for _, window in ipairs(windows) do
        -- A move event precedes its own workspace/monitor update; do not move it twice.
        if (opening or window ~= event) and (window == main or child_window(window, main))
            and window.workspace and window.workspace ~= destination then
          local size, old_scale = window.size, window.monitor and window.monitor.scale
          local width, height
          if window ~= main and positive(old_scale) and positive(new_scale)
              and type(size) == "table" and positive(size.x) and positive(size.y) then
            width, height = size.x * old_scale / new_scale, size.y * old_scale / new_scale
          end
          local moved = hl.dispatch(hl.dsp.window.move({window = window, workspace = destination, follow = false}))
          if moved and moved.ok and window.mapped and window.workspace == destination
              and positive(width) and positive(height) then
            hl.dispatch(hl.dsp.window.resize({window = window, x = width, y = height, relative = false}))
          end
        end
      end
    end)
    busy = false
    if not ok then error(failure) end
  end
  hl.on("window.move_to_workspace", function(event, destination) together(event, destination, false) end)
  hl.on("window.open", function(event) together(event, nil, true) end)
end
'''
# Freeze the deployed workspace repair before adding the drag fix.
WORKSPACE_BLOCK = LEGACY_BLOCK.removesuffix(END + b"\n") + WORKSPACE_HOOK + GROUP_FOCUS_HOOK + END + b"\n"
DRAG_RULE = b'''-- Qt moves its own utility windows while dragging. Compositor animation competes.
o.window({ class = "^steam_app_fusion360$", initial_title = "^Fusion360$", xwayland = true }, { no_anim = true })
'''
DRAG_BLOCK = WORKSPACE_BLOCK.removesuffix(END + b"\n") + DRAG_RULE + END + b"\n"
# Save dialogs are NORMAL windows without WM_TRANSIENT_FOR. Same-PID windows
# belong to the unique Fusion main window, including its modal and backdrop.
DIALOG_WORKSPACE_HOOK = WORKSPACE_HOOK.replace(
    b'''return fusion(child) and child ~= main and child.pid == main.pid and child.floating
        and (child.initial_title == "Fusion360"
          or (type(child.initial_title) == "string"
            and child.initial_title:match("^Msg:QTView:.*MessageTray$")))''',
    b'''return fusion(child) and child ~= main and child.pid == main.pid''',
).replace(b"if window ~= main and positive(old_scale)",
          b"if window ~= main and window.floating and positive(old_scale)")
DIALOG_FOCUS_HOOK = GROUP_FOCUS_HOOK.replace(
    b'''and window.initial_title == "Fusion360" and window.workspace == main.workspace''',
    b'''and window.workspace == main.workspace''',
).replace(
    b'''    if not main_window(event) and not (event.floating and event.initial_title == "Fusion360") then return end
''', b"",
).replace(
    b"local function raise(window)", b"local changed = false\n      local function raise(window, force)",
).replace(
    b"if member(window) and window.allowed_over_fullscreen == false then",
    b"if member(window) and (force or window.allowed_over_fullscreen == false) then",
).replace(
    b"return result and result.ok", b"changed = true\n          return result and result.ok",
).replace(
    b'''      for _, window in ipairs(windows) do
        if child_window(window, main) and not raise(window) then return end
      end''',
    b'''      local function utility(window)
        return window.initial_title == "Fusion360" or
          (type(window.initial_title) == "string" and window.initial_title:match("^Msg:QTView:.*MessageTray$"))
      end
      -- Backdrops and palettes first, then actual dialogs. Never put the veil
      -- above Save while repairing eligibility after a fullscreen/workspace move.
      for _, window in ipairs(windows) do
        if child_window(window, main) and utility(window) and not raise(window) then return end
      end
      for _, window in ipairs(windows) do
        if child_window(window, main) and not utility(window) and not raise(window, changed) then return end
      end''',
)
MODAL_BLOCK = DRAG_BLOCK.replace(WORKSPACE_HOOK, DIALOG_WORKSPACE_HOOK).replace(GROUP_FOCUS_HOOK, DIALOG_FOCUS_HOOK)
# Fullscreen changes can reorder already-eligible surfaces. Reestablish the
# stack once for that event; ordinary focus keeps its eligibility-only behavior.
FULLSCREEN_FOCUS_HOOK = DIALOG_FOCUS_HOOK.replace(
    b'local class, busy = "steam_app_fusion360", false',
    b'local class, busy = "steam_app_fusion360", false\n  local pending, generation = nil, 0',
).replace(
    b"local function repair(event)", b"local function repair(event, force_stack)",
).replace(
    b"not raise(window, changed)", b"not raise(window, force_stack or changed)",
).replace(
    b'hl.on("window.fullscreen", repair)', b'''hl.on("window.fullscreen", function(window)
    if busy or not fusion(window) then return end
    generation = generation + 1
    local current = generation
    if pending then pending:set_enabled(false) end
    -- Fullscreen's native layout/stack update runs after its event callbacks.
    -- Repair once after that update, never through an ongoing polling loop.
    pending = hl.timer(function()
      if current ~= generation then return end
      pending = nil
      repair(window, true)
    end, {timeout=600,type="oneshot"})
  end)''',
)
# Preserve the deployed fullscreen-only repair for exact upgrade and rollback.
FULLSCREEN_BLOCK = MODAL_BLOCK.replace(DIALOG_FOCUS_HOOK, FULLSCREEN_FOCUS_HOOK)
LIFECYCLE_FOCUS_HOOK = FULLSCREEN_FOCUS_HOOK.replace(
    b'''  hl.on("window.fullscreen", function(window)
    if busy or not fusion(window) then return end
    generation = generation + 1''',
    b'''  local function schedule(window)
    if busy or not fusion(window) then return end
    local main
    for _, candidate in ipairs(hl.get_windows({class = class, mapped = true})) do
      if main_window(candidate) and candidate.pid == window.pid then
        if main then return end
        main = candidate
      end
    end
    if not main then return end
    generation = generation + 1''',
).replace(
    b"repair(window, true)", b"repair(main, true)",
).replace(
    b"  end)\nend\n",
    b'''  end
  hl.on("window.fullscreen", schedule)
  hl.on("window.open", schedule)
  hl.on("window.move_to_workspace", schedule)
end
''',
)
BLOCK = MODAL_BLOCK.replace(DIALOG_FOCUS_HOOK, LIFECYCLE_FOCUS_HOOK)
BLOCK_VERSIONS = (LEGACY_BLOCK, MONITOR_BLOCK, GROUP_BLOCK, WORKSPACE_BLOCK, DRAG_BLOCK, MODAL_BLOCK, FULLSCREEN_BLOCK, BLOCK)
KNOWN_BLOCKS = {hashlib.sha256(block).hexdigest(): block for block in BLOCK_VERSIONS}


class FocusRuleError(Exception):
    pass


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(path: Path) -> Path:
    result = Path(os.path.abspath(Path(path).expanduser()))
    if "agent-dot-files" in result.parts:
        raise FocusRuleError("The focus helper must not modify agent-dot-files.")
    for component in (result, *result.parents):
        if component.is_symlink():
            raise FocusRuleError("The focus helper refuses paths containing symbolic links.")
    return result


def _read_config(path: Path) -> tuple[bytes, os.stat_result]:
    _path(path)
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise FocusRuleError("The Hyprland configuration must be a user-owned regular file.")
        return path.read_bytes(), info
    except OSError:
        raise FocusRuleError("The existing Omarchy Hyprland configuration could not be read.") from None


def validate_lua(path: Path) -> None:
    """Parse only. Never execute the user's Lua configuration."""
    compiler = shutil.which("luac")
    if not compiler:
        raise FocusRuleError("Lua syntax validation requires luac; no configuration was changed.")
    try:
        result = subprocess.run([compiler, "-p", str(Path(path).absolute())],
                                capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        raise FocusRuleError("Lua syntax validation could not complete.") from None
    if result.returncode:
        raise FocusRuleError("Lua syntax validation failed; no configuration was changed.")


def _write(path: Path, data: bytes, mode: int = 0o600) -> None:
    _path(path)
    fd, temporary = tempfile.mkstemp(prefix=".fusion-focus-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def _record_write(directory: Path, record: dict) -> None:
    _write(directory / "record.json", (json.dumps(record, indent=2) + "\n").encode())


@contextmanager
def _locked_state(state_dir: Path):
    state_dir = _path(state_dir)
    for parent in (state_dir, *state_dir.parents):
        if (parent / ".git").exists():
            raise FocusRuleError("Private configuration backups must stay outside a Git repository.")
    directory = state_dir / "hyprland-focus"
    _path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise FocusRuleError("Focus-rule recovery storage must be user-owned and private (0700).")
    fd = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise FocusRuleError("Another focus-rule operation is running.") from None
        yield directory
    finally:
        os.close(fd)


def _saved_bytes(directory: Path, name: str, prefix: str, digest: str) -> bytes:
    if not isinstance(name, str) or Path(name).name != name or not name.startswith(prefix):
        raise ValueError()
    data = _path(directory / name).read_bytes()
    if _hash(data) != digest:
        raise ValueError()
    return data


def _check_record(directory: Path, config: Path, record: dict) -> None:
    if (record.get("schema") != 1 or record.get("application_id") != APP
            or record.get("config_path") != str(config)
            or record.get("block_sha256") not in KNOWN_BLOCKS
            or record.get("status") not in {"installed", "install-prepared", "removed",
                                             "remove-prepared", "rollback-prepared"}):
        raise ValueError()
    if record["status"] == "rollback-prepared" and "upgrade" not in record:
        raise ValueError()
    _saved_bytes(directory, record["original_backup"], "before-install-", record["original_sha256"])


def _previous_version(directory: Path, config: Path, record: dict) -> tuple[bytes, bytes, bytes]:
    upgrade = record["upgrade"]
    raw = _saved_bytes(directory, upgrade["record_backup"], "before-upgrade-record-", upgrade["record_sha256"])
    old = json.loads(raw)
    _check_record(directory, config, old)
    before = _saved_bytes(directory, upgrade["config_backup"], "before-upgrade-config-", upgrade["config_sha256"])
    current_block, old_block = KNOWN_BLOCKS[record["block_sha256"]], KNOWN_BLOCKS[old["block_sha256"]]
    # Strictly decreasing known versions bound validation and rule out cycles
    # or unknown histories while retaining every deployed revision's bytes.
    if (BLOCK_VERSIONS.index(old_block) >= BLOCK_VERSIONS.index(current_block)
            or old["status"] == "removed" or _find_block(before) != old_block):
        raise ValueError()
    if "upgrade" in old:
        _previous_version(directory, config, old)
    return raw, before, old_block


def _load_record(directory: Path, config: Path) -> dict | None:
    path = _path(directory / "record.json")
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_bytes())
        _check_record(directory, config, record)
        if "upgrade" in record:
            _previous_version(directory, config, record)
        return record
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise FocusRuleError("The private focus-rule ownership or backup record is invalid.") from None


def _find_block(data: bytes) -> bytes | None:
    if BEGIN not in data and END not in data:
        return None
    matches = [block for block in KNOWN_BLOCKS.values() if data.count(block) == 1]
    if data.count(BEGIN) != 1 or data.count(END) != 1 or len(matches) != 1:
        raise FocusRuleError("The Fusion focus block was edited or duplicated; it was preserved.")
    block = matches[0]
    offset = data.index(block)
    if offset and data[offset - 1:offset] != b"\n":
        raise FocusRuleError("The Fusion focus block is not on its own lines; it was preserved.")
    return block


def _backup(directory: Path, kind: str, data: bytes, suffix: str = ".lua") -> str:
    name = ("before-" + kind + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-" + uuid.uuid4().hex[:12] + suffix)
    _write(directory / name, data)
    return name


def _validate_candidate(directory: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".candidate-", suffix=".lua", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        validate_lua(Path(temporary))
    finally:
        os.unlink(temporary)


def _replace_config(config: Path, previous: bytes, updated: bytes, info: os.stat_result) -> None:
    current, current_info = _read_config(config)
    if (current != previous or current_info.st_ino != info.st_ino
            or current_info.st_dev != info.st_dev or current_info.st_mode != info.st_mode):
        raise FocusRuleError("The Hyprland configuration changed during the operation; it was preserved.")
    _write(config, updated, stat.S_IMODE(info.st_mode))


def _without_owned_block(directory: Path, previous: bytes, record: dict, block: bytes) -> bytes:
    if _hash(previous) == record["installed_sha256"]:
        # Exact round trip, including an original file without a final newline.
        return (directory / record["original_backup"]).read_bytes()
    return previous.replace(block, b"", 1)


def _restore_previous_record(directory: Path, config: Path, record: dict) -> dict:
    raw, _, _ = _previous_version(directory, config, record)
    _write(directory / "record.json", raw)
    return json.loads(raw)


def install_focus_rule(config_path: Path, state_dir: Path) -> bool:
    """Install or migrate the exact owned block; return whether config changed."""
    config = _path(config_path)
    with _locked_state(state_dir) as directory:
        previous, info = _read_config(config)
        record = _load_record(directory, config)
        block = _find_block(previous)
        changed = False
        if record and record.get("upgrade"):
            _, before, old_block = _previous_version(directory, config, record)
            if record.get("status") == "rollback-prepared" and block == old_block:
                record = _restore_previous_record(directory, config, record)
            elif record.get("status") == "install-prepared" and block == old_block:
                if previous != before:
                    raise FocusRuleError("The configuration changed during the prepared rule upgrade; it was preserved.")
                # Complete exactly the prepared revision, even if this helper is
                # newer, before considering a further upgrade below.
                target = KNOWN_BLOCKS[record["block_sha256"]]
                updated = previous.replace(old_block, target, 1)
                _validate_candidate(directory, updated)
                _replace_config(config, previous, updated, info)
                record["status"] = "installed"
                _record_write(directory, record)
                previous, info = _read_config(config)
                block, changed = target, True
        if block:
            if record is None or record.get("status") == "removed":
                raise FocusRuleError("An unowned Fusion focus block already exists; it was preserved.")
            if _hash(block) != record["block_sha256"]:
                raise FocusRuleError("The Fusion block does not match its ownership record; it was preserved.")
            if block == BLOCK:
                validate_lua(config)
                if record.get("status") != "installed":
                    record["status"] = "installed"
                    _record_write(directory, record)
                return changed
            original = _without_owned_block(directory, previous, record, block)
            updated = previous.replace(block, BLOCK, 1)
        else:
            if record and record.get("upgrade") and record.get("status") in {"install-prepared", "rollback-prepared"}:
                raise FocusRuleError("The prepared rule transition no longer matches the configuration; it was preserved.")
            original = previous
            updated = previous + (b"\n" if previous and not previous.endswith(b"\n") else b"") + BLOCK
        _validate_candidate(directory, updated)
        upgrade = None
        if block:
            raw = (directory / "record.json").read_bytes()
            if json.loads(raw) != record:
                raise FocusRuleError("The ownership record changed during the rule upgrade; it was preserved.")
            upgrade = {
                "record_backup": _backup(directory, "upgrade-record", raw, ".json"), "record_sha256": _hash(raw),
                "config_backup": _backup(directory, "upgrade-config", previous), "config_sha256": _hash(previous),
            }
        record = {
            "schema": 1, "application_id": APP, "config_path": str(config),
            "block_sha256": _hash(BLOCK), "original_sha256": _hash(original),
            "installed_sha256": _hash(updated), "original_mode": stat.S_IMODE(info.st_mode),
            "original_backup": _backup(directory, "install", original),
            "status": "install-prepared",
        }
        if upgrade:
            record["upgrade"] = upgrade
        # The backup and ownership record reach disk before the user config changes.
        _record_write(directory, record)
        _replace_config(config, previous, updated, info)
        record["status"] = "installed"
        _record_write(directory, record)
        return True


def remove_focus_rule(config_path: Path, state_dir: Path) -> bool:
    """Remove only the unchanged owned block, preserving any surrounding edits."""
    config = _path(config_path)
    state_dir = _path(state_dir)
    if not (state_dir / "hyprland-focus" / "record.json").exists():
        return False
    with _locked_state(state_dir) as directory:
        record = _load_record(directory, config)
        if record is None:
            return False
        previous, info = _read_config(config)
        block = _find_block(previous)
        if record.get("upgrade") and record.get("status") in {"install-prepared", "rollback-prepared"}:
            _, _, old_block = _previous_version(directory, config, record)
            if block == old_block:
                record = _restore_previous_record(directory, config, record)
        if not block:
            record["status"] = "removed"
            _record_write(directory, record)
            return False
        if record.get("status") == "removed":
            raise FocusRuleError("A focus block appeared after removal; it was preserved.")
        if _hash(block) != record["block_sha256"]:
            raise FocusRuleError("The Fusion block does not match its ownership record; it was preserved.")
        updated = _without_owned_block(directory, previous, record, block)
        _validate_candidate(directory, updated)
        record["before_removal_backup"] = _backup(directory, "remove", previous)
        record["before_removal_sha256"] = _hash(previous)
        record["before_removal_mode"] = stat.S_IMODE(info.st_mode)
        record["status"] = "remove-prepared"
        _record_write(directory, record)
        _replace_config(config, previous, updated, info)
        record["status"] = "removed"
        _record_write(directory, record)
        return True


def rollback_focus_rule(config_path: Path, state_dir: Path) -> bool:
    """Restore the frozen previous block/record, keeping surrounding user edits."""
    config, state_dir = _path(config_path), _path(state_dir)
    if not (state_dir / "hyprland-focus" / "record.json").exists():
        return False
    with _locked_state(state_dir) as directory:
        record = _load_record(directory, config)
        if not record or not record.get("upgrade") or record.get("status") == "removed":
            return False
        previous, info = _read_config(config)
        block = _find_block(previous)
        raw, before, old_block = _previous_version(directory, config, record)
        target = KNOWN_BLOCKS[record["block_sha256"]]
        if block == old_block and record.get("status") in {"install-prepared", "rollback-prepared"}:
            _write(directory / "record.json", raw)
            return False
        if block != target:
            raise FocusRuleError("The upgraded Fusion block was changed or removed; it was preserved.")
        updated = before if _hash(previous) == record["installed_sha256"] else previous.replace(target, old_block, 1)
        _validate_candidate(directory, updated)
        if record.get("status") != "rollback-prepared":
            _backup(directory, "rollback-record", (directory / "record.json").read_bytes(), ".json")
            record["before_rollback_backup"] = _backup(directory, "rollback", previous)
            record["status"] = "rollback-prepared"
            _record_write(directory, record)
        _replace_config(config, previous, updated, info)
        _write(directory / "record.json", raw)
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "remove", "rollback", "validate"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "validate":
            validate_lua(args.config)
            print("Lua syntax is valid; the configuration was not executed.")
        else:
            if args.state is None:
                parser.error("install, remove and rollback require --state")
            action = {"install": install_focus_rule, "remove": remove_focus_rule, "rollback": rollback_focus_rule}[args.action]
            changed = action(args.config, args.state)
            print("Focus rule " + ("updated." if changed else "unchanged."))
            print("No compositor reload was requested by this helper.")
    except FocusRuleError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
