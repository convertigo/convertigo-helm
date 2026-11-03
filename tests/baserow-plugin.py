#!/usr/bin/env python3
"""Render tests of baserow.plugins.c8oforms: no cluster access or deployment."""
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

chart = Path(__file__).resolve().parents[1] / 'stable/convertigo'
lock = json.loads((chart / 'files/baserow-plugins/c8oforms.json').read_text())
archive = (chart / 'files/baserow-plugins' / lock['archive']).read_bytes()
assert hashlib.sha256(archive).hexdigest() == lock['sha256'], 'Embedded archive does not match its lock'
url = 'file:///c8o-plugins/' + lock['archive']
config_map = 'plugin-convertigo-c8oforms-' + lock['sha256'][:16]


def render(*options, chart_dir=chart):
    return subprocess.check_output(['helm', 'template', 'plugin', str(chart_dir), *options], text=True)


def failure(*options, chart_dir=chart):
    result = subprocess.run(['helm', 'template', 'plugin', str(chart_dir), *options], text=True, capture_output=True)
    assert result.returncode != 0, 'Invalid configuration was accepted: %s' % (options,)
    return result.stderr


def documents(rendered):
    return {re.search(r'^# Source: convertigo/(\S+)', d, re.M).group(1): d
            for d in rendered.split('\n---\n') if '# Source: ' in d}


def plugin_objects(rendered):
    return [d for d in rendered.split('\n---\n') if 'c8oforms-plugin' in d or 'BASEROW_PLUGIN_URLS' in d
            or 'PIP_NO_BUILD_ISOLATION' in d or 'c8oforms.convertigo.net' in d]


subprocess.check_call(['helm', 'lint', str(chart)], stdout=subprocess.DEVNULL)
enabled = ('--set', 'baserow.plugins.c8oforms.enabled=true')

# Disabled by default, and the same rendering as before the key existed (--reuse-values)
default = render()
assert not plugin_objects(default)
# The default Baserow image is one the plugin is tested on
assert 'image: baserow/baserow:1.34.5' in documents(default)['templates/BRdeployment.yaml']
assert '1.34.5' in lock['tested_baserow_versions']
assert 'templates/BRconfigmapC8oforms.yaml' in documents(render(*enabled))
assert render('--set', 'baserow.plugins.c8oforms.enabled=false') == default
assert render('--set', 'baserow.plugins=null') == default
assert not plugin_objects(render(*enabled, '--set', 'baserow.enabled=false'))

for tag in lock['tested_baserow_versions']:
    docs = documents(render(*enabled, '--set', 'baserow.image.tag=' + tag))
    deployment = docs['templates/BRdeployment.yaml']
    assert 'image: baserow/baserow:' + tag in deployment
    assert '- name: BASEROW_PLUGIN_URLS\n              value: "%s"' % url in deployment
    # Offline install: pip builds the plugin with the setuptools of the image (inverted variable)
    assert '- name: PIP_NO_BUILD_ISOLATION\n              value: "false"' in deployment
    assert '- name: c8oforms-plugin\n          configMap:\n            name: %s' % config_map in deployment
    assert '- name: c8oforms-plugin\n              mountPath: /c8o-plugins\n              readOnly: true' in deployment
    assert '- name: br-plugins\n          emptyDir: {}' in deployment
    assert '- name: br-plugins\n              mountPath: /baserow/data/plugins' in deployment
    cm = docs['templates/BRconfigmapC8oforms.yaml']
    assert 'name: ' + config_map in cm and 'immutable: true' in cm
    assert 'c8oforms.convertigo.net/commit: "%s"' % lock['commit'] in cm
    data = re.search(r'^  %s: (\S+)$' % re.escape(lock['archive']), cm, re.M).group(1)
    assert base64.b64decode(data) == archive

# Untested Baserow (the default of the chart before 1.34.5)
assert 'tested on Baserow' in failure(*enabled, '--set', 'baserow.image.tag=1.30.1')

# Archive from an existing ConfigMap: the chart creates none
docs = documents(render(*enabled, '--set', 'baserow.image.tag=1.34.5',
                        '--set', 'baserow.plugins.c8oforms.existingConfigMap=customer-c8oforms'))
assert 'templates/BRconfigmapC8oforms.yaml' not in docs
assert '- name: c8oforms-plugin\n          configMap:\n            name: customer-c8oforms' in docs['templates/BRdeployment.yaml']

# An embedded archive that does not match its lock is refused
with tempfile.TemporaryDirectory(prefix='baserow-plugin-test-') as directory:
    altered = Path(directory) / 'chart'
    shutil.copytree(chart, altered)
    with open(altered / 'files/baserow-plugins' / lock['archive'], 'ab') as f:
        f.write(b'\0')
    assert 'does not match the sha256' in failure(*enabled, '--set', 'baserow.image.tag=1.34.5', chart_dir=altered)
print('PASS baserow.plugins.c8oforms default/enabled/existing ConfigMap/untested Baserow/altered archive', flush=True)
