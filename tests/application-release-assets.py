#!/usr/bin/env python3
"""Explicit public-metadata/HEAD preflight; no install, credentials, container or asset extraction."""
import argparse
import json
import re
import sys
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ASSETS=('C8Oforms.car','c8oforms_standalone.tar.gz','no_code_studio_and_dependencies.zip')
p=argparse.ArgumentParser(description=__doc__)
source=p.add_mutually_exclusive_group(required=True)
source.add_argument('--version',help='Exact public C8oForms release tag; no fallback is selected')
source.add_argument('--values',type=Path,help='Read the quoted nocodestudio.version from chart defaults for publication')
args=p.parse_args()
if args.values:
    # Read only this simple default-values section, without an extra YAML dependency on the runner.
    section=False; selected=None; enabled=True
    for line in args.values.read_text().splitlines():
        if line=='nocodestudio:':section=True;continue
        if section and line and not line[0].isspace() and not line.startswith('#'):break
        if not section:continue
        if re.match(r'\s+archiveUrl:',line) and not re.fullmatch(r"\s+archiveUrl:\s*(?:\"\"|'')\s*(?:#.*)?",line):
            print(json.dumps({'status':'custom-url-not-allowed-in-public-defaults'}));raise SystemExit(1)
        if re.fullmatch(r'\s+enable:\s*false\s*(?:#.*)?',line):enabled=False
        if re.match(r'\s+version:',line):
            value=re.fullmatch(r"\s+version:\s*['\"]([A-Za-z0-9][A-Za-z0-9._+-]*)['\"]\s*(?:#.*)?",line)
            if value:selected=value[1]
    if not enabled:
        print(json.dumps({'status':'application-disabled'}));raise SystemExit(0)
    if selected is None:p.error('Expected a nonempty quoted nocodestudio.version in chart defaults')
    args.version=selected
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*',args.version):p.error('Expected a release tag')
api='https://api.github.com/repos/convertigo/C8oForms/releases/tags/'+urllib.parse.quote(args.version,safe='')
request=urllib.request.Request(api,headers={'Accept':'application/vnd.github+json','User-Agent':'convertigo-helm-release-check'})
try:
    with urllib.request.urlopen(request,timeout=30) as response:release=json.load(response)
except urllib.error.HTTPError as error:
    print(json.dumps({'tag':args.version,'status':'release-unavailable','http':error.code}))
    raise SystemExit(1)
except (OSError,ValueError):
    print(json.dumps({'tag':args.version,'status':'metadata-unreadable'}));raise SystemExit(1)
checks=[];valid=not release.get('draft') and release.get('tag_name')==args.version
if re.search(r'-(rc|beta)',args.version,re.I):valid=valid and release.get('prerelease') is True
for name in ASSETS:
    a=next((a for a in release.get('assets',[]) if a.get('name')==name),None)
    if a is None:
        checks.append({'name':name,'status':'missing'});valid=False;continue
    url=a.get('browser_download_url','');parsed=urllib.parse.urlparse(url)
    expected='/convertigo/C8oForms/releases/download/'+args.version+'/'+name
    safe=parsed.scheme=='https' and parsed.netloc=='github.com' and urllib.parse.unquote(parsed.path)==expected and not parsed.query
    digest=a.get('digest','');ok=safe and a.get('state')=='uploaded' and a.get('size',0)>0 and re.fullmatch(r'sha256:[0-9a-f]{64}',digest) is not None
    status=None
    if ok:
        try:
            with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:status=response.status
        except urllib.error.HTTPError as error:status=error.code
        except OSError:status=0
        ok=status==200
    checks.append({'name':name,'size':a.get('size'),'sha256':digest,'http':status,'status':'available' if ok else 'unverified'})
    valid=valid and ok
print(json.dumps({'tag':args.version,'published_at':release.get('published_at'),'prerelease':release.get('prerelease'),
                  'status':'public-assets-available' if valid else 'assets-incomplete','assets':checks},indent=2))
# This preflight does not assert compatibility or public availability at a later date.
sys.exit(0 if valid else 1)
