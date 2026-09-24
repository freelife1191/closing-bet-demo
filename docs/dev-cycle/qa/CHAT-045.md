# [CHAT-045] 챗봇 VCP 요약이 점수 없는 종목을 「0점 (매수 추천)」으로 LLM 문맥에 넣는다 — QA 기록

- 대상: `chatbot/signal_context.py` 의 `build_vcp_buy_recommendations_text`(점수 결측 시 표기 생략, 이름 None 처리)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-24 11:34 | 실행 2026-09-24 11:35
- 검증 기준 커밋: `a64d299` (첫 커밋). 사본은 이 커밋의 `git archive` 이며 실행 중 범위 파일은 바뀌지 않았다
- 구성 근거: 설계 승인(11:31), 호출 경로 추적(챗봇 VCP 의도 → `core_intent_context_mixin._build_vcp_intent_context` → `chatbot/intent_context.build_vcp_intent_context` → `core_data_access_mixin._fetch_vcp_ai_analysis` → `chatbot/data_service.fetch_vcp_ai_analysis` → `load_vcp_ai_payload`(`kr_ai_analysis.json`) → `build_vcp_analysis_summary_text`), 재분석 행 모양(`engine/vcp_ai_orchestration_helpers.py:35` 가 `ticker`·`stock_name`·추천 칸만 둔다)
- QA 엔진(engine): Claude Code. 결과는 LLM 에 넘기는 문맥 문자열이며 화면에 직접 보이지 않는다. 화면 흐름(챗봇 전송)은 실제 LLM 호출과 쿼터 소모가 따르므로 실행하지 않는다. browser_applicability: not_applicable(근거: 바뀐 값은 LLM 입력 문자열뿐이고, 그 문자열을 만드는 함수 경로 전체를 하네스로 호출한다)
- 하네스: scratchpad `chat045qa_harness.py`. 검증 기준 커밋의 `git archive` 사본을 코드로 쓰고, 빈 임시 `data` 디렉터리에 수집 모양의 `kr_ai_analysis.json`(`000088`, 점수 72, BUY)을 만든 뒤 `[VCP-044]` 저장 경로 `update_vcp_ai_cache_files` 로 재분석 결과(`030200` KT, 점수 없음, BUY)를 넣는다. 이어 `fetch_vcp_ai_analysis`·`build_vcp_intent_context` 를 부른다. 대조는 수정 전 커밋 `8b0b2eb` 사본에서 같은 하네스를 돌린다
- 원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고, 실제 LLM·발송은 하지 않는다
- 필수 여부(required): S-1·S-2 예
- 반복(iteration): 1회. 첫 실행(11:35:05)은 하네스가 날짜 없는 `kr_ai_analysis.json` 하나만 만들어, 재분석 저장이 날짜 파일을 기준으로 다시 쓰면서 `000088` 이 빠졌다(`[VCP-044]` 에 기록만 한 「레거시 단독 날짜 없는 파일의 행 유실」과 같은 현상이며 수집은 날짜 파일도 함께 쓰므로 운영 경로가 아니다). 하네스가 수집처럼 네 파일을 모두 만들도록 고쳐 11:35:19 에 다시 돌렸고, 아래 「실제」는 그 결과다
- 결과: 통과 (필수 2/2)
- 증거: 아래 각 시나리오의 「실제」 줄(하네스 출력 원문), scratchpad `chat045qa_harness.py`·`chat045qa-after.log`·`chat045qa-before.log`
- 정리(cleanup): 사본 둘(`a64d299`·`8b0b2eb`)과 임시 `data` 삭제 뒤 없음 확인. 서버·브라우저는 띄우지 않았다. 원본 `data/kr_ai_analysis.json` 수정 시각(09-02 11:26) 그대로

## 시나리오

### S-1. 재분석이 넣은 점수 없는 BUY 종목이 「0점」 없이 문맥에 들어간다 (핵심)
- 조작: 하네스 1회
- 기대: `030200` 행에 `score`·`vcp_score`·`name` 이 없다. `fetch_vcp_ai_analysis` 출력에 `- **KT** (매수 추천)` 이 있고 「0점」이 없다. 머리글은 「매수 추천 2건」. 수정 전 사본에서는 `- **KT**: 0점 (매수 추천)` 이 나온다
- 실제: `030200 keys: ['gemini_recommendation', 'stock_name', 'ticker']`. 머리글 「분석 2건 (기준일 2026-09-24, 0일 경과), 매수 추천 2건」, 목록에 `- **KT** (매수 추천)` 이 있고 「0점」은 없다. 수정 전 사본은 같은 입력에서 `- **KT**: 0점 (매수 추천)`. 통과

### S-2. 점수가 있는 수집 행과 의도 문맥은 그대로다
- 조작: S-1 과 같은 실행
- 기대: `- **한화3우B**: 72점 (매수 추천)` 이 수정 전후 같고, `build_vcp_intent_context` 가 S-1 의 요약을 그대로 담는다
- 실제: `- **한화3우B**: 72점 (매수 추천)` 이 수정 전후 같다. `build_vcp_intent_context` 는 「[VCP AI 분석 결과]」 뒤에 S-1 과 같은 요약을 담고 지시문(「VCP 데이터에 근거해 …」)도 전후가 같다. 통과
