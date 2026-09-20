#!/usr/bin/env python3
"""Three real isolated workers must leave one authoritative memory snapshot."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[4]
    assert root.name.startswith('storage-memory-20260921-') and not (root / '.git').exists()
    os.environ['CHATBOT_MEMORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS'] = '0'
    from chatbot.storage_memory_manager import MemoryManager
    from chatbot.storage_sqlite_memory import load_memories_from_sqlite
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        directory = Path(sys.argv[2]).resolve()
        assert directory.is_relative_to(root / 'tmp')
        worker = sys.argv[3]
        owner = 'qa-worker-' + worker
        manager = MemoryManager(owner, data_dir=directory)
        manager.add('user_profile', {'name': owner, 'persona': 'synthetic'}, owner)
        for i in range(6):
            assert manager.save_daily_suggestions(f'daily_suggestions_process_{worker}_{i}', [{'title': f'{worker}:{i}'}])
            manager.add(f'note-{i}', f'{worker}:{i}', owner)
        print(json.dumps({'worker': worker, 'result': 'PASS'}))
        return
    with tempfile.TemporaryDirectory(prefix='snapshot-process-', dir=root / 'tmp') as raw:
        directory = Path(raw)
        seed = MemoryManager('qa-seed', data_dir=directory)
        seed.add('seed', 'keep', 'qa-seed')
        workers = []
        outputs = []
        try:
            for i in range(3):
                workers.append(subprocess.Popen([sys.executable, __file__, '--worker', raw, str(i)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
            for worker in workers:
                output, _ = worker.communicate(timeout=30)
                outputs.append(output.strip())
                assert worker.returncode == 0, output
            # Do not instantiate a reader manager here: its startup snapshot could mask a stale file.
            sqlite_rows = load_memories_from_sqlite(directory / 'chatbot_storage.db', logging.getLogger(__name__))
            json_rows = json.loads((directory / 'chatbot_memory.json').read_text())
            assert json_rows == sqlite_rows
            assert len(json_rows['']) == 18
            for i in range(3):
                owner = f'qa-worker-{i}'
                assert json_rows[owner]['user_profile']['value']['name'] == owner
                assert len(json_rows[owner]) == 7
                for j in range(6):
                    assert json_rows[owner][f'note-{j}']['value'] == f'{i}:{j}'
            print(json.dumps({'result': 'PASS', 'worker_count': 3, 'cache_rows': 18, 'owner_rows_each': 7, 'snapshot_equals_sqlite': True, 'workers': outputs}))
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait(timeout=5)
    assert not directory.exists()
    print('owned worker processes and temporary directory cleaned')


if __name__ == '__main__':
    main()
