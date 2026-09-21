"""Imports only in sandbox: initialization runs real model boundary & preservation probe."""
import runpy
from pathlib import Path
root=Path(__file__).resolve().parents[4]
runpy.run_path(str(Path(__file__).with_name('fixture.py')),run_name='qa_fixture_probe')
print((root/'qa-engine.json').read_text())
