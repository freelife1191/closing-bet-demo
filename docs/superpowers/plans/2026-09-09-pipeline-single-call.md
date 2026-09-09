# Pipeline single call Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** JONGGA-014의 Phase1 내부 TypeError가 재호출 없이 원래 예외로 전파된다.
**Architecture:** 기존 파이프라인과 Phase1.execute(candidates, target_date)를 유지하며 호환 폴백만 제거한다.
**Tech Stack:** Python, pytest, async.
**Spec:** 2026-09-09 대화에서 제시한 JONGGA-014: 내부 TypeError 때문에 분석이 두 번 실행되는 폴백 제거. 사용자 「승인」. 이 문서는 그 한 항목만 다룬다.

## Global Constraints
- develop에서 사용자 root package.json 및 다른 변경 보존. 실제 data/.env/서비스 변경 금지.
- 위험경로 engine/phases_pipeline.py 수정이므로 T3. 전체 pytest/Vitest, 순차 ponytail/code-review/review, UltraQA와 웹 진입 실측 필요.
- 단계별 리뷰 상한 15분, QA 명령 60초(전체 테스트 10분), 같은 실패 3회/QA 5회 제한.

### Task 1: Phase1 단일 호출
**Files:** engine/phases_pipeline.py; tests/engine/test_phases_pipeline_refactor.py.
**Interfaces:** SignalGenerationPipeline.execute(candidates, market_status=None, target_date=None) 입력/최종 Signal 목록 동일. Phase1Analyzer.execute(candidates, target_date=None)는 market_status를 받지 않는다.
- [ ] 오류 객체와 호출 횟수·후속 단계 미호출을 검사한다.
```python
error = TypeError("phase1 internal error")
class _Phase1InternalTypeErrorStub:
    async def execute(self, candidates, target_date=None):
        calls.append(("phase1", candidates, target_date))
        raise error
pipeline = _build_pipeline(calls)
pipeline.phase1 = _Phase1InternalTypeErrorStub()
with pytest.raises(TypeError) as caught:
    await pipeline.execute(CANDIDATES, target_date=TARGET_DATE)
assert caught.value is error
assert len(calls) == 1
```
- [ ] venv/bin/python -m pytest tests/engine/test_phases_pipeline_refactor.py 실행: 기존 재호출 때문에 새 검사 실패 확인.
- [ ] try/except를 아래 한 호출로 치환한다.
```python
phase1_results = await self.phase1.execute(candidates, target_date=target_date)
```
- [ ] 대상 검사와 전체 pytest/Vitest 실행. 기존 정상·빈결과·날짜전달 계약 유지.
- [ ] T3 독립 리뷰 후 QA 행렬 포함 첫 커밋. 격리 종가 화면의 분석 진입을 외부 I/O 대역과 연결해 정상/TypeError 결과 확인. 원래 예외와 호출횟수는 서비스 하네스 보강.
- [ ] 필수 QA·정리 후에만 ID별 아카이브/제거.

## 계획 검토 응답
독립 검토 REJECT: 인터페이스 지칭과 승인 범위 명확화를 반영했다. 회귀 테스트는 위 단계에서 새로 추가한다. 브라우저 생략 제안은 기존 화면이 사용하는 백엔드 변경도 실측을 요구하는 ultraqa.md §1-1 및 승인 설계와 충돌해 미반영. 예외 동일성은 하네스로, 사용자 진입/오류 표시는 브라우저로 구분 검증한다.
