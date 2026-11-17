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
assert values['nocodestudio']['version']==''
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
        assert p.returncode!=0 and 'published nocodestudio.version' in p.stderr and not p.stdout.strip()
        return None
    assert p.returncode==0,'Candidate render failed'
    return [d for d in yaml.safe_load_all(p.stdout) if d]

def deployments(ds):return {d['metadata']['name']:d for d in ds if d['kind']=='Deployment'}
def main(d):return d['spec']['template']['spec']['containers'][0]
render(failure=True)
render('--set','nocodestudio.enable=false')
base=render('--set-string','nocodestudio.version=fixture-published-release');before=deployments(base)
assert main(before['rehearsal-convertigo-convertigo'])['image']=='convertigo:8.4.8'
assert main(before['rehearsal-convertigo-timescale'])['image']=='timescale/timescaledb:2.32.0-pg16'
render('-f',str(ROOT/'providers/outscale/values.yaml'),'-f',str(ROOT/'providers/outscale/values-replay-848.yaml'),failure=True)
replay=render('-f',str(ROOT/'providers/outscale/values.yaml'),'-f',str(ROOT/'providers/outscale/values-replay-848.yaml'),'--set-string','nocodestudio.version=fixture-published-release')
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
assert 'NOCODESTUDIO_VERSION="fixture-published-release"' in script
assert yaml.safe_load((ROOT/'providers/outscale/values-replay-848.yaml').read_text())['nocodestudio']['version']==''
assert '/releases/download/$NOCODESTUDIO_VERSION/c8oforms_standalone.tar.gz' in script
assert 'Select a published nocodestudio.version' in script
assert '2.1.23' not in script
print('PASS candidate 8.4.8, pending application selection/plugin/database versions, immutable CI rehearsal, generated credentials, RWX/Sentinel and volume references')

# The deliberately unselected candidate cannot pass the publication guard. A supplied fixture tag
# exercises the local positive path without claiming any public application release exists.
pending=subprocess.run(['bash',str(ROOT/'tests/release-image.sh')],env=dict(os.environ,KUBECONFIG='/dev/null'),capture_output=True,text=True)
assert pending.returncode!=0 and 'published nocodestudio.version' in pending.stderr
with tempfile.TemporaryDirectory(prefix='release-application-fixture-') as folder:
    root=Path(folder); (root/'stable').mkdir(); (root/'tests').mkdir()
    shutil.copytree(CHART,root/'stable/convertigo')
    shutil.copyfile(ROOT/'tests/release-image.sh',root/'tests/release-image.sh')
    fixture=root/'stable/convertigo/values.yaml'
    fixture.write_text(fixture.read_text().replace('    version: ""','    version: "fixture-published-release"',1))
    accepted=subprocess.run(['bash',str(root/'tests/release-image.sh')],env=dict(os.environ,KUBECONFIG='/dev/null'),capture_output=True,text=True)
    assert accepted.returncode==0,'Publication guard rejected an explicit fixture tag'
print('PASS publication guard refuses an unselected application release; explicit fixture path works')
