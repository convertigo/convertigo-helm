#!/usr/bin/env python3
"""Local candidate/rehearsal rendering only; no Kubernetes, Docker or external lookup."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import shutil
import yaml

ROOT=Path(__file__).resolve().parents[1]
CHART=ROOT/'stable/convertigo'
metadata=yaml.safe_load((CHART/'Chart.yaml').read_text())
values=yaml.safe_load((CHART/'values.yaml').read_text())
assert metadata['version']==metadata['appVersion']=='8.4.8'
assert values['nocodestudio']['version']=='2.1.23'
assert values['nocodestudio']['archiveUrl']==''
assert values['baserow']['image']['tag']=='1.34.5'
assert values['timescaledb']['image']['tag']=='2.32.0-pg16'
assert not values['awsMarketplace']['enabled']
assert not values['crypto']['passphrase'] and not values['crypto']['existingSecret']
plugin=json.loads((CHART/'files/baserow-plugins/c8oforms.json').read_text())
assert plugin['release']=='v0.3.1' and '1.34.5' in plugin['tested_baserow_versions']
assert hashlib.sha256((CHART/'files/baserow-plugins'/plugin['archive']).read_bytes()).hexdigest()==plugin['sha256']

def render(*args, failure=False):
    p=subprocess.run(['helm','template','rehearsal',str(CHART),*args],env=dict(os.environ,KUBECONFIG='/dev/null'),capture_output=True,text=True)
    if failure:
        assert p.returncode!=0 and 'nocodestudio.version or nocodestudio.archiveUrl' in p.stderr and not p.stdout.strip()
        return None
    assert p.returncode==0,'Candidate render failed'
    return [d for d in yaml.safe_load_all(p.stdout) if d]

def deployments(ds):return {d['metadata']['name']:d for d in ds if d['kind']=='Deployment'}
def main(d):return d['spec']['template']['spec']['containers'][0]
render('--set-string','nocodestudio.version=',failure=True)
render('--set','nocodestudio.enable=false')
base=render();before=deployments(base)
assert main(before['rehearsal-convertigo-convertigo'])['image']=='convertigo:8.4.8'
assert main(before['rehearsal-convertigo-timescale'])['image']=='timescale/timescaledb:2.32.0-pg16'
replay=render('-f',str(ROOT/'providers/outscale/values.yaml'),'-f',str(ROOT/'providers/outscale/values-replay-848.yaml'))
ds=deployments(replay);engine=ds['rehearsal-convertigo-convertigo'];pod=engine['spec']['template']['spec']
assert engine['spec']['replicas']==3
image=main(engine)['image']
assert re.fullmatch(r'convertigo/convertigo-ci:\d+-hotfix-8\.4\.8-beta@sha256:[a-f0-9]{64}',image)
assert main(ds['rehearsal-convertigo-timescale'])['image']=='timescale/timescaledb:2.32.0-pg16'
assert main(ds['rehearsal-convertigo-br'])['image']=='baserow/baserow:1.34.5'
assert any(d['kind']=='StatefulSet' and d['spec']['replicas']==3 for d in replay)
assert any(d['kind']=='PersistentVolumeClaim' and 'ReadWriteMany' in d['spec']['accessModes'] for d in replay)
assert not any(d['kind']=='Ingress' for d in replay)
secrets=[d for d in replay if d['kind']=='Secret']
assert len(secrets)==2 and not any('crypto-passphrase' in d['data'] for d in secrets)
projected=next(v for v in pod['volumes'] if v['name']=='installation-credentials')['projected']['sources']
secret_names={d['metadata']['name'] for d in secrets}
assert all(s['secret']['name'] in secret_names for s in projected)
for d in replay:
    if d['kind']=='Deployment':
        ps=d['spec']['template']['spec'];names={v['name'] for v in ps.get('volumes',[])}
        for c in ps['containers']+ps.get('initContainers',[]):
            assert all(v['name'] in names for v in c.get('volumeMounts',[]))
script=next(d['data']['installCarFiles.sh'] for d in replay if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
assert 'NOCODESTUDIO_VERSION="2.1.23"' in script
assert yaml.safe_load((ROOT/'providers/outscale/values-replay-848.yaml').read_text())['nocodestudio']['version']=='2.1.23'
assert '/releases/download/$NOCODESTUDIO_VERSION/c8oforms_standalone.tar.gz' in script
assert 'Select an application version or archive URL' in script
assert "NOCODESTUDIO_ARCHIVE_URL=''" in script
print('PASS candidate 8.4.8, public default/plugin/database versions, immutable CI rehearsal, generated credentials, RWX/Sentinel and volume references')

# Rendering a target is not proof of its public availability. Empty selection is still rejected,
# and the beta is selected only by its separate rehearsal overlay.
fallback=render('-f',str(ROOT/'providers/outscale/values.yaml'),'-f',str(ROOT/'providers/outscale/values-replay-848.yaml'),
                '-f',str(ROOT/'providers/outscale/values-replay-848-fallback.yaml'))
fallback_script=next(d['data']['installCarFiles.sh'] for d in fallback if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
assert 'NOCODESTUDIO_VERSION="2.2.0-beta349.1"' in fallback_script
assert '2.2.0-beta349.1' not in script
print('PASS public default and explicit beta fallback, no silent downgrade; empty selection remains rejected')

# The override is a complete URL, independent of the public tag/path and kept literal by the shell.
url="https://artifacts.example.invalid/builds/custom.tar.gz?literal=$fixture_literal&label='x'"
custom=render('--set-string','nocodestudio.archiveUrl='+url,'--set-string','nocodestudio.version=')
custom_script=next(d['data']['installCarFiles.sh'] for d in custom if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
assignment=next(l for l in custom_script.splitlines() if l.startswith('NOCODESTUDIO_ARCHIVE_URL='))
p=subprocess.run(['bash','-c',assignment+'\nprintf "%s" "$NOCODESTUDIO_ARCHIVE_URL"'],capture_output=True,text=True,check=True)
assert p.stdout==url
assert 'SOURCE_URL="$NOCODESTUDIO_ARCHIVE_URL"' in custom_script
assert '--config "$STAGE/forms-download.conf"' in custom_script
with tempfile.TemporaryDirectory(prefix='private-url-default-fixture-') as folder:
    f=Path(folder)/'values.yaml';f.write_text('nocodestudio:\n  version: "2.2-rc"\n  archiveUrl: "https://artifacts.example.invalid/custom.tar.gz"\n')
    p=subprocess.run(['python3',str(ROOT/'tests/application-release-assets.py'),'--values',str(f)],capture_output=True,text=True)
    assert p.returncode==1 and json.loads(p.stdout)['status']=='custom-url-not-allowed-in-public-defaults'
    assert 'example.invalid' not in p.stdout+p.stderr
    fallback=render('-f',str(ROOT/'providers/outscale/values.yaml'),'-f',str(ROOT/'providers/outscale/values-replay-848.yaml'),
                    '-f',str(f),'-f',str(ROOT/'providers/outscale/values-replay-848-fallback.yaml'))
    fallback_script=next(d['data']['installCarFiles.sh'] for d in fallback if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
    assert 'NOCODESTUDIO_VERSION="2.2.0-beta349.1"' in fallback_script
    assert "NOCODESTUDIO_ARCHIVE_URL=''" in fallback_script
    assert 'artifacts.example.invalid' not in fallback_script

print('PASS literal full-URL override and no private-source URL accepted for public default publication')

# Optional checksum syntax is enforced at render time; defaults remain backwards compatible.
assert values['nocodestudio']['archiveSha256']==''
valid='aB'*32
checked=render('--set-string','nocodestudio.archiveSha256='+valid)
checked_script=next(d['data']['installCarFiles.sh'] for d in checked if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
assert 'NOCODESTUDIO_ARCHIVE_SHA256="'+valid.lower()+'"' in checked_script
assert checked_script.index('ARCHIVE_ACTUAL_SHA256=$(sha256sum') < checked_script.index('tar xzf')
for bad in ['abc','g'*64,'a'*63,'a'*65]:
    p=subprocess.run(['helm','template','rehearsal',str(CHART),'--set-string','nocodestudio.archiveSha256='+bad],capture_output=True,text=True,env=dict(os.environ,KUBECONFIG='/dev/null'))
    assert p.returncode!=0 and 'archiveSha256' in p.stderr and not p.stdout.strip()
print('PASS optional archive SHA-256 syntax, normalization and verification before extraction')
