#!/usr/bin/env python3
"""Register the local Fusion MCP endpoint without contacting Fusion or changing credentials."""

import argparse
import fcntl
import os
from pathlib import Path
import stat
import tempfile
import tomllib


FRAGMENT = Path(__file__).resolve().parent / "config/codex-mcp.toml"


def check_path(path):
    for part in (path, *path.parents):
        if part.is_symlink() or part.name == "agent-dot-files":
            raise ValueError("Refusing a symlink or agent-dot-files configuration path.")


def configure(config, backup_directory, install=False):
    check_path(config)
    fragment = FRAGMENT.read_bytes()
    expected = tomllib.loads(fragment.decode())["mcp_servers"]["fusion360"]
    with os.fdopen(os.open(config, os.O_RDONLY | os.O_NOFOLLOW), "rb") as current:
        fcntl.flock(current, fcntl.LOCK_EX)
        identity = os.fstat(current.fileno())
        if (not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1
                or identity.st_uid != os.getuid() or stat.S_IMODE(identity.st_mode) & 0o077):
            raise ValueError("Codex config must be a private, user-owned regular file with one link.")
        original = current.read()
        parsed = tomllib.loads(original.decode())
        servers = parsed.get("mcp_servers", {})
        if "fusion360" in servers:
            if servers["fusion360"] != expected:
                raise ValueError("An existing fusion360 entry differs; it was left unchanged.")
            return True, None
        if any(isinstance(server, dict) and server.get("url") == expected["url"] for server in servers.values()):
            raise ValueError("This Fusion endpoint is already registered under another name.")
        if not install:
            return False, None
        updated = original + (b"\n" if original.endswith(b"\n") else b"\n\n") + fragment
        candidate = tomllib.loads(updated.decode())
        candidate["mcp_servers"].pop("fusion360")
        if not candidate["mcp_servers"] and "mcp_servers" not in parsed:
            candidate.pop("mcp_servers")
        if candidate != parsed:
            raise ValueError("The registration would change another setting; config was left unchanged.")
        check_path(backup_directory)
        if backup_directory.is_relative_to(FRAGMENT.parent.parent):
            raise ValueError("The private config backup must be outside this repository.")
        backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = backup_directory.stat()
        if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) & 0o077:
            raise ValueError("The backup directory must be private and owned by the current user.")
        descriptor, backup = tempfile.mkstemp(prefix="codex-config-before-fusion-mcp-", suffix=".toml",
                                              dir=backup_directory)
        with os.fdopen(descriptor, "wb") as saved:
            saved.write(original)
            saved.flush()
            os.fsync(saved.fileno())
        descriptor, temporary = tempfile.mkstemp(prefix=".fusion-mcp-", dir=config.parent)
        try:
            with os.fdopen(descriptor, "wb") as replacement:
                replacement.write(updated)
                replacement.flush()
                os.fchmod(replacement.fileno(), stat.S_IMODE(identity.st_mode))
                os.fsync(replacement.fileno())
            check_path(config)
            latest = config.stat()
            if ((latest.st_dev, latest.st_ino, latest.st_nlink) !=
                    (identity.st_dev, identity.st_ino, 1) or config.read_bytes() != original):
                raise ValueError("Codex config changed during registration; it was left unchanged.")
            os.replace(temporary, config)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True, Path(backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true", help="Append only the Fusion MCP entry, preserving other settings")
    action.add_argument("--check", action="store_true", help="Check the saved entry without contacting Fusion")
    args = parser.parse_args()
    config_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().absolute()
    backup_directory = (Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) /
                        "fusion360-for-omarchy/codex-config-backups").expanduser().absolute()
    try:
        configured, backup = configure(config_home / "config.toml", backup_directory, args.install)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Fusion MCP configuration failed: {error}\n")
    print("Fusion MCP is registered for future local Codex sessions." if configured else "Fusion MCP is not registered.")
    if backup:
        print(f"Previous config saved privately at {backup}")
    return 0 if configured else 1


if __name__ == "__main__":
    raise SystemExit(main())
