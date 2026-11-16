#!/usr/bin/env python3
"""Render-only ownership checks; runtime UID/RWX qualification needs an isolated environment."""
import argparse
from pathlib import Path
import subprocess


def command(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--docker', action='store_true', help='Legacy harness; use startup-installation.py for current local checks')
parser.add_argument('--image', default='convertigo/convertigo-ci:hotfix')
parser.add_argument('--chart', type=Path, default=Path(__file__).resolve().parents[1] / 'stable/convertigo')
args = parser.parse_args()
chart = args.chart


def render(template, *options, chart_dir=chart):
    return command('helm', 'template', 'ownership', str(chart_dir), '--show-only',
                   'templates/' + template, *options)


default = render('C8Odeployment.yaml')
assert 'name: workspace-setup' in default
assert 'runAsUser: 0' in default
assert default == render('C8Odeployment.yaml', '--set', 'workspaceOwnershipInit.enabled=true')
disabled = ('--set', 'workspaceOwnershipInit.enabled=false')
without = render('C8Odeployment.yaml', *disabled)
assert 'name: workspace-setup' in without and 'runAsUser: 1000' in without
extra = ('--set-json', 'extraInitContainers=[{"name":"custom-init","image":"busybox","command":["true"]}]')
with_extra = render('C8Odeployment.yaml', *disabled, *extra)
assert 'name: custom-init' in with_extra and 'name: workspace-setup' in with_extra
assert render('C8Odeployment.yaml', '--set', 'workspaceOwnershipInit=null') == default
print('PASS serialized workspace init, root/non-root mode, custom init containers and legacy values', flush=True)
if not args.docker:
    raise SystemExit(0)
raise SystemExit('Legacy Docker harness retired; run startup-installation.py, and qualify RWX on an explicitly authorized cluster')
