#!/usr/bin/env python3
"""Local candidate/rehearsal rendering only; no Kubernetes, Docker or external lookup."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[1]
CHART=ROOT/'stable/convertigo'
metadata=yaml.safe_load((CHART/'Chart.yaml').read_text())
values=yaml.safe_load((CHART/'values.yaml').read_text())
assert metadata['version']==metadata['appVersion']=='8.4.8'
assert values['nocodestudio']['version']=='2.1.23'
assert values['baserow']['image']['tag']=='1.34.5'
assert values['timescaledb']['image']['tag']=='2.32.0-pg16'
assert not values['awsMarketplace']['enabled']
assert not values['crypto']['passphrase'] and not values['crypto']['existingSecret']
plugin=json.loads((CHART/'files/baserow-plugins/c8oforms.json').read_text())
assert plugin['release']=='v0.3.1' and '1.34.5' in plugin['tested_baserow_versions']
assert hashlib.sha256((CHART/'files/baserow-plugins'/plugin['archive']).read_bytes()).hexdigest()==plugin['sha256']

def render(*args):
    p=subprocess.run(['helm','template','rehearsal',str(CHART),*args],env=dict(os.environ,KUBECONFIG='/dev/null'),capture_output=True,text=True)
    assert p.returncode==0,'Candidate render failed'
    return [d for d in yaml.safe_load_all(p.stdout) if d]

def deployments(ds):return {d['metadata']['name']:d for d in ds if d['kind']=='Deployment'}
def main(d):return d['spec']['template']['spec']['containers'][0]
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
assert '/download/2.1.23/c8oforms_standalone.tar.gz' in script
assert 'METERING_ENABLED="false"' in script and 'BOOTSTRAP_CUSTOM_PASSPHRASE="false"' in script
assert any('BASEROW_PLUGIN_URLS'==e['name'] for e in main(ds['rehearsal-convertigo-br'])['env'])
print('PASS candidate 8.4.8, Forms/plugin/database versions, immutable CI rehearsal, generated credentials, RWX/Sentinel and volume references')
