# INFRA-074 T3 deep adversarial review

Verdict: **ACCEPT**

Baseline: `92d84ab`. Review surface: final startup/stop lifecycle, dependency sync, requirements and the vendored pykrx rebuild/patch/wheel. Test and fixture files were reviewed in SUMMARY mode only (diff stat and test names); their payloads were not interpreted. No original service, port, env, data, log or venv action was performed.

Scope Check: **CLEAN**

Intent and delivered files agree: remove false stop/restart success, preserve unrelated listeners, serialize lifecycle operations, verify readiness, shorten healthy dependency logs, and contain KRX login transport/JSON failures.

## Findings

Pre-Landing Review: **No unresolved issues found.**

## Adversarial decisions and residual ceilings

### Accepted: forced startup cleanup fails closed when a descendant detaches

`frontend/scripts/run-next.js:270-289` forwards TERM to Next, while `scripts/service_lifecycle.sh:312-318` can escalate to KILL on the verified launcher. KILL cannot run the forwarding handler, so a pathological TERM-resistant descendant can outlive its launcher.

The final boundary is honest and safe: `restart_all.sh:39-46` verifies the port after launcher cleanup, retains the PID record when a listener remains, emits a specific detached-child/manager warning, and returns the already-failing restart status. It does not claim cleanup success or kill an unprovable reparented process. `README.md:70` documents this ceiling. Normal stop uses the previously captured listener identities and can KILL only those verified PIDs. A generic process-group manager is outside this bounded repair. **WATCH, not blocking.**

### Accepted: dependency installers retain lifecycle lock FD 9

`restart_all.sh:74` intentionally lets the synchronous dependency child inherit FD 9. If the parent is interrupted while pip/npm is still mutating the shared venv/node_modules, the installer keeps the kernel flock and prevents a concurrent restart from entering the same package tree. Long-running backend/frontend children close FD 9 at `restart_all.sh:84,95`. `INFRA-074-plan.md:35` documents that install hooks which daemonize are unsupported; current npm policy blocks the relevant lifecycle scripts. **WATCH, not blocking.**

## Reviewed and accepted

- Port ownership requires current UID, exact backend/frontend cwd, expected command signature, recorded start identity and listener ancestry. Unknown, foreign and reoccupied listeners fail closed.
- Lifecycle locking uses a kernel flock on shell FD 9 and rejects concurrent stop/restart operations; abnormal owner exit releases the lock when its synchronous work is done.
- Dependency sync occurs only after managed services exit and ports are free; ports are checked again after sync and before each spawn.
- Readiness requires live recorded launcher identity, owned listener ancestry and HTTP success; both services are rechecked before `Ready!`.
- Completed and running Bash jobs are detected without a pipeline subshell, and new-child cleanup verifies shell parentage, service identity and start token before signaling.
- KRX warmup and both login POSTs disable redirects, classify non-2xx/non-JSON/schema/network failures without response or credential output, clear failed authentication state, and preserve strict public/authenticated origin separation.
- Wheel `3648009d...` matches the README candidate hash and the requirements pin is `1.2.9+cookie.2`.
- `AGENTS.md` now distinguishes the historical overwritten log from INFRA-074 append behavior; `AGENTS.md` and `CLAUDE.md` describe managed-service-only stop semantics.

## Verification performed by this review

- `bash -n restart_all.sh stop_all.sh scripts/service_lifecycle.sh scripts/sync_dependencies.sh` — PASS
- `git diff --check 92d84ab -- <reviewed text files>` — PASS
- Test/fixture coverage was read by names and diff summary only. It covers listener visibility, exact signatures, lock contention/recovery, PID reuse, supervisor reoccupation, port-free-but-master-alive, post-sync reoccupation, readiness identity and partial-start cleanup.
- No full pytest, browser, network, real KRX login, original dependency install or service interaction was run in this independent pass.

## Reviewed hashes

```text
0c5a27f5f4fe68d1cbb9a56da4f392c98a3645d272c2ff16dcded4e63ae1ed11  restart_all.sh
51d75910fa62c5476c4c54a02b9e29b71b470528b4e5c739347308164fe5b38c  stop_all.sh
028f929c5abbaf5a57202dda77976f856a512250ef186648a57b5a334e7d6d0a  scripts/service_lifecycle.sh
ecd34f67ab25b8f83cf9945579cd3d42be56d6647f6c080b391dd177bf090e70  scripts/sync_dependencies.sh
9fc989afb5d20544f2d78d5ced444d82ac6c4ac4ef5d24c484bff7dd7534f20a  requirements.txt
2c94eb5be01aaf3c6d43694c557bfbe9a6f0df27c6dc719b8d114789013687dc  vendor/pykrx/rebuild.py
0ed6f6bdb3ccab09993a3962a10d1734c2b18eed9e2a0f76137676a52d26e635  vendor/pykrx/transport.patch
fad812b081f0f0740b16dfbd107cd0806d8d447d65ed099a78ffb47521cefb13  vendor/pykrx/README.md
3648009de4202f6087be7e8eef174a86c3d77eed6d3db60eb9ecf18ac6b8a099  vendor/pykrx/pykrx-1.2.9+cookie.2-py3-none-any.whl
8e700df14f95498bb34fe8958b19a2ba6bc1b6cda60f7f0edcbba632cd95b3d5  AGENTS.md
fd3aa638d1004e6aa8663689066f1a546ed33a2fd3083fb7f29c9814a14969c4  CLAUDE.md
6a1e913da6d50aa777a68b7e1c75500d8ce354b87ec05a0197ed4139e73fa4d3  README.md
a188bd2e6e957500d325934dc0c68fedc4e2a5030662ac1d51adf8c3f0dd91a1  reviewed scoped diff from 92d84ab
```

Recommendation: proceed to the isolated real restart smoke; the remaining detached-child and installer-daemon cases are explicitly fail-closed/documented ceilings rather than silent-success paths.
