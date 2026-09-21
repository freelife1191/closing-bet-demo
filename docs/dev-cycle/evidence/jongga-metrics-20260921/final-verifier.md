# 독립 완료 증거 검수

- 검수일: 2026-09-21
- 판정: **PASS (범위 한정)**
- 검수 범위: `docs/dev-cycle/qa/batch-jongga-metrics-2026-09-21.md`와
  `docs/dev-cycle/evidence/jongga-metrics-20260921/`의 보존 증거만 읽음.
- 제품 소스, 원본 `.env`/`data`, 원본 3500/5501/live, 네트워크, LLM·수집·거래·설정·삭제 동작은 접근하지 않음. 테스트·서버 재실행도 하지 않음.

## PASS 근거

1. 최종 pytest JSON/압축 로그가 동일하게 `exit_code: 0`, `2452 passed, 3 skipped`를 기록한다. skip은 수동 Gemini 2건과 `.env` 부재 1건으로 명시되어 있다.
2. 최종 Vitest JSON/압축 로그가 `exit_code: 0`, `83 files passed`, `640 passed`를 기록한다.
3. typecheck와 lint는 각각 exit 0이다. lint의 `184 warnings`는 보고서에 숨겨지지 않았고 errors는 0이다.
4. build 로그는 애플리케이션 빌드, 필수 route, TypeScript 검사 3개를 모두 통과했다고 기록하며 exit 0이다.
5. Next 진단 JSON은 `issues: []`, `configErrors: []`, `sessionErrors: []`이다.
6. Q1~Q7 필수 시나리오가 보고서에서 7/7 통과로 정리되어 있고, `ego-known/legacy/invalid`, detail 3종, recovery error/known PNG를 직접 열람해 값·기간 표기·음수 PER 설명·legacy bonus·오류 복구 화면이 기록된 JSON과 일치함을 확인했다.
7. `request-audit.json`은 금지 mutation 0, 원본 서비스 요청 0, 최종 행렬 예상 외 오류 0을 기록한다. 준비 단계 ConnectionRefused 9건과 의도된 detail 503 3건은 별도로 분류되어 있다.
8. `cleanup.json`, 각 `*-stop-*.json`, `ego-finish.json`이 scratch 제거, 소유 포트 57950/57951/57952 종료, managed browser space 종료를 기록한다. `source-verification.json`은 6개 동결 파일의 scratch/root 일치와 root package 보존을 기록한다.

## 한정 및 누락

- 이 검수는 보존된 실행 증거의 독립 대조이며 새 실행 검증이 아니다.
- PNG는 모두 1440×1100 데스크톱 캡처다. 보고서도 전체 앱·모바일 디자인 검사가 아님을 명시한다. 따라서 모바일/반응형 완료까지 주장할 근거는 없다.
- `provenance.md`와 보고서가 실제 공급자 회계기간 및 특정 종목 EPS/순이익 부호 원인을 미확정으로 명시한다. 합성 provider 검증이므로 실데이터 기준기간 확정으로 확대 해석하면 안 된다.
- pytest의 3 skip은 실패가 아니지만, 수동 Gemini와 `.env` 의존 검증은 실행되지 않았다는 제한을 유지한다.
- lint warning 184건은 0 error와 별개로 남아 있다.
- 초기 QA의 gateway 준비 실패 9건과 observer 실패 1건은 `qa-failures.md`에 보존되고, 후속 cycle에서 복구된 기록이 있다. 이를 최종 성공에서 소급 삭제한 흔적은 없다.

## 결론

승인된 JONGGA-033·018 범위의 완료 증거는 PASS다. 위 한정(데스크톱 한정, 실제 공급자 회계기간 미확정, 3 skip, lint warnings)을 완료 범위에 붙여 기록해야 하며, 이 한정 때문에 BLOCK할 증거 모순은 발견되지 않았다.
