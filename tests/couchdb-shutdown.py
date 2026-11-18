#!/usr/bin/env python3
"""Render checks of the CouchDB container command; no cluster access.

The command writes setup.ini, then execs the image's init (tini) with the image's entrypoint and CouchDB, so that
SIGTERM reaches CouchDB. A shell left as PID 1 ignored it, and CouchDB was killed at the end of the grace period.
"""
import os
from pathlib import Path
import subprocess
import yaml

CHART = Path(__file__).resolve().parents[1] / 'stable/convertigo'
SETUP = "echo '[couchdb]\nsingle_node=true' > /opt/couchdb/etc/local.d/setup.ini"
START = 'exec tini -- /docker-entrypoint.sh /opt/couchdb/bin/couchdb'


def couchdb(*args):
    out = subprocess.check_output(['helm', 'template', 'cdb', str(CHART), '--set-string', 'nocodestudio.version=fixture-published-release',
                                   '--show-only', 'templates/CDBdeployment.yaml', *args], env=dict(os.environ, KUBECONFIG='/dev/null'), text=True)
    return yaml.safe_load(out)['spec']['template']['spec']


for case in [(), ('--set-json', 'workspace.accessModes=["ReadWriteMany"]'), ('--set', 'couchdb.image.tag=3.5.1')]:
    pod = couchdb(*case)
    command = pod['containers'][0]['command']
    assert command[:2] == ['/bin/sh', '-c'] and command[2] == SETUP + ' && ' + START, case
    assert 'args' not in pod['containers'][0], case
    # tini must be PID 1: no shared process namespace, whose pause process would take that place.
    assert not pod.get('shareProcessNamespace'), case
assert couchdb('--set', 'couchdb.enabled=true')['containers'][0]['command'][2].endswith(START)
print('PASS CouchDB writes setup.ini, then execs tini with the image entrypoint', flush=True)
