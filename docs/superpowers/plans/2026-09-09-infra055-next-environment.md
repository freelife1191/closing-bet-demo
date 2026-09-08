# INFRA-055 Next environment isolation Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the bounded implementation slice. The leader owns integration, review and QA. Steps use checkboxes.

**Goal:** Exclude backend-only secrets from Next dev/build/start environments and newly generated caches while preserving session, identity and admin configuration behavior.

**Architecture:** Replace the full frontend/.env link with one Node launcher used by npm dev/build/start. It reads configuration as data with the already installed @next/env parser, then launches the actual Next CLI with an explicit environment allowlist. It never writes a second secret configuration file. Resolve @next/env from the installed Next CLI dependency location so hoisted and nested npm layouts both work.

**Tech Stack:** Node built-ins, installed @next/env, Next 16.3.4, Python pytest subprocess fixtures, Vitest and agent-browser.

**Spec:** Bounded chat design on 2026-09-09, approved by user's following “진행해”. T3 because .env.example and secret handling change. Process-only delivery implements the approved common execution path without adding a secret copy.

## Global constraints

- Original repo: /Users/freelife/vibe/lecture/hodu/closing-bet-demo, base 97113d4, branch develop. Implement in the independent clone; original untracked package.json SHA256 4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8 stays untouched.
- Never read/change original actual .env/.env.production/.env.vertex or data/. Only tracked .env.example is an input to inspection. Runtime behavior below is tested only on synthetic files in the clone.
- Never contact original Next3500/Flask5501/live URL. Market-gate GET can collect data. No real LLM, notifications, trading, reset, save, refresh, delete, deploy or production restart.
- No new dependencies, no public prefix for secrets, no whole environment or credentials in logs/artifacts/CLI arguments.
- Keep current 0700 .next protection. Previously existing original caches are not deleted by this round; validate fresh and warm caches in the owned clone.
- Codex UltraQA lifecycle is app-adapted; do not mutate original .omx/state. Real web QA uses agent-browser and screenshots must be opened.

## Task 1: Filter the actual Next execution boundary

**Files:** create frontend/scripts/run-next.js and tests/scripts/test_next_environment.py; modify frontend/package.json and restart_all.sh. Update scripts/env_value.sh comments only if necessary.

**Interface:** `node frontend/scripts/run-next.js <dev|build|start> [...Next args]`. No shell evaluation; spawn process.execPath and require.resolve('next/dist/bin/next'). Inherit stdio, forward termination to the owned child, propagate exit/signal failure. Resolve paths from __dirname, independent of caller cwd. Invoke `next <command> <fixed absolute frontend directory> [...options]`; the launcher rejects extra positional arguments before spawn while preserving values for installed Next options. Actual Next16.3 ignores excess positional arguments; do not model a nonexistent rejection in the test stub.

Application allowlist: GOOGLE_CLIENT_ID, NEXT_PUBLIC_GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, NEXTAUTH_SECRET, NEXTAUTH_URL, NEXTAUTH_URL_INTERNAL, ADMIN_EMAILS, ADMIN_API_TOKEN, INTERNAL_IDENTITY_SECRET, API_URL, NEXT_PUBLIC_API_URL. ADMIN_API_TOKEN is required by the existing Next admin route, so correct the TODO's mistaken backend-only classification.

Runtime allowlist: PATH, HOME, TMPDIR, TMP, TEMP, USER, LOGNAME, SHELL, LANG, LC_ALL, TZ, SYSTEMROOT, WINDIR, COMSPEC, PATHEXT, PORT, NODE_ENV, NEXT_TELEMETRY_DISABLED, NEXT_TRACE_UPLOAD_DISABLED, CI. Do not propagate NODE_OPTIONS, arbitrary NEXT_PUBLIC_* or Next private serialized environment fields. Next computes its own internal fields after launch.

Configuration contract:
- Parent application values retain precedence. NODE_ENV is the exception: force dev=development, build/start=production in both parser and child. There is no test mode in the launcher interface; test fixtures exercise those same modes. Test NODE_ENV=test npm build against production files and production child environment.
- Frontend files follow Next's `.env.<mode>.local`, `.env.local`, `.env.<mode>`, `.env` ordering; then corresponding root files supply missing values. Use installed @next/env for both a raw-reference pass and the actual expansion pass, with a logger that throws a generic configuration error without contents. Temporarily replace dollars by a collision-free marker for raw parsing; keep the real originals for expansion. Restore the sanitized parent environment and parser initial snapshot between passes.
- Root .env.vertex is not part of Next's normal load order and is not loaded.
- Read regular files without following symlinks. Exactly frontend/.env -> ../.env is the supported legacy link: skip it in frontend entries, use root entries, and unlink only that exact link after all preflight succeeds. Reject other symlinks/FIFOs/non-regular env inputs without touching them.
- Reject unsupported keys in ordinary frontend env files, rather than let Next reload backend-only values. Validate every frontend file that the selected mode can load; inactive mode files are checked when that mode runs.
- Use the parser's per-file env keys for validation, including export/quoted assignments. Next subprocess inherits only the above keys. Do not use undocumented __NEXT_PROCESSED_ENV bypass flags.
- Before launch, create absent .next with0700; chmod an existing real directory to0700 without deleting cached files. Reject symlink or ordinary file. Use O_DIRECTORY|O_NOFOLLOW to open the directory, fchmod/fstat on that descriptor and close it in finally; recheck path type and0700 before spawn. A race replacing .next with a foreign symlink must not chmod its target. Test absent,0755 and existing-cache preservation. Preflight failure is nonzero before starting Next and never prints an env value.

- [ ] Capture baseline pytest and Vitest in the network-restricted clone.
- [ ] Add failing subprocess regression using a temporary frontend layout, copied launcher if present, and stub next CLI which captures only synthetic env values to an owned file. Before implementation use the existing package-script path to demonstrate backend secret inheritance; missing launcher alone is not the defect proof.

```python
assert child_env['ADMIN_API_TOKEN'] == 'QA_ADMIN'
assert child_env['INTERNAL_IDENTITY_SECRET'] == 'QA_IDENTITY'
assert 'SMTP_PASSWORD' not in child_env
assert 'UNKNOWN_BACKEND_SECRET' not in child_env
assert 'NODE_OPTIONS' not in child_env
```

- [ ] Implement the minimal launcher; npm scripts become `node scripts/run-next.js dev`, `... build`, `... start`. Remove restart_all.sh's link creation; npm is the common boundary. Keep unrelated process cleanup defects outside scope.
- [ ] Add executable edge cases: dev/build/start forwarding and fixed project path/extra positional rejection; inherited test NODE_ENV normalized; .next absent/0755/cache-preservation; parent/frontend/root precedence; duplicate/export/quoted/multiline/dollar/shell-looking input; backend values in parent and files; stale legacy link; unrelated link/file preservation; prohibited frontend key; read failure; .next symlink; exit7; SIGTERM and bounded child cleanup. Assertions target child behavior and original byte preservation, not implementation text alone.
- [ ] Run targeted pytest and shell/node syntax checks. All subprocess tests use temporary paths, fake values and bounded timeouts.

## Task 2: Document, review and statically verify

**Files:** .env.example and CLAUDE.md explain npm boundary, allowed shared authentication keys, precedence, rejection behavior, original caches and lack of automatic running-process updates. docs/dev-cycle/TODO.md holds approval/progress; reviews/INFRA-055.md holds exact review inputs/verdicts.

- [ ] Fix .env.example's obsolete link comment. Do not change actual credential files.
- [ ] Critic accepts this plan before implementation. After implementation run ponytail, code review with architecture lane, deep review, and independent security review in tier order. Record each scope hash and original verdict; fix blockers and rerun affected checks.
- [ ] Run full pytest, full Vitest including actual npm build smoke, frontend typecheck/lint, Python AST and node --check/bash -n. Record raw logs, exits, counts and skips; a missing LSP backend is not a PASS.
- [ ] Confirm only .env.example is tracked and secret sentinels are absent in runtime error/log/body and public bundle artifacts. Necessary Next server auth secrets may remain in private compiler caches, protected by0700; the target is backend-only secrets.

## Task 3: UltraQA actual process/cache/browser verification

**Files:** docs/dev-cycle/qa/INFRA-055.md, evidence/INFRA-055/*, monthly/daily archive only after final PASS.

- [ ] Before dynamic commands write a required matrix S1-S6 with expectation, exact harness, actual result, evidence and cleanup. Commit reviewed implementation and empty-result matrix after static success; keep TODO.
- [ ] S1 normal process/cache: synthetic root env contains unique backend sentinels, required fake Next credentials and fixture API_URL. Actual npm dev loads real dashboard, produces filesystem cache, then exits cleanly. Scan all .next files including private caches bytewise; backend sentinel matches=0, cache artifact count>0. Repeat warm dev; required runtime behavior survives.
- [ ] S2 build/start: fresh cache actual npm build and npm start, scan newly generated cache and served/server bundle files; prohibited sentinel matches=0. Pass fake backend secrets in parent too, proving inherited-environment filtering. Verify build succeeds and actual dashboard renders.
- [ ] S3 admin UI: synthetic NextAuth cookie, actual app SettingsModal settings read and actual Next admin route -> isolated Flask admin gate. Open real settings and verify masked fixture data, HTTP200 and actual identity/admin check. Stub only auxiliary data/external effects; no real provider OAuth/LLM/notifications.
- [ ] S4 viewer/anonymous: separate synthetic viewer cookie and no-cookie probe; UI does not offer admin environment settings; adversarial direct same-app request receives403. Identity forwarding is checked by actual Flask verification using only fake keys.
- [ ] S5 malformed/bypass/cancel: execute the launcher against own fixtures with bad frontend key, symlink, unsafe-looking literal, child failure and termination; fail closed/nonzero with no secret output, no foreign file mutation and no owned process residue. Regression subprocess cases can supply this CLI-only evidence.
- [ ] S6 preservation/cleanup: capture source hashes, package hash, safe process IDs/ports, namespace and expected fake paths. Close owned browser sessions, stop owned processes, remove owned clone/caches/fakeenv only after evidence extraction and fast-forward integration. Original servers/secrets/data are untouched.
- [ ] Browser isolation: explicit owned loopback ports and API_URL, allowlisted browser domains plus deny-only outbound proxy; server outbound sandbox. Capture snapshots/request status/screenshots and open all final images, inspect console/pages plus Next MCP compilation/runtime errors.
- [ ] If a required row fails, diagnose/fix/retry in same approved scope; max5 QA cycles or same failure3. No false completion or retroactive optional downgrade.
- [ ] After all reviews/static/dynamic/cleanup pass, fast-forward original develop, verify source and user package hashes; archive once and remove INFRA-055 only in final archive commit. Report actual limitations including no original cache cleanup/deployment.

## Implementation review refinements (same approved scope)

Actual Next ignores excess positional arguments; launcher validation is required, with a real npm regression rather than a self-rejecting stub. Preserve separate values for port/hostname/keepAliveTimeout/HTTPS paths/upload trace/build paths and optional inspect/build-mode/internal-trace; Next still validates option availability and values. The fixed project directory never comes from these arguments.

Security reproduced lstat→chmod symlink replacement against synthetic directories: generic exit1 was too late to preserve foreign mode. Descriptor-based chmod closes that boundary. Direct @next/env resolution is anchored at Next, avoiding a dependency/hoisting assumption without adding a package. These findings are validated in the final review delta.

### Expansion boundary correction

Security reproduced `NEXT_PUBLIC_API_URL=$SMTP_PASSWORD` and `$ADMIN_API_TOKEN` carrying private values into a public allowed key. Check effective raw references before expansion: application values can refer only to application keys, and public application values can refer only to the two public application keys. Every effective application key is checked, covering indirect chains. Match dollar-name and braced/default/nested references, reject escaped variable-like dollars and bare dollar construction; preserve non-reference shell-looking `$(` text. The existing Next parser still handles actual quoting, interpolation and malformed expansions.

The raw pass starts with empty process env/empty parser initial snapshot, with a collision-checked marker containing non-key characters replacing all dollars. It uses the same installed parser, not a hand-written dotenv grammar. Reconstruct effective raw values with parent precedence for policy checks; then fully restore sanitized parent env and updateInitialEnv before the actual original-text expansion. No Node version increase or new dependency is introduced. Literal secret strings deliberately pasted into public values are outside what key/reference classification can identify.

### Final parser-semantic refinements

- Variable names follow the installed ASCII word grammar, including leading digits.
- Literal `$(` is inert; every other dollar must start a static permitted reference. Escaped variable-like dollars, bare dollars and `$$` construction fail closed because recursive substitution/Next reload can turn them into private references. Validate expanded application values again before any preflight mutation. The earlier escaped-private literal preservation proposal was disproved by actual parser probes and is superseded here.
- Runtime controls are parent-only; root env values never fill PORT/telemetry/PATH. This closes backend→runtime smuggling without widening application references.
- Missing/zero O_NOFOLLOW or O_DIRECTORY fails before reading configuration. No silent platform fallback. Optional-value Next flags may be bare; their values remain optional.
