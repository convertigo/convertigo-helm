#!/usr/bin/env python3
"""Exercise real Helm upgrades against a loopback-only, GET-only synthetic Kubernetes API.

No production kubeconfig, cluster, account, container or credential is used. The server holds only
fresh test fixtures and simulates lookup and Helm release storage; this is not a runtime test.
"""
import base64
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import tempfile
import threading
from urllib.parse import urlparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / 'stable/convertigo'
BASE = '6d49543'  # Published 8.4.7, before installation bootstrap changes.
NAME, NS, FULL = 'upgrade-fixture', 'fixture', 'upgrade-fixture-convertigo'
KIND = {'Pod':('v1','pods'), 'Secret':('v1','secrets'), 'ConfigMap':('v1','configmaps'),
        'PersistentVolumeClaim':('v1','persistentvolumeclaims'), 'Service':('v1','services'),
        'ServiceAccount':('v1','serviceaccounts'), 'Deployment':('apps/v1','deployments'),
        'StatefulSet':('apps/v1','statefulsets'), 'Ingress':('networking.k8s.io/v1','ingresses')}


def merge(a, b):
    for k,v in b.items():
        if isinstance(v,dict) and isinstance(a.get(k),dict): merge(a[k],v)
        else: a[k]=v
    return a


class API(BaseHTTPRequestHandler):
    objects={}; paths=[]; writes=0
    def log_message(self,*args): pass
    def do_POST(self):
        type(self).writes+=1; self.send_error(405)
    do_PUT=do_PATCH=do_DELETE=do_POST
    def do_GET(self):
        path=urlparse(self.path).path; type(self).paths.append(path)
        if path=='/version': body={'major':'1','minor':'33','gitVersion':'v1.33.0'}
        elif path=='/api': body={'apiVersion':'v1','kind':'APIVersions','versions':['v1']}
        elif path=='/apis':
            body={'apiVersion':'v1','kind':'APIGroupList','groups':[
                {'name':g,'versions':[{'groupVersion':g+'/v1','version':'v1'}],
                 'preferredVersion':{'groupVersion':g+'/v1','version':'v1'}}
                for g in ['apps','networking.k8s.io']]}
        elif path in ['/api/v1','/apis/apps/v1','/apis/networking.k8s.io/v1']:
            version=path.removeprefix('/api/').removeprefix('/apis/')
            body={'apiVersion':'v1','kind':'APIResourceList','groupVersion':version,'resources':[
                {'name':plural,'singularName':'','namespaced':True,'kind':kind,'verbs':['get','list']}
                for kind,(ver,plural) in KIND.items() if ver==version]}
        elif path in self.objects: body=self.objects[path]
        elif path.endswith('/secrets'):
            body={'apiVersion':'v1','kind':'SecretList','metadata':{'resourceVersion':'1'},
                  'items':[v for k,v in self.objects.items() if k.startswith(path+'/') and v.get('type')=='helm.sh/release.v1']}
        elif path.endswith('/namespaces/'+NS): body={'apiVersion':'v1','kind':'Namespace','metadata':{'name':NS}}
        else:
            self.send_response(404); self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'apiVersion':'v1','kind':'Status','status':'Failure','reason':'NotFound','code':404}).encode());return
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps(body).encode())


def path_for(d):
    v,p=KIND[d['kind']]
    return ('/api/'+v if v=='v1' else '/apis/'+v)+'/namespaces/'+NS+'/'+p+'/'+d['metadata']['name']


def call(command, env):
    p=subprocess.run(command,env=env,capture_output=True,text=True)
    if p.returncode:
        # Keep command output private; no rendered values in assertion/log messages.
        failure=Path(tempfile.gettempdir())/'helm-upgrade-fixture-failure-private.txt'
        failure.write_text(p.stdout+p.stderr); failure.chmod(0o600)
        raise AssertionError('Helm command failed; inspect the private temporary failure file')
    return p.stdout


def docs(text): return [d for d in yaml.safe_load_all(text) if d]
def pod(d): return d['spec']['template']['spec']
# C8O_COUCHDB_UUID is a new, non-credential variable of CouchDB, checked below and in tests/couchdb-uuid.py.
def environment(d): return [e for e in pod(d)['containers'][0].get('env',[]) if e['name']!='C8O_COUCHDB_UUID']
def byname(ds): return {(d['kind'],d['metadata']['name']):d for d in ds}


with tempfile.TemporaryDirectory(prefix='helm-upgrade-credentials-') as tmp:
    directory=Path(tmp)
    archive=subprocess.check_output(['git','archive',BASE,'stable/convertigo'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t: t.extractall(directory/'baseline',filter='data')
    old=directory/'baseline/stable/convertigo'
    oldvalues=yaml.safe_load((old/'values.yaml').read_text())
    # All account/password material is synthesized at test time. No historical password is used.
    configured=merge(json.loads(json.dumps(oldvalues)), {
        'publicAddr':'fixture.invalid', 'redis':{'enabled':True,'auth':{'enabled':True,'password':secrets.token_hex(24)}},
        'timescaledb':{'password':secrets.token_hex(24),'billing_password':secrets.token_hex(24)},
        'baserow':{'baserow_password':secrets.token_hex(24)},
        'couchdb':{'password':secrets.token_hex(24)},
        'additionalJavaOpts':['-Dconvertigo.engine.crypto.passphrase='+secrets.token_hex(24),
                              '-Dconvertigo.engine.admin.password='+secrets.token_hex(24)]})
    server=ThreadingHTTPServer(('127.0.0.1',0),API)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    kube=directory/'kubeconfig'; kube.write_text(yaml.safe_dump({'apiVersion':'v1','kind':'Config',
        'clusters':[{'name':'fixture','cluster':{'server':'http://127.0.0.1:'+str(server.server_port)}}],
        'contexts':[{'name':'fixture','context':{'cluster':'fixture','user':'fixture','namespace':NS}}],
        'current-context':'fixture','users':[{'name':'fixture','user':{}}]}));kube.chmod(0o600)
    env=dict(os.environ,KUBECONFIG=str(kube),HELM_DRIVER='secret')
    def template(chart,values,upgrade=False,live=False):
        values=json.loads(json.dumps(values))
        if chart==CHART and not upgrade:
            values.setdefault('nocodestudio',{}).setdefault('version','fixture-published-release')
        f=directory/'values.yaml';f.write_text(yaml.safe_dump(values));f.chmod(0o600)
        return call(['helm','template',NAME,str(chart),'-n',NS,'-f',str(f),
                     *(['--is-upgrade'] if upgrade else []),
                     *(['--dry-run=server','--disable-openapi-validation'] if live else [])],env)
    try:
        for with_secret, minimal_config, redis_auth in [(False,False,True),(True,False,True),(False,True,True),(False,True,False)]:
            API.objects={};API.paths=[];API.writes=0
            values=json.loads(json.dumps(configured))
            values['redis']['auth']['enabled']=redis_auth
            if with_secret:
                # The released chart consumes CouchDB lookup and Redis secretKeyRefs.
                values['couchdb'].update(existingSecret='fixture-couch',existingSecretUsernameKey='username',existingSecretPasswordKey='password')
                values['redis']['auth'].update(existingSecret='fixture-redis')
                for name,data in [('fixture-couch',{'username':'fixture-admin','password':secrets.token_hex(24)}),
                                  ('fixture-redis',{'redis-password':secrets.token_hex(24)})]:
                    obj={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':NS},'type':'Opaque',
                         'data':{k:base64.b64encode(v.encode()).decode() for k,v in data.items()}}
                    API.objects[path_for(obj)]=obj
            baseline=template(old,values,live=with_secret);before=docs(baseline)
            for obj in before:
                if obj['kind'] in KIND: API.objects[path_for(obj)]=obj
            release={'name':NAME,'namespace':NS,'version':1,
                     'info':{'status':'deployed','description':'Synthetic 8.4.7 fixture'},
                     'chart':{'metadata':yaml.safe_load((old/'Chart.yaml').read_text()),'values':oldvalues},
                     'config':({'publicAddr':'fixture.invalid','redis':{'enabled':True,'auth':{'enabled':redis_auth}}} if minimal_config else values),'manifest':baseline}
            data=base64.b64encode(gzip.compress(json.dumps(release).encode())).decode()
            secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'sh.helm.release.v1.'+NAME+'.v1','namespace':NS,
                'labels':{'owner':'helm','name':NAME,'status':'deployed','version':'1'}},'type':'helm.sh/release.v1',
                'data':{'release':base64.b64encode(data.encode()).decode()}}
            API.objects[path_for(secret)]=secret
            prior_objects=json.loads(json.dumps(API.objects))
            # Real helm upgrade, server dry-run only, against our loopback fixture API.
            result=call(['helm','upgrade',NAME,str(CHART),'-n',NS,'--reuse-values',
                         '--dry-run=server','--disable-openapi-validation','-o','json'],env)
            rendered=json.loads(result)['manifest'];after=docs(rendered);b=byname(before);a=byname(after)
            ordinary=docs(json.loads(call(['helm','upgrade',NAME,str(CHART),'-n',NS,
                '--dry-run=server','--disable-openapi-validation','-o','json'],env))['manifest'])
            ordinary_byname=byname(ordinary)
            for key,obj in b.items():
                if obj['kind']=='Deployment':
                    added=[e for e in pod(ordinary_byname[key])['containers'][0].get('env',[]) if e['name']=='C8O_COUCHDB_UUID']
                    assert added==([] if not key[1].endswith('-cdb') else [{'name':'C8O_COUCHDB_UUID','valueFrom':{'configMapKeyRef':{'name':FULL+'-cdb-uuid','key':'uuid'}}}])
                    assert environment(ordinary_byname[key])==environment(obj), 'Ordinary upgrade changed established credentials'
                    if obj['metadata']['name'].endswith('-timescale'):
                        assert pod(ordinary_byname[key])['containers'][0]['image']==pod(obj)['containers'][0]['image'],'Ordinary upgrade changed database image'
            assert not any(d['kind']=='Secret' for d in ordinary), 'Ordinary upgrade generated a Secret'
            for key,obj in b.items():
                if obj['kind']=='Deployment':
                    if obj['metadata']['name'].endswith('-timescale'):
                        assert pod(a[key])['containers'][0]['image']==pod(obj)['containers'][0]['image'],'Database image changed implicitly'
                    assert environment(a[key])==environment(obj),'Existing component environment changed: '+obj['metadata']['name']
            assert not any(d['kind']=='Secret' for d in after),'An upgrade generated a new Secret'
            for key,obj in a.items():
                if obj['kind']=='Deployment':
                    p=pod(obj)
                    assert not any(c['name']=='baserow-setup' for c in p.get('initContainers',[]))
                    assert not {'admin-credential','installation-credentials'} & {v['name'] for v in p.get('volumes',[])}
            script=next(d['data']['installCarFiles.sh'] for d in after if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
            assert 'PRESERVE_CREDENTIALS="true"' in script
            workspace=directory/('workspace-'+str(with_secret)+str(minimal_config)+str(redis_auth))
            conf=workspace/'configuration';conf.mkdir(parents=True)
            (workspace/'projects/fixture').mkdir(parents=True)
            (workspace/'.chart-install-complete').write_text('v2:nocode=true:'+values['nocodestudio']['version']+':install=true:metering=false')
            properties=conf/'engine.properties'
            properties.write_text(('crypto.passphrase='+secrets.token_hex(24)+'\n' if redis_auth else '')+'admin.username=fixture\nadmin.password='+hashlib.sha512(b'admin' if with_secret else secrets.token_bytes(24)).hexdigest()+'\n')
            symbols=conf/'global_symbols.properties';symbols.write_text('fixture.symbol='+secrets.token_hex(24)+'\n')
            roles=conf/'user_roles.db';roles.write_bytes(secrets.token_bytes(64))
            originals={f:(f.read_bytes(),f.stat().st_mode) for f in [properties,symbols,roles]}
            tools=directory/'tools';tools.mkdir(exist_ok=True)
            flock=tools/'flock';flock.write_text('#!'+sys.executable+'\nimport fcntl,sys\nfcntl.flock(int(sys.argv[-1]),fcntl.LOCK_EX)\n');flock.chmod(0o755)
            for tool in ['java','curl','sha512sum']:
                stub=tools/tool;stub.write_text('#!/bin/sh\nexit 99\n');stub.chmod(0o755)
            installer=directory/'upgrade-installer.sh';installer.write_text(script)
            run=subprocess.run(['bash',str(installer)],env=dict(os.environ,WORKSPACE=str(workspace),
                PATH=str(tools)+os.pathsep+os.environ['PATH']),capture_output=True,text=True)
            assert run.returncode==0,'Existing workspace initializer failed'
            assert not (conf/'.chart-crypto-state').exists(),'Existing workspace received a new credential marker'
            assert all(f.read_bytes()==data and f.stat().st_mode==mode for f,(data,mode) in originals.items()), 'Existing workspace identity changed'
            assert API.objects==prior_objects and API.writes==0,'Fixture API was mutated'
            assert any('/deployments/' in p for p in API.paths),'Workload lookup was not exercised'
            print('PASS real Helm server-dry-run upgrade and untouched workspace:', 'existing Secrets' if with_secret else 'no existing Secret', 'minimal saved values' if minimal_config else 'full saved values', 'AUTH' if redis_auth else 'no AUTH')
        # Also cover a post-bootstrap upgrade: retain all bytes, including extra credential keys.
        API.objects={};API.paths=[]
        fresh=docs(template(CHART,{},False,False))
        for obj in fresh:
            if obj['kind'] in KIND: API.objects[path_for(obj)]=obj
        for obj in API.objects.values():
            if obj['kind']=='Secret': obj['data']['fixture-extra-key']=base64.b64encode(secrets.token_bytes(24)).decode()
        secrets_before={k:v['data'] for k,v in API.objects.items() if v['kind']=='Secret'}
        upgraded=docs(template(CHART,{'image':{'jxmx':'1536'},'timescaledb':{'password':secrets.token_hex(24)},
            'baserow':{'baserow_password':secrets.token_hex(24)},'crypto':{'existingSecret':'different-phrase'},
            'admin':{'existingSecret':'different-admin'}},True,True))
        for d in upgraded:
            if d['kind']=='Secret': assert d['data']==secrets_before[path_for(d)]
        assert len([d for d in upgraded if d['kind']=='Secret'])==len(secrets_before)-1
        old_byname=byname(fresh)
        for d in upgraded:
            if d['kind']=='Deployment':
                expected=environment(old_byname[(d['kind'],d['metadata']['name'])])
                if d['metadata']['name'].endswith('-convertigo'):
                    expected=json.loads(json.dumps(expected))
                    next(e for e in expected if e['name']=='JXMX')['value']='1536'
                assert environment(d)==expected
        unchanged=docs(template(CHART,{},True,True))
        assert {path_for(d):d['data'] for d in unchanged if d['kind']=='Secret'}==secrets_before
        print('PASS generated Secrets reused byte-for-byte; changed credential values cannot rotate existing component environments')
        # Custom phrases are supplied explicitly and retained without replacing data on future upgrades.
        API.objects={}
        custom=docs(template(CHART,{'crypto':{'passphrase':secrets.token_hex(24)}},False,False))
        for obj in custom:
            if obj['kind'] in KIND: API.objects[path_for(obj)]=obj
        custom_data={path_for(d):d['data'] for d in custom if d['kind']=='Secret'}
        assert len(custom_data)==3
        for configuration in [{},{'crypto':{'passphrase':secrets.token_hex(24)}}]:
            after=docs(template(CHART,configuration,True,True))
            assert {path_for(d):d['data'] for d in after if d['kind']=='Secret'}==custom_data
        print('PASS custom phrase Secret is explicitly supplied once and retained unchanged on upgrade')

    finally:
        server.shutdown();server.server_close();thread.join()
