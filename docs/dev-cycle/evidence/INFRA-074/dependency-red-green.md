Dependency regression before implementation: tests/scripts/test_sync_dependencies.py 1 failed, 8 passed (Requirement already satisfied present).
After quiet output and npm diagnostics changes: 9 passed in9.38s, exit0.
Synthetic package manager prints normal noise and an explicit installation failure; tests assert noise suppression, failure preservation, first/repeat/lockchange/missing module and no Ready on failure.
