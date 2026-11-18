#!/usr/bin/env python3
"""Render checks of single-pod Deployments on ReadWriteOnce volumes; no cluster access.

CouchDB, TimescaleDB and a lone Convertigo on a ReadWriteOnce workspace use RollingUpdate with maxSurge 0 and a
required anti-affinity with their own pods per node. RWO volume attachment still serializes access across nodes.
Upgrades from rolling Deployments work with server-side apply (Helm 4). Baserow and RWX databases keep Recreate.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / 'stable/convertigo'
BASE = '929e1cb'  # 8.4.8 candidate with Recreate for CouchDB and TimescaleDB, rolling updates for Convertigo.
NAME = 'rollout'
FULL = NAME + '-convertigo'
VERSION = ('--set-string', 'nocodestudio.version=fixture-published-release')
RWX = ('--set-json', 'workspace.accessModes=["ReadWriteMany"]')
RECREATE = {'type': 'Recreate'}
SURGE0 = {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': 0, 'maxUnavailable': 1}}


def deployments(*args, chart=CHART):
    out = subprocess.check_output(['helm', 'template', NAME, str(chart), *VERSION, *args],
                                  env=dict(os.environ, KUBECONFIG='/dev/null'), text=True)
    return {d['metadata']['name'].removeprefix(FULL + '-'): d for d in yaml.safe_load_all(out) if d and d['kind'] == 'Deployment'}


def strategy(d):
    return d['spec'].get('strategy')


def affinity(d):
    return d['spec']['template']['spec'].get('affinity')


def own_anti_affinity(d):
    term = {'labelSelector': {'matchLabels': d['spec']['selector']['matchLabels']}, 'topologyKey': 'kubernetes.io/hostname'}
    assert d['spec']['selector']['matchLabels'].items() <= d['spec']['template']['metadata']['labels'].items()
    return term


def single_pod(d):
    return strategy(d) == SURGE0 and own_anti_affinity(d) in affinity(d)['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution']


# 1. Defaults (ReadWriteOnce workspace, one replica): every single-pod Deployment waits for its old pod.
default = deployments()
assert all(single_pod(default[n]) for n in ['convertigo', 'cdb', 'timescale'])
assert strategy(default['br']) == RECREATE and affinity(default['br']) is None
print('PASS maxSurge 0 and own anti-affinity for CouchDB, TimescaleDB and a lone Convertigo; Baserow Recreate', flush=True)

# 2. A shared workspace, several replicas or autoscaling keep the current Convertigo rolling updates.
for case in [RWX, ('--set', 'replicaCount=2'), ('--set', 'autoscaling.enabled=true')]:
    d = deployments(*case)
    assert strategy(d['convertigo']) is None and affinity(d['convertigo']) is None, case
    assert single_pod(d['cdb']) and single_pod(d['timescale']), case
assert single_pod(deployments('--set', 'workspace.accessModes=null')['convertigo'])

# 3. User affinity of Convertigo is kept, the anti-affinity term is added to its own.
user = {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {'nodeSelectorTerms': [
            {'matchExpressions': [{'key': 'pool', 'operator': 'In', 'values': ['apps']}]}]}},
        'podAntiAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': [
            {'labelSelector': {'matchLabels': {'tier': 'other'}}, 'topologyKey': 'kubernetes.io/hostname'}]}}
merged = deployments('--set-json', 'affinity=' + json.dumps(user))['convertigo']
assert single_pod(merged) and affinity(merged)['nodeAffinity'] == user['nodeAffinity']
assert affinity(merged)['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution'][0] == user['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution'][0]
assert affinity(deployments('--set-json', 'affinity=' + json.dumps(user), *RWX)['convertigo']) == user
print('PASS shared workspaces unchanged, user affinity merged', flush=True)
# A DB explicitly using RWX cannot rely on RWO attachment fencing across nodes.
# Keep the previous Recreate behavior instead of permitting two writers on a shared volume.
for component,name in [('couchdb','cdb'),('timescaledb','timescale')]:
    shared=deployments('--set-json',component+'.accessModes=["ReadWriteMany"]')[name]
    assert strategy(shared)==RECREATE and affinity(shared) is None
print('PASS shared database volumes retain Recreate', flush=True)


# 4. Nothing else changes from BASE.
with tempfile.TemporaryDirectory(prefix='rollout-strategy-') as tmp:
    archive = subprocess.check_output(['git', 'archive', BASE, 'stable/convertigo'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        t.extractall(tmp, filter='data')
    base = Path(tmp) / 'stable/convertigo'
    for case in [(), RWX]:
        new, old = deployments(*case), deployments(*case, chart=base)
        for d in list(new.values()) + list(old.values()):
            d['spec'].pop('strategy', None)
            d['spec']['template']['spec'].pop('affinity', None)
        for d in [new['cdb'], old['cdb']]:  # Covered by tests/couchdb-shutdown.py.
            for key in ['command', 'env']:
                d['spec']['template']['spec']['containers'][0].pop(key, None)
        # The interrupted-staging cleanup intentionally changes the installer checksum;
        # its behavior is covered by startup-installation.py, not this rollout comparison.
        for d in [new['convertigo'], old['convertigo']]:
            d['spec']['template']['metadata']['annotations'].pop('checksum/workspace-installer', None)
        assert new == old, case
print('PASS rest of the Deployments unchanged', flush=True)
