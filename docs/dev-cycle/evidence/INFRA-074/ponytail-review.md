# INFRA-074 ponytail review

Baseline: `92d84ab`

`scripts/service_lifecycle.sh:L349-378: shrink: backend/frontend HTTP 확인이 urllib heredoc 두 개와 curl 선택 갈래로 중복된다. 동기화 뒤 항상 존재하는 venv Python 한 경로에 service 인자를 넘겨 backend만 JSON object를 검사하면 된다.`

`tests/test_restart_cleanup_contract.py:L8-20: delete: helper 이름과 금지 문자열을 읽는 정적 검사는 unmanaged listener·respawn·PID 재사용 실행 회귀와 중복되고 구현 이름에 결합된다. 동적 lifecycle 회귀가 대체한다.`

`net: -33 lines possible.`

## Reviewed hashes

```text
9bf65e0f9070543d5895cc55aaa00628e5f94df092e75bb75c5dfe76d73dbd83  restart_all.sh
51d75910fa62c5476c4c54a02b9e29b71b470528b4e5c739347308164fe5b38c  stop_all.sh
cebe9712fe31a64c5c8d11d2944cadd76ab84ab1697bfc75f66330159666247e  scripts/service_lifecycle.sh
ecd34f67ab25b8f83cf9945579cd3d42be56d6647f6c080b391dd177bf090e70  scripts/sync_dependencies.sh
9fc989afb5d20544f2d78d5ced444d82ac6c4ac4ef5d24c484bff7dd7534f20a  requirements.txt
2c94eb5be01aaf3c6d43694c557bfbe9a6f0df27c6dc719b8d114789013687dc  vendor/pykrx/rebuild.py
bca44af927096df32629c0990fbc2e1b38a0931ed2173f2b0ef473cb3b374201  vendor/pykrx/transport.patch
b5188c46444315d75cdd1b15ef5a70b5b91e766c7f4a94d804c92e12cb87ac18  vendor/pykrx/README.md
0ac5b63575717f7794833e4da3276f95a5d0eba57ba5c34ff1dbf8448a457ba8  vendor/pykrx/pykrx-1.2.9+cookie.2-py3-none-any.whl
00da9f245b976199cbdb85c01bb9c4caeaa8f3e2f0f9525d40b27a550e1a5d0e  tests/scripts/test_service_lifecycle.py
25a923275478b0df6eea671ea35feb851defebcaf757d2ade309ab86871e7a92  tests/scripts/test_lifecycle_adversarial.py
59c1139c65469bc8f3f6b45edbdc72c69a5a9cd04ed44ba66d29111899cbca26  tests/scripts/test_sync_dependencies.py
8fd2301a054807eacc08143b8ebe8d0259762799cc330171db612985051dc50b  tests/test_restart_cleanup_contract.py
e2586afc988b4a08e93c7014cdf14fe3e305737522e1afa5ad560be976d0ac99  tests/test_pykrx_login_guard.py
a26e6205cb63b401c7756a5d62f3ba25fa7f68fb70e6b4658205fa1c1c89f2b8  tests/fixtures/pykrx_login_guard_probe.py
d202dbc4ba664698ac617b430c68e4531ec10c10296ac37717d8af6a924a4387  scoped diff from 92d84ab
```

## Final disposition
Both simplifications applied: one urllib probe; replaced static cleanup string test with dynamic lifecycle tests. Earlier hashes above intentionally retained as review history, superseded by final frozen.json and deep-review.md (which reviewed final login redirect and lifecycle changes). No old wheel is deployed.
