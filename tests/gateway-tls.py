#!/usr/bin/env python3
"""Gateway API routes and the self-signed TLS Secret: render checks, and stability against a loopback-only,
GET-only synthetic Kubernetes API (lookup of the existing Secret). No cluster, kubeconfig or account is used.

Also checks that every bundled values file renders as before these options (BASE), generated secrets aside.
"""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import threading
from urllib.parse import urlparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / 'stable/convertigo'
BASE = '929e1cb'  # 8.4.8 candidate before the Gateway API and self-signed TLS options.
NAME, NS = 'gw', 'fixture'
OFFLINE = dict(os.environ, KUBECONFIG='/dev/null')
VERSION = ('--set-string', 'nocodestudio.version=fixture-published-release')
GATEWAY = ('--set', 'ingress.enabled=false', '--set', 'gateway.enabled=true')
CREATED = (*GATEWAY, '--set', 'gateway.gatewayClassName=eg')


def helm(*args, chart=CHART, env=OFFLINE, check=True):
    p = subprocess.run(['helm', 'template', NAME, str(chart), '-n', NS, *VERSION, *args], env=env, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError('helm template failed: ' + p.stderr.strip().splitlines()[-1])
    return p


def docs(*args, **kwargs):
    return [d for d in yaml.safe_load_all(helm(*args, **kwargs).stdout) if d]


def kinds(ds, kind):
    return {d['metadata']['name']: d for d in ds if d['kind'] == kind}


def normalized(*args, **kwargs):
    # What these options touch: the Ingress objects, and no Gateway API object or generated TLS Secret by default.
    # The other objects are covered by their own tests (rollout strategy, CouchDB, credentials...).
    ds = docs(*args, **kwargs)
    return ([d for d in ds if d['kind'] in ('Ingress', 'Gateway', 'HTTPRoute')]
            + [d['metadata']['name'] for d in ds if d['kind'] == 'Secret' and d.get('type') == 'kubernetes.io/tls'])


def certificate(secret):
    pem = base64.b64decode(secret['data']['tls.crt'])
    return subprocess.run(['openssl', 'x509', '-noout', '-subject', '-ext', 'subjectAltName'], input=pem,
                          capture_output=True, check=True).stdout.decode()


def fails(*args):
    p = helm(*args, check=False)
    assert p.returncode, args
    return p.stderr


# 1. Same render as BASE for the defaults and every values file of the repository, and for legacy values without
#    the new keys (helm upgrade --reuse-values from an older release).
with tempfile.TemporaryDirectory(prefix='gateway-tls-') as tmp:
    archive = subprocess.check_output(['git', 'archive', BASE, 'stable/convertigo'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        t.extractall(tmp, filter='data')
    base = Path(tmp) / 'stable/convertigo'
    files = sorted(p for d in ['providers', 'examples', 'tests/fixtures'] for p in (ROOT / d).rglob('*.yaml')
                   if 'values' in p.name or p.parent.name == 'fixtures')
    cases = [()] + [('-f', str(f)) for f in files] + [('--set', 'ingress.enabled=false'),
                                                      ('--set', 'gateway=null', '--set', 'tls=null')]
    for case in cases:
        assert normalized(*case) == normalized(*case, chart=base), case
print('PASS unchanged Ingress, no Gateway API object or TLS Secret for', len(cases), 'value sets, including', len(files), 'repository values files', flush=True)

# 2. Defaults: Ingress with the cert-manager issuer and convertigo-tls, no Gateway API object, no generated Secret.
default = docs()
assert not kinds(default, 'Gateway') and not kinds(default, 'HTTPRoute') and 'convertigo-tls' not in kinds(default, 'Secret')
assert kinds(default, 'Ingress')[NAME + '-convertigo']['spec']['tls'][0]['secretName'] == 'convertigo-tls'
renamed = docs('--set', 'tls.secretName=custom-tls')
assert {i['spec']['tls'][0]['secretName'] for i in kinds(renamed, 'Ingress').values()} == {'custom-tls'}

# 3. Gateway created by the chart: HTTP and HTTPS listeners, routes, HTTPS redirect and a self-signed certificate.
created = docs(*CREATED)
gateway = kinds(created, 'Gateway')[NAME + '-convertigo']
assert gateway['spec']['gatewayClassName'] == 'eg'
listeners = {l['name']: l for l in gateway['spec']['listeners']}
assert (listeners['http']['port'], listeners['https']['port']) == (80, 443) and 'hostname' not in listeners['https']
assert listeners['https']['tls']['certificateRefs'] == [{'kind': 'Secret', 'name': 'convertigo-tls'}]
routes = kinds(created, 'HTTPRoute')
route = routes[NAME + '-convertigo']['spec']
assert route['parentRefs'] == [{'name': NAME + '-convertigo', 'sectionName': 'https'}] and 'hostnames' not in route
root = [r for r in route['rules'] if r['matches'][0]['path'] == {'type': 'Exact', 'value': '/'}][0]
assert root['filters'][0]['requestRedirect'] == {'path': {'type': 'ReplaceFullPath', 'replaceFullPath': '/convertigo/'}, 'statusCode': 301}
assert len(route['rules']) == 3
convertigo = [r for r in route['rules'] if r['matches'][0]['path'] == {'type': 'PathPrefix', 'value': '/convertigo'}][0]
baserow = [r for r in route['rules'] if r['matches'][0]['path'] == {'type': 'PathPrefix', 'value': '/'}][0]
assert convertigo['backendRefs'] == [{'name': NAME + '-convertigo', 'port': 28080}]
assert baserow['backendRefs'] == [{'name': NAME + '-convertigo-br', 'port': 80}]
assert convertigo['timeouts'] == {'request': '3600s', 'backendRequest': '3600s'} and 'sessionPersistence' not in convertigo
redirect = routes[NAME + '-convertigo-https-redirect']['spec']
assert redirect['parentRefs'] == [{'name': NAME + '-convertigo', 'sectionName': 'http'}]
assert redirect['rules'][0]['filters'][0]['requestRedirect'] == {'scheme': 'https', 'statusCode': 301}
secret = kinds(created, 'Secret')['convertigo-tls']
assert secret['type'] == 'kubernetes.io/tls' and 'CN=localhost' in certificate(secret)
assert not kinds(created, 'Ingress')
named = docs(*CREATED, '--set', 'publicAddr=c8o.example.com')
assert {l.get('hostname') for l in kinds(named, 'Gateway')[NAME + '-convertigo']['spec']['listeners']} == {'c8o.example.com'}
assert 'DNS:c8o.example.com' in certificate(kinds(named, 'Secret')['convertigo-tls'])
assert 'IP Address:192.0.2.10' in certificate(kinds(docs(*CREATED, '--set', 'publicAddr=192.0.2.10'), 'Secret')['convertigo-tls'])
tuned = docs(*CREATED, '--set', 'gateway.httpsRedirect=false', '--set', 'gateway.rootRedirectEnabled=false',
             '--set', 'baserow.enabled=false', '--set-json', 'gateway.sessionPersistence={"type":"Cookie","sessionName":"route"}',
             '--set-json', 'gateway.infrastructure={"annotations":{"example.com/lb-name":"c8o"}}')
assert list(kinds(tuned, 'HTTPRoute')) == [NAME + '-convertigo']
tuned_rules = kinds(tuned, 'HTTPRoute')[NAME + '-convertigo']['spec']['rules']
assert [r['matches'][0]['path']['value'] for r in tuned_rules] == ['/convertigo']
assert tuned_rules[0]['sessionPersistence'] == {'type': 'Cookie', 'sessionName': 'route'}
assert kinds(tuned, 'Gateway')[NAME + '-convertigo']['spec']['infrastructure'] == {'annotations': {'example.com/lb-name': 'c8o'}}
print('PASS Gateway created by the chart, listeners, routes, redirects and self-signed certificate', flush=True)

# 4. cert-manager provides the certificate: issuer annotation kept, nothing generated.
issued = docs(*CREATED, '--set', 'publicAddr=c8o.example.com', '--set', 'gateway.annotations.cert-manager\\.io/cluster-issuer=letsencrypt-prod')
assert kinds(issued, 'Gateway')[NAME + '-convertigo']['metadata']['annotations'] == {'cert-manager.io/cluster-issuer': 'letsencrypt-prod'}
assert 'convertigo-tls' not in kinds(issued, 'Secret')
assert 'convertigo-tls' not in kinds(docs(*CREATED, '--set', 'tls.selfSigned=false'), 'Secret')

# 5. Existing Gateway: routes attached by parentRefs, no Gateway, no Secret, publicAddr as host name.
attached = docs(*GATEWAY, '--set', 'publicAddr=c8o.example.com', '--set-json',
                'gateway.parentRefs=[{"name":"shared","namespace":"gateway-system","sectionName":"https"}]')
assert not kinds(attached, 'Gateway') and 'convertigo-tls' not in kinds(attached, 'Secret')
assert list(kinds(attached, 'HTTPRoute')) == [NAME + '-convertigo']
spec = kinds(attached, 'HTTPRoute')[NAME + '-convertigo']['spec']
assert spec['parentRefs'] == [{'name': 'shared', 'namespace': 'gateway-system', 'sectionName': 'https'}]
assert spec['hostnames'] == ['c8o.example.com']
assert kinds(docs(*GATEWAY, '--set-json', 'gateway.parentRefs=[{"name":"shared"}]', '--set-json',
                  'gateway.hostnames=["a.example.com","b.example.com"]'), 'HTTPRoute')[NAME + '-convertigo']['spec']['hostnames'] == ['a.example.com', 'b.example.com']
print('PASS existing Gateway by parentRefs, and cert-manager issuer left in charge', flush=True)

# 6. Ingress: self-signed only on request (tls.selfSigned=true) and without issuer annotation.
ingress = docs('--set', 'tls.selfSigned=true', '--set', 'ingress.annotations.cert-manager\\.io/cluster-issuer=null')
assert 'CN=localhost' in certificate(kinds(ingress, 'Secret')['convertigo-tls'])
assert 'convertigo-tls' not in kinds(docs('--set', 'tls.selfSigned=true'), 'Secret')
assert 'convertigo-tls' not in kinds(docs('--set', 'ingress.annotations.cert-manager\\.io/cluster-issuer=null'), 'Secret')
print('PASS Ingress self-signed certificate only on request and without issuer', flush=True)

# 7. Invalid combinations.
assert 'cannot both be true' in fails('--set', 'gateway.enabled=true', '--set', 'gateway.gatewayClassName=eg')
assert 'needs gateway.parentRefs' in fails(*GATEWAY)
assert 'tls.selfSigned must be' in fails(*CREATED, '--set', 'tls.selfSigned=yes')
print('PASS invalid combinations refused', flush=True)


# 8. Stability: an existing Secret of this release is reused as is; one created outside the release is left alone.
class API(BaseHTTPRequestHandler):
    objects = {}
    writes = 0
    groups = {'v1': ['secrets', 'services', 'configmaps', 'persistentvolumeclaims', 'serviceaccounts', 'pods'],
              'apps/v1': ['deployments', 'statefulsets'], 'networking.k8s.io/v1': ['ingresses'],
              'gateway.networking.k8s.io/v1': ['gateways', 'httproutes']}
    kind = {'secrets': 'Secret', 'services': 'Service', 'configmaps': 'ConfigMap', 'persistentvolumeclaims': 'PersistentVolumeClaim',
            'serviceaccounts': 'ServiceAccount', 'pods': 'Pod', 'deployments': 'Deployment', 'statefulsets': 'StatefulSet',
            'ingresses': 'Ingress', 'gateways': 'Gateway', 'httproutes': 'HTTPRoute'}

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
        for version, plurals in self.groups.items():
            if path == ('/api/' if version == 'v1' else '/apis/') + version:
                return self.reply(200, {'kind': 'APIResourceList', 'groupVersion': version, 'resources': [
                    {'name': p, 'singularName': '', 'namespaced': True, 'kind': self.kind[p], 'verbs': ['get', 'list']} for p in plurals]})
        if path in self.objects:
            return self.reply(200, self.objects[path])
        if path.endswith('/secrets'):
            return self.reply(200, {'kind': 'SecretList', 'metadata': {'resourceVersion': '1'}, 'items': []})
        if path.endswith('/namespaces/' + NS):
            return self.reply(200, {'kind': 'Namespace', 'metadata': {'name': NS}})
        self.reply(404, {'kind': 'Status', 'status': 'Failure', 'reason': 'NotFound', 'code': 404})


def existing(owned):
    first = kinds(docs(*CREATED), 'Secret')['convertigo-tls']
    annotations = {'convertigo.com/self-signed': 'true'}
    if owned:
        annotations.update({'meta.helm.sh/release-name': NAME, 'meta.helm.sh/release-namespace': NS})
    return {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/tls', 'data': first['data'],
            'metadata': {'name': 'convertigo-tls', 'namespace': NS, 'annotations': annotations,
                         'labels': {'app.kubernetes.io/managed-by': 'Helm'} if owned else {}}}


server = ThreadingHTTPServer(('127.0.0.1', 0), API)
threading.Thread(target=server.serve_forever, daemon=True).start()
with tempfile.TemporaryDirectory(prefix='gateway-tls-api-') as tmp:
    kube = Path(tmp) / 'kubeconfig'
    kube.write_text(yaml.safe_dump({'apiVersion': 'v1', 'kind': 'Config', 'current-context': 'fixture',
                                    'clusters': [{'name': 'fixture', 'cluster': {'server': 'http://127.0.0.1:%d' % server.server_port}}],
                                    'contexts': [{'name': 'fixture', 'context': {'cluster': 'fixture', 'user': 'fixture', 'namespace': NS}}],
                                    'users': [{'name': 'fixture', 'user': {}}]}))
    kube.chmod(0o600)
    live = dict(os.environ, KUBECONFIG=str(kube), HELM_DRIVER='secret')
    path = '/api/v1/namespaces/%s/secrets/convertigo-tls' % NS
    try:
        API.objects = {path: existing(owned=True)}
        again = kinds(docs(*CREATED, '--dry-run=server', '--disable-openapi-validation', env=live), 'Secret')['convertigo-tls']
        assert again['data'] == API.objects[path]['data']
        API.objects = {path: existing(owned=False)}
        foreign = docs(*CREATED, '--dry-run=server', '--disable-openapi-validation', env=live)
        assert 'convertigo-tls' not in kinds(foreign, 'Secret')
        assert kinds(foreign, 'Gateway')[NAME + '-convertigo']['spec']['listeners'][1]['tls']['certificateRefs'][0]['name'] == 'convertigo-tls'
        assert API.writes == 0
    finally:
        server.shutdown()
print('PASS self-signed certificate kept across upgrades, own certificate left untouched', flush=True)
