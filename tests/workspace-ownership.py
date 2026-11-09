#!/usr/bin/env python3
"""Render tests; add --docker to exercise the rendered installer with Linux UIDs."""
import argparse
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import uuid


def command(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--docker', action='store_true')
parser.add_argument('--image', default='convertigo/convertigo-ci:hotfix')
parser.add_argument('--chart', type=Path, default=Path(__file__).resolve().parents[1] / 'stable/convertigo')
args = parser.parse_args()
chart = args.chart


def render(template, *options, chart_dir=chart):
    return command('helm', 'template', 'ownership', str(chart_dir), '--show-only',
                   'templates/' + template, *options)


default = render('C8Odeployment.yaml')
assert 'name: volume-mount-hack' in default
assert default == render('C8Odeployment.yaml', '--set', 'workspaceOwnershipInit.enabled=true')
disabled = ('--set', 'workspaceOwnershipInit.enabled=false')
without = render('C8Odeployment.yaml', *disabled)
assert 'initContainers:' not in without
extra = ('--set-json', 'extraInitContainers=[{"name":"custom-init","image":"busybox","command":["true"]}]')
with_extra = render('C8Odeployment.yaml', *disabled, *extra)
assert 'initContainers:' in with_extra and 'name: custom-init' in with_extra
assert 'volume-mount-hack' not in with_extra
both = render('C8Odeployment.yaml', *extra)
assert 'name: custom-init' in both and 'name: volume-mount-hack' in both
assert render('C8Odeployment.yaml', '--set', 'workspaceOwnershipInit=null') == default
# Emulate the effective values of an upgrade reusing a release from before the
# new key existed. New chart defaults are not necessarily added by --reuse-values.
with tempfile.TemporaryDirectory(prefix='workspace-legacy-values-') as directory:
    legacy = Path(directory) / 'chart'
    shutil.copytree(chart, legacy)
    values = legacy / 'values.yaml'
    original = values.read_text()
    without_key = original.replace('workspaceOwnershipInit:\n  enabled: true\n\n', '')
    assert original != without_key, 'Legacy fixture must remove the new key'
    values.write_text(without_key)
    assert render('C8Odeployment.yaml', chart_dir=legacy) == default
    assert 'initContainers:' not in render('C8Odeployment.yaml', *disabled, chart_dir=legacy)
print('PASS default/disabled/custom init containers and legacy values', flush=True)
if not args.docker:
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix='convertigo-workspace-test-') as directory:
    work = Path(directory)
    # The container uses arbitrary UIDs and must be able to read the fixtures.
    work.chmod(0o755)
    for enabled in (False, True):
        cm = render('configmapInstallCarFiles.yaml', '--set', 'baserow.enabled=true',
                    '--set', 'nocodestudio.enable=' + str(enabled).lower())
        script = cm.split('  installCarFiles.sh: |\n', 1)[1]
        script = '\n'.join(line[4:] if line.startswith('    ') else line
                           for line in script.splitlines()) + '\n'
        (work / ('install-' + str(enabled).lower() + '.sh')).write_text(script)
    (work / 'bin').mkdir(mode=0o755)
    # No network access: a tiny local archive exercises the real extraction path.
    curl = work / 'bin/curl'
    curl.write_text('#!/bin/bash\ncase "$*" in\n'
                    '  *169.254.169.254*) exit 1 ;;\n'
                    '  *c8oforms_standalone.tar.gz*) cat /test/forms.tar.gz ;;\n'
                    '  *) echo "Unexpected curl call" >&2; exit 99 ;;\nesac\n')
    curl.chmod(0o755)
    with tarfile.open(work / 'forms.tar.gz', 'w:gz') as archive:
        content = b'fixture project\n'
        member = tarfile.TarInfo('c8oforms_standalone/data/workspace/projects/BaserowIntegration/c8o/test.txt')
        member.size = len(content)
        member.mode = 0o644
        archive.addfile(member, io.BytesIO(content))

    def run_case(name, uid, gid, volume_group, *, reused=False, writable=True, nocode=True):
        volume = 'codex-workspace-' + uuid.uuid4().hex[:12]
        command('docker', 'volume', 'create', volume)
        mounts = ('--mount', 'type=volume,src=' + volume + ',dst=/workspace',
                  '--mount', 'type=bind,src=' + str(work) + ',dst=/test,readonly')
        try:
            # Empty volumes are populated from the image again on the next run,
            # including permissions. Keep a marker so our permission fixture persists.
            prepare = ('find /workspace -mindepth 1 -delete; touch /workspace/.permission-test; '
                       f'chown 0:{volume_group} /workspace; chmod {"2770" if writable else "0755"} /workspace')
            if reused:
                prepare += ('; mkdir -p /workspace/projects /workspace/configuration; '
                            f'chown 0:{volume_group} /workspace/projects /workspace/configuration; '
                            'chmod 2770 /workspace/projects /workspace/configuration; '
                            'echo preserve-me > /workspace/configuration/global_symbols.properties; '
                            f'chown 0:{volume_group} /workspace/configuration/global_symbols.properties; '
                            'chmod 0660 /workspace/configuration/global_symbols.properties')
            command('docker', 'run', '--rm', '--network', 'none', *mounts,
                    '--entrypoint', '/bin/bash', args.image, '-ec', prepare)
            flags = [] if uid == 0 else ['--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true']
            script = '/test/install-' + str(nocode).lower() + '.sh'
            checks = ('test -d /workspace/projects; '
                      'test -s /workspace/configuration/global_symbols.properties; ')
            if nocode:
                checks += 'test "$(cat /workspace/projects/BaserowIntegration/c8o/test.txt)" = "fixture project"; '
                checks += f'test "$(stat -c %u /workspace/projects/BaserowIntegration/c8o/test.txt)" = {1000 if uid == 0 else uid}; '
            if reused:
                checks += ('test "$(cat /workspace/configuration/global_symbols.properties)" = preserve-me; '
                           f'test "$(stat -c %u /workspace/configuration/global_symbols.properties)" = {1000 if uid == 0 else 0}; ')
            # Exercise the normal restart fast path too.
            checks += f'bash {script}; echo "PASS {name}"'
            result = subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                                     '--user', f'{uid}:{gid}', '--group-add', str(volume_group),
                                     *flags, *mounts, '--entrypoint', '/bin/bash', args.image,
                                     '-ec', f'export PATH=/test/bin:$PATH; bash {script}; ' + checks],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if writable:
                assert result.returncode == 0, name + '\n' + result.stdout
            else:
                assert result.returncode != 0 and 'Permission denied' in result.stdout, result.stdout
            print('PASS ' + name, flush=True)
        finally:
            command('docker', 'volume', 'rm', volume)

    run_case('Convertigo UID 1000, fresh install and restart', 1000, 1000, 1000)
    run_case('arbitrary UID with group 0 access', 1001230000, 0, 0)
    run_case('arbitrary UID with supplemental group access, reused workspace', 12345, 12345, 2000, reused=True)
    run_case('arbitrary UID with No Code Studio disabled', 12345, 12345, 2000, nocode=False)
    run_case('root keeps ownership handoff to Convertigo UID 1000', 0, 0, 0)
    run_case('inaccessible workspace still fails', 12345, 12345, 0, writable=False)
