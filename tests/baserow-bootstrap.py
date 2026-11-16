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
import sys
import tempfile
import types

SOURCE = Path(__file__).resolve().parents[1] / 'stable/convertigo/files/bootstrap/baserow-admin.py'
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
