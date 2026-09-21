# KRX independent security review
Reviewer /root/krx_security_review; baseline92d84ab; read-only, no real requests.

Final original recommendation: APPROVE (0 CRITICAL/HIGH/MEDIUM/LOW open in scoped code).
Original HIGH redirect credential leak and MEDIUM masking catch are fixed. README distinction fixed (hash fad812b0...). Evidence krx-verification.md records verified upstream SHA e768a648... and two identical rebuilds SHA3648009d..., matching packaged wheel/README.
Independent no-network checks: new-wheel login probe14 cases PASS, transport probe7 groups PASS external_requests0, wheel CRC+40 RECORD hashes PASS, AST5 files PASS, diff-check clean, secret scan found only synthetic sentinel.
Final hashes: requirements9fc989af; rebuild2c94eb5b; patch0ed6f6bd; wheel3648009d; READMEfad812b0; loginprobe9e925141; logintest4a31661d; transportprobeb0df91a4; transporttestc3fa6d75.
LSP diagnostics tooling unavailable in this leaf; AST and executed isolated probes substituted. Ordinary repo-venv pytest remains expected to fail until dependency sync because installed pykrx is cookie.1; direct packaged-wheel probes passed. Root validation uses fresh scratch venv and candidate wheel.
