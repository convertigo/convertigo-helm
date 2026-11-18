#!/usr/bin/env python3
"""CouchDB server uuid: render checks, and stability against a loopback-only, GET-only synthetic Kubernetes API
(lookup of the kept ConfigMap). No cluster, kubeconfig or account is used.

FullSync clients (PouchDB) derive their replication id from the uuid returned by /convertigo/fullsync/: a new uuid
at each CouchDB start made every client restart from the beginning of the changes feed.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from urllib.parse import urlparse
import yaml

CHART = Path(__file__).resolve().parents[1] / 'stable/convertigo'
NAME, NS = 'uuid', 'fixture'
CONFIGMAP = NAME + '-convertigo-cdb-uuid'
VERSION = ('--set-string', 'nocodestudio.version=fixture-published-release')
HEX32 = re.compile(r'^[0-9a-f]{32}$')


def render(*args, env=None, check=True):
    p = subprocess.run(['helm', 'template', NAME, str(CHART), '-n', NS, *VERSION, *args],
                       env=env or dict(os.environ, KUBECONFIG='/dev/null'), capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError('helm template failed: ' + p.stderr.strip().splitlines()[-1])
    return p if not check else [d for d in yaml.safe_load_all(p.stdout) if d]


def uuid_of(docs):
    return next(d['data']['uuid'] for d in docs if d['kind'] == 'ConfigMap' and d['metadata']['name'] == CONFIGMAP)


# 1. New install: a generated uuid in a kept ConfigMap, passed to CouchDB and written to setup.ini.
docs = render()
configmap = next(d for d in docs if d['kind'] == 'ConfigMap' and d['metadata']['name'] == CONFIGMAP)
assert HEX32.match(configmap['data']['uuid']) and configmap['metadata']['annotations']['helm.sh/resource-policy'] == 'keep'
couchdb = next(d for d in docs if d['kind'] == 'Deployment' and d['metadata']['name'].endswith('-cdb'))['spec']['template']['spec']['containers'][0]
assert {'name': 'C8O_COUCHDB_UUID', 'valueFrom': {'configMapKeyRef': {'name': CONFIGMAP, 'key': 'uuid'}}} in couchdb['env']
assert "uuid = %s\n' \"$C8O_COUCHDB_UUID\" > /opt/couchdb/etc/local.d/setup.ini && exec tini" in couchdb['command'][2]
assert uuid_of(render('--set', 'couchdb.uuid=0123456789abcdef0123456789abcdef')) == '0123456789abcdef0123456789abcdef'
assert render('--set', 'couchdb.uuid=not-an-uuid', check=False).returncode
assert not any(d['metadata']['name'] == CONFIGMAP for d in render('--set', 'couchdb.enabled=false'))
assert HEX32.match(uuid_of(render('--set', 'couchdb.uuid=null')))
print('PASS generated or provided uuid, kept ConfigMap, setup.ini written before CouchDB starts', flush=True)


# 2. Upgrades: the kept uuid is reused; a missing or invalid one is replaced (upgrade from 8.4.7: stable from then on).
class API(BaseHTTPRequestHandler):
    objects = {}
    writes = 0
    groups = {'v1': {'secrets': 'Secret', 'services': 'Service', 'configmaps': 'ConfigMap', 'pods': 'Pod',
                     'persistentvolumeclaims': 'PersistentVolumeClaim', 'serviceaccounts': 'ServiceAccount'},
              'apps/v1': {'deployments': 'Deployment', 'statefulsets': 'StatefulSet'},
              'networking.k8s.io/v1': {'ingresses': 'Ingress'}}

    def log_message(self, *args):
        pass

    def do_POST(self):
        type(self).writes += 1
        self.send_error(405)
    do_PUT = do_PATCH = do_DELETE = do_POST

    def reply(self, code, body):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/version':
            return self.reply(200, {'major': '1', 'minor': '33', 'gitVersion': 'v1.33.0'})
        if path == '/api':
            return self.reply(200, {'kind': 'APIVersions', 'versions': ['v1']})
        if path == '/apis':
            return self.reply(200, {'kind': 'APIGroupList', 'groups': [
                {'name': g.split('/')[0], 'versions': [{'groupVersion': g, 'version': 'v1'}], 'preferredVersion': {'groupVersion': g, 'version': 'v1'}}
                for g in self.groups if g != 'v1']})
        for version, kinds in self.groups.items():
            if path == ('/api/' if version == 'v1' else '/apis/') + version:
                return self.reply(200, {'kind': 'APIResourceList', 'groupVersion': version, 'resources': [
                    {'name': p, 'singularName': '', 'namespaced': True, 'kind': k, 'verbs': ['get', 'list']} for p, k in kinds.items()]})
        if path in self.objects:
            return self.reply(200, self.objects[path])
        if path.endswith('/secrets'):
            return self.reply(200, {'kind': 'SecretList', 'metadata': {'resourceVersion': '1'}, 'items': []})
        if path.endswith('/namespaces/' + NS):
            return self.reply(200, {'kind': 'Namespace', 'metadata': {'name': NS}})
        self.reply(404, {'kind': 'Status', 'status': 'Failure', 'reason': 'NotFound', 'code': 404})


def kept(value):
    return {'/api/v1/namespaces/%s/configmaps/%s' % (NS, CONFIGMAP): {
        'apiVersion': 'v1', 'kind': 'ConfigMap', 'data': {'uuid': value},
        'metadata': {'name': CONFIGMAP, 'namespace': NS, 'labels': {'app.kubernetes.io/managed-by': 'Helm'},
                     'annotations': {'meta.helm.sh/release-name': NAME, 'meta.helm.sh/release-namespace': NS}}}}


server = ThreadingHTTPServer(('127.0.0.1', 0), API)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix='couchdb-uuid-') as tmp:
    kube = Path(tmp) / 'kubeconfig'
    kube.write_text(yaml.safe_dump({'apiVersion': 'v1', 'kind': 'Config', 'current-context': 'fixture',
                                    'clusters': [{'name': 'fixture', 'cluster': {'server': 'http://127.0.0.1:%d' % server.server_port}}],
                                    'contexts': [{'name': 'fixture', 'context': {'cluster': 'fixture', 'user': 'fixture', 'namespace': NS}}],
                                    'users': [{'name': 'fixture', 'user': {}}]}))
    kube.chmod(0o600)
    live = dict(os.environ, KUBECONFIG=str(kube), HELM_DRIVER='secret')
    online = ('--dry-run=server', '--disable-openapi-validation')
    try:
        API.objects = kept('fedcba9876543210fedcba9876543210')
        assert uuid_of(render(*online, env=live)) == 'fedcba9876543210fedcba9876543210'
        assert uuid_of(render(*online, '--set', 'couchdb.uuid=0123456789abcdef0123456789abcdef', env=live)) == '0123456789abcdef0123456789abcdef'
        API.objects = kept('')
        assert HEX32.match(uuid_of(render(*online, env=live)))
        # Second upgrade: the live CouchDB Deployment already has the variable; it must stay single.
        for live_env in [[{'name': 'COUCHDB_USER', 'value': 'admin'}],
                         [{'name': 'COUCHDB_USER', 'value': 'admin'}, {'name': 'C8O_COUCHDB_UUID', 'value': 'stale'}]]:
            API.objects = {**kept('fedcba9876543210fedcba9876543210'),
                           '/apis/apps/v1/namespaces/%s/deployments/%s-convertigo-cdb' % (NS, NAME): {
                               'apiVersion': 'apps/v1', 'kind': 'Deployment',
                               'metadata': {'name': NAME + '-convertigo-cdb', 'namespace': NS, 'labels': {'app.kubernetes.io/managed-by': 'Helm'},
                                            'annotations': {'meta.helm.sh/release-name': NAME, 'meta.helm.sh/release-namespace': NS}},
                               'spec': {'template': {'spec': {'containers': [{'name': 'cdb', 'image': 'couchdb:3.5', 'env': live_env}]}}}}}
            upgraded = render(*online, '--is-upgrade', env=live)
            env = next(d for d in upgraded if d['kind'] == 'Deployment' and d['metadata']['name'].endswith('-cdb'))['spec']['template']['spec']['containers'][0]['env']
            assert [e for e in env if e['name'] == 'C8O_COUCHDB_UUID'] == [{'name': 'C8O_COUCHDB_UUID', 'valueFrom': {'configMapKeyRef': {'name': CONFIGMAP, 'key': 'uuid'}}}], live_env
            assert {'name': 'COUCHDB_USER', 'value': 'admin'} in env, live_env
        API.objects = {}
        first, second = uuid_of(render(*online, env=live)), uuid_of(render(*online, env=live))
        assert HEX32.match(first) and HEX32.match(second)
        assert API.writes == 0
    finally:
        server.shutdown()
print('PASS kept uuid reused on upgrade, missing or invalid one replaced, variable single on later upgrades', flush=True)
