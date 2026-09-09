## Summary
VCP-020/021/023/024 범위는 현재 구현·회귀 테스트·evidence와 정합합니다. 날짜 증명은 단일 ISO signal_date와 date-specific 파일 내부 날짜를 기준으로 fail-closed이며, legacy fallback은 현재 날짜이면서 payload가 같은 날짜를 명시할 때만 허용됩니다. 1일 수급은 None을 유지하면서 producer→CSV→AI prompt로 전달되고, 0은 실제 값으로 보존됩니다.
Architectural Status: CLEAR

## Analysis
- engine/vcp_ai_orchestration_helpers.py:13-17: VCP_AI_RECOMMENDATION_FIELDS가 세 recommendation field의 단일 정본입니다. route/cache/tracker/reanalysis가 이 tuple을 import하므로 문자열 tuple이 여러 모듈에서 재정의되지 않습니다. engine.vcp_ai_orchestration_helpers는 표준 라이브러리만 import하므로 확인된 import cycle은 없습니다.
- services/kr_market_vcp_payload_service.py:269-368: _resolve_single_signal_date가 모든 signal이 dict이고, 날짜가 모두 동일하며, %Y-%m-%d 왕복 정규화까지 통과할 때만 merge를 진행합니다. mixed/missing/invalid date는 즉시 merge하지 않습니다. date-specific 파일은 ai_analysis_results_YYYYMMDD.json만 읽습니다. _is_date_specific_payload_compatible는 내부 signal_date가 없으면 날짜 파일명을 근거로 허용하고, 값이 있으면 요청 날짜와 정확히 일치해야 허용합니다. generic kr_ai_analysis.json은 현재 날짜에 한해 읽으며, _payload_matches_signal_date로 payload 내부 날짜가 현재 signal date와 일치할 때만 사용합니다. date-specific loader가 TypeError를 내는 구형 deep_copy=False 미지원 경로는 기존 TypeError 재호출 fallback으로 유지됩니다. 이는 loader API 호환성 fallback이며 날짜 proof를 우회하지 않습니다.
- engine/screener_result_builders.py:30-38,54-60: foreign_net_1d/inst_net_1d의 producer 기본값이 0에서 None으로 바뀌어 결측과 실제 0을 구분합니다. signal item은 기존 CSV row의 1일 값을 foreign_1d/inst_1d로 전달하고, 누락된 구형 CSV는 None으로 수용합니다.
- engine/vcp_ai_analyzer_helpers.py:553-635: safe_optional_float를 통해 None, 빈 문자열, NaN, inf, 비숫자 문자열을 숫자 기본값으로 바꾸지 않습니다. 완전한 입력만 기존 BUY/SELL/HOLD 계산을 사용합니다. 부분 입력은 실제로 확인된 score 또는 양쪽 기간의 완전한 음수 수급만 사용해 보수적 SELL을 허용하고, 그 외에는 HOLD/55를 반환합니다. 이는 테스트의 partial_sell_uses_only_real_negative_evidence 계약과 일치합니다. 실제 0은 finite optional float로 유지되어 완전 입력의 중립 수급 계산에 참여합니다.
- engine/signal_tracker_ai_helpers.py:85-90: provider priority는 (gemini, gpt, perplexity)와 공개 field tuple을 zip으로 조립합니다. field tuple 길이/순서가 provider priority와 직접 연결되는 의도된 계약이며, 현재 정본 tuple과 일치합니다.
- services/kr_market_vcp_reanalysis_service.py:20-41,90-155,533-536: second provider alias(openai, zai, z.ai, perplexity)가 정본 field를 통해 해석됩니다. 알 수 없는 provider는 GPT field로 fallback하며 기존 호환 계약을 유지합니다. reanalysis required key는 정본의 Gemini field와 second-provider field를 사용합니다.
- targeted-green-final.json: VCP-020/021/024 targeted green 130 passed exit0. date-specific 파일의 내부 날짜 없음은 filename 근거로 허용, 충돌/invalid는 거부. generic legacy는 현재 날짜와 명시적 일치 payload만 허용. legacy loader failure 시 date payload가 유지됨.
- fallback-green.json: fallback 관련 58 passed. 결측/NaN/inf/비숫자는 HOLD/55와 정보 부족 문구로 유지되고, 실제 0과 완전 verdict는 기존 계산으로 검증되었습니다.
- static-results.json: full pytest exit0 2280 passed,2 skipped. full Vitest 및 type-check도 exit0. 로그 tail에 일부 jsdom URL 출력은 있으나 테스트 실패가 아니며, 외부 HTTP 실행 증거로 해석할 근거는 없습니다.

## Root Cause
수정 전 결함은 세 가지였습니다.
1. recommendation field 목록이 여러 모듈에 중복되어 provider 추가·저장·응답 merge 간 schema가 어긋날 수 있었습니다.
2. payload merge가 첫 signal 날짜만 보고 generic legacy를 fallback하여 과거 날짜에 최신 판정을 섞을 수 있었습니다.
3. 1일 수급 결측을 0으로 대체해 rule fallback이 정보 부족을 실제 중립 수급으로 오인할 수 있었습니다.
현재 변경은 각각 정본 tuple, 전체 날짜 proof, optional finite numeric 흐름으로 경계를 고정합니다.

## Recommendations
1. CLEAR: 현재 VCP 변경 범위는 계획의 날짜 proof, legacy fail-closed, CSV backward compatibility, None/0 구분, fallback 입력 보존 계약을 충족합니다.
2. 부분 입력에서 실제 음수 score/수급이면 SELL을 허용하는 동작은 “모든 결측은 무조건 HOLD”가 아니라 기존 승인된 보수적 partial evidence 계약입니다. 이 정책을 바꾸려면 별도 범위 결정이 필요합니다.
3. 새 registry/module을 추가하지 않고 기존 engine.vcp_ai_orchestration_helpers를 정본으로 사용한 선택은 계획의 “새 추상화 부담 금지”와 맞습니다.

## Architectural Status
CLEAR

## References
검토당시 review-input.json의5252bec 기준. 경로·표시서식을 정리하고 판단본문을 보존했다. 이 결과 뒤 code-review가 legacy 병합 shape 예외 회귀를 발견하여 해당 delta는 재검토 대상이다.

## Legacy-shape delta 재검토
추가된 legacy-shape 보완 delta는 정상적으로 적용되었습니다. 동일 날짜의 검증된 date-specific payload를 먼저 ai_data_map에 만든 뒤 legacy 로드/병합을 별도 try로 감싸므로, legacy가 None/잘못된 shape를 반환하거나 merge callback이 TypeError를 내도 이미 검증된 날짜 판정이 사라지지 않습니다.
Architectural Status: CLEAR

### Delta Analysis
- services/kr_market_vcp_payload_service.py:288-319: 날짜별 payload를 먼저 ai_data_map으로 구성합니다. 현재 날짜에서만 generic legacy를 읽습니다. legacy payload가 같은 signal_date를 명시한 뒤에만 병합합니다. legacy loader 실패와 legacy merge callback 실패를 별도 outer try에서 로그 처리하고, ai_data_map을 유지합니다. 따라서 signals=None, 비 iterable legacy shape, callback TypeError가 date-specific 결과를 훼손하지 않습니다.
- tests/services/test_kr_market_vcp_payload_service_refactor.py:~290-310: 동일 날짜 date-specific payload가 있고 legacy shape가 invalid한 경우에도 기존 Gemini 판정이 보존되는 회귀 계약이 추가되었습니다. loader의 deep_copy=False TypeError 후 재호출 실패도 검증된 date payload를 보존하는 기존 계약과 함께 유지됩니다.
- legacy-shape-red.json: 보완 전 예상 실패 TypeError: NoneType object is not iterable, exit1.
- legacy-shape-green.json: 보완 후 payload service 테스트32 passed exit0. invalid same-date legacy shape가 이미 검증된 date-specific recommendation을 폐기하지 않음.

### Root Cause
이전 구현은 legacy 병합 callback 호출을 부분적으로만 보호했습니다. date-specific map이 이미 생성되어도 legacy branch의 build_ai_data_map 또는 merge callback이 예외를 내면 함수 전체가 중단되어, 정상적인 날짜 판정까지 결과에 반영되지 않을 수 있었습니다.
현재 delta는 legacy를 선택적 보강 단계로 격리해 이 경계를 복원합니다.

### Architectural Status
CLEAR
날짜 proof, legacy fail-closed, loader TypeError 호환성, invalid legacy shape 격리가 서로 충돌하지 않습니다. 새 모듈이나 import cycle도 추가되지 않았습니다.
Delta SHA: source8febf71a20415d9dff03a8a4cab0e674cabbc3fc834108df93200160f2ee420f / testb2dc11252d9eadb5a3bb6c2cb47a0e63706d5da39f8c46a581304e211f0404c6.
