#!/usr/bin/env python3
"""Opt-in Docker upgrade test; keeps test data, stops all containers it creates.

Pull baserow/baserow:{1.30.1,1.34.5} and timescale/timescaledb:latest-pg16
first. Run from the repository root. No Kubernetes or external credentials needed.
Plugin installation and all API checks run on an internal Docker network.
"""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'Disposable-validation-only-471!'
EMAIL = 'validation@example.invalid'


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def api(method, path, data=None, auth=None, expected=200):
    headers = {'Content-Type': 'application/json'}
    if auth:
        headers['Authorization'] = auth
    request = urllib.request.Request(
        api_root + path,
        data=None if data is None else json.dumps(data).encode(),
        headers=headers, method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=90)
    except urllib.error.HTTPError as error:
        response = error
    body = response.read()
    assert response.code == expected, '%s %s: HTTP %s, %s' % (
        method, path, response.code, body[:1000])
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body.decode()


def wait_ready():
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            result = api('GET', '/api/_health/')
            if result:
                return
        except (OSError, AssertionError):
            pass
        if run('docker', 'inspect', '-f', '{{.State.Running}}', current) != 'true':
            raise RuntimeError('%s stopped; inspect its Docker logs' % current)
        time.sleep(5)
    raise TimeoutError('Baserow did not become healthy; inspect Docker logs')


def sql(query):
    return run('docker', 'exec', db, 'psql', '-U', 'baserow', '-d', 'baserow',
               '-At', '-c', query)


def migrations():
    return set(sql("SELECT app || ':' || name FROM django_migrations").splitlines())


def start_baserow(suffix, image, plugin=False):
    global current, api_root
    print(run('free', '-m'), flush=True)
    current = options.prefix + '-' + suffix
    args = ['docker', 'run', '-d', '--name', current, '--network', options.prefix,
            '--network-alias', 'baserow', '--memory', '1800m', '--cpus', '2',
            '--shm-size', '256m',
            '--mount', 'type=bind,src=%s,dst=/baserow/data' % (directory / 'data')]
    env = dict(DATABASE_HOST=db, DATABASE_NAME='baserow', DATABASE_USER='baserow',
               DATABASE_PASSWORD=PASSWORD, DATABASE_PORT='5432',
               BASEROW_PUBLIC_URL='http://localhost:%s' % options.port,
               BASEROW_EXTRA_ALLOWED_HOSTS='*', BASEROW_AMOUNT_OF_GUNICORN_WORKERS='1',
               BASEROW_AMOUNT_OF_WORKERS='1', SYNC_TEMPLATES_ON_STARTUP='false',
               BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION='false')
    if plugin:
        args += ['--mount', 'type=bind,src=%s,dst=/c8o-plugins,readonly' % (directory / 'archive'),
                 '--mount', 'type=bind,src=%s,dst=/baserow/data/plugins' % (directory / 'plugins')]
        env.update(BASEROW_PLUGIN_URLS=plugin_url, PIP_NO_BUILD_ISOLATION='false')
    for key, value in env.items():
        args += ['-e', key + '=' + value]
    args += ['--entrypoint', '/bin/sh', image, '-c', command]
    run(*args)
    created.append(current)
    set_api_root()
    wait_ready()


def set_api_root():
    global api_root
    address = run('docker', 'inspect', '-f',
                  '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', current)
    # Docker 29 does not publish ports on internal networks. The host can reach
    # their bridge addresses; the chart exposes the backend on 0.0.0.0:8000.
    api_root = 'http://%s:8000' % address


def authenticate():
    return 'JWT ' + api('POST', '/api/user/token-auth/',
                        {'username': EMAIL, 'password': PASSWORD})['token']


def rows(table, auth):
    result = []
    page = 1
    while True:
        data = api('GET', '/api/database/rows/table/%s/?user_field_names=true&size=200&page=%s'
                   % (table, page), auth=auth)
        result.extend(data['results'])
        if not data['next']:
            assert len(result) == data['count']
            return result
        page += 1


def aggregate(table, auth, **params):
    params['user_field_names'] = 'true'
    return api('GET', '/api/c8o/aggregate/table/%s/?%s' % (
        table, urllib.parse.urlencode(params)), auth=auth)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prefix', default='helm-baserow-' + time.strftime('%Y%m%d%H%M%S'))
parser.add_argument('--port', type=int, default=18084)
parser.add_argument('--resume-empty-baseline', action='store_true',
                    help='Adopt this test prefix after interruption, before any API data was seeded')
options = parser.parse_args()
assert re.fullmatch(r'helm-baserow-[a-z0-9-]+', options.prefix)
directory = ROOT / '.tmp' / options.prefix
directory.mkdir(parents=True, exist_ok=options.resume_empty_baseline)
for name in ['postgres', 'data', 'archive', 'plugins']:
    (directory / name).mkdir(exist_ok=options.resume_empty_baseline)
rendered = run('helm', 'template', 'validation', str(ROOT / 'stable/convertigo'),
               '--set', 'baserow.plugins.c8oforms.enabled=true')
deployment = next(d for d in rendered.split('\n---\n')
                  if '# Source: convertigo/templates/BRdeployment.yaml' in d)
command = json.loads(re.search(r'^          command: (.+)$', deployment, re.M)[1])[2]
plugin_url = re.search(r'name: BASEROW_PLUGIN_URLS\s+value: "([^"]+)"', deployment)[1]
assert 'name: PIP_NO_BUILD_ISOLATION\n              value: "false"' in deployment
cm = next(d for d in rendered.split('\n---\n')
          if '# Source: convertigo/templates/BRconfigmapC8oforms.yaml' in d)
archive, encoded = re.search(r'^  (c8oforms-\S+\.tar\.gz): (\S+)$', cm, re.M).groups()
(directory / 'archive' / archive).write_bytes(base64.b64decode(encoded))
db = options.prefix + '-db'
created = []
current = None
try:
    print(run('free', '-m'), flush=True)
    if options.resume_empty_baseline:
        current = options.prefix + '-1301'
        created.extend([db, current])
        run('docker', 'start', db, current)
        time.sleep(5)
        assert sql('SELECT COUNT(*) FROM core_workspace') == '0', 'Baseline already contains API data'
        set_api_root()
        wait_ready()
    else:
        run('docker', 'network', 'create', '--internal', options.prefix)
        run('docker', 'run', '-d', '--name', db, '--network', options.prefix,
            '--memory', '256m', '--cpus', '1',
            '-e', 'POSTGRES_USER=baserow', '-e', 'POSTGRES_DB=baserow',
            '-e', 'POSTGRES_PASSWORD=' + PASSWORD,
            '--mount', 'type=bind,src=%s,dst=/var/lib/postgresql/data' % (directory / 'postgres'),
            'timescale/timescaledb:latest-pg16', 'postgres', '-c', 'shared_buffers=32MB',
            '-c', 'max_connections=50')
        created.append(db)
        for attempt in range(60):
            try:
                if sql('SELECT 1') == '1':
                    break
            except subprocess.CalledProcessError:
                time.sleep(1)
        start_baserow('1301', 'baserow/baserow:1.30.1')
    api('POST', '/api/user/', dict(name='Validation', email=EMAIL, password=PASSWORD,
                                 authenticate=True), expected=200)
    auth = authenticate()
    workspace = api('POST', '/api/workspaces/', {'name': 'Upgrade validation'}, auth)['id']
    database = api('POST', '/api/applications/workspace/%s/' % workspace,
                   {'name': 'Validation database', 'type': 'database'}, auth)['id']
    tables = []
    for name in ['Categories', 'Entries']:
        tables.append(api('POST', '/api/database/tables/database/%s/' % database,
                          {'name': name, 'data': [['Name']], 'first_row_header': True}, auth)['id'])
    categories, entries = tables
    for field in [dict(name='Category', type='link_row', link_row_table_id=categories),
                  dict(name='Amount', type='number', number_decimal_places=2),
                  dict(name='Active', type='boolean'),
                  dict(name='Double', type='formula', formula="field('Amount') * 2")]:
        api('POST', '/api/database/fields/table/%s/' % entries, field, auth)
    category_ids = [api('POST', '/api/database/rows/table/%s/?user_field_names=true' % categories,
                        {'Name': name}, auth)['id'] for name in ['Group A', 'Group B']]
    values = [dict(Name='Entry %03d' % i, Amount=str(i), Active=i % 2 == 0,
                   Category=[category_ids[i % 2]]) for i in range(1, 252)]
    for offset in range(0, len(values), 100):
        api('POST', '/api/database/rows/table/%s/batch/?user_field_names=true' % entries,
            {'items': values[offset:offset + 100]}, auth)
    token = api('POST', '/api/database/tokens/',
                {'name': 'Upgrade validation', 'workspace': workspace}, auth)['key']
    token_auth = 'Token ' + token
    before = {table: rows(table, token_auth) for table in tables}
    assert len(before[entries]) == 251
    baseline = migrations()
    print('PASS 1.30.1: workspace, database, two linked tables, 251 rows, formula and token', flush=True)
    run('docker', 'stop', '-t', '30', current)
    start_baserow('1345', 'baserow/baserow:1.34.5', plugin=True)
    assert run('docker', 'network', 'inspect', '-f', '{{.Internal}}', options.prefix) == 'true'
    run('docker', 'exec', current, 'python3', '-c',
        'import socket\n'
        'try:\n socket.create_connection(("1.1.1.1", 443), timeout=3)\n'
        'except OSError:\n print("No outbound Internet route")\n'
        'else:\n raise RuntimeError("Unexpected Internet access")')
    logs = run('docker', 'logs', current, stderr=subprocess.STDOUT)
    assert 'Loaded backend plugins: c8oforms' in logs
    assert 'Downloading setuptools' not in logs
    after_migrations = migrations()
    assert baseline <= after_migrations
    print('PASS migrations: %s added, none lost' % len(after_migrations - baseline), flush=True)
    assert {table: rows(table, token_auth) for table in tables} == before
    auth = authenticate()
    print('PASS preserved rows, links, formulas, account password and database token', flush=True)
    path = '/api/c8o/aggregate/table/%s/' % entries
    api('GET', path, expected=401)
    summary = aggregate(entries, token_auth, aggregations='total=sum:Amount,avg=avg:Amount')
    assert summary['results'] == [{'count': 251, 'total': 31626.0, 'avg': 126.0}], summary
    grouped = aggregate(entries, auth, group_by='Category', aggregations='total=sum:Amount',
                        with_fields='true')
    assert grouped['count'] == 2 and sum(r['count'] for r in grouped['results']) == 251
    assert sum(r['total'] for r in grouped['results']) == 31626.0
    assert len(grouped['fields']) == 5
    filtered = aggregate(entries, token_auth, aggregations='sum:Amount', filter__Active__boolean='true')
    assert filtered['results'] == [{'count': 125, 'sum:Amount': 15750.0}], filtered
    api('GET', path + '?user_field_names=true&group_by=Missing', auth=auth, expected=400)
    api('GET', '/api/c8o/aggregate/table/999999/', auth=auth, expected=404)
    print('PASS /api/c8o/: whole-table and linked grouping, filters, fields, JWT/token, 401/400/404', flush=True)
    written = api('POST', '/api/database/rows/table/%s/?user_field_names=true' % entries,
                  dict(Name='Written after upgrade', Amount='42.50', Category=category_ids), token_auth)
    assert Decimal(written['Double']) == Decimal('85.00'), written
    before[entries] = rows(entries, token_auth)
    run('docker', 'restart', '-t', '30', current)
    wait_ready()
    assert rows(entries, token_auth) == before[entries]
    assert aggregate(entries, token_auth, aggregations='sum:Amount')['results'][0]['count'] == 252
    print('PASS restart reinstalls offline plugin; post-upgrade writes survive', flush=True)
    # Recreating the pod without the emptyDir and plugin variables disables the plugin.
    run('docker', 'stop', '-t', '30', current)
    start_baserow('disabled', 'baserow/baserow:1.34.5')
    assert rows(entries, token_auth) == before[entries]
    api('GET', path, auth=token_auth, expected=404)
    print('PASS disabling plugin removes endpoints and preserves data', flush=True)
    print('PASS Docker upgrade validation; data retained under %s' % directory, flush=True)
finally:
    for container in reversed(created):
        subprocess.run(['docker', 'stop', '-t', '30', container], check=False,
                       stdout=subprocess.DEVNULL)
