#!/usr/bin/env python3
"""Read-only saved-evidence checks; no product import or network access."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent

def read(name):
    return json.loads((EVIDENCE / name).read_text())

frozen = read('review-frozen.json')
for name, digest in frozen.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256(subprocess.check_output(['git', 'show', f'9c69e9a:{name}'], cwd=ROOT)).hexdigest() == digest
for item in read('raw-index.json'):
    raw = gzip.decompress((EVIDENCE / item['archive']).read_bytes())
    assert len(raw) == item['bytes']
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
for name in ['pytest-final', 'vitest', 'typecheck', 'lint', 'build', 'fixture']:
    result = read(name + '.json')
    assert result['exit_code'] == 0 and not result['timed_out']
assert '2452 passed, 3 skipped' in gzip.decompress((EVIDENCE / 'pytest-final.log.gz').read_bytes()).decode()
for row in read('ego-matrix.json'):
    assert row['actualTotal'] == str(row['total'])
    assert row['api']['status'] == 200
    assert row['api']['body']['indicators']['eps'] == -266
    assert row['api']['body']['financials']['netIncome'] == 2_600_000_000
    assert row['observed']['errors'] == row['observed']['consoleErrors'] == []
recovery = read('ego-recovery.json')
assert [row['status'] for row in recovery] == [503, 200]
assert recovery[0]['observed']['timeOrigin'] == recovery[1]['observed']['timeOrigin']
for row in recovery:
    assert row['observed']['errors'] == row['observed']['consoleErrors'] == []
for name in ['get_errors', 'get_compilation_issues']:
    response = read('next-' + name + '.json')[0]['result']['content'][0]['text']
    assert all(value == [] for value in json.loads(response).values())
cleanup = read('cleanup.json')
assert cleanup['scratch_removed'] and not Path(cleanup['scratch']).exists()
assert all(cleanup['ports_closed'].values()) and read('ego-finish.json')['closedSpace']
assert hashlib.sha256((ROOT / 'package.json').read_bytes()).hexdigest() == cleanup['package_sha256']
for name in read('image-review.json')['images']:
    assert (EVIDENCE / name).is_file()
assert read('request-audit.json')['forbidden_mutations'] == 0
print(json.dumps({'result': 'PASS', 'frozen_files': len(frozen), 'raw_archives': len(read('raw-index.json')), 'browser_modes': 3, 'required_qa': '7/7', 'cleanup': 'complete'}))
