#!/usr/bin/env python3
"""Back up, recover, update or remove this installation's desktop integration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
import install


def snapshot_name(kind):
    return kind + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def copy_prefix(source, destination):
    destination.mkdir(mode=0o700)
    # GNU cp keeps Wine's directory symlinks as links and reflinks on Btrfs.
    subprocess.run(["cp", "-a", "--reflink=auto", "--", str(source) + "/.", str(destination)], check=True)


def metadata(loc, lock):
    return {"schema": 1, "application_id": install.APP, "source_state": str(loc.state),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runner_sha256": lock["runner"]["sha256"], "steam_runtime": lock["steam_runtime"]["version"],
            "runner_overlay": lock.get("runner_overlay")}


def backup(loc, lock, module, directory=None):
    install.require_closed(loc, module)
    if not loc.prefix.is_dir():
        raise install.InstallError("There is no dedicated prefix to back up.")
    root = Path(directory).expanduser().absolute() if directory else loc.state / "backups"
    if root.resolve().is_relative_to(loc.prefix.resolve()):
        raise install.InstallError("A backup must be outside the prefix being copied.")
    for parent in (install.SOURCE, *install.SOURCE.parents):
        if (parent / ".git").exists() and root.resolve().is_relative_to(parent):
            raise install.InstallError("A credential-bearing backup must remain outside the repository.")
    install.private_directory(root)
    destination = root / snapshot_name("snapshot")
    destination.mkdir(mode=0o700)
    try:
        copy_prefix(loc.prefix, destination / "prefix")
        install.write_json(destination / "snapshot.json", metadata(loc, lock))
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def restore(loc, snapshot, lock, module):
    install.require_closed(loc, module)
    snapshot = Path(snapshot).expanduser().absolute()
    install.reject_symlink(snapshot)
    install.reject_symlink(snapshot / "prefix")
    record = json.loads((snapshot / "snapshot.json").read_text())
    if (record.get("schema") != 1 or record.get("application_id") != install.APP
            or record.get("runner_sha256") != lock["runner"]["sha256"]
            or record.get("steam_runtime") != lock["steam_runtime"]["version"]
            or not (snapshot / "prefix").is_dir()):
        raise install.InstallError("The snapshot does not match this installation's pinned runtime.")
    if snapshot.resolve().is_relative_to(loc.prefix.resolve()):
        raise install.InstallError("A recovery snapshot cannot be inside the active prefix.")
    staged_root = Path(tempfile.mkdtemp(prefix=".restore-", dir=loc.state))
    preserved = None
    try:
        copy_prefix(snapshot / "prefix", staged_root / "prefix")
        if loc.prefix.exists():
            root = loc.state / "backups"
            install.private_directory(root)
            preserved = root / snapshot_name("before-restore")
            preserved.mkdir(mode=0o700)
            install.write_json(preserved / "snapshot.json", metadata(loc, lock))
            os.rename(loc.prefix, preserved / "prefix")
        try:
            os.rename(staged_root / "prefix", loc.prefix)
        except BaseException:
            if preserved:
                os.rename(preserved / "prefix", loc.prefix)
            raise
    finally:
        shutil.rmtree(staged_root)
    return preserved


def remove_mime_references(path, associations):
    """xdg-mime has no unset command: remove only our exact IDs, retaining all other text."""
    if not path.exists():
        return
    install.reject_symlink(path)
    old = path.read_text()
    section = ""
    output = []
    for line in old.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        key, separator, value = line.partition("=")
        if (section in {"Default Applications", "Added Associations", "Removed Associations"}
                and separator and key.strip() in associations):
            owned = associations[key.strip()]["desktop"]
            values = [v for v in value.strip().split(";") if v and v != owned]
            if owned in value.strip().split(";"):
                if values:
                    output.append(key + "=" + ";".join(values) + ";\n")
                continue
        output.append(line)
    updated = "".join(output)
    if updated != old:
        install.atomic_write(path, updated.encode(), path.stat().st_mode & 0o777)


def uninstall(loc, manifest):
    # The whitelist prevents a stale/tampered manifest from deleting arbitrary files.
    allowed = {loc.state / path for path in (*install.SUPPORT_FILES, *install.OPTIONAL_SUPPORT)}
    allowed.update(loc.data_home / "applications" / desktop for desktop in install.SCHEMES.values())
    allowed.update(loc.bin_home / name for name in (*install.COMMANDS, install.APP + "-maintenance"))
    for path in manifest["files"]:
        candidate = Path(path)
        runtime_source = candidate.is_relative_to(loc.state) and install.is_runtime_source(str(candidate.relative_to(loc.state)))
        if candidate not in allowed and not runtime_source:
            raise install.InstallError("The manifest contains an unexpected integration path.")
    for scheme, association in manifest["associations"].items():
        if install.SCHEMES.get(scheme) != association.get("desktop"):
            raise install.InstallError("The manifest contains an unexpected protocol association.")
        current = install.run(["xdg-mime", "query", "default", scheme], loc,
                              capture_output=True, text=True).stdout.strip()
        if current == association["desktop"] and association["previous"]:
            install.run(["xdg-mime", "default", association["previous"], scheme], loc)
    candidates = {loc.config_home / "mimeapps.list", loc.data_home / "applications/mimeapps.list"}
    for desktop in os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":"):
        if re.fullmatch(r"[a-z0-9_-]+", desktop):
            candidates.update({loc.config_home / (desktop + "-mimeapps.list"),
                               loc.data_home / "applications" / (desktop + "-mimeapps.list")})
    for candidate in candidates:
        remove_mime_references(candidate, manifest["associations"])
    focus = install.focus_rules()
    if focus is not None:
        try:
            focus.remove_focus_rule(loc.config_home / "hypr/hyprland.lua", loc.state)
        except focus.FocusRuleError as error:
            raise install.InstallError(str(error)) from None
    changed = []
    for name, record in list(manifest["files"].items()):
        path = Path(name)
        actual = install.file_record(path)
        if actual is None and not path.exists():
            del manifest["files"][name]
        elif actual == record:
            path.unlink()
            del manifest["files"][name]
        else:
            changed.append(name)
    if changed:
        install.write_json(loc.manifest, manifest)
        raise install.InstallError("Modified integration files were preserved; private manifest retained: " + ", ".join(changed))
    loc.manifest.unlink(missing_ok=True)
    for path in (loc.state / "bin", loc.state / "lib"):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if shutil.which("update-desktop-database"):
        install.run(["update-desktop-database", str(loc.data_home / "applications")], loc,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def rollback_overlay(loc, module):
    install.require_closed(loc, module)
    receipt_path = loc.state / "runner-overlay.json"
    install.reject_symlink(receipt_path)
    if not receipt_path.is_file():
        raise install.InstallError("No runtime-overlay recovery record exists; no runner was changed.")
    receipt = json.loads(receipt_path.read_text())
    recovery = install.validate_overlay_recovery(loc, receipt)
    overlay = receipt["overlay"]
    lock = {"runner": {"name": receipt["runner"], "sha256": receipt["base_runner_sha256"]},
            "runner_overlay": overlay}
    modules = install.current_overlay_modules(loc, lock)
    originals = {}
    for item, _, _ in modules:
        original = recovery / Path(item["target"]).name
        data = original.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["original_sha256"]:
            raise install.InstallError("A recovery module changed during verification; no module was restored.")
        originals[item["target"]] = (data, original.stat().st_mode & 0o777)
    previous_bytes = (recovery / "compatibility-lock.json").read_bytes()
    if hashlib.sha256(previous_bytes).hexdigest() != receipt["previous_lock_sha256"]:
        raise install.InstallError("The recovery lock changed during verification; no module was restored.")
    active_lock = loc.state / "compatibility-lock.json"
    install.reject_symlink(active_lock)
    current = {}
    if active_lock.is_file():
        current = json.loads(active_lock.read_text())
        if (current.get("runner", {}).get("name") != receipt["runner"]
                or current.get("runner", {}).get("sha256") != receipt["base_runner_sha256"]
                or current.get("runner_overlay") not in (None, overlay)):
            raise install.InstallError("The current compatibility lock conflicts with this rollback.")
    if current.get("runner_overlay") is None and any(actual != item["original_sha256"] for item, _, actual in modules):
        raise install.InstallError("Patched modules lack their matching required-overlay lock; no rollback was started.")
    # Verify the whole pair first. Keep the required-overlay lock until every
    # original is restored, so interruption between replacements fails closed.
    for item, target, actual in modules:
        if actual != item["original_sha256"]:
            data, mode = originals[item["target"]]
            install.atomic_write(target, data, mode)
    if any(install.digest(target) != item["original_sha256"] for item, target, _ in modules):
        raise install.InstallError("Restored modules failed verification; the required-overlay lock was retained.")
    install.atomic_write(active_lock, previous_bytes)
    receipt["phase"] = "rolled_back"
    install.write_json(receipt_path, receipt)
    if loc.manifest.exists():
        manifest = install.load_manifest(loc)
        if str(active_lock) in manifest["files"]:
            manifest["files"][str(active_lock)] = install.file_record(active_lock)
            install.write_json(loc.manifest, manifest)
    return recovery


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    install.add_locations(parser)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("backup", help="Copy a closed prefix to a private snapshot")
    save.add_argument("--backup-dir", metavar="PATH")
    recover = commands.add_parser("restore", help="Restore a snapshot and preserve the current prefix")
    recover.add_argument("snapshot")
    commands.add_parser("update", help="Back up, then rerun the verified official downloader")
    commands.add_parser("rollback-overlay", help="Restore original runtime modules and the prior lock without changing the prefix")
    commands.add_parser("uninstall", help="Remove owned integration, preserving prefix, runner, cache and backups")
    args = parser.parse_args(argv)
    loc = install.Locations.from_args(args)
    try:
        with install.maintenance_lock(loc):
            manifest = install.load_manifest(loc)
            if args.command == "uninstall":
                if not loc.manifest.exists():
                    raise install.InstallError("No owned integration manifest exists; nothing was removed.")
                uninstall(loc, manifest)
                print("Owned desktop integration removed. Prefix, designs, runner, cache and backups were retained.")
                return 0
            module = install.core()
            if args.command == "rollback-overlay":
                saved = rollback_overlay(loc, module)
                print("Original runtime modules and lock restored. Prefix retained. Recovery files: " + str(saved))
                print("The original graphics limitations apply again; this does not mark Fusion accepted.")
                return 0
            lock = install.read_lock(loc.state if (loc.state / "compatibility-lock.json").is_file() else install.SOURCE)
            if args.command == "backup":
                print(backup(loc, lock, module, args.backup_dir))
            elif args.command == "restore":
                preserved = restore(loc, args.snapshot, lock, module)
                print("Prefix restored. Previous prefix preserved at: " + str(preserved or "none (no previous prefix)"))
            else:
                install.ensure_packages(loc, install=False)
                install.verify_runtime_build(loc, lock)
                saved = backup(loc, lock, module)
                print("Recovery snapshot: " + str(saved), flush=True)
                installer = install.fetch_verified(lock["autodesk_installer"], loc.cache / "Fusion Client Downloader.exe")
                try:
                    result = module.install_exe(install.runtime_paths(loc, module), str(installer))
                except module.LauncherError as error:
                    raise install.InstallError(str(error)) from None
                if result:
                    raise install.InstallError("Update did not complete; use restore with the printed snapshot.")
                install.finish_prefix(loc, module, lock)
                report = module.status(install.runtime_paths(loc, module))
                install.write_json(loc.state / "last-update.json", {
                    "fusion_version": report["fusion_version"], "recovery_snapshot": str(saved),
                    "acceptance": "not yet reviewed"})
                print("Downloader completed. Launch Fusion and verify modeling plus save/reopen before accepting the update.")
            return 0
    except (install.InstallError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("Maintenance stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
