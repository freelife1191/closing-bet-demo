# UltraQA Report — JONGGA-014

- engine: ultraqa | lifecycle: app-adapted | phase: blocked | iteration: 1 | same_failure_count: 0
- 목표: Phase1 단일 실행/원래 TypeError 전파 및 실제 종가 화면의 실행/결과 흐름 보존.
- baseline: pytest2260통과/2skip, Vitest424통과, typecheck0. 검토 SHA는 ../evidence/batch-2026-09-09/review-input.json.
- browser_applicability: required | browser_driver: agent-browser
- 호출부: closing-bet/page.tsx runUpdate→POST /api/kr/jongga-v2/run→generator_runtime_mixin→SignalGenerationPipeline.
- 대상: 격리 http://127.0.0.1:57361/dashboard/kr/closing-bet (시작 전 소유권 검증).
- namespace/session: closing-batch-20260909 / qa
- UltraQA Report: [JONGGA-014.md](JONGGA-014.md)
- 안전: 합성 Phase와 HTTP 경계, 실제 pipeline/Next UI. 원본 data/.env/3500/5501/live 및 LLM·발송·거래 금지.
- 상한: 명령60초, QA5회/동일실패3회. native 상태 변경 없음.

| ID | 의도/모델 | Setup/command | 기대 | 실제 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| S-1 | 정상·날짜전달 | 실제 pipeline의 pytest/합성Phase | phase1→2→3→4 1회씩, 날짜 보존 | 통과 | 단일호출 | ../evidence/batch-2026-09-09/pipeline-probe.json | 완료 | 예 |
| S-2 | 내부오류·반복시도 | 실제 pipeline TypeError | 같은 예외1회, 후속Phase0 | 통과 | 단일호출 | ../evidence/batch-2026-09-09/pipeline-probe.json | 완료 | 예 |
| S-3 | 사용자 실행·실패복구 | 실제 종가UI 실행/확인모달/상태조회, 합성서버 | 정상결과표시, 실패도 성공으로 만들지 않음 | 실패: 정상200 뒤버튼잠김, TypeError500은성공으로표시안함 | 추가범위 사용자선택대기 | ../evidence/batch-2026-09-09/jongga-ui-baseline-failure.json | 공유검사후정리완료 | 예 |
| S-4 | 격리·오인성공 | package SHA, 요청/오류로그, 소유PID정리 | 원본불변, 외부효과0, 프로세스종료 | 통과 | 없음 | ../evidence/vcp-integrity-20260909/cleanup.json | 완료 | 예 |

새 JSON/문자열 입력 경계 없음. prompt injection 문구는 실행하지 않는다. 기존 빈결과·기본날짜도 회귀검사로 확인.
필수 통과3/4. S-3 정상완료버튼잠김 실패. 구현완료와 QA완료를 구분한다.

JONGGA-037은 기존UI결함으로 분리했지만 현재 필수S-3 실패를 통과로바꾸지 않는다. 해당수정 추가승인 전 JONGGA-014 완료아카이브 금지.

ULTRAQA BLOCKED: JONGGA-037 기존 UI 완료상태 수정의 추가 범위 승인 대기. 모든소유프로세스/임시자료정리완료. 재개시 S-3부터, iteration1을이어간다.
