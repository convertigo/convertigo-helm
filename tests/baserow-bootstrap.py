#!/usr/bin/env python3
"""Exercise the bootstrap policy with fake Django models; no database or instance is accessed."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import stat
import subprocess
import sys
import tempfile
import types
import yaml

CHART = Path(__file__).resolve().parents[1] / 'stable/convertigo'
SOURCE = CHART / 'files/bootstrap/baserow-admin.py'
rendered = subprocess.run(['helm', 'template', 'fixture', str(CHART)],
                          env=dict(os.environ, KUBECONFIG='/dev/null'), capture_output=True, text=True, check=True)
init_script = next(d['data']['baserow-init.sh'] for d in yaml.safe_load_all(rendered.stdout)
                   if d and d['kind']=='ConfigMap' and 'baserow-init.sh' in d.get('data', {}))
ownership_line = next(line for line in init_script.splitlines() if 'chown "${DOCKER_USER' in line)
assert init_script.index(ownership_line) < init_script.index('/baserow.sh backend-cmd wait_for_db')
DB = {'users': [], 'settings': {'allow_new_signups': True, 'allow_signups_via_workspace_invitations': True, 'show_admin_signup_page': True}, 'created': 0}


class User:
    def __init__(self, email, password, staff=True):
        self.email=email; self.password_hash=hashlib.sha256(password.encode()).hexdigest()
        self.is_staff=staff; self.is_active=True
    def check_password(self, value):
        return self.password_hash == hashlib.sha256(value.encode()).hexdigest()


class Users:
    def exists(self): return bool(DB['users'])
    def filter(self, **kwargs):
        matches=[x for x in DB['users'] if x.email == kwargs['email']]
        return types.SimpleNamespace(first=lambda: matches[0] if matches else None)


class UserHandler:
    def force_create_user(self, *, email, name, password, is_staff):
        x=User(email,password,is_staff); DB['users'].append(x); DB['created']+=1; return x


class Settings:
    def __init__(self): self.__dict__.update(DB['settings'])
    def save(self, update_fields):
        for key in update_fields: DB['settings'][key]=getattr(self,key)


@contextlib.contextmanager
def atomic():
    before=copy.deepcopy(DB)
    try: yield
    except Exception:
        DB.clear(); DB.update(before); raise


@contextlib.contextmanager
def cursor():
    def execute(sql): assert sql == 'SELECT pg_advisory_xact_lock(814701)'
    yield types.SimpleNamespace(execute=execute)


for name in ['django','django.contrib','django.contrib.auth','django.db','baserow','baserow.core','baserow.core.handler','baserow.core.user','baserow.core.user.handler','baserow.core.user.utils']:
    sys.modules[name]=types.ModuleType(name)
sys.modules['django.contrib.auth'].get_user_model=lambda: types.SimpleNamespace(objects=Users())
sys.modules['django.db'].connection=types.SimpleNamespace(cursor=cursor)
sys.modules['django.db'].transaction=types.SimpleNamespace(atomic=atomic)
sys.modules['baserow.core.handler'].CoreHandler=lambda: types.SimpleNamespace(get_settings=lambda: Settings())
sys.modules['baserow.core.user.handler'].UserHandler=UserHandler
sys.modules['baserow.core.user.utils'].normalize_email_address=lambda x:x.strip().lower()

with tempfile.TemporaryDirectory(prefix='baserow-admin-fixture-') as directory:
    root=Path(directory); credential=root/'credential'; password=secrets.token_hex(32); credential.write_text(password); credential.chmod(0o600)
    email='admin@example.invalid'
    def reset():
        DB.clear(); DB.update(users=[],settings={'allow_new_signups':True,'allow_signups_via_workspace_invitations':True,'show_admin_signup_page':True},created=0)
    def execute(data, *, adopt=False, fail=False):
        old=dict(os.environ)
        os.environ.update(DATA_DIR=str(data), BASEROW_ADMIN_PASSWORD_FILE=str(credential),
                          BOOTSTRAP_BASEROW_EMAIL=email, BOOTSTRAP_ADOPT_EXISTING=str(adopt).lower(), BOOTSTRAP_PUBLIC_SIGNUP='false')
        try:
            try:runpy.run_path(str(SOURCE),run_name='__main__')
            except RuntimeError:
                assert fail, 'Unexpected bootstrap refusal'; return
            assert not fail, 'Bootstrap should have refused this state'
        finally:
            os.environ.clear(); os.environ.update(old)
    # 0555 reproduces the EACCES that UID 9999 receives on a root-owned 0755 mount,
    # without requiring root on the test host. Identity/chown adapters exercise the
    # rendered shell command; actual UID/GID ownership needs a Linux volume test.
    tools=root/'ownership-tools';tools.mkdir();calls=root/'ownership-calls'
    identity=tools/'id';identity.write_text('#!/bin/sh\nprintf "%s\\n" "$FIXTURE_UID"\n');identity.chmod(0o755)
    chown=tools/'chown';chown.write_text('#!'+sys.executable+'''
import os,sys,pathlib,stat
assert len(sys.argv)==3, 'Only the data directory may change ownership'
assert sys.argv[1]==os.environ['EXPECTED_OWNER']
p=pathlib.Path(sys.argv[2]);assert p==pathlib.Path(os.environ['DATA_DIR'])
with open(os.environ['OWNER_CALLS'],'a') as f:f.write('root-only\\n')
# Model write access acquired by the Baserow owner; leave every child untouched.
p.chmod(stat.S_IMODE(p.stat().st_mode)|stat.S_IWUSR)
''');chown.chmod(0o755)
    def prepare_owner(data, *, uid='0', owner=None):
        e=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],DATA_DIR=str(data),
               FIXTURE_UID=uid,OWNER_CALLS=str(calls),EXPECTED_OWNER=(owner or 'baserow_docker_user')+':')
        e.pop('DOCKER_USER',None)
        if owner is not None:e['DOCKER_USER']=owner
        subprocess.run(['bash','-eu','-c',ownership_line],env=e,check=True,capture_output=True,text=True)
    reset();block=root/'fresh-block';block.mkdir();child=block/'existing-child';child.write_text('keep');child.chmod(0o640)
    block.chmod(0o555)
    try:
        if os.geteuid()!=0:
            try:execute(block)
            except PermissionError as error:
                assert Path(error.filename)==block/'.chart-admin-bootstrap.lock'
            else:raise AssertionError('Non-writable data root must reject the bootstrap lock')
            assert not (block/'.chart-admin-bootstrap.lock').exists() and DB['created']==0
        prepare_owner(block,uid='9999')
        assert not calls.exists() and stat.S_IMODE(block.stat().st_mode)==0o555
        prepare_owner(block)
        assert stat.S_IMODE(block.stat().st_mode)==0o755
        execute(block)
        assert DB['created']==1 and (block/'.chart-admin-bootstrap').exists()
        original_marker=(block/'.chart-admin-bootstrap').read_bytes()
        original_identity=DB['users'][0].password_hash
        before_child=(child.read_bytes(),stat.S_IMODE(child.stat().st_mode))
        prepare_owner(block,owner='fixture-baserow')
        execute(block)
        assert DB['created']==1 and DB['users'][0].password_hash==original_identity
        assert (block/'.chart-admin-bootstrap').read_bytes()==original_marker
        assert (child.read_bytes(),stat.S_IMODE(child.stat().st_mode))==before_child
        assert calls.read_text().splitlines()==['root-only','root-only']
    finally:block.chmod(0o755)
    reset()
    print('PASS non-writable block-root regression, root-only targeted ownership and initialized-volume retry')
    fresh=root/'fresh'; execute(fresh)
    assert DB['created']==1 and DB['users'][0].is_staff and not any(DB['settings'].values())
    assert (fresh/'.chart-admin-bootstrap').stat().st_mode & 0o777 == 0o600
    original=DB['users'][0].password_hash; execute(fresh)
    assert DB['created']==1 and DB['users'][0].password_hash==original
    credential.write_text(secrets.token_hex(32)); execute(fresh,fail=True)
    assert DB['users'][0].password_hash==original; credential.write_text(password)
    reset(); DB['users']=[User(email,password)]; legacy=root/'legacy'; before=copy.deepcopy(DB['settings'])
    execute(legacy,fail=True); assert DB['settings']==before and not (legacy/'.chart-admin-bootstrap').exists()
    execute(legacy,adopt=True); assert DB['created']==0 and DB['users'][0].password_hash==original
    assert not any(DB['settings'].values())
    reset(); DB['users']=[User('someone@example.invalid',password)]; execute(root/'other',adopt=True,fail=True)
    assert len(DB['users'])==1 and DB['created']==0 and all(DB['settings'].values())
    reset(); DB['users']=[User(email,password,False)]; execute(root/'nonstaff',adopt=True,fail=True)
    assert DB['users'][0].is_staff is False and all(DB['settings'].values())
    reset(); pending=root/'pending';pending.mkdir();(pending/'.chart-admin-bootstrap').write_text(json.dumps({'email':email,'fingerprint':hashlib.sha256(password.encode()).hexdigest(),'phase':'pending'}))
    execute(pending); assert DB['created']==1 and json.loads((pending/'.chart-admin-bootstrap').read_text())['phase']=='complete'
    reset(); execute(pending,fail=True); assert DB['created']==0
print('PASS first admin before service, closed signup, retries, unchanged existing accounts and refused credential mismatch')
