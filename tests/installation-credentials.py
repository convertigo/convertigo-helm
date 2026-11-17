#!/usr/bin/env python3
"""Offline renders and optional Java-library fixture checks; never start an engine or query a cluster."""
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import tempfile
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine-lib', type=Path, help='Directory with the matching engine/dependencies JARs')
parser.add_argument('--java', default='java')
args = parser.parse_args()
CHART = Path(__file__).resolve().parents[1] / 'stable/convertigo'


def render(*options, failure=False):
    p = subprocess.run(['helm', 'template', 'credentials', str(CHART), '--set-string', 'nocodestudio.version=fixture-published-release', *options],
                       capture_output=True, text=True, env=dict(os.environ, KUBECONFIG='/dev/null'))
    if failure:
        assert p.returncode != 0, 'Unsafe upgrade was accepted'
        return None
    assert p.returncode == 0, 'Render failed'
    return [x for x in yaml.safe_load_all(p.stdout) if x]


def bundle(docs):
    return next(x for x in docs if x['kind'] == 'Secret' and x['metadata']['name'].endswith('-credentials'))


default = render()
a = bundle(default)['data']; b = bundle(render())['data']
assert len(a) == 6 and all(len(base64.b64decode(v)) == 64 for v in a.values())
assert all(a[k] != b[k] for k in a) and len(set(a.values())) == len(a)
assert 'crypto-passphrase' not in a
assert not any(d['kind']=='Secret' and d['metadata']['name'].endswith('-crypto') for d in default)
fixture_phrase = secrets.token_hex(24)
custom_value = render('--set-string', 'crypto.passphrase='+fixture_phrase)
custom_secret = next(d for d in custom_value if d['kind']=='Secret' and d['metadata']['name'].endswith('-crypto'))
assert base64.b64decode(custom_secret['data']['crypto-passphrase']).decode()==fixture_phrase
external_phrase = render('--set', 'crypto.existingSecret=fixture-crypto', '--set', 'crypto.passphraseKey=phrase')
assert not any(d['kind']=='Secret' and d['metadata']['name'].endswith('-crypto') for d in external_phrase)
for ds, opted in [(default,False),(render('--set','crypto.engineCompatibilityConfirmed=true'),False),
                  (render('--set','credentials.existingSecret=fixture-installation'),False),
                  (custom_value,True),(external_phrase,True)]:
    pod=next(d['spec']['template']['spec'] for d in ds if d['kind']=='Deployment' and d['metadata']['name'].endswith('-convertigo'))
    sources=next(v for v in pod['volumes'] if v['name']=='installation-credentials')['projected']['sources']
    phrase_sources=[x['secret'] for x in sources if any(i['path']=='crypto-passphrase' for i in x['secret'].get('items',[]))]
    assert bool(phrase_sources)==opted
    opts=next(e['value'] for e in pod['containers'][0]['env'] if e['name']=='JAVA_OPTS')
    assert 'crypto.passphrase' not in opts and fixture_phrase not in opts
    assert not opted or not phrase_sources[0].get('optional',False)
    script=next(d['data']['installCarFiles.sh'] for d in ds if d['kind']=='ConfigMap' and 'installCarFiles.sh' in d.get('data',{}))
    assert ('BOOTSTRAP_CUSTOM_PASSPHRASE="'+str(opted).lower()+'"') in script
legacy_upgrade = render('--is-upgrade')
assert not any(x['kind'] == 'Secret' for x in legacy_upgrade)
# Historical values and JVM settings remain accepted; no adoption flag is required.
render('--is-upgrade', '--set', 'timescaledb.password=fixture',
       '--set-string', 'additionalJavaOpts[0]=-Dconvertigo.engine.crypto.passphrase=fixture')
provided = render('--is-upgrade', '--set', 'credentials.existingSecret=prior-credentials',
                  '--set', 'admin.existingSecret=prior-admin')
assert not any(x['kind'] == 'Secret' for x in provided)
render('--set', 'couchdb.existingSecretNamespace=another-namespace', failure=True)
for d in default:
    if d['kind'] != 'Deployment':
        continue
    pod = d['spec']['template']['spec']
    if d['metadata']['name'].endswith('-convertigo'):
        main = pod['containers'][0]
        assert not any('PASSWORD' in x['name'] for x in main['env'])
        java_opts = next(x['value'] for x in main['env'] if x['name'] == 'JAVA_OPTS')
        assert 'fullsync.couch.password=' not in java_opts and 'jdbc.password=' not in java_opts
        assert not {'installation-credentials', 'admin-credential'} & {x['name'] for x in main['volumeMounts']}
    if d['metadata']['name'].endswith('-br'):
        assert pod['initContainers'][0]['name'] == 'baserow-setup'
        assert 'baserow-admin' not in {x['name'] for x in pod['containers'][0]['volumeMounts']}
        assert next(x for x in pod['initContainers'][0]['env'] if x['name'] == 'BOOTSTRAP_PUBLIC_SIGNUP')['value'] == 'false'
source = (CHART / 'templates/configmapInstallCarFiles.yaml').read_text()
assert '.secret=' not in source
assert 'lookup "v1" "Secret"' in (CHART / 'templates/installation-secret.yaml').read_text()
assert 'convertigo.io/credential-schema: v1' in (CHART / 'templates/C8OpersistentVolumeClaim.yaml').read_text()
print('PASS independent generated credentials, file-only engine bootstrap, guarded upgrades and Baserow init')
if args.engine_lib is None:
    raise SystemExit(0)
jars = [args.engine_lib / 'convertigo-engine-8.4.7.jar', args.engine_lib / 'dependencies-8.4.7.jar']
assert all(p.exists() for p in jars), 'Matching 8.4.7 library fixtures are required'
classpath = os.pathsep.join(map(str, jars))
initializer = CHART / 'files/bootstrap/InitializeWorkspace.java'
with tempfile.TemporaryDirectory(prefix='installation-crypto-fixture-') as directory:
    root = Path(directory); inputs = root / 'credentials'; inputs.mkdir()
    values = {k:secrets.token_hex(32) for k in [*a,'crypto-passphrase']}
    for key,value in values.items():
        p = inputs/key; p.write_text(value); p.chmod(0o600)
    def call(workspace, action, *, adopt=False, fail=False, compatible=True, custom=True):
        e = dict(os.environ, WORKSPACE=str(workspace), INSTALLATION_CREDENTIALS_DIR=str(inputs),
                 BOOTSTRAP_ADOPT_EXISTING=str(adopt).lower(), BOOTSTRAP_CUSTOM_PASSPHRASE=str(custom).lower(), BOOTSTRAP_REDIS_PASSWORD='true', BOOTSTRAP_CRYPTO_COMPATIBLE=str(compatible).lower())
        p = subprocess.run([args.java,'-Xmx256m','--class-path',classpath,str(initializer),action],env=e,capture_output=True,text=True)
        assert (p.returncode != 0) if fail else (p.returncode == 0), 'Unexpected Java initializer status'
    blocked = root/'unconfirmed'; blocked.mkdir()
    call(blocked,'prepare',compatible=False,fail=True)
    assert not (blocked/'configuration/engine.properties').exists()
    first = root/'fresh'; first.mkdir()
    call(first,'prepare'); properties = first/'configuration/engine.properties'
    assert ('crypto.passphrase='+values['crypto-passphrase']) in properties.read_text()
    assert 'log4j.logger.cems.Context=WARN' in properties.read_text()
    (first/'configuration/global_symbols.properties').write_text('fixture=preserved\n')
    call(first,'symbols')
    symbols=first/'configuration/global_symbols.properties'; cipher=symbols.read_text()
    assert values['baserow-admin-password'] not in cipher and values['billing-password'] not in cipher
    assert 'lib_baserow.password.secret=x' in cipher and 'C8OBilling.password.secret=x' in cipher
    assert properties.stat().st_mode & 0o777 == 0o600
    # A changed supplied passphrase or credential never modifies an initialized workspace.
    prior=properties.read_bytes(); old=values['crypto-passphrase']; (inputs/'crypto-passphrase').write_text(secrets.token_hex(32))
    call(first,'prepare',fail=True); assert properties.read_bytes()==prior
    (inputs/'crypto-passphrase').write_text(old)
    old_pwd=values['baserow-admin-password']; (inputs/'baserow-admin-password').write_text(secrets.token_hex(32))
    call(first,'prepare',fail=True); assert properties.read_bytes()==prior
    prior_symbols=symbols.read_bytes(); call(first,'symbols',fail=True); assert symbols.read_bytes()==prior_symbols
    (inputs/'baserow-admin-password').write_text(old_pwd)
    # Existing workspaces never receive any credential or crypto write, even without adoption.
    legacy=root/'legacy'; (legacy/'configuration').mkdir(parents=True)
    legacy_phrase=secrets.token_hex(32)
    lp=legacy/'configuration/engine.properties'; lp.write_text('crypto.passphrase='+legacy_phrase+'\n')
    ls=legacy/'configuration/global_symbols.properties'; ls.write_bytes(b'fixture.legacy=value\n')
    before=ls.read_bytes(); prior_properties=lp.read_bytes(); call(legacy,'prepare',compatible=False)
    call(legacy,'prepare',adopt=True,compatible=False); call(legacy,'symbols',adopt=True)
    assert lp.read_bytes()==prior_properties
    assert 'crypto.passphrase='+legacy_phrase in lp.read_text() and ls.read_bytes()==before
    # An old workspace with no explicit passphrase keeps that absence (engine's existing setting).
    absent=root/'legacy-implicit'; (absent/'configuration').mkdir(parents=True)
    (absent/'configuration/engine.properties').write_text('fixture=value\n')
    call(absent,'prepare',adopt=True)
    assert 'crypto.passphrase=' not in (absent/'configuration/engine.properties').read_text()
    # Resume between persisted identity and engine configuration.
    retry=root/'retry'; (retry/'configuration').mkdir(parents=True)
    (retry/'configuration/.chart-crypto-state').write_text('mode=new\nfingerprint='+hashlib.sha256(old.encode()).hexdigest()+'\n')
    call(retry,'prepare'); assert 'crypto.passphrase='+old in (retry/'configuration/engine.properties').read_text()
    # Round-trip only freshly generated fixture data, never any historical or deployed symbol.
    check=root/'RoundTrip.java'
    check.write_text('''import java.nio.file.*; import java.util.*;
import com.twinsoft.convertigo.engine.util.Crypto2;
class RoundTrip { public static void main(String[] a) throws Exception {
Properties p=new Properties(); try(var in=Files.newInputStream(Path.of(a[0]))){p.load(in);}
String key=Files.readString(Path.of(a[1]));
String expected=Files.readString(Path.of(a[2]));
if(!expected.equals(Crypto2.decodeFromHexString(key,p.getProperty("lib_baserow.password.secret")))) System.exit(1);
if(!Files.readString(Path.of(a[3])).equals(Crypto2.decodeFromHexString(key,p.getProperty("C8OBilling.password.secret")))) System.exit(1);
}}''')
    p=subprocess.run([args.java,'-Xmx256m','--class-path',classpath,str(check),str(symbols),str(inputs/'crypto-passphrase'),str(inputs/'baserow-admin-password'),str(inputs/'billing-password')],capture_output=True,text=True)
    assert p.returncode==0,'Fixture Crypto2 round-trip failed'
    # Default initialization works without any custom phrase file or compatibility opt-in.
    (inputs/'crypto-passphrase').unlink()
    standard=root/'default-mode'; standard.mkdir()
    call(standard,'prepare',custom=False,compatible=False)
    ep=standard/'configuration/engine.properties'
    assert 'crypto.passphrase' not in ep.read_text()
    call(standard,'symbols',custom=False,compatible=False)
    default_symbols=standard/'configuration/global_symbols.properties'
    # Independently recover the public library default via disassembly, without initializing the enum.
    javap=str(Path(args.java).with_name('javap')) if '/' in args.java else 'javap'
    metadata=subprocess.run([javap,'-c','-p','-classpath',classpath,
        'com.twinsoft.convertigo.engine.EnginePropertiesManager$PropertyName'],capture_output=True,text=True,check=True)
    lines=metadata.stdout.splitlines();index=next(i for i,l in enumerate(lines) if l.strip().endswith('// String crypto.passphrase'))
    expected_default=lines[index+1].split('// String ',1)[1].strip()
    default_file=root/'library-default-private';default_file.write_text(expected_default);default_file.chmod(0o600)

    p=subprocess.run([args.java,'-Xmx256m','--class-path',classpath,str(check),str(default_symbols),str(default_file),
        str(inputs/'baserow-admin-password'),str(inputs/'billing-password')],capture_output=True,text=True)
    assert p.returncode==0,'Default-mode Crypto2 fixture round-trip failed'
    trace=subprocess.run([args.java,'-Xmx256m','-Xlog:class+init=info','--class-path',classpath,str(initializer),'symbols'],
        env=dict(os.environ,WORKSPACE=str(standard),INSTALLATION_CREDENTIALS_DIR=str(inputs),BOOTSTRAP_CUSTOM_PASSPHRASE='false'),capture_output=True,text=True)
    assert trace.returncode==0,'Default-mode initializer tracing failed'
    assert not re.search(r"Initializing .*com[./]twinsoft[./]convertigo[./]engine[./]Engine(?:'|\s)",trace.stdout)
    assert not re.search(r"Initializing .*EnginePropertiesManager[$]PropertyName",trace.stdout)

    # An unselected file is ignored; merely having a phrase in the general bundle is not opt-in.
    (inputs/'crypto-passphrase').write_text(secrets.token_hex(32))
    call(standard,'prepare',custom=False,compatible=False)
    assert ep.read_bytes()!=b'' and 'crypto.passphrase' not in ep.read_text()
    # A mode change during interrupted initialization is refused before credentials are written.
    before_change=ep.read_bytes()
    call(standard,'prepare',custom=True,fail=True)
    assert ep.read_bytes()==before_change
    call(first,'prepare',custom=False,fail=True); assert properties.read_bytes()==prior
    # Explicit Secret mode cannot silently fall back to the default if the mounted key is missing.
    (inputs/'crypto-passphrase').unlink()
    missing=root/'missing-custom';missing.mkdir()
    call(missing,'prepare',custom=True,fail=True)
    assert not (missing/'configuration/engine.properties').exists()

print('PASS real Crypto2 default/custom round-trips, explicit opt-in, missing Secret refusal and unchanged legacy workspaces')
