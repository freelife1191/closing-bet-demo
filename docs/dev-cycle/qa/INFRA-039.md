# [INFRA-039] QA 시나리오

Flask 바인딩을 loopback 으로 좁힌 변경의 검사 목록입니다.

## 대상과 범위

바꾼 자리는 `config.py` 의 `FLASK_HOST` 기본값, `restart_all.sh` 의 gunicorn `--bind`,
추적하지 않는 `.env` 와 `.env.production` 의 `FLASK_HOST` 값입니다. `app/__init__.py` 의
죽은 `__main__` 블록을 지웠고, `.env.example`·`Procfile`·`README.md`·`AGENTS.md`·
`CLAUDE.md`·`services/identity_helpers.py` 의 설명을 고쳤습니다.

## 실행 전 반드시 알아야 할 것

**바인딩 변경은 `kill -HUP` 으로 반영되지 않습니다.** gunicorn 마스터가 리스닝 소켓을
잡고 워커가 그것을 상속하므로, HUP 은 워커만 새로 띄우고 소켓은 그대로 둡니다. 파이썬
코드 변경에는 HUP 이 충분하지만 이 항목의 QA 는 `./stop_all.sh` 와 `./restart_all.sh` 로
완전히 재기동해야 합니다.

**비용이 들거나 되돌릴 수 없는 조작은 하지 않습니다.** 알림 테스트 발송, 재분석,
모의투자 주문, Market Gate 갱신을 실행하지 않습니다. 아래 시나리오는 모두 읽기 전용
요청이거나 프로세스 상태 확인입니다.

`/api/health` 는 존재하지 않습니다. `app.route('/health')` 로 등록되어 있어 `/health`
이며, `/api/kr/status` 가 blueprint 아래의 읽기 전용 경로입니다.

## 기준값 (변경 전 실측, 2026-09-07)

| 확인 | 값 | 명령 |
|---|---|---|
| 바인딩 | `*:5501` | `lsof -nP -iTCP:5501 -sTCP:LISTEN` |
| LAN 에서 Flask 직접 | `200` | `curl http://192.168.50.7:5501/api/kr/status` |
| LAN 에서 Next | `200` | `curl http://192.168.50.7:3500/api/kr/status` |

LAN 주소는 `ipconfig getifaddr en0` 으로 구합니다. 기기가 바뀌면 그 값을 다시 읽습니다.

## 시나리오

| ID | 검사 | 기대값 | 필수 |
|---|---|---|---|
| S-1 | 재기동 뒤 `lsof` 로 바인딩 확인 | `127.0.0.1:5501` (`*:5501` 이 아님) | 필수 |
| S-2 | LAN 주소로 Flask 직접 접속 | 연결 거부 (`curl` 종료 코드 7) | 필수 |
| S-3 | LAN 주소로 Next 접속 | `200` 유지 | 필수 |
| S-4 | loopback 으로 Flask 직접 접속 | `200` 유지 | 필수 |
| S-5 | Next 를 거친 API 응답 | `200` 이고 본문이 변경 전과 같음 | 필수 |
| S-6 | 브라우저에서 대시보드 화면 | 자료가 정상 표시되고 콘솔 오류 없음 | 필수 |
| S-7 | `.env` 에서 `FLASK_HOST` 를 지운 하위 프로세스 | `config.FLASK_HOST` 가 `127.0.0.1` | 필수 |
| S-8 | `FLASK_HOST=0.0.0.0` 을 준 하위 프로세스 | `0.0.0.0` (넓히는 길이 살아 있음) | 필수 |
| S-9 | `Procfile` 을 표준 정규식으로 파싱 | `web` 프로세스가 잡힘 | 필수 |
| S-10 | `bash -n restart_all.sh` | 종료 코드 0 | 필수 |
| S-11 | 신원 서명이 필요한 경로가 여전히 동작 | 로그인 상태에서 챗봇 목록이 보임 | 선택 |

**S-1 이 이 항목의 핵심입니다.** 보안 리뷰가 지적한 대로 `config.FLASK_HOST` 는
`python flask_app.py` 만 읽고 운영 gunicorn 은 `restart_all.sh` 의 셸 변수를 읽습니다.
운영 경로의 바인딩을 검사하는 단위 테스트는 없으므로 이 실측이 그 자리를 대신합니다.

S-11 을 선택으로 둔 이유는 로그인이 필요하고, 이 사이클은 관리자 계정으로 로그인하지
않기 때문입니다. 익명 상태로 화면이 뜨는 것은 S-6 이 덮습니다.

## 결과 (2026-09-07 실행)

기준 커밋은 `aaf1c53` 입니다. `./stop_all.sh` 와 `./restart_all.sh` 로 완전히 재기동한 뒤
실행했습니다.

| ID | 결과 | 증거 |
|---|---|---|
| S-1 | **통과** | `lsof` 출력이 `*:5501` → `127.0.0.1:5501`. Next 는 `*:3500` 유지 |
| S-2 | **통과** | `curl http://192.168.50.7:5501/api/kr/status` 가 종료 코드 7, `http_code=000`. 재기동 직전 같은 명령은 200 이었습니다 |
| S-3 | **통과** | `curl http://192.168.50.7:3500/api/kr/status` = 200 |
| S-4 | **통과** | `curl http://127.0.0.1:5501/api/kr/status` = 200 |
| S-5 | **통과** | Next 경유와 Flask 직접의 응답 본문이 같습니다 (`collected_stocks: 1997`, 같은 `updated_at`) |
| S-6 | **통과** | `localhost:3500/dashboard/kr` 에서 Market Gate `55 Neutral`, KOSPI 200 섹터 지수 12개 전부 표시, 마지막 업데이트 21:19. 콘솔 오류 0건 |
| S-7 | **통과** | `pytest tests/app/test_flask_binding.py::test_default_host_is_loopback` |
| S-8 | **통과** | `pytest tests/app/test_flask_binding.py::test_explicit_host_still_wins` |
| S-9 | **통과** | 표준 Procfile 정규식으로 파싱해 `web` 프로세스가 잡힙니다. 주석 두 줄은 무시됩니다 |
| S-10 | **통과** | `bash -n restart_all.sh` 종료 코드 0 |
| S-11 | 미실행 | 선택 항목입니다. 이 사이클은 관리자 계정으로 로그인하지 않습니다 |

필수 10건이 모두 통과했습니다.

### 정적 검증

- `pytest` 1794 통과 · 2 skip (신규 2건 포함), 종료 코드 0
- `npx vitest run` 328 통과 (54 파일), `npm run type-check` 종료 코드 0
- `git diff --cached --check` 종료 코드 0

### S-6 에서 겪은 오판과 그 원인

처음에 `127.0.0.1:3500` 으로 화면을 열었더니 Market Gate 가 `--Score` 와 `Analyzing...`
에 갇히고 섹터 지수가 빈 상자로 나왔습니다. 이것을 결함으로 판정할 뻔했습니다.

원인은 이번 변경이 아니라 접속 주소였습니다. Next.js 의 `allowedDevOrigins` 가 개발
서버에서 `localhost` 만 기본 허용하므로, `127.0.0.1` 로 열면 페이지는 200 으로 뜨지만
클라이언트가 부르는 API 가 막힙니다. 콘솔에는 아무 오류도 남지 않고
`logs/frontend.log` 에만 「add it to allowedDevOrigins」 안내가 찍힙니다.

`curl` 은 오리진 검사에 걸리지 않아 `127.0.0.1:3500` 으로도 200 을 받습니다. 그래서
curl 이 통과했다는 사실이 브라우저도 된다는 뜻이 아니었습니다. 같은 함정을 다음 사이클이
밟지 않도록 `references/browser-notes.md` 에 적었습니다.

### 정리

- 브라우저 탭을 `about:blank` 로 되돌렸습니다. 다른 작업의 탭은 건드리지 않았습니다.
- 스크린샷 두 장은 스크래치패드에만 두었고 저장소에 남기지 않았습니다.
- 비용이 드는 조작은 하나도 실행하지 않았습니다. 알림 테스트 발송, 재분석, 모의투자,
  Market Gate 갱신 버튼을 누르지 않았습니다.
- 서버는 새 코드로 떠 있는 상태를 유지합니다.
