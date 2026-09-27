# Native shader compiler preparation

The initial Wine-built-in `d3dcompiler_47` route produced a gray canvas with an
invisible committed solid. Selecting Fusion's own compiler produced a white
canvas; complete independent workflow review is still required.

The lock records the compiler already shipped in the **registered current Fusion
build**, at `d3dcompiler_v2/d3dcompiler_47.dll` beside `Fusion360.exe`:

- Microsoft file version: `10.0.14393.33`
- Size: `4483648` bytes
- SHA-256: `c349f3510ccce2df194dfd88829a9a790c8028eddedbecd54485ea92c1c771f7`

No DLL is downloaded, copied from another product, or redistributed by this
repository. The explicit preparation also copies these same bytes to **only the
Test 2 prefix's** `drive_c/windows/system32/d3dcompiler_47.dll`: Qt D3D11 can request
the system compiler while Fusion's OGS renderer uses the application copy.
Launch checks both files against the same size/hash. An Autodesk update that
changes this file requires review and a new lock.

Close every process using the dedicated Test 2 prefix and preserve its registry
before preparing the override. This explicit command is a preparation action;
ordinary launch never performs it. Run it from this repository:

```bash
python3 -B - <<'PY'
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, 'lib')
import fusion_wine as fusion

paths = fusion.Paths(Path.home() / '.local/share/fusion360-for-omarchy-wine')
lock = fusion.compatibility_lock(paths)
configuration = fusion.session_configuration(paths, lock)
if fusion.session_processes(paths, configuration):
    raise SystemExit('Close all Test 2 Wine processes before preparation.')
fusion.validate_runtime(paths, lock, configuration)
control = fusion.native_compiler_spec(lock)
application = fusion.resolve_targets(paths)['fusion']
source = application.parent / control['relative_path']
if source.is_symlink() or not source.resolve().is_relative_to(application.parent):
    raise SystemExit('Compiler source must belong to the registered Autodesk build.')
data = source.read_bytes()
if len(data) != control['size'] or hashlib.sha256(data).hexdigest() != control['sha256']:
    raise SystemExit('The shipped Autodesk compiler differs from the reviewed lock.')
destination = paths.prefix / control['system32_copy']['relative_path']
if not destination.parent.resolve().is_relative_to(paths.prefix):
    raise SystemExit('The system32 directory points outside the dedicated prefix.')
backups = paths.state / 'backups'
backups.mkdir(mode=0o700, exist_ok=True)
backup = Path(tempfile.mkdtemp(prefix='native-compiler-', dir=backups))
shutil.copy2(paths.prefix / 'user.reg', backup / 'user.reg')
if destination.exists() or destination.is_symlink():
    shutil.copy2(destination, backup / 'system32-d3dcompiler_47.dll', follow_symlinks=False)
else:
    (backup / 'system32-was-absent').touch(mode=0o600)
descriptor, temporary = tempfile.mkstemp(prefix='.fusion-compiler-', dir=destination.parent)
try:
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)  # Replace an old link; never follow it.
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
subprocess.run([
    str(paths.wine), 'reg.exe', 'add',
    control['registry_hive'] + '\\' + control['registry_key'],
    '/v', control['registry_value'], '/t', 'REG_SZ',
    '/d', control['override'], '/f',
], env=fusion.wine_environment(paths, configuration), check=True)
print('Private preparation backup:', backup)
PY
```

The only required entry is
`HKCU\Software\Wine\AppDefaults\Fusion360.exe\DllOverrides`, string value
`d3dcompiler_47 = native,builtin`. Global entries, HKLM entries, other application
entries, and malformed values do not satisfy the launch check. Fusion must start
fresh after preparation; changing the registry cannot replace an already loaded
compiler in a running Fusion process.

Let the preparation's Wine processes exit so `user.reg` is flushed before the
checked cold launch. Preparation backups contain private registry data and must
remain outside Git. To recover, close Test 2 Wine, restore the preserved system32
entry (including its original symlink, if present) through a temporary file and
atomic replacement, or remove the prepared copy if `system32-was-absent` exists.
Restore only the earlier Fusion-specific registry value when reversing that
change; keep the full registry backup for reference without overwriting newer
account settings. Restore the corresponding old code/lock as well: the new
preflight correctly refuses a reverted Wine-built-in compiler.

`status --json` reports `native_compiler_prepared` for the registry/file checks.
This does not certify which module an existing process loaded or prove rendering
acceptance. Authentication retains its separate running-session checks.

# Runtime and session migration

The final-round `runtime_environment` selects exactly the pair
`WINE_X11_ARGB_SHAPE_INPUT=1` and `WINE_X11_ARGB_CONSTANT_ALPHA=1` with the reviewed
Wine 11.17 alpha module. Source support also accepts `{}` for an explicitly
reviewed unpatched configuration. Both selected flags must match the installed
runtime file hashes and session record.
No other Wine experiment flags pass through. Explicit Qt backend choices remain
separate and are merged with this locked pair.

Session identity now includes all pinned runtime file hashes and the compiler
control. Before deploying this change or any later alpha module, stop the whole
Test 2 Wine session; privately back up the old lock, any module being replaced,
and `session.json`. Deploy matching wrappers, both library files, and lock
together. After preserving it, remove the **closed** old `session.json`, then
cold launch. The launcher refuses stale records or mixed active configurations;
it does not migrate or rewrite a live session automatically.
