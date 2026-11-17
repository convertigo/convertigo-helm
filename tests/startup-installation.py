#!/usr/bin/env python3
"""Local render and fixture tests only: no Docker, kubectl, network or session fault injection.

Requires helm, bash, Python and PyYAML. The fixture flock shim uses the host's real advisory locks;
this tests process serialization, not a remote RWX driver's cross-node locking behavior.
The credential CLI is mocked here; installation-credentials.py covers the real Java initializer.
"""
import base64
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import yaml

CHART = Path(__file__).resolve().parents[1] / 'stable/convertigo'


def render(*options):
    return [x for x in yaml.safe_load_all(subprocess.check_output(
        ['helm', 'template', 'startup', str(CHART), '--set-string', 'nocodestudio.version=fixture-published-release', *options], text=True)) if x]


def engine(docs):
    return next(x['spec']['template']['spec'] for x in docs
                if x['kind'] == 'Deployment' and x['metadata']['name'].endswith('-convertigo'))


def installer(docs):
    return next(x['data']['installCarFiles.sh'] for x in docs
                if x['kind'] == 'ConfigMap' and 'installCarFiles.sh' in x.get('data', {}))


def assert_render_failure(*options):
    p = subprocess.run(['helm', 'template', 'startup', str(CHART), '--set-string', 'nocodestudio.version=fixture-published-release', *options],
                       capture_output=True, text=True)
    assert p.returncode != 0, 'Invalid administrator option was accepted'


default = render()
pod = engine(default)
init = pod['initContainers'][0]
assert init['name'] == 'workspace-setup' and init['securityContext']['runAsUser'] == 0
assert init['command'][0] == '/bin/bash'
main = pod['containers'][0]
assert 'installCarFiles' not in str(main['command'])
assert 'admin-credential' not in {m['name'] for m in main['volumeMounts']}
assert 'admin-credential' in {m['name'] for m in init['volumeMounts']}
assert not any('ADMIN_PASSWORD' in e['name'] for e in main['env'])
assert not any('admin.password' in str(e) for e in main['env'])
assert main['startupProbe']['failureThreshold'] * main['startupProbe']['periodSeconds'] == 600
admin = next(x for x in default if x['kind'] == 'Secret' and x['metadata']['name'].endswith('-admin'))
assert len(base64.b64decode(admin['data']['password'])) == 48
assert 'lookup "v1" "Secret"' in (CHART / 'templates/admin-secret.yaml').read_text()
assert '169.254.169.254' not in installer(default)
assert 'flock -x -w ' in installer(default)
assert installer(default).rindex('mv -- "$STAGE/complete"') > installer(default).index('find "$PROJECTS_DIR"')
subprocess.run(['bash', '-n'], input=installer(default), text=True, check=True)
assert_render_failure('--set-string','nocodestudio.version=')
assert_render_failure('--set', 'admin.username=bad user')
assert_render_failure('--set', 'admin.passwordKey=bad:key')
assert_render_failure('--set-string', 'additionalJavaOpts=-Dconvertigo.engine.admin.password=fixture')

options = ['--set', 'replicaCount=3', '--set', 'workspace.accessModes[0]=ReadWriteMany',
           '--set', 'redis.enabled=true', '--set', 'redis.sentinel.enabled=true',
           '--set', 'redis.persistence.enabled=true', '--set', 'admin.existingSecret=fixture-admin',
           '--set', 'timescaledb.existingSecret=fixture-database',
           '--set', 'baserow.existingSecret=fixture-database',
           '--set', 'podAnnotations.fixture=retained']
docs = render(*options)
assert not any(x['kind'] == 'Secret' and x['metadata']['name'].endswith('-admin') for x in docs)
assert len(engine(docs)['initContainers']) == 1
envs = engine(docs)['containers'][0]['env']
java_opts = next(x['value'] for x in envs if x['name'] == 'JAVA_OPTS')
assert 'session.store.mode=redis' in java_opts and 'session.redis.topology=sentinel' in java_opts
assert next(x['spec']['replicas'] for x in docs if x['kind'] == 'StatefulSet' and x['metadata']['name'].endswith('-redis')) == 3
assert not any(x['name'].endswith('_PASSWORD') for x in envs)
for x in docs:
    if x['kind'] == 'Deployment' and x['metadata']['name'].endswith(('-cdb', '-timescale', '-br')):
        assert x['spec']['strategy']['type'] == 'Recreate'
assert engine(render('--set', 'workspaceOwnershipInit.enabled=false'))['initContainers'][0]['securityContext']['runAsUser'] == 1000
custom = engine(render('--set', 'workspaceOwnershipInit.enabled=false', '--set', 'securityContext.runAsUser=1234', '--set', 'securityContext.runAsGroup=4321'))['initContainers'][0]['securityContext']
assert custom['runAsUser'] == 1234 and custom['runAsGroup'] == 4321
assert 'startupProbe' not in engine(render('--set', 'startupProbe.enabled=false'))['containers'][0]
assert engine(render('--set', 'startupProbe=null'))['containers'][0]['startupProbe']
# Reused old values without any of the new keys retain safe startup defaults.
assert engine(render('--set', 'admin=null', '--set', 'projectInstallation=null', '--set', 'awsMarketplace=null'))['initContainers']
print('PASS startup/init, generated/existing admin Secret, database references, RWX/Sentinel and legacy values')

with tempfile.TemporaryDirectory(prefix='chart-startup-fixture-') as directory:
    root = Path(directory)
    tools = root / 'bin'; tools.mkdir()
    archive = root / 'projects.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for project in ['BaserowIntegration', 'FixtureLibrary']:
            data = b'fixture: complete\n'
            member = tarfile.TarInfo('c8oforms_standalone/data/workspace/projects/' + project + '/c8oProject.yaml')
            member.size = len(data); member.mode = 0o600
            tar.addfile(member, io.BytesIO(data))
    def tool(name, body):
        p = tools / name; p.write_text('#!' + sys.executable + '\n' + body); p.chmod(0o755)
    tool('java', 'import sys,os,pathlib\nif sys.argv[-1]=="prepare":\n p=pathlib.Path(os.environ["WORKSPACE"])/"configuration/.chart-crypto-state";p.parent.mkdir(parents=True,exist_ok=True);p.write_text("mode=new\\n")\nsys.exit(0)\n')
    tool('flock', '''import fcntl,os,sys,time
fd=int(sys.argv[-1]); deadline=time.monotonic()+float(sys.argv[sys.argv.index('-w')+1])
while True:
 try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB); break
 except BlockingIOError:
  if time.monotonic()>deadline:sys.exit(1)
  time.sleep(.02)
''')
    tool('curl', '''import os,sys,pathlib,shutil,time
with open(os.environ['COUNT_FILE'],'a') as f:f.write('download\\n')
if os.environ.get('FAIL_DOWNLOAD')=='1':sys.exit(22)
assert any('c8oforms_standalone.tar.gz' in a for a in sys.argv)
time.sleep(.15)
shutil.copyfile(os.environ['ARCHIVE'],sys.argv[sys.argv.index('-o')+1])
''')
    tool('tar', '''import sys,tarfile,pathlib
# Fixture extraction with the same four-component prefix removed, no host-specific tar extensions.
dest=pathlib.Path(sys.argv[sys.argv.index('-C')+1])
with tarfile.open(sys.argv[2]) as t:
 for m in t:
  parts=pathlib.PurePosixPath(m.name).parts[4:]
  assert parts and '..' not in parts
  p=dest.joinpath(*parts);p.parent.mkdir(parents=True,exist_ok=True)
  p.write_bytes(t.extractfile(m).read());p.chmod(m.mode)
''')
    tool('sha512sum', '''import sys,os,hashlib
if os.environ.get('FAIL_HASH')=='1':sys.exit(1)
print(hashlib.sha512(sys.stdin.buffer.read()).hexdigest()+'  -')
''')
    secret = root / 'credential'; secret.write_bytes(os.urandom(24).hex().encode()); secret.chmod(0o600)
    script = root / 'installer.sh'; script.write_text(installer(default))
    def env(workspace, count, **extra):
        return dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'], WORKSPACE=str(workspace),
                    ADMIN_SECRET_FILE=str(secret), ARCHIVE=str(archive), COUNT_FILE=str(count), **extra)
    def run(e, fail=False):
        p = subprocess.run(['bash', str(script)], env=e, capture_output=True, text=True)
        assert (p.returncode != 0) if fail else (p.returncode == 0), 'Installer fixture returned unexpected status'
    pending = root / 'pending-release'; pending.mkdir(); pending_count = root / 'pending-count'
    script.write_text(installer(default).replace('NOCODESTUDIO_VERSION="fixture-published-release"','NOCODESTUDIO_VERSION=""'))
    run(env(pending, pending_count),fail=True)
    assert not pending_count.exists() and not (pending/'configuration').exists()
    # Retained installations with no selected version do not fetch an unknown application release.
    retained=root/'retained-release'; (retained/'configuration').mkdir(parents=True)
    (retained/'projects/FixtureLibrary').mkdir(parents=True)
    retained_properties=retained/'configuration/engine.properties';retained_properties.write_text('fixture=keep\n')
    run(env(retained,pending_count))
    assert retained_properties.read_text()=='fixture=keep\n' and not pending_count.exists()
    script.write_text(installer(default))
    workspace = root / 'workspace'; workspace.mkdir(); count = root / 'count'
    run(env(workspace, count, FAIL_DOWNLOAD='1'), fail=True)
    assert not (workspace / '.chart-install-complete').exists()
    assert not (workspace / 'projects/BaserowIntegration').exists()
    # Three starts share a real advisory file lock. Only the first downloads after an interruption.
    jobs = [subprocess.Popen(['bash', str(script)], env=env(workspace, count),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(3)]
    assert all(p.wait(timeout=30) == 0 for p in jobs), 'Concurrent init fixture failed'
    assert len(count.read_text().splitlines()) == 2, 'Concurrent starts downloaded more than once'
    properties = workspace / 'configuration/engine.properties'
    expected = hashlib.sha512(secret.read_bytes()).hexdigest()
    assert 'admin.password='+expected in properties.read_text()
    assert properties.stat().st_mode & 0o777 == 0o600
    assert (workspace / '.chart-install-complete').exists()
    assert not list(workspace.glob('.chart-install.??????'))
    # An existing customized administrator is preserved in automatic/generated mode.
    preserved = hashlib.sha512(b'custom fixture account').hexdigest()
    properties.write_text('admin.username=fixture\nadmin.password='+preserved+'\n')
    run(env(workspace, count))
    assert 'admin.password='+preserved in properties.read_text()
    # Even an explicitly selected Secret must not replace an existing administrator on restart.
    script.write_text(installer(render('--set', 'admin.existingSecret=fixture-admin')))
    run(env(workspace, count))
    assert 'admin.password='+preserved in properties.read_text()
    # Interruption after publication must not mark completion or overwrite existing project changes on retry.
    script.write_text(installer(default))
    interrupted = root / 'interrupted'; interrupted.mkdir(); second_count = root / 'count2'
    run(env(interrupted, second_count, FAIL_HASH='1'), fail=True)
    assert not (interrupted / '.chart-install-complete').exists()
    project = interrupted / 'projects/BaserowIntegration/c8oProject.yaml'
    assert project.exists(); project.write_text('keep-local-edit\n')
    run(env(interrupted, second_count))
    assert project.read_text() == 'keep-local-edit\n'
    assert (interrupted / '.chart-install-complete').exists()
print('PASS interrupted download/publication, three concurrent starts, last marker, admin preservation and private properties')
