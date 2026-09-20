# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 최종 필수 QA가 통과한 완료 항목만 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.
>
> 2026-09-01 여섯 카테고리 감사(`[INFRA-004]`)로 30개 항목이 들어왔습니다. 각 항목의
> 근거에 적힌 `AUDIT-*` 문서는 `docs/dev-cycle/audits/` 에 있으며, 항목마다 위치를
> 절 번호까지 적어 두었으므로 사이클을 시작할 때 그 절을 먼저 읽습니다.
> 2026-09-07 `[INFRA-036]` 으로 백로그를 현행화했습니다. 해소된 항목 9건을 제거하고 같은 원인의
> 항목 26건을 병합했으며, 목록과 사유는 `archive/2026-09.md` 의 「백로그 정리」 절에 있습니다.

> 2026-09-09 비상용 검토 정정: 긴급성이 낮다는 이유로 제외했던 19건을 복구했습니다(검토 시점 68건). 이후 완료 건은 아카이브에 따라 제거합니다.
> 구조 통합·입력 보강·업그레이드·화면 개선도 유효한 작업입니다. 필요성과 실행 순서를 구분하고,
> 관련 코드와 검증을 공유하는 항목은 묶어서 진행합니다. 기존 체크리스트와 설계 선택지는 보존합니다.
> 판단 정정 기록: [백로그 검토](reviews/backlog-noncommercial-2026-09-09.md).

## P0 — 즉시

## P1 — 이번 주기

### [INFRA-045] 감사 로그의 IP 를 요청자가 헤더 한 줄로 정할 수 있다
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-039]` 사이클의
  `oh-my-claudecode:critic` 지적(확신도 높음). 실측으로 확인했습니다.
- Next.js 16.3.4 는 `frontend/node_modules/next/dist/server/base-server.js:612` 에서
  `req.headers['x-forwarded-for'] ??= originalRequest?.socket?.remoteAddress` 로 헤더를
  붙입니다. **`??=` 이므로 클라이언트가 보낸 값을 덮어쓰지 않습니다.** 브라우저가
  `X-Forwarded-For: 203.0.113.9` 를 보내면 그 값이 그대로 감사 기록에 남습니다.
- `POST /api/system/log-event` 로 실측한 결과입니다. 헤더 없이 Next 를 거치면
  `::ffff:127.0.0.1`, 위조 헤더를 붙이면 `203.0.113.9`, Flask 에 직접 보내면
  `198.51.100.4` 가 기록되었습니다.
- 같은 패턴이 세 자리에 있습니다. `app/__init__.py:207` 의 `_resolve_real_ip`,
  `app/routes/common_update_routes.py:97` 의 `_resolve_request_ip`,
  `services/kr_market_chatbot_request_helpers.py:212` 의 `extract_chatbot_client_ip`
  입니다. 세 번째는 챗봇 대화 로그, 두 번째는 `/api/system/log-event` 의 IP 입니다.
- **`ProxyFix(app.wsgi_app, x_for=1)` 로는 막지 못합니다.** 위조 값이 이미 헤더에 들어
  있으므로 홉 수를 세는 것으로는 걸러지지 않습니다.
- **`proxy.ts` 에서는 헤더를 지울 수는 있어도 다시 쓸 수는 없습니다.** Next 15 에서
  `request.ip` 가 사라졌고, proxy 는 `??=` 가 실행된 뒤에 돌아 이미 채워진 헤더만
  봅니다. 그 값이 클라이언트가 보낸 것인지 Next 가 붙인 것인지 구분할 방법이 없습니다.
  그러므로 proxy 에서 지우는 것은 Flask 에서 헤더를 안 읽는 것과 결과가 같고,
  「위조를 막으면서 진짜 IP 를 지키는」 길은 어느 쪽에도 없습니다.
- 그러므로 이 항목은 앞단 배포 구조를 먼저 정해야 합니다. Flask 앞에 신뢰할 수 있는
  리버스 프록시(nginx·Cloudflare 등)가 서는지, 아니면 Next 가 유일한 앞단인지에 따라
  답이 갈립니다. 전자면 그 프록시가 헤더를 다시 쓰고 `ProxyFix` 의 홉 수를 그에 맞춥니다.
  후자면 헤더를 버리고 `remote_addr` 만 쓰는 편이 정직합니다.
- `[INFRA-039]` 가 바인딩을 좁혀 Flask 직접 경로는 막혔습니다. 남은 것은 Next 경유
  위조이며, 그 경로로는 브라우저가 보낸 헤더가 그대로 통과합니다.
- 기존 테스트 `tests/app/test_common_routes_refactor.py:288` 의
  `assert captured["ip_address"] == "10.0.0.1"` 과
  `tests/app/test_kr_market_chatbot_service.py:483` 이 지금의 헤더 신뢰 동작을 못 박고
  있습니다. 방향을 바꾸면 이 둘도 함께 고쳐야 합니다.
- QA 시나리오: 브라우저 개발자 도구로 `X-Forwarded-For` 를 붙여 요청해도 감사 로그에
  그 값이 남지 않는다
- [ ] 앞단 배포 구조를 확인해 헤더를 신뢰할지 버릴지 결정
- [ ] 세 자리를 그 결정에 맞춤 (한 자리만 고치지 않는다)
- [ ] 기존 테스트 두 건을 새 계약에 맞게 고침
- [ ] 감사 로그의 IP 가 무엇을 뜻하는지 코드 주석에 적음

- 진행 상태 (2026-09-09): 실제 앞단 프록시 구성·Procfile 기반 PaaS 사용 계획 정보 대기. 사용자의 연속 진행 요청에 따라 독립적으로 처리 가능한 INFRA-017·038을 먼저 완료했으며, 이 항목의 배포 정책은 아직 변경하지 않았다.

### [INFRA-046] `Procfile` 이 지금 아키텍처에서 동작하지 않는 배포 방식을 남겨 둔다
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-039]` 사이클의
  `oh-my-claudecode:security-reviewer` 지적(심각도 중, 확신도 높음). 파일을 열어 확인했습니다.
- `Procfile` 은 `web: gunicorn flask_app:app` 한 줄이며 **Flask 만 띄웁니다.** Next.js 를
  띄우는 줄이 없습니다.
- 그런데 `[INFRA-027]` 이후 신원 확정은 `frontend/src/proxy.ts` 가 맡습니다. proxy 가 없으면
  `X-Auth-Identity` 를 붙이는 자리가 없어 **모든 요청이 익명으로 처리됩니다.** 챗봇 소유자
  판정과 AI 분석, `[INFRA-037]` 이 세운 관리자 알림 게이트가 전부 막힙니다.
- 동시에 PaaS 라우터가 그 프로세스를 인터넷에 공개하므로 Flask 가 직접 노출됩니다.
  `[INFRA-039]` 가 다른 자리를 loopback 으로 좁힐 때 이 파일만 `0.0.0.0` 을 남긴 이유가
  그 노출이며, 그래서 「앞단에서 이 포트를 막는다」는 지시가 성립하지 않습니다. 그 포트가
  곧 서비스 포트이기 때문입니다.
- 저장소에 PaaS 설정 파일(`app.json`·`render.yaml`·`fly.toml`·`Dockerfile` 등)이 하나도
  없고, `Procfile` 은 2026-02-03 「Deployment Ready」 커밋 한 번으로 들어온 뒤 손대지
  않았으며 어느 문서에도 언급이 없습니다. 실제로 쓰이는 경로가 아닐 가능성이 높습니다.
- `[INFRA-039]` 는 이 파일에 「이 경로로 배포하지 않는다」는 주석을 달아 두었습니다.
  주석은 임시 조치이며 파일 자체의 처리를 정해야 합니다.
- 선택지는 셋입니다. (가) 파일을 지웁니다. 쓰이지 않는 것이 확인되면 가장 정직합니다.
  (나) Next 와 Flask 를 함께 띄우도록 고칩니다. 그러려면 프로세스 두 개와 그 사이의
  loopback 연결을 정의해야 합니다. (다) 지금처럼 주석만 두고 남깁니다.
- 어느 쪽이든 실제 배포 계획을 먼저 확인해야 합니다.
- [ ] 이 저장소가 PaaS 배포를 쓸 계획이 있는지 확인
- [ ] 그 답에 따라 파일을 지우거나 두 프로세스로 고침
- [ ] `services/identity_helpers.py` 와 `.env.example` 의 `Procfile` 언급을 결과에 맞춤

- 진행 상태 (2026-09-09): 실제 앞단 프록시 구성·Procfile 기반 PaaS 사용 계획 정보 대기. 사용자의 연속 진행 요청에 따라 독립적으로 처리 가능한 INFRA-017·038을 먼저 완료했으며, 이 항목의 배포 정책은 아직 변경하지 않았다.

### [FLOW-014] 자료가 얇은 기준일에서 수급 조회가 종목 수만큼 pykrx 왕복을 낸다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: `[FLOW-011]` 사이클의 code-reviewer 지적과 실측
- `[FLOW-011]` 이 호출자를 `verify_with_references=True` 한 번 호출로 바꾸면서, CSV 에
  5거래일이 모이지 않은 종목이 참조 조회 대상이 되었습니다. 예전에는 그 자리에서 값 없이
  끝났으므로 조회가 없었습니다. 정확성을 얻고 시간을 내준 맞바꿈입니다.
- 대상 종목 수가 기준일에 따라 크게 달라집니다. `_get_or_build_trend_map` 과
  `_detect_csv_anomaly_flags` 를 직접 돌려 2026-09-04 자료로 잰 값이며, 전체는 1997 종목
  입니다. **「신규」만 이번 변경이 만든 비용입니다.** 「기존」은 플래그가 붙어 예전에도
  둘째 호출이 참조를 받아 오던 종목이라 비용이 달라지지 않았습니다.

  | target_date | 신규 (`missing_csv`) | 기존 (플래그 있음) |
  |---|---|---|
  | 최신 (`target_date=None`) | **0** | 20 |
  | 2026-02-23 | 57 | 7 |
  | 2026-01-15 (CSV 시작일 부근) | **1997** | 0 |

- 비용의 모양이 비대칭입니다. 자료가 정상이면 정확히 0 이고, 자료가 얇아진 순간에만 전
  종목으로 튑니다. 평소에 재면 아무 문제가 없어 보이는 것이 이 항목의 어려운 점입니다.

- 최악의 경로는 `python scripts/init_data.py vcp-signal <과거날짜>` 입니다. `max_stocks`
  기본값이 600(`engine/constants_market_system.py`)이고 `engine/screener.py:227` 의 순회가
  순차이므로, 왕복 0.3~1초로 잡으면 한 번에 3~10분이 붙습니다. 스케줄러와 `all` 경로는
  `target_date=None` 이라 Toss 우선 경로로 가므로 해당하지 않습니다.
- 최신 창(`target_datetime=None`)에서는 왕복이 종목당 두 번이 될 수 있습니다.
  `_resolve_best_payload:823` 의 `if not pykrx_ref and is_latest_reference_window` 때문에
  pykrx 가 빈손이면 Toss 까지 부릅니다. 위 표의 「왕복 × 종목 수」 계산은 과거 기준일에서만
  정확합니다. 과거 기준일은 `is_latest_reference_window` 가 거짓이라 Toss 를 건너뜁니다.
- 상세 조회 라우트(`app/routes/kr_market_data_backtest_stock_routes.py:54` 의
  `get_stock_detail`)는 끝까지 동기 경로입니다. 그래서 막히는 것은 이벤트 루프가 아니라
  gunicorn 워커 스레드(`--workers 2 --threads 8`)입니다. 15분 슬롯 캐시가 앞에 있어 평소
  노출은 좁지만, CSV 가 4영업일 넘게 낡아 `stale_csv` 가 전 종목에 붙으면 모든 상세 조회가
  이 경로로 들어갑니다.
- 참조 조회 실패는 캐시되지 않습니다. `services/investor_trend_5day_service.py:763` 이
  「miss(None)를 장시간 캐시하지 않아 일시 장애 후 재시도를 허용한다」고 명시하며
  `test_reference_cache_does_not_pin_miss_result` 가 그 동작을 고정합니다. 그래서 pykrx
  에도 자료가 없는 종목은 매 호출마다 왕복을 새로 냅니다.
- 요청 처리 경로도 범위에 들어갑니다. Toss 참조는 `timeout=10` 에 재시도 3회라 최악
  33초가량 워커를 붙잡고, pykrx 쪽은 이 저장소가 시간 제한을 걸지 않습니다. 종목 상세
  페이로드 캐시가 슬롯마다 한 번으로 눌러 주고 기존에도 `get_full_stock_detail` 이 왕복
  6회를 내므로 증폭 자체는 크지 않습니다. `[FLOW-011]` 사이클의 security 리뷰가 짚었습니다.
- [ ] 실패를 짧게(분 단위) 캐시할지, 아니면 호출자가 대량 경로임을 알릴 수단을 둘지 정함
- [ ] 요청 처리 경로에는 참조 조회의 전체 시간 예산을 두고 초과하면 CSV 로 내려가는 편이
      나은지 검토. 대량 배치 경로와 요구가 다릅니다
- [ ] 정한 방식으로 과거 기준일 스크리닝 한 번의 소요 시간을 재고 개선폭을 기록
- [ ] 실패 캐시를 넣는다면 `test_reference_cache_does_not_pin_miss_result` 의 의도와
      충돌하지 않는지 확인하고, 충돌하면 그 검사의 겨냥점을 옮김
- [ ] 참조 조회 횟수를 고정하는 검사를 넣을지 정함. 지금은 `_detect_csv_anomaly_flags`
      의 판정을 넓혔을 때 종목마다 네트워크가 붙기 시작해도 알려 줄 검사가 없습니다.
      `test_get_investor_trend_5day_for_ticker_skips_reference_when_csv_is_normal` 이
      한 종목으로 같은 불변식을 보고 있으므로, 겹치지 않는 형태를 찾아야 합니다

### [INFRA-030] 레거시 `engine/collectors.py` 와 모듈형 `engine/collectors/` 가 공존해 죽은 코드가 남는다
- 카테고리: 인프라 | 티어: T3 | 근거: `[FLOW-011]` 사이클(수급 호출자 통합)의 실측
- `engine/collectors.py` 가 `__path__` 를 스스로 지정해 모듈이면서 패키지처럼 동작합니다
  (`:31-34`). 파일 끝(`:2486-2501`)에서 `EnhancedNewsCollector` 와 `NaverFinanceCollector`
  만 모듈형으로 덮어쓰고 `KRXCollector` 는 덮어쓰지 않습니다.
- 그래서 같은 일을 하는 코드가 두 벌 있고 한 벌만 실행됩니다. 실측으로 확인한 것은
  다음 둘입니다.
  - `engine/collectors.py` 의 `NaverFinanceCollector._get_investor_trend` 는 모듈형에
    덮여 실행되지 않습니다. `from engine.collectors import NaverFinanceCollector` 가
    모듈형을 가져옵니다
  - `engine/collectors/krx_local_data_mixin.py` 의 `get_supply_data` 는
    `engine.collectors.krx.KRXCollector` 를 임포트하는 실행 코드가 없어 테스트에서만
    돕니다. 실행되는 것은 `engine/collectors.py` 의 `KRXCollector` 입니다
- 두 벌이 갈라지면 어느 쪽을 고쳤는지 알 수 없습니다. `[FLOW-011]` 이 판정 헬퍼를
  정리할 때 실행되지 않는 자리까지 함께 고쳐야 했습니다.
- 같은 자리에 개인 수급의 일관성 문제가 하나 겹쳐 있습니다. 서비스는 개인 수급을 돌려주지
  않으므로 `engine/collectors/krx_local_data_mixin.py:1237` 은 정상 경로에서 `retail_buy_5d=0`
  을 넣고 `engine/collectors/naver_pykrx_mixin.py:453` 은 `individual` 을 0 으로 둡니다.
  이상징후로 pykrx 경로에 빠질 때만 실값이 채워집니다. 같은 필드가 어느 경로를 거쳤느냐에
  따라 0 이기도 실값이기도 합니다. `[FLOW-011]` 사이클의 code-reviewer 가 짚었습니다.
- [ ] 어느 구현을 남길지 정하고 나머지를 지움
- [ ] `__path__` 조작을 없앨 수 있는지 확인 (`engine/collectors/__init__.py` 로 대체)
- [ ] 지운 쪽만 검사하던 테스트를 남긴 쪽으로 옮기거나 지움
- [ ] 개인 수급을 늘 0 으로 둘지, 서비스가 함께 돌려주게 할지 정하고 두 경로를 맞춤

### [JONGGA-033] 종목 상세 모달의 EPS·순이익 부호가 어긋나고 PER 툴팁이 음수를 설명하지 못한다
- 카테고리: 종가베팅 | 티어: T1 | 근거: 2026-09-05 `[FLOW-012]` 사이클의 `/qa-only` ISSUE-001·ISSUE-003
- 2026-09-07 백로그 정리에서 `[FE-035]` 를 흡수했습니다. 같은 모달의 같은 재무 절입니다.
- QA 시나리오: 상세 모달의 EPS 부호와 「재무 정보」 순이익 부호가 같은 방향을 가리키고, PER 이
  음수인 종목의 툴팁이 그 값을 어떻게 읽어야 하는지 알려 준다
- **EPS 와 순이익**: 로보티즈(108490)는 EPS 가 `-266` 인데 순이익이 `26억` 이고,
  레인보우로보틱스(277810)는 EPS 가 `87` 인데 순이익이 `-7091만` 입니다. S-Oil·한미반도체·LG전자는
  일치합니다. EPS 툴팁이 자기를 「순이익 ÷ 발행주식수」로 설명하므로 대조한 사용자는 한쪽이
  틀렸다고 읽습니다. 두 값 모두 Toss 응답에서 오며 `services/kr_market_stock_detail_service.py:502`
  의 `indicators.eps` 와 같은 함수의 `financials.net_income` 입니다. EPS 가 최근 4분기 합산이고
  순이익이 다른 기간일 가능성이 높으므로 Toss 원본에서 두 필드의 기준 기간을 먼저 확인합니다.
- **PER 툴팁**: 로보티즈의 PER 은 `-1147.60` 인데 `closing-bet/page.tsx:645` 의 툴팁은 「낮을수록
  저평가, 업종 평균과 비교 필요」라고만 적혀 있습니다. 음수 PER 은 적자라는 뜻이라 저평가와
  무관한데, 툴팁대로 읽으면 가장 저평가된 값으로 오독합니다. 「음수면 적자를 뜻하므로 비교
  대상이 아닙니다」 한 줄이면 됩니다.
- [ ] Toss 응답에서 EPS 와 순이익의 기준 기간이 서로 다른지 확인
- [ ] 기간이 다르다면 화면에 그 기준을 함께 적거나 같은 기간으로 맞춤
- [ ] PER 툴팁에 음수 사례 설명을 더함

### [VCP-022] VCP 상세 모달의 세 탭 가운데 둘은 아직 0% 를 그릴 수 있다
- 카테고리: VCP 시그널 | 티어: T3 | 근거: 2026-09-07 JONGGA-008 의 code-review 와 QA
- `[JONGGA-008]` 이 확신도 없음을 값 없음으로 고쳤지만 그 화면의 게이지는 활성 탭에 따라
  세 추천 가운데 하나를 봅니다. 고쳐진 것은 `_build_vcp_gemini_recommendation` 이 CSV 에서
  만드는 gemini 추천 하나뿐입니다. gpt 와 perplexity 추천은 `ai_analysis.json` 캐시에서
  오고 그 캐시는 `engine/vcp_ai_analyzer_helpers.py:658` 의
  `_normalize_confidence_value(..., default=0)` 을 지납니다. **남는 것은 규칙이 두 벌이라는
  중복 문제가 아니라, 방금 고친 그 화면의 세 탭 중 둘이 여전히 0% 를 그릴 수 있다는 잔여
  결함입니다.** `getRec` 이 병합 결과 대신 원시 캐시를 다시 보는 두 번째 후보
  (`stock?.gemini_recommendation`)도 같은 경로입니다.
- 남는 창은 좁습니다. `confidence` 키가 있으되 숫자가 아닌 응답이 그 자리에서 0 이 됩니다.
  `is_low_quality_recommendation` 이 확신도를 숫자로 읽지 못하는 응답을 저품질로 판정해
  되돌리고, 점수 기반 대체 경로(`engine/vcp_ai_analyzer_helpers.py:576-582`)는 언제나
  확신도를 만들어 내기 때문입니다. 그래도 창이 닫혀 있지는 않습니다.
- 티어 판정: `engine/vcp_ai_analyzer_helpers.py` 는 `tier-rules.md` §2 의 위험 경로
  「VCP 판정」입니다(그 문서 204행). 한 줄만 고쳐도 T3 입니다. `[JONGGA-008]` 이 T2 를
  유지하려고 이 파일을 건드리지 않았고 그 결과 이 잔여 결함이 남았습니다.
- 낮은 확신도로 함께 볼 것 하나. `int(float(v))` 는 버림이라 `0.9` 는 0 이 됩니다.
  `tests/services/test_kr_market_vcp_payload_service_refactor.py:45` 의 픽스처가
  `"ai_confidence": 0.9` 를 담고 있어 0~1 척도 생산자의 흔적일 가능성이 제기되었습니다.
  2026-09-07 확인 결과 그 검사는 캐시 동작만 단언하고 확신도 값을 보지 않으며 같은
  픽스처의 `entry_price: 100.0` 과 `return_pct: 1.0` 도 임의 값입니다. 저장소에서 확신도를
  만드는 자리는 모두 0~100 정수이므로 재현 경로를 찾지 못했습니다. 이 항목에서 그 척도를
  쓰는 생산자가 실제로 있는지 한 번 더 확인합니다.
- 범위에서 뺀 것: `RecommendationCombiner.combine` 의 「둘 다 없음 → confidence 0」은
  다루지 않습니다. code-review 가 경로를 끝까지 따라가, 그것이 만드는
  `final_recommendation` 이라는 이름은 저장소에서 `engine/kr_ai_analyzer.py:109` 와 검사
  두 줄에만 나오고 병합은 `_AI_RECOMMENDATION_FIELDS` 세 개만 옮기며 프론트엔드에는 그
  이름이 없다는 것을 확인했습니다. 2026-09-07 직접 grep 으로도 세 자리뿐임을 확인했습니다.
- 같은 파일에 `inf` 구멍이 두 자리 남아 있습니다. `[JONGGA-008]` 이 `safe_confidence` 에서
  고친 것과 도달 조건이 같은데, 위험 경로라 그 라운드에서 손대지 못했습니다.
  `engine/vcp_ai_analyzer_helpers.py:221-223` 의 `is_low_quality_recommendation` 과
  `:305-307` 의 `_normalize_confidence_value` 가 `int(float(...))` 를
  `except (TypeError, ValueError)` 로만 감쌉니다. `OverflowError` 는 `ValueError` 가 아니라
  `ArithmeticError` 의 하위라 걸리지 않습니다. 앞엣것은 입력이 원시 LLM 응답이고 호출부
  다섯 곳(`engine/vcp_ai_analyzer.py:361`, `547`, `563`, `1021`, `1070`)에 지역 예외 처리가
  없습니다.
- 같은 화면 같은 열에 걸린 별건 하나를 함께 다룹니다. `GeminiStrategy.analyze` 와
  `GPTStrategy.analyze`(`engine/kr_ai_strategies.py:66-68`, `120-122`)의 docstring 이
  「현재는 안정성을 위해 Mock 기반 분석 결과를 반환한다」이며, 사유를 `random.choice` 로
  조립하고 확신도를 `random.randint` 로 만들며 `action` 을 `"BUY"` 로 고정합니다. 그
  산출물이 `scripts/init_data.py:2318-2328` 을 거쳐 `data/ai_analysis_results_*.json` 으로
  저장되고, `services/kr_market_vcp_payload_service.py:275` 가 읽어 VCP 화면의 gemini·gpt
  탭에 그려집니다. 호출 지점 둘 다 살아 있습니다(`scripts/init_data.py:2675` 배치와
  `services/kr_market_route_service.py:138` 의 사용자 재분석).
  - 2026-09-07 전수 확인: **이미 실제로 발생한 적이 있습니다.** `MockAnalysisTemplates`
    의 문구가 `data/` 의 아홉 개 분석 파일 어디에 나타나는지 세었습니다.

    | 파일 | 화면에 닿는 두 필드 | `final_recommendation` |
    |---|---|---|
    | `ai_analysis_results_20260211.json` | **모의 2** · 실제 2 | 모의 2 |
    | `ai_analysis_results_20260212·13·20·26` | 모의 0 · 실제 3~6 | 없음 |
    | `ai_analysis_results_20260505.json` | 모의 0 · 실제 8 | 모의 4 |
    | `ai_analysis_results.json`, `kr_ai_analysis.json` | 모의 0 · 실제 8 | 모의 4 |

    최신 자료는 화면에 닿는 두 필드가 모두 실제 분석입니다. 실제 분석 경로가 나중에 돌아
    그 둘을 덮어쓰고, 덮이지 않는 `final_recommendation` 에만 모의가 남기 때문입니다.
    그런데 **2026-02-11 자료는 그 둘에 모의 산출물이 2건 남아 있습니다.** 그날은 덮어쓰기가
    일어나지 않았다는 뜻이고, 화면에서 그 날짜를 조회하면 무작위로 조립된 사유가 「Gemini
    분석」으로 보입니다. 잠재 문제가 아니라 이미 한 번 새어 나온 문제입니다. 이 항목에서
    두 경로의 선후를 확정하고, 모의 산출물이 화면에 닿는 필드에 들어가지 못하게 막습니다.
  - 대조 방법 둘을 함께 적어 둡니다. 사유에 `MockAnalysisTemplates` 의 문구(「주력 제품의
    수출 호조세 지속」·「K-칩스법」·「PER 밴드 하단」 등)가 있는지 보는 것과, `action` 이
    전 종목 `BUY` 로만 채워져 있는지 보는 것입니다. `engine/kr_ai_strategies.py:99` 가
    `action` 을 `"BUY"` 로 고정하므로 실제 분석 경로만 `HOLD` 와 `SELL` 을 냅니다.
- 티어 규칙에 관해 판단이 필요한 것이 하나 있습니다. code-review 가 확신도 중간으로
  제기했습니다. `engine/signal_tracker_ai_helpers.py` 의 `apply_ai_results` 는
  `ai_action`·`ai_confidence`·`ai_reason`·`ai_provider` 네 열을 직접 만들어 넣는 자리인데
  `tier-rules.md` §2 의 「VCP 판정」 목록에 없습니다. 그 절이 두 파일을 목록에 넣은 근거를
  「이 결정이 VCP 표의 AI 추천 열을 그대로 좌우하므로」라고 적고 있어 실질이 같습니다.
  다만 §4 의 갱신 조건은 「파일이 새로 생기거나 이동」과 「목록 밖 파일에 `CREATE TABLE` 이
  새로 들어옴」 둘뿐이라 문언이 곧바로 추가를 요구하지는 않습니다. 목록에 넣으면 그 파일을
  건드리는 모든 항목이 T3 이 됩니다.
  2026-09-07 사용자 결정: **이 항목에서 정합니다.** 지금은 목록을 바꾸지 않고, 같은 파일을
  실제로 여는 이 라운드에서 판단합니다. 그 사이에 다른 항목이 이 파일을 건드리면 현행
  목록대로 T2 로 판정합니다.
- QA 시나리오: gpt 탭과 gemini 탭의 확신도 게이지가 같은 규칙으로 그려진다
- [ ] `_normalize_confidence_value` 와 `safe_confidence` 를 한 벌로 합친다
- [ ] `getRec` 의 원시 캐시 후보가 병합 결과와 같은 규칙을 쓰는지 확인한다
- [ ] 0~1 척도로 확신도를 저장하는 생산자가 실제로 있는지 확인한다
- [ ] 같은 파일의 `inf` 구멍 두 자리를 함께 막는다
- [ ] 모의 구현 산출물과 실제 분석 산출물 중 어느 쪽이 나중에 파일을 쓰는지 확정한다.
      최신 파일들은 실제 분석이 나중에 돌아 두 필드를 덮었는데 `20260211` 만 덮이지
      않았다. **왜 그날만 덮어쓰기가 일어나지 않았는지**를 먼저 밝힌다. 그것이 재발
      조건이다.
- [ ] `ai_analysis_results_20260211.json` 에 남은 모의 판정 2 건을 어떻게 할지 정한다.
      이미 화면에 새어 나간 값이므로 그 파일을 지울지, 다시 분석해 덮을지, 그대로 둘지를
      정해야 한다. `data/` 는 읽기 전용 규약이라 사용자 결정이 필요하다.
- [ ] `engine/signal_tracker_ai_helpers.py` 를 위험 경로 목록에 넣을지 정한다
- [ ] 세 탭의 게이지를 같은 자료로 실측해 대조한다

### [INFRA-047] 조회용 GET 라우트 둘이 백그라운드 작업과 외부 호출을 일으킨다
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-040]` 사이클에서 「상태를 바꾸는
  GET 라우트가 없는지 전수 확인」을 하다 찾았습니다. `oh-my-claudecode:security-reviewer` 도
  같은 판정을 냈습니다(확신도 높음).
- `app/routes/common_portfolio_routes.py:61` 의 `GET /api/portfolio` 가
  `paper_trading.start_background_sync()` 를 부릅니다. 조회 한 번이 동기화 스레드를 띄웁니다.
- `app/routes/kr_market_system_http_routes.py:83` 의 `GET /api/kr/market-gate` 는 자료가
  낡았으면 `trigger_market_gate_background_refresh()` 로 분석 스레드를 띄웁니다
  (`app/routes/kr_market.py:270`). 외부 API 호출과 파일 쓰기가 따라옵니다.
- **CSRF 는 아닙니다.** 둘 다 요청자의 신원을 보지 않으므로 공격자가 자기 브라우저에서
  직접 불러도 결과가 같고 피해자의 쿠키가 필요하지 않습니다. 그래서 `[INFRA-040]` 의
  차단 대상이 아니었습니다.
- 문제는 다른 데 있습니다. 조회 요청이 비용과 부작용을 내면 캐시·프리페치·크롤러가 그것을
  일으킵니다. 브라우저가 링크를 미리 가져오기만 해도 분석이 돌 수 있습니다.
- QA 시나리오: `GET /api/kr/market-gate` 를 연달아 불러도 분석 스레드가 새로 뜨지 않는다
- [ ] 두 라우트의 갱신 트리거를 조회에서 떼어낼지, 아니면 별도 POST 로 옮길지 정함
- [ ] 프론트엔드에서 그 갱신을 부르던 자리를 찾아 함께 고침
- [ ] 갱신이 조회로 일어나지 않는 것을 고정하는 검사 추가

### [INFRA-048] `INTERNAL_IDENTITY_SECRET` 이 비면 관리자 화면이 말없이 사라진다
- 설계 승인: 2026-09-20 현재 대화의 4건 설계에 사용자 「승인」. 범위·계획: `evidence/infra-boundaries-20260920/plan.md`. 공유 T3 검토·UltraQA App 대응·ego-browser 실측.
- 카테고리: 인프라 | 티어: T3 (`.env.example` 을 건드리므로 `tier-rules.md` §2 「시크릿과
  인증」) | 근거: 2026-09-07 `[INFRA-041]` 사이클의
  `oh-my-claudecode:security-reviewer` 지적 2(확신도 높음)
- `[INFRA-041]` 이 `/api/admin/check` 의 판정을 `g.user_email` 로 옮기면서
  `INTERNAL_IDENTITY_SECRET` 이 관리자 화면의 사실상 필수 값이 되었습니다. 그 값이 비면
  `frontend/src/proxy.ts:70-74` 가 서명 헤더를 붙이지 않고
  `services/identity_helpers.py:74-76` 이 `None` 을 돌려주므로 관리자 판정이 언제나
  거짓입니다.
- **보안 방향으로는 fail-closed 라 개선입니다.** 문제는 안내가 없다는 것입니다.
  `.env.example:180` 은 이 값을 비운 채 배포되고 `:23-24` 의 경고는 「모든 사용자가
  익명으로 처리된다」까지만 적습니다. 참조본을 그대로 복사한 배포에서 관리자는 아무
  메시지 없이 관리 버튼을 잃고, 원인을 짐작할 단서가 화면에도 로그에도 없습니다.
- 실제 권한 게이트인 `frontend/src/app/api/system/env/route.ts:26-33` 의
  `resolveAdminToken` 은 이 비밀을 보지 않으므로 **화면은 잠기고 API 는 인가되는
  비대칭**이 생깁니다. 엄격한 쪽이 화면이라 권한 상승은 아닙니다.
- `.env.example` 의 경고를 보강할지, 값이 비었을 때 기동 로그에 한 줄 남길지 설계에서
  정합니다. 후자는 `[INFRA-041]` 이 만든 의존을 코드가 스스로 알리게 합니다.
- QA 시나리오: `INTERNAL_IDENTITY_SECRET` 을 비운 채 기동하면 그 사실을 알 수 있는
  단서가 로그나 문서에 남는다
- [ ] 안내를 문서에 둘지 기동 로그에 둘지 정함
- [ ] `.env.example` 의 경고에 관리자 화면 영향을 더할지 결정
- [ ] 값이 빈 상태를 재현해 안내가 실제로 보이는지 확인

## P2 — 대기

### [INFRA-054] `restart_all.sh` 의 프로세스 정리 한 줄이 통째로 무동작이다
- 설계 승인: 2026-09-20 현재 대화의 4건 설계에 사용자 「승인」. 범위·계획: `evidence/infra-boundaries-20260920/plan.md`. 공유 T3 검토·UltraQA App 대응·ego-browser 실측.
- 카테고리: 인프라 | 티어: T1 | 근거: 2026-09-08 `[INFRA-049]` 사이클에서 발견했습니다.
  같은 사이클의 `oh-my-claudecode:security-reviewer` 도 종료 코드로 확인했습니다.
- `restart_all.sh:36` 의 `pkill -f "flask_app.py" "next dev" "npm.*dev"` 는 `pkill` 에
  패턴을 셋 넘깁니다. `pkill` 은 패턴을 하나만 받으므로 사용법 오류로 종료하고 **아무것도
  죽이지 않습니다.** `|| true` 가 그 오류를 삼켜 조용합니다.
- 확인 결과: 존재하지 않는 이름 둘로 부르면 종료 코드 1 이 나옵니다. macOS 의 `pgrep` 은
  여러 패턴을 OR 로 처리하는 것처럼 보이는 사례가 있어 판정이 갈렸는데, 실제 정리를 하는
  것은 35행의 `kill_port` 뿐입니다. **「뒤의 둘이 무시된다」가 아니라 「줄 전체가
  무동작」으로 읽어야 합니다.**
- 영향: 포트를 잡지 않은 좀비 프로세스가 남습니다. `kill_port` 가 포트 기준으로만
  정리하므로 다른 포트에 붙었거나 포트를 놓은 프로세스는 살아남습니다. `stop_all.sh` 는
  72~76행에서 패턴마다 `pkill` 을 따로 부르므로 이 문제가 없습니다.
- 수정 방향: `stop_all.sh` 처럼 패턴마다 한 줄씩 나눕니다. 세 줄이면 끝납니다.
- QA 시나리오: 세 패턴에 해당하는 프로세스를 띄운 뒤 스크립트를 돌리면 전부 종료된다
- [ ] `pkill` 호출을 패턴마다 나눔
- [ ] `stop_all.sh` 와 정리 대상 패턴이 같은지 대조

### [CHAT-027] 프로필이 메모리 영역에 들어오면서 생긴 어긋남 둘
- 카테고리: 챗봇 | 티어: T1 | 근거: 2026-09-06 `[CHAT-021]` 사이클의 코드 리뷰
- `[CHAT-021]` 이 `user_profile` 을 소유자 버킷으로 옮기면서 메모리와 같은 취급을 받게
  되었고, 그 결과 두 자리가 어긋납니다. 둘 다 사소하고 같은 주변이라 한 항목으로 묶습니다.
  종전에 셋이었던 것 가운데 화면의 `/clear all` 설명 문구는 2026-09-07 백로그 정리에서
  같은 명령어 목록을 다루는 `[CHAT-019]` 로 옮겼습니다.
- `chatbot/command_service.py:119` 의 `render_memory_view` 가 소유자 버킷을 그대로 보여
  주므로 사용자가 `/memory` 로 넣은 적 없는 `user_profile` 이 `/memory view` 에 나타나고
  `/memory remove user_profile` 로 지울 수도 있습니다.
- `chatbot/runtime_setup_service.py:162` 의 `init_user_profile_from_env` 는 가드가
  `not memory.memories` 인데 저장소가 2단이 된 뒤로는 어느 소유자에게든 행이 하나라도
  있으면 거짓입니다. 공용에 캐시 두 행이 이미 있어 영영 발동하지 않으므로 `USER_PROFILE`
  환경 변수는 어떤 화면에도 영향을 주지 못합니다.
- [ ] `/memory view` 에서 프로필을 가리거나 별도 표기로 구분
- [ ] `init_user_profile_from_env` 를 지우거나 발동하도록 고침

### [CHAT-023] 공용 메모리의 추천 질문 캐시가 상한 없이 쌓인다
- 카테고리: 챗봇 | 티어: T1 | 근거: 2026-09-05 `[CHAT-017]` 사이클의 코드 리뷰
- `chatbot/daily_suggestions_service.py:65` 가 `daily_suggestions_<persona>_<watchlist>` 키로
  추천 질문을 공용 영역에 저장합니다. `chatbot/data_service.py:133` 의 조회는 1시간 신선도만
  보고 낡은 행을 지우지는 않습니다.
- `[CHAT-017]` 이 공용 영역을 사용자 명령에서 도달 불가능하게 만들었으므로 `/clear all` 도
  `/memory clear` 도 이 행들에 닿지 않습니다. `save_memories_to_sqlite` 의 stale 정리는
  스냅샷에 있는 행을 남기므로 정리 수단이 아닙니다.
- 캐시 키가 (페르소나 × 관심종목) 조합이고 관심종목이 사용자 입력이라 조합에 상한이 없습니다.
  조합마다 한 행씩 영구히 쌓입니다.
- 티어 판정: 만료된 행을 지우는 자리 하나를 정하면 됩니다. 저장 직후에 같은 접두사의 낡은 행을
  지우는 방법과, 다른 캐시들이 쓰는 `prune_rows_by_updated_at_if_needed`(`services/sqlite_utils.py`)를
  쓰는 방법이 있습니다. 후자를 쓰면 기존 프루닝 규약에 맞습니다.
- [ ] 만료된 공용 캐시 행을 지우는 자리를 정하고 구현
- [ ] 상한이 실제로 걸리는지 pytest 로 고정

### [CHAT-012] 챗봇 저장소의 스키마 준비 골격을 공용 게이트로 흡수
- 카테고리: 챗봇 | 티어: T2 | 근거: 2026-09-05 `[CHAT-003]` 사이클의 code-reviewer 지적
- QA 시나리오: 챗봇 대화 목록과 메시지 이력이 통합 전과 같게 조회된다
- `chatbot/storage_sqlite_common.py:95-194` 의 `ensure_chatbot_storage_schema` 가
  `[CHAT-003]` 이 만든 `services/sqlite_ready_gate.py` 의 `SqliteReadyGate` 와 같은
  골격입니다. 줄 단위로 대응이 맞습니다. 진입 `:103`↔`:66`, 대기 루프 `:111-116`↔`:72-77`,
  in-progress 등록 `:118`↔`:79`, `finally` 재진입 `:180`↔`:94`, `add_bounded_ready_key`
  `:183-187`↔`:97-101`, `notify_all` `:190`↔`:104` 입니다.
- 차이는 `force_recheck: bool = False` 인자 하나뿐입니다. 그 인자를 게이트의 `ensure` 에
  더하면 흡수됩니다.
- `[CHAT-003]` 이 이 파일을 범위에서 뺀 것은 그 항목이 정한 대상이 캐시 두 모듈이었고,
  이 파일은 캐시가 아니라 세션·메시지·메모리 저장소이기 때문입니다.
- [ ] `SqliteReadyGate.ensure` 에 `force_recheck` 를 더함
- [ ] `ensure_chatbot_storage_schema` 를 게이트 위임으로 교체
- [ ] 기존 회귀 테스트가 그대로 통과하는지 확인

### [INFRA-032] 나머지 열다섯 모듈의 SQLite 준비 골격을 공용 게이트로 흡수
- 카테고리: 인프라 | 티어: T3 | 근거: 2026-09-05 `[CHAT-003]` 사이클의 code-reviewer 지적
- QA 시나리오: 종가베팅·VCP·실시간 시세·누적 성과 화면이 통합 전과 같은 값을 그린다
- `services/sqlite_utils.py` 의 `add_bounded_ready_key` 를 쓰는 비테스트 모듈이 열여섯
  개이고, 그 가운데 `[CHAT-003]` 이 두 개를, `[CHAT-012]` 가 한 개를 가져갑니다. 남는
  것은 다음 열다섯 개입니다.

      services/kr_market_data_cache_sqlite_payload.py
      services/kr_market_vcp_signals_cache.py
      services/kr_market_jongga_payload_helpers.py
      services/kr_market_realtime_price_cache.py
      services/kr_market_realtime_latest_close_cache.py
      services/kr_market_realtime_market_map_cache.py
      services/kr_market_backtest_summary_cache.py
      services/kr_market_cumulative_cache.py
      services/kr_market_data_cache_jongga.py
      services/common_update_status_service.py
      services/file_row_count_cache.py
      services/paper_trading_db_setup.py
      engine/kr_ai_stock_info_cache.py
      engine/signal_tracker_source_cache.py
      engine/signal_tracker_analysis_source_cache.py

- `[CHAT-003]` 은 두 모듈을 옮기면서 코드 줄이 13줄 늘었습니다(주석 제외 820 → 833).
  중복 로직 354줄이 사라진 자리를 위임 호출의 인자 전달이 채웠기 때문입니다. 나머지가
  따라오면 순감으로 돌아섭니다.
- 열다섯 개를 한 사이클에 다 옮기면 규모가 통제를 벗어나므로, 화면 단위로 서너 개씩 나누어
  진행할지 이 항목을 시작할 때 정합니다.
- [ ] 옮길 순서를 화면 단위로 묶어 확정
- [ ] 각 묶음마다 기존 회귀 테스트가 그대로 통과하는지 확인
- [ ] 옮긴 뒤 주석을 뺀 코드 줄 수가 실제로 줄었는지 측정

### [INFRA-028] Gemini 재분석 요청의 날짜 목록에 형식 검사도 개수 상한도 없다
- 설계 승인: 2026-09-20 현재 대화의 4건 설계에 사용자 「승인」. 범위·계획: `evidence/infra-boundaries-20260920/plan.md`. 공유 T3 검토·UltraQA App 대응·ego-browser 실측.
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-04 `[INFRA-006]` 사이클의 /review
  보안 스페셜리스트 지적(확신도 70, 60, 40)
- `services/kr_market_route_service.py:113` 의 `parse_target_dates` 는 신뢰 경계를 넘어온
  값을 문자열로 바꾸고 공백만 없앤다. 날짜 형식도 목록 길이도 보지 않는다.
- 그 값이 `scripts/init_data.py` 의 파일명 조립부까지 그대로 닿는다. 지금 경로 탈출이
  성립하지 않는 이유는 파일명 조립부의 방어가 아니라 그보다 앞의
  `df['signal_date'] == str(t_date)` 필터가 실재하지 않는 날짜를 걸러 내기 때문이다.
  방어가 우연히 다른 자리에 놓여 있어 필터 조건이 느슨해지는 순간 취약해진다.
- 같은 값이 필터를 적용하기 전에 `log(f"Deep Analysis for date: {t_date}")` 로 기록되므로
  개행 문자를 넣으면 로그에 가짜 항목을 만들 수 있다. 이 로그를 파싱하는 소비자는 확인하지
  못했으므로 영향은 제한적이다.
- Flask 의 `MAX_CONTENT_LENGTH` 가 설정되어 있지 않아 항목이 수만 개인 배열도 받는다.
- [ ] `parse_target_dates` 에서 `\d{4}-\d{2}-\d{2}` 형식과 목록 길이 상한을 확정
- [ ] 형식에 맞지 않는 값을 이 한 자리에서 걸러 파일명 조립부까지 닿지 않게 한다
- [ ] `MAX_CONTENT_LENGTH` 를 설정할지 판정
- [ ] 잘못된 형식이 거부됨을 고정하는 검사 추가
- [ ] pytest 전체 통과 확인

### [JONGGA-030] 티커 정규화 구현이 여섯 벌로 흩어져 규칙이 서로 다르다
- 카테고리: 종가베팅 | 티어: T3 | 근거: 2026-09-04 JONGGA-017 사이클의 리뷰, `[JONGGA-005]` 사이클의 변이 검사, AUDIT-FLOW §2.2
- 2026-09-07 백로그 정리에서 `[INFRA-023]`(`000000` 가짜 종목)과 `[FLOW-007]`(백테스트 패딩
  헬퍼)을 흡수했습니다. 셋 다 「`zfill(6)` 을 각자 구현해 규칙이 어긋난다」는 하나의 문제입니다.
- QA 시나리오: 영문자 코드를 가진 종목의 카드에 현재가와 수익률이 그려지고, 티커가 빈 행이 가격
  맵에 `000000` 으로 들어가지 않는다
- **영문자 코드**: `services/kr_market_realtime_price_service.py:42` 의 `normalize_ticker` 는
  `str(ticker).zfill(6)` 한 줄이라 소문자 `0007c0` 이 들어오면 가격 맵의 키가 `0007c0` 이 됩니다.
  조회하는 쪽의 `_normalize_ticker` 는 `[JONGGA-017]` 이후 `0007C0` 을 내므로 어긋나 가격이 붙지
  않습니다. 같은 파일의 `_is_normalized_unique_ticker_list` 는 `ticker.isdigit()` 를 요구해 영문자
  코드는 늘 「정규화 안 됨」으로 판정되어 최적화 경로를 타지 못합니다. 지금은 자료가 대문자로만
  들어와 드러나지 않고, 어긋나도 남의 가격이 붙지는 않으므로 `[JONGGA-017]` 보다 덜 급합니다.
- **`000000` 가짜 종목**: `services/kr_market_csv_utils.py:237` 이 `df_prices["ticker"].astype(str).str.zfill(6)`
  로 티커를 만드므로 CSV 에 티커가 빈 행이 있고 종가가 유효하면 `"000000"` 키가 가격 맵에
  들어갑니다. `services/kr_market_data_cache_prices.py:41` 과 `:63` 의 SQLite 직렬화·역직렬화도
  같은 `zfill(6)` 을 하며 바로 다음 줄의 `if not ticker_key: continue` 는 zfill 뒤라 결코 참이
  되지 않는 죽은 검사입니다. 종가베팅 경로는 `[JONGGA-005]` 가 전부 0 인 코드를 빈 문자열로
  돌리도록 막았고, 남은 것은 맵을 만드는 쪽이며 VCP 경로가 이 키를 조회하는지는 확인하지 않았습니다.
- **흩어진 구현**: `services/paper_trading_sync_service.py:14`,
  `services/paper_trading_price_fetchers.py:19`, `services/kr_market_realtime_price_cache.py:62`,
  `engine/collectors/krx_data_mixin.py:22`, `services/kr_market_vcp_cache_update_service.py:17` 이
  각자 `_normalize_ticker` 를 정의합니다. 이름이 같아 한 함수처럼 보이지만 서로 다른 구현입니다.
  백테스트 쪽도 `services/kr_market_backtest_scenario_helpers.py:17` 과
  `services/kr_market_backtest_trade_helpers.py:24` 가 `_get_ticker_padded_series` 를 각자 두고
  있는데 `services.kr_market_csv_utils.get_ticker_padded_series` 가 같은 일을 합니다.
- 티어 근거: 가격 캐시 계열 파일이라 `tier-rules.md` §2 저장소 스키마에 닿습니다.
- [ ] 정본으로 삼을 정규화 함수 하나를 정하고 위 구현들을 그것으로 교체
- [ ] `_is_normalized_unique_ticker_list` 의 판정에 영문자 코드를 반영
- [ ] 빈 티커 행을 맵에서 제외할지 `zfill` 앞에서 걸러 낼지 정하고 죽은 검사 두 곳을 정리
- [ ] VCP 가격 반영 경로가 `000000` 을 조회하는지 확인하고 그렇다면 함께 막음
- [ ] 백테스트 두 헬퍼를 공용 함수로 교체하고 `_ticker_padded` 캐시 컬럼 동작이 같은지 확인
- [ ] 소문자 코드와 빈 티커가 섞인 DataFrame 에 대한 검사를 남김

### [JONGGA-018] 가산점이 화면이 밝힌 상한 7점을 넘는다
- 카테고리: 종가베팅 | 티어: T3 | 근거: 2026-09-03 JONGGA-005 사이클의 `/qa` NEW-002
- QA 시나리오: 카드 점수표의 「보너스 (가산점)」이 그 카드가 밝힌 상한을 넘지 않는다
- 카드가 "가산점 (Max 7)" 이라고 적으면서 그보다 큰 값을 표시합니다. 총점도 그만큼
  부풀려집니다.
- 2026-09-03 실측: `2026-02-11` 자료에서 아크릴이 `+9/7`, LG전자가 `+8/7` 입니다. 아크릴의
  총점 16점은 기본 7점과 보너스 9점의 합입니다. 원본 자료
  (`data/jongga_v2_results_20260211.json`)의 `score_details.bonus_score` 가 이미 9와 8이므로
  화면은 자료를 그대로 그린 것이며, 계산은 `engine/scorer.py` 의 `_calculate_bonus` 가
  합니다.
- 티어 근거: 고칠 자리인 `engine/scorer.py` 와 `engine/scorer_scoring_mixin.py` 는 종가베팅
  점수와 등급을 결정합니다. §2 의 「신호와 등급 결정」 절이 다루는 일과 같으므로 T3 으로
  판정합니다. 두 파일은 아직 그 목록에 없으니, 착수하는 사이클의 첫 커밋에서 §4 에 따라
  목록에 추가합니다.
- [ ] 가산점 세 갈래(거래량 급증 5, 장대양봉 1, 상한가 1)의 합이 상한을 넘을 수 있는
      경로를 찾음
- [ ] 상한을 강제할 것인지 화면의 상한 표기를 실제에 맞출 것인지 정함
- [ ] 상한을 넘는 입력으로 검사를 고정
- [ ] 이미 저장된 자료를 어떻게 다룰지 정함. 다시 계산할 것인가 그대로 둘 것인가

### [VCP-005] `vcp_ai_analyzer.py` 의 죽은 폴백 코드와 중복 헬퍼 정리
- 카테고리: VCP 시그널 | 티어: T3 | 근거: AUDIT-VCP §3.1, §2.1
- 티어 근거: `engine/vcp_ai_analyzer.py` 는 `tier-rules.md` §2 의 "VCP 판정" 위험 경로에
  올라 있으므로 줄 수와 무관하게 T3 입니다. 리뷰는 `/ponytail-review` → `/code-review` →
  `/review` 순서를 지킵니다. 실행 코드를 바꾸므로 `/qa-only` 는 돌립니다. 화면이 바뀌지는
  않으므로 agent-browser 로 값을 대조할 자리는 없습니다.
- [ ] 호출자가 없는 `_fallback_to_zai` 제거
- [ ] `_resolve_perplexity_fallback_providers` 와 `_build_perplexity_fallback_chain` 의
      실행되지 않는 분기 정리
- [ ] `_extract_status_code` 세 사본을 하나로 통합
- [ ] `max_parse_attempts = 1` 로 죽어 있는 재시도 구조 정리
- [ ] 기존 27건의 Z.ai 테스트가 그대로 통과하는지 확인

### [FLOW-006] 백테스트 재노출 전용 계층을 걷어낸다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW §3.1
- [ ] `..._service`, `..._calculators`, `..._cumulative`, `..._signal_stats` 네 파일의
      외부 호출자를 확인한 뒤 남길 진입점 하나를 결정
- [ ] 나머지 재노출 계층 제거하고 `app/routes/kr_market_backtest_helpers.py` 의 import 정리
- [ ] `tests/services/test_kr_market_backtest_service.py` 의 import 경로 갱신
- [ ] pytest 전체 통과 확인

### [INFRA-008] init_data 의 죽은 진입점 정리
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §3.1, §3.2
- `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] `create_market_gate`(1993-2096)를 삭제하고 Market Gate 생성 경로가
      `engine/market_gate.MarketGate` 하나임을 확인
- [ ] `reset_cache`(529-534)의 존치 여부를 판단하고 불필요하면 삭제
- [ ] `assign_grade`(91-145)를 실제 등급 판정 경로에 연결하거나,
      `tests/test_grading_logic.py` 와 함께 폐기
- [ ] pytest 전체 통과 확인

### [INFRA-018] numpy 2.x 승격 — 제거된 별칭 참조와 pykrx 상한을 함께 푼다
- 카테고리: 인프라 | 티어: T2 | 근거: [INFRA-001] 사이클의 실측
- numpy 2.x 로 올리는 것을 막는 것이 두 가지입니다. 하나만 풀면 나아가지 못합니다.
  - `numpy_json_encoder.py:38` 이 numpy 2.0 에서 제거된 `np.float_` 을 참조합니다.
  - `pykrx==1.2.3` 이 `numpy<2.0,>=1.24.0` 을 요구합니다. PyPI 메타데이터 실측 결과
    1.2.6 까지가 `numpy<2.0` 이고 1.2.7 부터 `numpy>=2.0` 으로 뒤집힙니다. 즉 pykrx 를
    1.2.7 이상으로 올리는 일과 numpy 승격은 한 묶음이며, 어느 한쪽만 올리면 pip 이
    의존성을 해결하지 못합니다.
- `np.float_` 은 numpy 1.x 에서도 `np.float64` 의 별칭이었으므로, 이미 같은 줄에 있는
  `np.float64` 만 남기면 두 버전에서 모두 동작합니다.
- pykrx 1.2.3 에서 1.2.7 로 네 단계를 건너뛰므로 시세 조회 API 의 반환 형태가 그대로인지
  확인해야 합니다. `engine/collectors.py` 등 19곳이 이 패키지를 씁니다.
- [ ] `np.float_` 참조 제거
- [ ] `pykrx` 를 numpy 2.x 를 허용하는 버전으로 올리고 시세 조회 경로 회귀 확인
- [ ] `requirements.txt` 의 numpy·pykrx 핀과 두 주석을 함께 갱신
- [ ] numpy 2.x 를 설치한 격리 환경에서 pytest 전체 통과 확인

### [INFRA-035] 모의투자 테스트가 pytest 를 돌릴 때마다 `data/` 에 SQLite 임시 파일을 남긴다
- 현재 라운드: 2026-09-09 테스트 격리 묶음 T2. 설계/실행 근거는 사용자 「연관된 라운드들 쭉 이어서」「최대한 한번에 묶어서」 및 AUTO-CONTINUE. 별도 승인 응답을 만들지 않음.
- [x] 제한된 설계와 변경 범위 확정 — `evidence/test-isolation-20260909/scope.md`
- [x] 독립 리뷰 ponytail SHIP → code-reviewer APPROVE / architect BLOCK→수정→CLEAR, 정적 검증 통과
- [x] UltraQA App 대응 5/5 통과·정리 완료 — `qa/INFRA-035.md`, 구현 커밋 `38fab47`
- 카테고리: 인프라 | 티어: T1 | 근거: 2026-09-07 `[FE-015]` 사이클의 QA 준비 중 발견, 2026-09-07 백로그 정리에서 출처 확인
- QA 시나리오: `pytest tests/services/test_paper_trading_service.py` 를 돌린 뒤 `data/` 의
  `.db-wal`·`.db-shm` 수가 늘지 않는다
- `data/` 최상위 파일 23,373 개 가운데 `.db-wal` 이 11,647 개이고 짝이 되는 `.db-shm` 이 같은 수입니다.
  실제 자료는 json·csv·db·lock 을 합쳐 80 개 안팎이고 디렉터리 전체가 637MB 입니다.
- **출처는 테스트 스위트입니다.** 처음 등록할 때는 이름이 `cmp_dev_*` 라고 적었으나 2026-09-07 에
  세어 보니 11,647 개 가운데 11,642 개가 `paper_trading_test_*` 이고 `cmp_dev_*` 는 셋뿐입니다.
  `tests/services/test_paper_trading_service.py:49` 의 픽스처가 `paper_trading_test_{uuid}.db` 를
  `data/` 에 만드는데(같은 파일 `:1411`, `:1432`, `:1851`, `:1868`, `:1886` 도 같음) 연결을 닫지
  않거나 본체만 지워서 WAL 과 SHM 이 남습니다. 가장 오래된 것이 2026-02-22, 가장 최근 것이
  2026-09-07 14:58 이라 지금도 pytest 한 번에 두 파일씩 새고 있습니다.
- 실무에 미치는 영향이 이미 있습니다. `[FE-015]` 와 `[VCP-011]` 사이클에서 `data/*` 를 인자로 넘기는
  명령이 인자 수 제한에 걸렸습니다. 앞으로도 `data/` 를 훑는 모든 작업이 같은 벽에 부딪힙니다.
- `data/` 는 읽기 전용 규약이므로 이미 쌓인 파일을 지우는 조작은 사용자 결정이 필요합니다.
  픽스처를 `tmp_path` 로 옮기면 새로 쌓이지는 않습니다.
- [x] 아직 `db_name`을 쓰던5개 테스트를 `tmp_path`로 전환. 공통 helper는 이미 임시 경로, 연결은 기존 AutoClosingSQLiteConnection이 닫음. 자체 DB/WAL/SHM 정리 보완 (`38fab47`)
- [x] 비밀 없는 격리 전체 pytest2279/3skip 통과 및 원본sidecar27396개 이름해시불변. 별도 data쓰기차단 target86개 통과로 새 data 쓰기방지 확인
- [ ] 이미 쌓인 11,647 쌍과 `cmp_dev_*` 셋을 어떻게 할지 사용자와 정함

- 현재 남은 일: 원본 누적 파일의 처리 결정만 대기. 기존 설명의 수량·공통 helper 경로는 과거 관측이며, 2026-09-09 원본 WAL/SHM 파일 합계는27396개. 기존 파일을 삭제하지 않았고 완료 아카이브도 만들지 않음.

### [INFRA-066] 개별 라우트 오류 래퍼가 예외 원문을 500 응답에 남긴다
- 설계 승인: 2026-09-20 현재 대화의 4건 설계에 사용자 「승인」. 범위·계획: `evidence/infra-boundaries-20260920/plan.md`. 공유 T3 검토·UltraQA App 대응·ego-browser 실측.
- 카테고리: 인프라 | 티어: T2 예상 | 근거: 2026-09-09 INFRA-017·038 범위 검토
- `app/routes/route_execution.py`의 `build_route_error_response`는 `str(error)`를 500으로 보내며, `execute_json_route`는 HTTPException까지 잡는다. `common_portfolio_routes.py`의 별도 wrapper와 payload builder도 같은 형태다.
- 전역 처리기 및 common update wrapper를 고친 INFRA-017·038이 닿지 않는 독립 경로다. 모의투자/다른 호출부의 기존 오류 계약을 따로 조사해야 하므로 현재 범위로 확대하지 않았다.
- QA 시나리오: 지정 호출부에 합성 경로가 포함된 예외를 주입해 응답에 원문이 없고, HTTP 요청 오류의 상태가 유지되는지 격리 실제 앱으로 검증한다.
- [ ] 호출부와 사용자용 오류 계약을 확정하고 실제 파일로 티어를 판정
- [ ] 내부 로그와 외부 오류를 분리하고 HTTPException 처리 계약을 맞춤
- [ ] 회귀 검사와 해당 사용자 흐름의 UltraQA·agent-browser 실측
