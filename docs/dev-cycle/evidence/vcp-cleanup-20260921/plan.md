# VCP cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Parent implements; independent source-only reviewers.

**Goal:** VCP-005/INFRA-008을 검증 완료하고 VCP-022 결측 확신도를 보완한다.
**Architecture:** 기존 API와 실제 fallback은 유지. 죽은 함수·루프를 삭제하고 공통 safe_confidence를 재사용한다.
**Tech Stack:** Python, pytest, Next.js/Vitest, ego-browser.
**Spec:** design.md

## Global Constraints

원본 .env/data/logs, 3500/5501/live 접근 금지. 실행은 비밀 없는 OS sandbox scratch만 사용.
루트 package.json 보존. 새 의존성·유료 API·설정·거래·삭제 금지. VCP-022는 역사 자료 요구가 남아 완료하지 않음.
사용자의 2026-09-21 승인 위임에 따라 parent가 설계·계획 검토 후 직접 실행.

## Review Focus

- Z.ai code 속성 해석 차이는 include_code=False로 보존.
- 모델 전환과 echo 2회 재시도 및 JSON repair는 계속 실행.
- provider 목록에 없는 fallback은 실행하지 않음.
- confidence None과 실제 0을 구분하고 범위 밖 원시 품질 값은 계속 거부.
- 제거된 assign_grade 검사를 실제 등급 엔진 검사를 지운 것으로 혼동하지 않음.

## Task 1: 회귀와 격리

Files: tests/engine/test_vcp_ai_analyzer_helpers_refactor.py, tests/engine/test_vcp_ai_analyzer_refactor.py.
- [ ] scratch 생성: git archive HEAD, 원본 .env/data 없이 venv 공유 및 node_modules 복제, 환경 allowlist, sandbox.
- [ ] 아래 케이스를 기존 helper 테스트에 추가한다.
```python
@pytest.mark.parametrize('value', [None, 'bad', '', float('inf'), float('-inf'), float('nan')])
def test_invalid_confidence_stays_missing(value):
    import json
    result = parse_json_response(json.dumps({'action': 'BUY', 'confidence': value, 'reason': '확신도 회귀 검증을 위한 충분한 한국어 분석 사유입니다.'}))
    assert result['confidence'] is None
    assert is_low_quality_recommendation(result)
```
- [ ] 격리 pytest target: 위 테스트 RED, 기존 analyzer/Z.ai/GPT/MarketGate/import/등급 tests GREEN 확인.

## Task 2: 최소 변경

Files: engine/vcp_ai_analyzer_helpers.py, engine/vcp_ai_analyzer.py, scripts/init_data.py, tests/test_grading_logic.py.
- [ ] `_normalize_confidence_value` 삭제, 호출은 `safe_confidence(value)`로 교체; 품질판정 except에 OverflowError 추가.
- [ ] status 추출 메서드 signature를 `(self, error, *, include_code=True)`로 변경; attrs는 include_code에 따라 선택.
```python
attrs = ('status_code', 'http_status', 'code') if include_code else ('status_code', 'http_status')
```
  Gemini 지역함수→self 메서드, Z.ai 지역함수→self 메서드(include_code=False).
- [ ] `_fallback_to_zai` 제거; `_build_perplexity_fallback_chain`의 이미 처리된 gpt/zai 반복 제거.
- [ ] `_resolve...`의 마지막 allowed_chain 분기와 빈 반환은 `return allowed_chain`으로 합침.
- [ ] Z.ai 1회 loop를 풀고 top-level loop break는 해당 모델 종료/다음모델 continue로 보존. echo 내부 break는 보존.
- [ ] init_data assign_grade/create_market_gate/reset_cache/get_market_indices/get_sector_indices와 캐시변수 제거. 이들만 호출하는 fetch 함수는 별도 확인 후 사용없으면 함께 제거.
- [ ] tests/test_grading_logic.py는 assign_grade 전용이므로 제거; 실제 engine grade tests 유지.
- [ ] target 및 전체 pytest, Vitest, lint, typecheck, build script 실행.

## Task 3: 리뷰·QA·마감

- [ ] diff/파일 SHA 고정 → ponytail → code-review와 architect → T3 review. 단계별 상한 15분, 묶음 상한 90분; 초과를 PASS로 세지 않음.
- [ ] UltraQA 행렬: VCP 상세 세 탭 None/0/75, 원시 캐시 fallback, 오류 복구, source-hash/dirty 보존, 소유 자원 정리.
- [ ] 구현+행렬 첫 커밋(명시적 경로 staging/check) 후 ego-browser 실제 화면 실행. 실제 parser로 fixture 생성.
- [ ] 필수통과 후 VCP-005/INFRA-008만 archive, VCP-022 잔여 유지. 연속 요청의 다음 묶음 검토.

## Critic 반영

- 두 confidence 호출부(패턴, JSON)를 모두 바꾼다. None을 숫자와 비교하는 곳은 품질 검사이며 TypeError 처리로 거부한다.
- status helper 회귀에 code=429 무시/인식, response.status_code=503, 문자열 429를 추가한다.
- 기존 Z.ai 테스트는 모델 전환/echo 2회/repair/마지막 실패/provider 제한을 이미 검사하므로 삭제하거나 기대를 낮추지 않는다.
- README/scripts/services/app/.claude 및 CLI 분기와 scheduler 소스에 세 삭제 함수의 외부 진입점이 없다. 저장소 밖의 수동 import 사용 여부까지 증명하지는 않는다.
- tests/engine/test_grade_classifier_refactor.py는 실제 엔진의 계약을 계속 검증한다. 폐기하는 7건은 연결되지 않은 옛 assign_grade의 별도 임계값 계약이며 현재 등급 기준과 같다고 주장하지 않는다.
