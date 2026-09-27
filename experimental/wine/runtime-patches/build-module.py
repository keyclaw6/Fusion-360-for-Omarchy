#!/usr/bin/env python3
"""Build the Wine 11.17 alpha module privately; never install or launch Wine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked(path, expected):
    if not path.is_file() or digest(path) != expected:
        raise ValueError('Checksum mismatch: ' + str(path))


def symbols(path, defined):
    output = subprocess.check_output(['nm', '-D', '--defined-only' if defined else '--undefined-only', str(path)], text=True)
    return sorted(line.split()[-1] for line in output.splitlines() if line.split())


def needed(path):
    output = subprocess.check_output(['readelf', '-d', str(path)], text=True)
    return sorted(re.findall(r'\(NEEDED\).*?\[(.*?)\]', output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive', type=Path, required=True)
    parser.add_argument('--runner-archive', type=Path, required=True)
    parser.add_argument('--sdk-root', type=Path, required=True, help='Already verified SDK root; its pinned sdk-manifest.json must be alongside it')
    parser.add_argument('--work-dir', type=Path, required=True, help='New private build directory')
    parser.add_argument('--output', type=Path, required=True, help='New private output file; never an installed module')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text())
    for name in ('bash', 'bwrap', 'patch', 'nm', 'readelf', 'ldd', 'cc', 'gdb'):
        if not shutil.which(name):
            parser.error('Missing local dependency: ' + name)
    source_archive = args.source_archive.expanduser().resolve()
    runner_archive = args.runner_archive.expanduser().resolve()
    sdk = args.sdk_root.expanduser().resolve()
    work = args.work_dir.expanduser().absolute()
    output = args.output.expanduser().absolute()
    if work.is_symlink() or (work.exists() and any(work.iterdir())):
        parser.error('--work-dir must be new or empty')
    if output.exists() or output.is_symlink():
        parser.error('--output must not exist')
    checked(source_archive, manifest['source']['archive_sha256'])
    checked(runner_archive, manifest['runner_archive']['sha256'])
    checked(sdk.parent / 'sdk-manifest.json', manifest['sdk']['manifest_sha256'])
    for item in manifest['patches']:
        checked(HERE / item['file'], item['sha256'])
    work.mkdir(parents=True, exist_ok=True)
    work = work.resolve()
    for name in ('source', 'obj64', 'candidate', 'originals', 'home'):
        (work / name).mkdir()
    with tarfile.open(source_archive, 'r:gz') as archive:
        archive.extractall(work / 'source', filter='data')
    children = list((work / 'source').iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError('Source archive must contain one directory')
    children[0].rename(work / 'source/wine')
    source = work / 'source/wine'
    inputs = {**manifest['link_inputs'], 'winex11.so': manifest['module']['original_sha256']}
    with tarfile.open(runner_archive, 'r:gz') as archive:
        for name, expected in inputs.items():
            member = archive.getmember('fusion-wine-build/lib/wine/x86_64-unix/' + name)
            if not member.isfile():
                raise ValueError('Runner link input must be a regular file')
            target = (work / 'originals' / name if name == 'winex11.so' else
                      work / 'obj64/dlls' / name.removesuffix('.so') / name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream, target.open('wb') as dest:
                shutil.copyfileobj(stream, dest)
            checked(target, expected)
    with (work / 'build.log').open('w') as log:
        for item in manifest['patches']:
            with (HERE / item['file']).open('rb') as stream:
                subprocess.run(['patch', '-p1', '-F0'], cwd=source, stdin=stream,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
        for relative, expected in manifest['source_files'].items():
            checked(source / relative, expected)
        shutil.copyfile(HERE / 'compile.sh', work / 'compile.sh')
        sdk_command = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', str(sdk), '/',
                       '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp', '--bind', str(work), '/work',
                       '--ro-bind', str(work / 'source'), '/source', '--chdir', '/work', '--clearenv',
                       '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/work/home',
                       '--setenv', 'LC_ALL', 'C', '--setenv', 'CCACHE_DISABLE', '1']
        subprocess.run([*sdk_command, '/bin/bash', '/work/compile.sh'], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
        candidate = work / 'candidate/winex11.so'
        original = work / 'originals/winex11.so'
        checked(candidate, manifest['module']['sha256'])
        if symbols(candidate, True) != symbols(original, True):
            raise ValueError('Exported symbols differ from standalone runtime')
        if symbols(candidate, False) != symbols(original, False):
            raise ValueError('Undefined imports differ from standalone runtime')
        if needed(candidate) != needed(original) or needed(candidate) != manifest['abi']['dt_needed']:
            raise ValueError('ELF dependencies differ from reviewed contract')
        # Only load debug information from private files; do not run or attach Wine.
        debug_built = work / 'obj64/dlls/winex11.drv/winex11.so'
        expressions = ['sizeof(struct user_driver_funcs)', 'sizeof(struct gdi_dc_funcs)', 'sizeof(struct window_surface)']
        expected_sizes = [manifest['abi'][name] for name in ('user_driver_funcs_size', 'gdi_dc_funcs_size', 'window_surface_size')]
        for binary in (original, debug_built):
            command = ['gdb', '-nx', '-batch', '-ex', 'file ' + str(binary)]
            for expression in expressions:
                command += ['-ex', 'p ' + expression]
            report = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
            log.write(report)
            if [int(n) for n in re.findall(r'\$\d+ = (\d+)', report)] != expected_sizes:
                raise ValueError('Shared driver structure sizes differ')
        environment = dict(os.environ)
        environment.pop('LD_PRELOAD', None)
        environment.pop('LD_AUDIT', None)
        environment['LD_LIBRARY_PATH'] = ':'.join(str(work / 'obj64/dlls' / name) for name in ('ntdll', 'win32u'))
        report = subprocess.check_output(['ldd', '-r', str(candidate)], env=environment,
                                         text=True, stderr=subprocess.STDOUT)
        log.write(report)
        if re.search(r'not found|undefined symbol:', report):
            raise ValueError('Private candidate has unresolved host relocations')
        for script in ('test-constant-alpha.py', 'test-input-shape.py'):
            subprocess.run(['python3', str(HERE / script), '--work-dir', str(work)], stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, candidate.open('rb') as src:
        shutil.copyfileobj(src, stream)
    output.chmod(0o755)
    (work / 'built-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Exact candidate rebuilt; ABI, host relocations, and source sanitizer checks passed: ' + str(output))


if __name__ == '__main__':
    main()
