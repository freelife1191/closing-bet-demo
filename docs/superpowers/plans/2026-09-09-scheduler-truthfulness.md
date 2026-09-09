# Scheduler truthfulness Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline execution; project dev-cycle review order takes precedence. Steps use checkbox tracking.

**Goal:** INFRA-019 설명을 실제 스케줄·AI 선택에 맞추고 INFRA-029의 거짓 성공 로그를 제거한다.
**Architecture:** 기존 스케줄과 실행 순서/알림 조건/반환값은 유지한다. 변경은 사람용 설명과 네 단계 결과에 따른 로그 분기에 한정한다.
**Tech Stack:** Python logging/pytest, Next.js/React/Vitest, agent-browser.
**Spec:** 현재 대화의 INFRA-019 → INFRA-029 bounded 설계, 사용자 2026-09-09 「승인」. T3 규칙에 따라 계획만 작성한다.

## Constraints and approval
- 독립 clone develop, 원본 미추적 package.json 보존. 실제 .env 값, 원본 data 쓰기 금지.
- 원본 3500/5501 및 live 요청 금지. 수집/LLM/발송/거래/삭제는 격리 대역으로만 검사.
- 신규 의존성 없음. 운영 재시작/배포/푸시 없음.
- 두 항목 모두 T3: .env.example 및 services/scheduler_jobs.py 위험 경로.
- native OMX 쓰기 소유권 없는 App 실행: UltraQA app-adapted, hook 상태 조작 금지.
- 리뷰 순서 critic → 구현 → ponytail → code-review(code-reviewer+architect) → review → security-review. 리뷰 각 15분, 테스트 각 15분, QA 5회/동일실패3회 상한; 전체 실행 상한 3시간.

## Task 1: INFRA-019 운영 안내 일치
Files: README.md, .env.example, frontend/src/app/page.tsx.
Interfaces: 기존 환경 변수 입력과 JSX 문구. 코드 스케줄/AI 공급자 알고리즘 변경 없음.
- [x] 코드의 30분/17:00 체인과 공급자 선택을 대조하고 baseline pytest/Vitest 실행.
- [x] README 15:20 단독잡/JONGGA_SCHEDULE_TIME 서술 제거. 기본 5분만 30분으로 정정; 사용자 지정 간격 개념 유지. 랜딩 매매 전략의 15:20~15:30은 스케줄이 아니므로 유지.
- [x] .env.example JONGGA_SCHEDULE_TIME 제거, MARKET_GATE_UPDATE_INTERVAL_MINUTES=30. 기존 실제 환경은 수정하지 않음.
- [x] 랜딩 GPT 설명: 설정에 따라 Gemini와 함께 보조 검증하며 전환 조건에 해당하면 사용 가능한 Z.ai로 대체. Perplexity: 설정에 따라 보조 검증하며 호출 제한·인증 오류 등 전환 조건에 해당하면 사용 가능한 Z.ai·GPT로 대체. 모든 오류가 폴백된다고 표현하지 않는다. API 키 누락 시에는 허용된 GPT로 선택을 변경한다. 코드의 429/503·quota/auth 분기 및 Z.ai→GPT 가용 체인과 대조한다. 내부 변수명과 상세 조건은 개발 문서에 유지한다.
- [x] 번들 03-layouts-and-pages.md 읽기. 문구 전용 수정이라 새 문자열 고정 단위테스트 없이 실제 브라우저로 확인.

## Task 2: INFRA-029 거짓 완료 로그 제거
Files: services/scheduler_jobs.py, tests/services/test_scheduler_jobs_refactor.py.
Interfaces: run_daily_closing_analysis(test_mode: bool=False) -> None, side effects order preserved.
- [x] 기존 정상 체인 검사를 재사용해 실패 단계 매개변수 회귀 검사 작성. 단계별 False 및 복합 실패, 종가 None/False, 앞 세 단계 None의 기존 성공 호환, 예외/알림 예외, finally 상태 초기화를 검사.
```python
# 각 경계만 대역 처리하고 실제 run_daily_closing_analysis 실행
assert "장 마감 정기 분석 및 종가베팅 완료" not in caplog.text
assert "부분 실패" in caplog.text
# 단순 실패 분기에도 네 단계 실행; 종가 성공이면 기존대로 알림 호출
```
- [x] targeted pytest로 RED 확인. 잘못된 기대값/하네스 오류와 제품 결함 구분.
- [x] 기존 chaining 안내의 '데이터 수집 완료'를 '데이터 수집·VCP 단계 처리 후'로 정정. 알림 완료 문구에서 전체 완료 의미 제거.
- [x] 네 단계 결과를 목록으로 합산. 앞 세 단계는 기존대로 `is False`, jongga는 기존 truthiness 유지. 알림 처리 후 부분 실패/전체 성공을 구분.
```python
failed_steps = [name for name, failed in (
    ("일별 주가", prices_ok is False), ("기관/외인 수급", inst_ok is False),
    ("VCP", vcp_ok is False), ("종가베팅", not jongga_ok),
) if failed]
if failed_steps:
    logger.error("[Scheduler] 장 마감 정기 분석 부분 실패: %s", ", ".join(failed_steps))
else:
    logger.info("<<< [Scheduler] 장 마감 정기 분석 및 종가베팅 완료")
```
- [x] targeted GREEN 및 독립 리뷰 지적 반영. 알림 전달 성공 여부 자체는 기존 계약이며 이번에 확대하지 않음.

## Task 3: 검증 및 완료
- [x] pytest 전체, Vitest 전체(실제 build 포함), type-check, lint, diff check. .env 추적/NEXT_PUBLIC/로그·응답·번들 비밀 노출 확인.
- [x] QA 행렬 확정: 019 데스크톱/모바일 랜딩 문구와 인접 탭, 실제 scheduler 등록 기본/사용자설정/폐지값 무효. 029 정상/각단계실패/복합실패/예외/재실행/상태정리. 별도 subprocess 하네스와 실제 agent-browser 사용.
- [ ] 검증 통과 구현·행렬 첫 커밋, TODO 유지. 기준 SHA에 대해 UltraQA 실행.
- [ ] 브라우저 DOM/PNG 실제 열람/console/errors/Next MCP 및 하네스 로그 증거. 예상 실패 입력과 전체 프로세스 exit를 구별.
- [ ] 소유 서버/브라우저/fixture/clone 정리 및 원본 package 해시 확인. FF 통합 후 각 ID QA/일별/월별 기록, 최종 아카이브 커밋에서만 TODO 제거.
