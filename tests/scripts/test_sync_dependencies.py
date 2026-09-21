#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 설치/프로세스 종료 없이 의존성 동기화와 기동 실패 경계를 실행한다."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    root=tmp_path/'project with spaces'
    (root/'scripts').mkdir(parents=True)
    (root/'frontend').mkdir()
    assert (ROOT/'scripts/sync_dependencies.sh').exists()
    shutil.copy2(ROOT/'scripts/sync_dependencies.sh',root/'scripts/sync_dependencies.sh')
    shutil.copy2(ROOT/'restart_all.sh',root/'restart_all.sh')
    shutil.copy2(ROOT/'scripts/env_value.sh',root/'scripts/env_value.sh')
    (root/'requirements.txt').write_text('example==1\n')
    (root/'frontend/package.json').write_text('{"name":"fixture","version":"1.0.0"}')
    (root/'frontend/package-lock.json').write_text('{"lockfileVersion":3}')
    bin_dir=root/'bin';bin_dir.mkdir()
    stub='''import json,os,sys,pathlib
root=pathlib.Path(os.environ['FIXTURE_ROOT']);name=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps([name,args])+"\\n")
if name=='python3.11':
 p=root/'venv/bin';p.mkdir(parents=True);(p/'python').write_text(pathlib.Path(sys.argv[0]).read_text());(p/'python').chmod(0o700);(p/'activate').write_text('deactivate() { :; }\\n');sys.exit(0)
if name=='python':
 if 'install' in args and os.environ.get('FAIL_PIP_INSTALL'):sys.exit(11)
 if 'check' in args and os.environ.get('FAIL_PIP_CHECK'):sys.exit(12)
if name=='npm':
 modules=root/'frontend/node_modules'
 if args[0]=='ci':
  if os.environ.get('FAIL_NPM_CI'):sys.exit(13)
  (modules/'.bin').mkdir(parents=True,exist_ok=True);(modules/'.bin/next').write_text('fixture');(modules/'.package-lock.json').write_text((root/'frontend/package-lock.json').read_text())
 if args[0]=='ls' and (not (modules/'.package-lock.json').exists() or os.environ.get('FAIL_NPM_LS')):sys.exit(14)
if name=='lsof':sys.exit(1)
if name=='nohup':(root/'started').write_text('unexpected start')
'''
    for name in ['python3.11','npm','lsof','pkill','ss','nohup']:
        p=bin_dir/name;p.write_text(f'#!{sys.executable}\n'+stub);p.chmod(0o700)
    return root


def run(root,script='scripts/sync_dependencies.sh',**flags):
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR') if k in os.environ}
    env.update(PATH=str(root/'bin')+':'+env['PATH'],FIXTURE_ROOT=str(root),**flags)
    return subprocess.run(['/bin/bash',str(root/script)],cwd=root.parent,env=env,capture_output=True,text=True,timeout=15)


def ci_count(root):
    return sum(name=='npm' and args[0]=='ci' for name,args in map(json.loads,(root/'calls.jsonl').read_text().splitlines()))


def test_initial_install_then_unchanged_skip_and_lock_change_update(project):
    assert run(project).returncode==0
    assert ci_count(project)==1
    assert run(project).returncode==0
    assert ci_count(project)==1
    (project/'frontend/package-lock.json').write_text('{"lockfileVersion":3,"changed":true}')
    assert run(project).returncode==0
    assert ci_count(project)==2


def test_missing_module_triggers_repair(project):
    assert run(project).returncode==0
    (project/'frontend/node_modules/.bin/next').unlink()
    assert run(project).returncode==0
    assert ci_count(project)==2


@pytest.mark.parametrize('flag',['FAIL_PIP_INSTALL','FAIL_PIP_CHECK','FAIL_NPM_CI','FAIL_NPM_LS'])
def test_failed_dependency_step_prevents_start(project,flag):
    result=run(project,'restart_all.sh',**{flag:'1'})
    assert result.returncode!=0
    assert 'Ready!' not in result.stdout
    assert not (project/'started').exists()


def test_missing_lockfile_fails_before_install(project):
    (project/'frontend/package-lock.json').unlink()
    assert run(project).returncode!=0
