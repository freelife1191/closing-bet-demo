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

### [JONGGA-033] 종목 상세 모달의 EPS·순이익 부호가 어긋나고 PER 툴팁이 음수를 설명하지 못한다
- 설계 승인: 2026-09-21 | 실제 대화: 직전 두 건 bounded 설계에 사용자 「승인」. 범위·경계: `evidence/jongga-metrics-20260921/scope.md`
- 현재 단계: 구현·독립리뷰·정적검증 완료, UltraQA 실측 대기 (T2: 점수 계산 변경 없음, 표시와 기간 전달만 변경)
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

## P2 — 대기

### [JONGGA-018] 가산점이 화면이 밝힌 상한 7점을 넘는다
- 설계 승인: 2026-09-21 | 실제 대화: 직전 두 건 bounded 설계에 사용자 「승인」. 범위·경계: `evidence/jongga-metrics-20260921/scope.md`
- 현재 단계: 구현·독립리뷰·정적검증 완료, UltraQA 실측 대기 (T2: 점수 계산 변경 없음, 표시와 기간 전달만 변경)
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
