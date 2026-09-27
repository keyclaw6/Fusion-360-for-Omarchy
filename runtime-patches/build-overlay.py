#!/usr/bin/env python3
"""Build pinned Wine modules in private storage; never modify a runner or prefix."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Checksum mismatch: {Path(path).name}')


def run(argv, *, cwd=None, env=None, log=None):
    subprocess.run([str(value) for value in argv], cwd=cwd, env=env,
                   stdout=log, stderr=subprocess.STDOUT if log else None, check=True)


def modules_from_manifest(manifest):
    if manifest['schema'] == 1:
        return [{key: manifest[key] for key in ('target', 'original_sha256', 'sha256')}]
    if manifest['schema'] != 2:
        raise ValueError('Unsupported overlay manifest schema')
    modules = manifest['modules']
    expected = ['files/lib/wine/x86_64-unix/winex11.so',
                'files/lib/wine/x86_64-unix/win32u.so']
    if [module['target'] for module in modules] != expected:
        raise ValueError('The two-module recipe requires the reviewed target pair in order')
    for module in modules:
        if set(module) != {'target', 'original_sha256', 'sha256'}:
            raise ValueError('Unsupported module manifest fields')
    return modules


def check_abi(sdk_command, name):
    """Compare exported ABI and loader dependencies to the official module."""
    def output(argv):
        return subprocess.check_output([str(value) for value in [*sdk_command, *argv]], text=True)

    def symbols(path):
        result = {}
        for line in output(['/usr/bin/nm', '-D', '--defined-only', '--format=posix', path]).splitlines():
            fields = line.split()
            # Function sizes can change; exported data layout must not.
            result[fields[0]] = (fields[1], None if fields[1] in 'TtWwiI' else fields[3:])
        return result

    def needed(path):
        return sorted(re.findall(r'\(NEEDED\).*\[([^]]+)\]',
                                 output(['/usr/bin/readelf', '-d', path])))

    original, candidate = '/work/originals/' + name, '/work/candidate/' + name
    if symbols(original) != symbols(candidate) or needed(original) != needed(candidate):
        raise ValueError('Exported ABI or required libraries changed: ' + name)


def fetch_sdk(spec, cache):
    """Verify every immutable OCI blob before extracting to a fresh private root."""
    cache.mkdir(parents=True, exist_ok=True)
    blobs = cache / 'sdk-blobs'
    blobs.mkdir(exist_ok=True)
    root = cache / 'sdk-root'
    root.mkdir(exist_ok=True)
    base = spec['registry'] + '/v2/' + spec['repository']
    manifest_url = base + '/manifests/sha256:' + spec['manifest_sha256']
    headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
    try:
        response = urlopen(Request(manifest_url, headers=headers), timeout=60)
    except HTTPError as error:
        if error.code != 401:
            raise
        auth = dict(re.findall(r'(\w+)="([^"]*)"', error.headers['WWW-Authenticate']))
        realm = auth.pop('realm')
        if not realm.startswith('https://'):
            raise ValueError('SDK registry returned an insecure token endpoint')
        auth['scope'] = 'repository:' + spec['repository'] + ':pull'
        with urlopen(realm + '?' + urlencode(auth), timeout=60) as stream:
            token = json.load(stream)['token']
        headers['Authorization'] = 'Bearer ' + token
        response = urlopen(Request(manifest_url, headers=headers), timeout=60)
    with response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != spec['manifest_sha256']:
        raise ValueError('SDK manifest checksum mismatch')
    manifest = json.loads(content)
    (cache / 'sdk-manifest.json').write_bytes(content)

    def download(entry):
        value = entry['digest'].removeprefix('sha256:')
        if not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Unsupported SDK blob digest')
        target = blobs / value
        if target.is_file() and target.stat().st_size == entry['size'] and digest(target) == value:
            return
        temporary = blobs / (value + '.partial')
        request = Request(base + '/blobs/' + entry['digest'], headers=headers)
        with urlopen(request, timeout=120) as source, temporary.open('wb') as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        checked(temporary, value)
        if temporary.stat().st_size != entry['size']:
            raise ValueError('SDK blob size mismatch')
        temporary.replace(target)

    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(download, [manifest['config'], *manifest['layers']]))

    def remove(path):
        if not path.parent.resolve().is_relative_to(root.resolve()):
            raise ValueError('SDK whiteout escapes its private root')
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    for layer in manifest['layers']:
        value = layer['digest'].removeprefix('sha256:')
        with tarfile.open(blobs / value, 'r:gz') as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts:
                    raise ValueError('SDK archive contains an unsafe path')
                parent = root / str(name.parent)
                if name.name == '.wh..wh..opq':
                    if parent.is_dir():
                        for child in parent.iterdir():
                            remove(child)
                    continue
                if name.name.startswith('.wh.'):
                    remove(parent / name.name[4:])
                    continue
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    continue
                if member.issym() and member.linkname.startswith('/'):
                    member.linkname = os.path.relpath(member.linkname.lstrip('/'), str(name.parent))
                elif member.islnk():
                    member.linkname = member.linkname.lstrip('/')
                target = root / str(name)
                if member.isfile() and target.is_symlink():
                    remove(target)
                archive.extract(member, root, filter='data')
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner-archive', required=True, type=Path)
    outputs = parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument('--output', type=Path, help='Single output file for a schema 1 recipe')
    outputs.add_argument('--output-dir', type=Path, help='New output directory for the schema 2 module pair')
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--sdk-root', type=Path, help='Reuse an already verified official SDK root')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        parser.error('Python 3.12 or newer is required')
    manifest = json.loads((HERE / 'manifest.json').read_text())
    modules = modules_from_manifest(manifest)
    if (manifest['schema'] == 2) != bool(args.output_dir):
        parser.error('Schema 2 requires --output-dir; schema 1 requires --output')
    for command in ('git', 'bash', 'bwrap', 'patch', 'autoreconf'):
        if not shutil.which(command):
            parser.error('Missing build dependency: ' + command)
    for patch in manifest['patches']:
        checked(HERE / patch['file'], patch['sha256'])
    archive = args.runner_archive.expanduser().resolve()
    checked(archive, manifest['runner']['archive_sha256'])
    output = (args.output_dir or args.output).expanduser().absolute()
    if output.is_symlink():
        raise ValueError('Output must not be a symbolic link')
    if output.exists():
        if manifest['schema'] == 2:
            names = {PurePosixPath(module['target']).name for module in modules}
            if not output.is_dir() or {path.name for path in output.iterdir()} != names:
                raise ValueError('Existing output must contain exactly the reviewed module pair')
            for module in modules:
                target = output / PurePosixPath(module['target']).name
                if target.is_symlink() or not target.is_file():
                    raise ValueError('Existing output module must be a regular file')
                checked(target, module['sha256'])
        else:
            checked(output, modules[0]['sha256'])
        print('The reviewed output already exists at ' + str(output))
        return 0
    work = args.work_dir.expanduser().absolute()
    if work.is_symlink() or (work.exists() and any(work.iterdir())):
        parser.error('--work-dir must be a new or empty directory')
    work.mkdir(parents=True, exist_ok=True)
    work = work.resolve()
    print('Preparing pinned source and SDK in ' + str(work), flush=True)
    sdk = args.sdk_root.expanduser().resolve() if args.sdk_root else fetch_sdk(manifest['sdk'], work)
    checked(sdk.parent / 'sdk-manifest.json', manifest['sdk']['manifest_sha256'])
    for name in ('dev', 'proc', 'tmp', 'work', 'source'):
        (sdk / name).mkdir(exist_ok=True)
    source = work / 'source'
    source.mkdir()
    obj = work / 'obj64'
    obj.mkdir()
    originals = work / 'originals'
    originals.mkdir()
    (work / 'home').mkdir()
    with (work / 'build.log').open('w') as log:
        run(['git', 'init', source], log=log)
        run(['git', 'remote', 'add', 'origin', manifest['runner']['source_repository']], cwd=source, log=log)
        run(['git', 'fetch', '--depth=1', '--filter=blob:none', 'origin', manifest['runner']['source_commit']], cwd=source, log=log)
        run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source, log=log)
        run(['git', 'submodule', 'update', '--init', '--depth=1', 'wine', 'wine-staging'], cwd=source, log=log)
        for relative, expected in (('.', manifest['runner']['source_commit']),
                                   ('wine', manifest['wine']['source_commit']),
                                   ('wine-staging', manifest['wine']['staging_commit'])):
            actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source / relative, text=True).strip()
            if actual != expected:
                raise ValueError('Source commit mismatch: ' + relative)
        run(['git', 'fetch', '--depth=2', 'origin', manifest['wine']['restore_configure_commit']], cwd=source / 'wine', log=log)
        preparation = source / manifest['runner']['preparation_script']
        checked(preparation, manifest['runner']['preparation_script_sha256'])
        original = preparation.read_text()
        helpers = original.split('### (1) PREP SECTION ###', 1)[0]
        wine_section = original.split('### (2) WINE PATCHING ###', 1)[1]
        script = 'set -e\n' + helpers + '\npushd wineopenxr\nfor p in ../patches/wineopenxr/*.patch; do apply_patch "$p"; done\npopd\n### (2) WINE PATCHING ###' + wine_section
        (work / 'prepare-ge-wine.sh').write_text(script)
        print('Applying the exact GE Wine preparation and local patches', flush=True)
        run(['bash', work / 'prepare-ge-wine.sh'], cwd=source, log=log)
        environment = dict(os.environ, XDG_CACHE_HOME=str(work / 'generated-cache'))
        run([source / 'wine/dlls/winevulkan/make_vulkan', '-x', 'vk.xml', '-X', 'video.xml'], cwd=source / 'wine', env=environment, log=log)
        run([source / 'wine/tools/make_specfiles'], cwd=source / 'wine', log=log)
        for patch in manifest['patches']:
            with (HERE / patch['file']).open('rb') as stream:
                subprocess.run(['patch', '-p1', '-F0'], cwd=source / 'wine', stdin=stream,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
        for relative, expected in manifest.get('source_files', {}).items():
            checked(source / 'wine' / relative, expected['sha256'])
        inputs = {**manifest['link_inputs'], **{
            PurePosixPath(module['target']).name: module['original_sha256'] for module in modules}}
        module_names = {PurePosixPath(module['target']).name for module in modules}
        remaining = set(inputs)
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                name = PurePosixPath(member.name)
                expected_prefix = manifest['runner']['name'] + '/files/lib/wine/x86_64-unix/'
                if not member.name.startswith(expected_prefix) or name.name not in remaining:
                    continue
                if member.name != expected_prefix + name.name or not member.isfile():
                    raise ValueError('Runner link input is not a regular file')
                target = (originals / name.name if name.name in module_names else
                          obj / 'dlls' / name.stem / name.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as stream, target.open('wb') as dest:
                    shutil.copyfileobj(stream, dest)
                checked(target, inputs[name.name])
                remaining.remove(name.name)
                if not remaining:
                    break
        if remaining:
            raise ValueError('Runner archive is missing required link inputs')
        sdk_command = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', sdk, '/',
                       '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp', '--bind', work, '/work',
                       '--ro-bind', source, '/source', '--chdir', '/work', '--clearenv',
                       '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/work/home',
                       '--setenv', 'LC_ALL', 'C', '--setenv', 'CCACHE_DISABLE', '1']
        print('Compiling the isolated Wine modules in the pinned Steam SDK', flush=True)
        shutil.copy2(HERE / 'compile.sh', work / 'compile.sh')
        run([*sdk_command, '/bin/bash', '/work/compile.sh'], log=log)
        for module in modules:
            name = PurePosixPath(module['target']).name
            checked(work / 'candidate' / name, module['sha256'])
            check_abi(sdk_command, name)
            relocations = subprocess.run([str(value) for value in [*sdk_command, '/usr/bin/env',
                 'LD_LIBRARY_PATH=/work/candidate:/work/obj64/dlls/ntdll', '/usr/bin/ldd', '-r',
                 '/work/candidate/' + name]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 text=True, check=True)
            log.write(relocations.stdout)
            if re.search(r'not found|undefined symbol:', relocations.stdout):
                raise ValueError('The built module has unresolved runtime dependencies: ' + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    if manifest['schema'] == 2:
        temporary = Path(tempfile.mkdtemp(prefix='.fusion-overlay-', dir=output.parent))
        try:
            for module in modules:
                name = PurePosixPath(module['target']).name
                shutil.copyfile(work / 'candidate' / name, temporary / name)
                (temporary / name).chmod(0o755)
            os.rename(temporary, output)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    else:
        descriptor, temporary = tempfile.mkstemp(prefix='.fusion-overlay-', dir=output.parent)
        os.close(descriptor)
        try:
            shutil.copyfile(work / 'candidate' / PurePosixPath(modules[0]['target']).name, temporary)
            os.chmod(temporary, 0o755)
            os.replace(temporary, output)
        finally:
            Path(temporary).unlink(missing_ok=True)
    (work / 'built-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Verified reviewed output: ' + str(output))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as error:
        print('Overlay build stopped: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
