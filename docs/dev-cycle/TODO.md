# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 완료된 항목은 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.
>
> 2026-09-01 여섯 카테고리 감사(`[INFRA-004]`)로 30개 항목이 들어왔습니다. 각 항목의
> 근거에 적힌 `AUDIT-*` 문서는 `docs/dev-cycle/audits/` 에 있으며, 항목마다 위치를
> 절 번호까지 적어 두었으므로 사이클을 시작할 때 그 절을 먼저 읽습니다.

## P0 — 즉시

### [JONGGA-002] Gemini 재분석 결과의 AI 사유 유실 수정
- 카테고리: 종가베팅 | 티어: T1 | 근거: AUDIT-JONGGA §1.1
- 구현 변경은 두 파일에서 30줄 이내로 끝날 것으로 봅니다. 테스트 파일은 `tier-rules.md`
  §1 의 제외 조항에 따라 합계에서 뺐습니다.
- [ ] `_apply_gemini_reanalysis_results` 가 `ai_evaluation` 에 `reason` 을 함께 담도록 수정
- [ ] `_extract_jongga_ai_evaluation` 이 사유가 빈 항목을 만나면 `score.llm_reason` 으로
      내려가도록 우선순위 체인 보강
- [ ] 재분석 전후로 `gemini_recommendation.reason` 이 유지되는지 검사하는 회귀 테스트 추가
- [ ] AI 분석 payload 를 소비하는 VCP 화면의 분석 사유 표시가 복구되는지 확인

### [JONGGA-003] 체크리스트 수급 항목의 키 이름 통일
- 카테고리: 종가베팅 | 티어: T1 | 근거: AUDIT-JONGGA §1.2
- 프론트엔드와 목 데이터 생성기가 이미 `supply_positive` 를 쓰고 있으므로, 백엔드를
  그쪽에 맞추는 방향이 변경 범위가 작습니다.
- [ ] `_normalize_jongga_signal_for_frontend` 가 만드는 체크리스트 키를 `supply_positive`
      로 맞춤
- [ ] `tests/app/test_kr_market_helpers_contract.py:308` 의 단언을 새 키로 갱신
- [ ] 저장소에 남은 `supply_demand` 표기를 전수 확인해 종가 체크리스트 경로에서 제거
- [ ] 외국인·기관 5일 순매수가 양수일 때 배지가 켜지는지 화면에서 확인

### [JONGGA-004] AI 미분석 종목의 확신도 추정치 표기 정리
- 카테고리: 종가베팅 | 티어: T2 | 근거: AUDIT-JONGGA §1.3
- 폴백 블록(1959-1966행)과 확신도 렌더 블록(2128-2154행)을 함께 손대고 대체 표기를
  넣으면 50줄을 넘길 것으로 보아 T2 로 판정했습니다. 화면 표시가 바뀌므로 T2 검증이
  요구하는 실측이 실제로 필요합니다. Next.js 가 16.1.6 이므로
  `frontend-skills.md` §3 에 따라 `next-dev-loop` 이 아니라 agent-browser 로 실측합니다.
- [ ] 등급에서 확신도를 유도하는 계산식을 제거하거나, 산출값을 확신도가 아닌 별도 이름으로
      분리
- [ ] AI 분석 결과가 없는 상태에서는 확신도 막대와 매매 추천 배지를 감추거나 추정임을
      배지 자리에서 바로 알 수 있게 표기
- [ ] 두 툴팁 문구를 실제 데이터 출처에 맞게 수정
- [ ] AI 결과가 없는 시그널과 있는 시그널을 각각 렌더링하는 vitest 추가
- [ ] agent-browser 로 카드 표시를 실측

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: 2026-09-01 실측
- [ ] `requirements.txt` 의 14개 패키지에 버전 핀 적용
- [ ] `google-genai` 1.62 → 2.x 호환성 확인 (`engine/genai_client.py` 호출부)
- [ ] `requirements.updated.txt` 와의 관계 정리 또는 폐기
- [ ] pytest 전체 통과 확인

## P1 — 이번 주기

### [VCP-007] AI 캐시 병합이 정상 추천을 지우고 실패 추천을 통과시키는 결함 수정
- 카테고리: VCP 시그널 | 티어: T2 | 근거: 2026-09-01 VCP-001 진행 중 발견
- `_merge_ai_data_into_vcp_signals`(`app/routes/kr_market_vcp_signal_helpers.py:283`)가
  캐시에 티커가 있기만 하면 `ai_item.get("gemini_recommendation")` 을 조건 없이
  대입합니다. 두 방향으로 어긋납니다. 캐시에 추천이 없으면 CSV 에서 만든 정상 추천이
  `None` 으로 지워지고, 캐시에 실패 기록이 들어 있으면 `[VCP-001]` 이 CSV 경로에서
  막아 둔 실패 추천이 이 경로로 되살아납니다.
- 첫 번째는 실재합니다. `data/vcp_signals_results_20260213.json` 등 세 파일이 티커만 있고
  `gemini_recommendation` 이 없는 상태입니다. 두 번째는 지금 캐시에는 없지만 구조가
  허용합니다.
- [ ] 캐시에 값이 없을 때 기존 추천을 지우지 않도록 대입 조건 수정
- [ ] 캐시에서 온 추천에도 `[VCP-001]` 과 같은 실패 판정을 적용
- [ ] 두 경우를 각각 확인하는 회귀 테스트 추가

### [INFRA-013] 위험 경로의 저장소 스키마 규칙을 파일명 대신 실제 스키마로 판정
- 카테고리: 인프라 | 티어: 문서 | 근거: 2026-09-01 FLOW-003 진행 중 발견
- `tier-rules.md` §2 가 저장소 스키마를 "파일명에 `sqlite` 를 포함하는 모듈" 로
  정의하는데, `CREATE TABLE` 을 실제로 정의하는 모듈은 21개이고 그 규칙이 잡는 것은
  3개입니다. FLOW-003 에서 `services/kr_market_cumulative_cache.py` 가 목록 밖이라
  판정이 T2 로 나왔고, 실질을 보고 손으로 T3 으로 올렸습니다.
- [ ] 판정 기준을 파일명에서 `CREATE TABLE` 정의 유무로 바꿈
- [ ] 해당하는 21개 모듈을 §2 목록에 반영

### [JONGGA-007] 화면에 보여주는 목표가·손절가를 백테스트와 같은 상수에서 만든다
- 카테고리: 종가베팅 | 티어: T1 | 근거: 2026-09-01 FLOW-003 진행 중 발견
- `app/routes/kr_market_jongga_normalize_helpers.py:124,126` 이 `entry * 1.09` 와
  `entry * 0.95` 로 목표가·손절가를 만듭니다. FLOW-003 이 만든 `JONGGA_TARGET_PCT`
  및 `JONGGA_STOP_PCT` 와 같은 값이지만 따로 적혀 있어서, 폭을 조정하면 화면이
  말하는 목표가와 백테스트가 재는 목표가가 갈라집니다.
- [ ] 두 리터럴을 공용 상수 참조로 교체
- [ ] 폭을 바꿨을 때 표시값이 따라오는지 확인하는 테스트 추가

### [INFRA-012] CLAUDE.md 의 스케줄러 실행 시각 정정
- 카테고리: 인프라 | 티어: 문서 | 근거: 2026-09-01 code-review
- `CLAUDE.md:209` 가 스케줄러를 "15:20, 15:40 KST" 로 적었으나 두 시각 모두 지금은
  존재하지 않습니다. 실제 등록은 `CLOSING_SCHEDULE_TIME` 기본값 17:00 하나이고
  종가베팅은 그 체인 안에서 이어 돌며, `README.md:1465` 는 이미 바르게 적혀 있습니다.
- [ ] `CLAUDE.md` 의 스케줄러 줄을 실제 등록과 맞춤
- [ ] 같은 절의 관련 모듈 목록에 사실과 어긋난 항목이 더 없는지 확인

### [FE-001] 낡은 업그레이드 베이스라인 테스트 정리
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: 2026-09-01 vitest 실행
- 대상 두 파일이 합계 513줄이고 구현 파일은 건드리지 않으므로, `tier-rules.md` §1 의
  제외 조항이 적용되지 않아 그대로 셉니다. 테스트 파일만 바꾸므로 `tier-rules.md` §1 의
  `/qa-only` 제외에 해당하고, agent-browser 로 대조할 화면도 없습니다.
- 세 건이 과거 업그레이드 시점의 버전을 고정 검사해 항상 실패합니다.
  현재 Next 16.1.6 / React 19.2.4 인데 각각 14.x, 18.x, 15.x 를 기대합니다.
- [ ] `tests/baseline/upgrade-baseline.test.ts` 의 버전 고정 검사 처리
- [ ] `tests/baseline/upgrade-nextjs15.test.ts` 의 버전 고정 검사 처리
- [ ] 버전 검사를 유지할지 삭제할지 결정 (하한선 검사로 바꾸는 방안 포함)
- [ ] vitest 160개 전체 통과 확인

### [FE-002] Next.js 16.1.6 을 16.3.4 로 올린다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: 2026-09-01 실측
- 선행 조건: `[FE-001]` 이 끝나야 합니다. 낡은 버전 고정 검사를 남겨 둔 채 올리면
  업그레이드가 만든 실패와 원래 있던 실패를 구별할 수 없습니다.
- `next-dev-loop`, `next-cache-components-adoption`, `next-cache-components-optimizer`,
  `next-partial-prefetching-adoption` 네 스킬이 모두 16.3 을 하한선으로 두고 있어,
  이 항목이 끝나기 전까지 호출할 수 없습니다.
  자세한 내용은 `.claude/skills/dev-cycle/references/frontend-skills.md` 에 있습니다.
- [ ] `next-upgrade` 스킬로 공식 마이그레이션 가이드와 코드모드를 적용
- [ ] `eslint-config-next` 를 같은 버전으로 맞춤
- [ ] `npm run build`, `npm run type-check`, `npm run lint` 통과 확인
- [ ] vitest 전체 통과 확인
- [ ] `next-dev-loop` 의 preflight 가 통과하는지 확인해 문턱이 실제로 열렸는지 검증
- [ ] `frontend-skills.md` §1 의 실측 표를 갱신

### [INFRA-010] 규약 문서의 담당 경로 공백을 메운다
- 카테고리: 인프라 | 티어: 문서 | 근거: AUDIT-FE 와 AUDIT-VCP 의 담당 경로 밖 관찰
- 두 감사가 각각 짚었습니다. 담당 카테고리가 없는 코드가 있으면 그 코드는 어느 감사에서도
  다뤄지지 않고 남습니다.
- [ ] `archive-format.md` §2 표에 `frontend/src/app/dashboard/kr/page.tsx` 와
      `cumulative/`, `data-status/` 세 경로의 담당 카테고리를 배정
- [ ] 같은 표에 `services/kr_market_vcp_*.py` 여섯 파일의 담당 카테고리를 배정.
      실제 VCP 응답을 만드는 파일인데 어느 행에도 잡히지 않습니다
- [ ] `frontend-skills.md` §1 의 `'use client'` 파일 수를 26개에서 25개로 정정.
      `not-found.tsx` 는 주석 문구가 검색에 잡혔을 뿐 서버 컴포넌트입니다
- [ ] 표에 적은 경로가 모두 실재하는지 확인

### [JONGGA-001] generator.py 의 인라인 페이즈 로직을 phases 모듈로 교체
- 카테고리: 종가베팅 | 티어: T3 | 근거: CLAUDE.md 이관
- [ ] `engine/generator.py` 의 인라인 페이즈 로직 범위 확정
- [ ] `engine/phases_*.py` 의 기존 클래스로 대체
- [ ] 신호 생성 결과가 교체 전후로 동일한지 확인
- [ ] 회귀 테스트 추가

### [VCP-003] 두 번째 AI 프로바이더 폴백 누락 수정
- 카테고리: VCP 시그널 | 티어: T1 | 근거: AUDIT-VCP §1.3
- 티어 근거: `engine/vcp_ai_orchestration_helpers.py` 한 파일이며 `tier-rules.md` §2 의
  위험 경로 목록에 없습니다. 구현 변경은 다섯 줄 안팎입니다. 다만 이 파일이 VCP 판정
  경로인데도 위험 경로 목록에서 빠져 있다는 점은 별도로 확인이 필요하므로 체크박스에
  넣었습니다.
- [ ] Perplexity 가 비활성일 때 GPT 분기로 이어지도록 조건 수정
- [ ] `.env.example` 의 `VCP_SECOND_PROVIDER` 권장 값과 `engine/config.py:199` 의 기본값이
      어긋난 상태를 정리
- [ ] 키가 없는 환경에서 GPT 가 두 번째 프로바이더로 선택되는지 확인하는 pytest 추가
- [ ] `engine/vcp_ai_orchestration_helpers.py` 를 `tier-rules.md` §2 위험 경로에 넣을지
      판단하고, 넣는다면 같은 커밋에서 목록을 갱신

### [CHAT-002] 계산해 놓고 버려지는 세 값 복구
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §1.2, §1.3, §1.4
- 티어 판정: `chatbot/chat_execution.py`, `chatbot/chat_handlers.py`,
  `chatbot/payload_service.py`, `chatbot/intent_context.py`, `chatbot/session_access.py` 는
  모두 위험 경로 밖입니다. 세 건 합계 150줄에서 250줄로 봅니다.
- [ ] 스트리밍 응답에서 `usage_metadata` 를 실제로 수집해 이벤트로 방출
- [ ] 의도 지시문을 종가베팅 외 네 의도에도 실을지, 네 의도의 지시문 생성을 걷어낼지 결정하고
      한쪽으로 통일
- [ ] `is_ephemeral_command` 가 `_EPHEMERAL_COMMANDS` 를 실제로 참조하도록 수정
- [ ] `tests/chatbot/test_chat_execution.py` 의 `usage_metadata == {}` 단언 갱신
- [ ] `tests/chatbot/test_payload_service.py:97` 의 지시문 테스트를 결정된 사양에 맞게 갱신
- [ ] `/clear`, `/model` 이 히스토리에 남는지 확인하는 회귀 테스트 추가

### [VCP-002] VCP 화면의 현재가 갱신 대상과 폴링 정리 결함 수정
- 카테고리: VCP 시그널 | 티어: T2 | 근거: AUDIT-VCP §1.2, §4.1
- 티어 근거: `frontend/src/app/dashboard/kr/vcp/page.tsx` 한 파일이며 위험 경로가
  아닙니다. 변경은 30줄 안쪽으로 예상되지만 장중 갱신 동작이 바뀌므로 실측이 필요해
  T2 로 올립니다.
- [ ] 현재가 갱신 effect 가 목록 내용 변화를 반영하도록 의존성 수정
- [ ] `checkRunningStatus` 가 만드는 `setInterval` 핸들을 ref 에 담아 언마운트에서 정리
- [ ] 날짜를 바꿔도 개수가 같을 때 갱신 대상이 따라 바뀌는지 확인하는 vitest 추가
- [ ] agent-browser 로 날짜 전환 후 현재가 갱신을 실측

### [FLOW-004] 백테스트 상태 어휘와 손익비 계산을 바로잡는다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW §1.3, §1.4, §5.2
- [ ] 전패(승 0건, 패 N건)와 미집계(종료 거래 0건)를 구분하도록 `determine_backtest_status` 수정
- [ ] 상태 문자열 집합을 확정하고 프론트엔드의 `status === 'OK'` 비교를 그 집합에 맞춤
- [ ] 손실이 0일 때의 손익비 표기 방식을 결정해 반영 (비율이 아닌 값을 내보내지 않음)
- [ ] `aggregate_cumulative_kpis` 실구현 테스트 추가 (승률·평균 ROI·손익비·등급별 ROI)
- [ ] `determine_backtest_status` 경계값 테스트 추가

### [JONGGA-005] 종가 라우트의 숫자·티커 정규화 헬퍼 통합
- 카테고리: 종가베팅 | 티어: T2 | 근거: AUDIT-JONGGA §2.1, §5.1
- [ ] `kr_market_signal_common` 의 `_safe_float` 와 `_safe_int` 로 변환 규칙을 일원화하고,
      퍼센트 기호와 "원" 글자 처리 기준을 한 곳에서 정함
- [ ] 종가 정규화 헬퍼와 등급 헬퍼의 지역 사본을 제거
- [ ] 티커 정규화의 빈 값 규약을 하나로 정하고, `"000000"` 방어 코드를 정리
- [ ] `_jongga_sort_key` 와 `_normalize_jongga_signal_for_frontend` 에 대한 테스트를
      함께 추가하고, 목표가·손절가 계수 1.09 와 0.95 의 근거를 상수로 옮길지 판단
- [ ] pytest 전체 통과 확인

### [FE-005] HTTP 호출 경로를 `fetchAPI` 로 통일하고 세션 조회 중복을 없앤다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: AUDIT-FE §2.1, §2.3, §5.2
- `api.ts` 열한 개 함수와 컴포넌트 세 개를 건드리므로 300줄에 근접합니다. 구현 후
  `git diff --stat` 이 300줄을 넘으면 `T3` 으로 올립니다.
- [ ] `krAPI` 와 `paperTradingAPI` 의 raw `fetch` 열한 곳을 `fetchAPI` 로 이관
- [ ] 409 응답 구분과 `error.error` 읽기 같은 개별 처리를 `fetchAPI` 위에서 표현
- [ ] `browser_session_id` 발급을 공용 헬퍼 하나로 모음. 챗봇 카테고리의 사본은
      해당 카테고리와 경계를 맞춘 뒤 정리
- [ ] 사용량 조회 두 곳에 `encodeURIComponent` 적용
- [ ] `src/lib/api.test.ts` 를 만들어 타임아웃, `AbortError`, 실패 상태 코드 분기 검사

### [FE-006] API 키 저장 경로를 정리하고 죽은 코드를 걷어낸다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: AUDIT-FE §1.4, §3.1
- 삭제 위주라서 줄 수로는 `T1` 에 해당할 수 있으나, 의존성이 함께 빠지면서 번들 구성이
  달라지므로 `tier-rules.md` §1 의 의존성 관련 조항 취지에 따라 `T2` 로 둡니다.
- [ ] `src/utils/secureStorage.ts` 삭제
- [ ] `crypto-js`, `@types/crypto-js`, 그리고 미사용인 `zustand` 와 `react-icons` 제거.
      `frontend/package.json` 은 인프라 카테고리 소관이므로 그쪽과 조율
- [ ] `PERPLEXITY_API_KEY` 를 읽는 쪽과 쓰는 쪽의 비대칭 해소
- [ ] API 키를 클라이언트에 남길지 서버에만 둘지 결정하고 한쪽으로 정리
- [ ] `npm run build` 와 vitest 전체 통과 확인

### [INFRA-006] init_data 임포트 경로를 하나로 통일
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1.2, §2.1
- `[INFRA-007]` 을 흡수했습니다. 같은 파일을 같은 티어로 두 번 여는 대신 한 사이클에서
  함께 처리합니다. 흡수된 번호는 재사용하지 않습니다.
- `scripts/init_data.py` 와 `services/scheduler_jobs.py` 가 모두 위험 경로에 있어 T3 입니다.
- [ ] `scripts/__init__.py` 를 추가할지, `sys.path` 주입을 걷어낼지 방식을 확정
- [ ] `services/scheduler_jobs.py:32-36` 의 `importlib` 지연 로드를
      `from scripts import init_data` 방식으로 통일
- [ ] `services/kr_market_route_service.py:142` 와 `tests/test_grading_logic.py:9` 의
      최상위 임포트를 같은 방식으로 정리
- [ ] `sys.modules` 에 `init_data` 와 `scripts.init_data` 가 동시에 올라가지 않음을
      확인하는 테스트 추가
- [ ] `scripts/init_data.py:55-65` 의 `NumpyEncoder` 사본을 삭제하고 공용
      `numpy_json_encoder` 를 import
- [ ] `cls=NumpyEncoder` 를 넘기는 다섯 곳(730, 1785, 1790, 1978, 2680)이 공용 구현을
      쓰는지 확인
- [ ] `datetime` 이 섞인 payload 가 정상 저장되는지 확인하는 테스트 추가
- [ ] pytest 전체 통과 확인

### [VCP-004] VCP 응답 생성 헬퍼의 검증 공백 메우기
- 카테고리: VCP 시그널 | 티어: T2 | 근거: AUDIT-VCP §5.1
- 티어 근거: 테스트 파일만 바꾸므로 `tier-rules.md` §1 의 제외 조항을 적용할 수 없고,
  추가되는 줄 수를 그대로 셉니다. 다섯 함수 분량이면 300줄 안쪽으로 예상됩니다.
- 선행 조건: `[VCP-001]` 과 `[VCP-007]` 이 끝난 뒤에 착수합니다. 지금 상태를 그대로
  고정하는 테스트를 먼저 쓰면 결함을 정답으로 굳히게 됩니다. 특히 세 번째 항목이 다루는
  `_merge_ai_data_into_vcp_signals` 는 `[VCP-007]` 이 고칠 대상입니다.
- [ ] `_apply_vcp_reanalysis_updates` 의 성공·실패 분기 테스트 추가
- [ ] `_build_ai_data_map` 과 `_merge_legacy_ai_fields_into_map` 의 병합 규칙 테스트 추가
- [ ] `_merge_ai_data_into_vcp_signals` 의 필드 덮어쓰기 동작 테스트 추가
- [ ] pytest 전체 통과 확인

### [FLOW-005] 수급 교차검증을 서비스 안에서 끝낸다
- 카테고리: 수급·백테스트 | 티어: T3 | 근거: AUDIT-FLOW §1.2, §2.1, §3.1
- `services/investor_trend_5day_service.py` 는 `tier-rules.md` §2 "수급 집계" 위험 경로이므로
  줄 수와 무관하게 T3 입니다. 호출자 정리는 `engine/` 과 종목상세 카테고리에 걸치므로,
  서비스 쪽 진입점을 먼저 만들고 호출자는 뒤이어 옮깁니다.
- [ ] `_resolve_best_payload` 의 교체 조건을 다시 정의해 `_is_large_disagreement` 가 실제로
      판정에 쓰이도록 하거나, 쓰지 않기로 하면 함수와 세 상수를 함께 제거
- [ ] `stale_csv` 단독으로 무조건 교체하던 동작을 의도한 규칙으로 고침
- [ ] 이상징후 재조회를 서비스 내부에서 수행하는 단일 진입점 추가
- [ ] 호출자 다섯 곳의 `_has_csv_anomaly_flags` 와 두 번 호출 패턴을 그 진입점으로 교체
- [ ] 호출자가 없는 `load_investor_trend_5day_map` 의 존치 여부 결정
- [ ] 교체 규칙 회귀 테스트 추가 (일치·불일치·지연 각 경우)

### [FE-007] 모달 셸을 통합하고 대형 클라이언트 컴포넌트를 나눈다
- 카테고리: 프론트엔드 공통 | 티어: T3 | 근거: AUDIT-FE §2.2, §3.2, §4.1
- `PaperTradingModal.tsx` 1,140줄 분해만으로 300줄을 넘기므로 `T3` 입니다.
- [ ] 다섯 벌의 모달 셸을 `Modal.tsx` 하나로 모으고 Escape 키와 ARIA 속성을 한 자리에서 보장
- [ ] `PaperTradingModal.tsx` 에서 자산 차트를 별도 컴포넌트로 분리
- [ ] `PaperTradingModal.tsx` 에서 입금과 계좌 초기화를 별도 컴포넌트로 분리
- [ ] `src/app/page.tsx` 의 탭 전환부만 클라이언트 컴포넌트로 떼어내고 나머지를 서버 컴포넌트로 환원
- [ ] `SellStockModal` 의 단일 값 상태와 빈 오버레이 제거
- [ ] `/qa-only` 로 모의투자 화면과 랜딩 화면의 시나리오를 돌리고 지적 사항을 [2] 구현으로
      되돌려 반영. `npm run build` 결과도 함께 확인

### [JONGGA-006] 종가베팅 페이지에서 범용 컴포넌트와 정적 모달 분리
- 카테고리: 종가베팅 | 티어: T3 | 근거: AUDIT-JONGGA §2.2, §4.1
- 선행 조건: `[FE-007]` 이 모달 셸을 `Modal.tsx` 로 통합한 뒤에 착수합니다. 통합 전에
  `GradeGuideModal` 을 옮기면 곧 다시 옮기게 됩니다.
- 이동만으로도 추가와 삭제의 합계가 300줄을 크게 넘으므로 T3 입니다. 분량이 부담되면
  범용 프리미티브 이동과 정적 모달 이동을 두 항목으로 쪼개는 방안을 먼저 검토합니다.
- [ ] `Tooltip` 지역 정의를 제거하고 `frontend/src/app/components/Tooltip.tsx` 를 사용.
      필요한 `wide` 와 `width` 프롭은 공용 컴포넌트 쪽에 반영
- [ ] `data-status/page.tsx` 의 세 번째 Tooltip 사본도 같은 방향으로 정리
- [ ] `PriceRangeBar`, `StatBox`, `ScoreBar` 를 컴포넌트 디렉터리로 이동
- [ ] `GradeGuideModal` 을 `ClosingBetCriteriaModal` 과 같은 자리로 이동
- [ ] `npm run build`, `npm run type-check`, vitest 전체 통과 확인
- [ ] `/qa-only` 로 종가베팅 화면과 데이터 상태 화면의 시나리오를 돌리고 지적 사항을
      [2] 구현으로 되돌려 반영

### [CHAT-003] 두 SQLite 캐시 모듈을 공용 골격으로 통합
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT §2.1
- 티어 판정: 949줄을 다루므로 300줄을 확실히 넘습니다. 공용 골격을
  `services/sqlite_utils.py` 에 두는 방안을 택하면 파일명에 `sqlite` 가 들어가 위험 경로에도
  닿으므로, 어느 쪽으로 가든 `T3` 입니다.
- [ ] 두 모듈의 실제 차이(테이블 이름, 페이로드 모양, 서명 계산)를 목록으로 확정
- [ ] 2단 캐시 골격을 한 곳으로 모으고 차이 부분만 주입받도록 정리
- [ ] `runtime_stock_map_cache` 와 `stock_context_cache` 의 공개 함수 시그니처 유지
- [ ] 기존 두 회귀 테스트가 그대로 통과하는지 확인
- [ ] 스키마 복구와 프루닝 동작이 양쪽에서 동일한지 검증하는 테스트 추가

### [CHAT-004] 챗봇 페이지 분할과 응답 파서 단일화
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT §2.2, §4.1, §5.1
- 티어 판정: 1,718줄 파일을 쪼개므로 300줄을 넘습니다. 선행 조건으로 `[CHAT-001]` 이
  끝나 있어야 합니다. 같은 SSE 블록을 두 항목이 동시에 건드리면 충돌합니다.
- [ ] 마크다운 교정과 추론·추천 질문 파싱을 별도 모듈로 분리
- [ ] 백엔드가 이미 나눠 보내는 `reasoning_chunk` / `answer_chunk` 를 신뢰하고, 프런트의
      중복 헤더 파싱 범위를 히스토리 복원 경로로 한정
- [ ] SSE 수신, 세션 관리, 음성 입력을 각각 훅이나 컴포넌트로 분리
- [ ] 파서 호출을 메모이제이션해 스트리밍 중 전체 메시지 재파싱을 제거
- [ ] 분리한 파서와 SSE 처리에 vitest 테스트 추가
- [ ] `/qa-only` 로 챗봇 화면의 스트리밍 시나리오를 돌리고 지적 사항을 [2] 구현으로
      되돌려 반영

### [FE-008] 대시보드 진입 시의 하이드레이션 불일치 제거
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: QA 리포트 2026-09-02 ISSUE-001
- 티어 판정: 원인 위치를 아직 특정하지 못했습니다. 서버와 클라이언트가 서로 다른 값을
  그리는 자리를 찾아야 하며, 후보는 `마지막 업데이트` 처럼 로케일 시각을 그리는 표시입니다.
  건드릴 파일 수가 확정되지 않아 `T2` 로 두고, 실제 범위가 넓어지면 상향합니다.
- [ ] 하이드레이션 경고를 내는 서브트리를 특정 (React DevTools 또는 경고 스택 추적)
- [ ] 서버와 클라이언트가 같은 값을 그리도록 수정 (시각 표시는 마운트 후 렌더 등)
- [ ] `/dashboard/kr` 진입 시 콘솔 오류 0건 확인
- [ ] `/qa-only` 실행

### [CHAT-007] 사이드바 대화 항목을 키보드로 열 수 있게 만든다
- 카테고리: 챗봇 | 티어: T1 | 근거: QA 리포트 2026-09-02 ISSUE-002
- 티어 판정: `frontend/src/app/chatbot/page.tsx` 의 사이드바 목록 렌더 두 곳만 바꿉니다.
  `div` 를 `button` 으로 바꾸거나 `role`·`tabIndex`·키 핸들러를 붙이는 정도라 50줄 아래입니다.
  `[CHAT-004]` 가 이 파일을 쪼개기 전에 끝내는 편이 충돌이 적습니다.
- [ ] 대화 항목에 포커스가 가고 Enter 로 열리도록 수정
- [ ] 삭제 버튼이 항목 안에 중첩되지 않도록 마크업 정리 (버튼 안의 버튼은 무효한 HTML)
- [ ] `/qa-only` 실행

## P2 — 대기

### [CHAT-006] 챗봇 SSE 스트림이 NaN 방어를 우회하는지 점검
- 카테고리: 챗봇 | 티어: T1 | 근거: 2026-09-01 VCP-006 의 code-review 지적
- `[VCP-006]` 이 붙인 JSON provider 는 `jsonify` 를 지나는 응답만 덮습니다. 챗봇 스트림은
  `services/kr_market_chatbot_stream_helpers.py:87,91` 에서 `json.dumps` 로 직접 직렬화하므로
  provider 를 지나지 않습니다. 청크에 NaN 이 실리면 프론트엔드의 `JSON.parse` 가 그 줄에서
  예외를 던져 스트림 처리가 끊깁니다.
- 다만 청크에 담기는 값은 모델이 준 문자열과 `usage_metadata` 의 토큰 수라서 NaN 이 생길
  여지가 좁습니다. 실재 여부를 먼저 확인하고, 없으면 항목을 닫습니다.
- [ ] 청크에 담기는 값의 출처를 확인해 NaN 이 실릴 수 있는지 판단
- [ ] 실릴 수 있으면 `sanitize_for_json` 을 거치도록 고치고 회귀 테스트 추가

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

### [CHAT-005] 죽은 프롬프트 상수와 레거시 경로 정리
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §3.1, §3.2
- 티어 판정: 삭제 위주이며 위험 경로에 닿지 않습니다. 170줄에서 250줄 사이로 보지만,
  구현 후 `git diff --stat` 이 300줄을 넘으면 `tier-rules.md` §3-6 에 따라 `T3` 으로
  올립니다. 위임 믹스인 다섯 개를 평탄화하는 작업은 규모가 따로여서 이 항목에 넣지
  않았습니다.
- [ ] `INTENT_PROMPTS`, `VCP_EXPERT_PERSONA`, `VCP_EXPERT_SUGGESTIONS` 제거
- [ ] 호출자 없는 래퍼 세 개(`_fetch_mock_data`, `_detect_stock_query_from_stock_map`,
      `_fallback_response`) 처리 방향 결정 후 정리
- [ ] `close()` 에 남은 초기화 잔재 제거 (종료 시 종목 맵 재로드 중단)
- [ ] `_CompatGenerativeModel` 과 `_run_legacy_model_chat` 이 아직 필요한지 확인 후 정리
- [ ] 삭제한 심볼을 참조하던 테스트 정리 및 pytest 전체 통과 확인

### [FLOW-006] 백테스트 재노출 전용 계층을 걷어낸다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW §3.1
- [ ] `..._service`, `..._calculators`, `..._cumulative`, `..._signal_stats` 네 파일의
      외부 호출자를 확인한 뒤 남길 진입점 하나를 결정
- [ ] 나머지 재노출 계층 제거하고 `app/routes/kr_market_backtest_helpers.py` 의 import 정리
- [ ] `tests/services/test_kr_market_backtest_service.py` 의 import 경로 갱신
- [ ] pytest 전체 통과 확인

### [FLOW-007] 티커 패딩 헬퍼를 공용 유틸로 통합한다
- 카테고리: 수급·백테스트 | 티어: T1 | 근거: AUDIT-FLOW §2.2
- [ ] `..._scenario_helpers` 와 `..._trade_helpers` 의 자체 구현을
      `services.kr_market_csv_utils.get_ticker_padded_series` 로 교체
- [ ] 캐시 컬럼(`_ticker_padded`) 동작이 교체 전후로 같은지 확인
- [ ] `tests/services/test_kr_market_backtest_service.py` 통과 확인

### [INFRA-008] init_data 의 죽은 진입점 정리
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §3.1, §3.2
- `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] `create_market_gate`(1993-2096)를 삭제하고 Market Gate 생성 경로가
      `engine/market_gate.MarketGate` 하나임을 확인
- [ ] `reset_cache`(529-534)의 존치 여부를 판단하고 불필요하면 삭제
- [ ] `assign_grade`(91-145)를 실제 등급 판정 경로에 연결하거나,
      `tests/test_grading_logic.py` 와 함께 폐기
- [ ] pytest 전체 통과 확인

### [INFRA-009] init_data 를 책임 단위로 분리
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §4.1, §5.2
- 선행 조건: `[INFRA-008]` 로 죽은 코드를 걷어낸 뒤 남은 규모로 분리 범위를 다시
  잡습니다. `scripts/init_data.py` 가 위험 경로에 있어 T3 입니다.
- [ ] 열세 가지 책임을 묶어 분리 단위를 확정 (수집 / 생성 / 알림 / CLI 를 후보로 검토)
- [ ] 한 번에 300줄을 넘기지 않도록 여러 사이클로 나누어 진행할 순서를 결정
- [ ] `scripts/debug_details.py:13` 의 깨진 import 를 정리 대상에 포함
- [ ] 분리 대상 함수 가운데 테스트가 없는 `create_jongga_v2_latest` 등에 회귀 테스트 추가
- [ ] 이동한 파일 경로를 `tier-rules.md` §2 위험 경로 목록에 반영

### [FLOW-002] 수급 데이터 분석 고도화
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: docs/plans/TO_DO_LIST.md 이관
- [ ] 섹터별 수급 집계 설계
- [ ] 기존 `services/investor_trend_5day_service.py` 와의 경계 정리

### [INFRA-017] 존재하지 않는 API 경로가 404 대신 500 을 돌려준다
- 카테고리: 인프라 | 티어: T2 | 근거: [FE-004] 사이클의 실측
- 관찰: `curl http://localhost:5501/api/health` 가 500 과 함께 본문에
  `"error": "Internal Server Error", "message": "404 Not Found: ..."` 를 돌려줍니다.
  존재하지 않는 경로이므로 404 가 나가야 하는데, 전역 예외 처리기가 `NotFound` 까지
  삼켜 500 으로 바꾸고 `logs/backend.log` 에 `CRITICAL SERVER ERROR` 로 남깁니다.
- [ ] 전역 예외 처리기가 `werkzeug.exceptions.HTTPException` 을 그대로 통과시키도록 수정
- [ ] 오탐 로그가 사라지는지 `logs/backend.log` 로 확인
- [ ] 없는 경로와 실제 서버 오류를 구분하는 회귀 검사 추가

### [INFRA-002] 타입 힌트 보강
- 카테고리: 인프라 | 티어: T2 | 근거: CLAUDE.md 이관
- [ ] 타입 힌트가 없는 공개 함수 범위 확정
- [ ] 우선순위가 높은 모듈부터 보강
- [ ] 한 번에 300줄을 넘기지 않도록 여러 항목으로 나누어 진행
