# [FLOW-019] 세 화면의 모집단 규칙을 맞추고 화면에 적는다 — QA 시나리오

- 대상 화면: http://localhost:3719/dashboard/kr/cumulative, http://localhost:3719/dashboard/kr/closing-bet, http://localhost:3719/dashboard/kr (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5719
- 구성 근거: `[FLOW-019]` 의 QA 줄 + 설계 승인(현행 모집단 유지·문구 명시, 30개 상한 유지·카드 표시) + 리뷰 지적 1·2·4. 기대값은
  격리 Flask 의 GET 응답에서 읽었다: `/api/kr/closing-bet/cumulative?limit=1` 의 `counts`·`kpi.roiByGrade`·`kpi.totalSignals`,
  `/api/kr/backtest-summary` 의 `closing_bet`, `/api/kr/jongga-v2/dates`, `/api/kr/jongga-v2/history/<날짜>` 의 등급 분포.
  1단계 리포트 도구 대신 이 응답과 TODO 의 QA 줄에서 시나리오를 만들었다(`[FLOW-017]` 과 같은 방식)
- 구성 2026-09-23 | 실행: (공란)
- 검증 기준 커밋: (첫 커밋 후 기입)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다.
  저장소 작업 트리를 scratchpad `qa-flow019/` 로 복사(`.env*`·`.git`·`venv`·`logs` 제외, `frontend/node_modules` 는
  APFS clone)하고, 더미 값(`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`,
  `ADMIN_EMAILS=qa-admin@example.com`, `SCHEDULER_ENABLED=false`)만 환경 변수로 준다. 세 화면 모두 조회만 하며
  종가베팅 화면의 일괄 매수·업데이트·재분석 버튼은 누르지 않는다
- 단계(phase): 시나리오 구성 완료 | 실행 (공란)
- 반복(iteration): 0회
- 결과: (공란)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 세 화면을 열어 건수·승률과 그 기준 문구를 읽는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-nextjs/SKILL.md`,
  `.claude/skills/closing-bet-verify/SKILL.md`, `frontend-skills.md` §2, Next 번들 문서 `05-server-and-client-components.md`
- 기대값 원천(격리 사본 `data/` 기준): counts `total 234`, 등급 `S 19·A 34·B 174·D 7`, `other 0`, 결과 `WIN 86·LOSS 140·OPEN 8`.
  요약 `closing_bet` `count 234`, `win_rate 38.1`, `status BAD`. 결과 파일 18개(30개 미만이라 요약과 누적성과의 모집단이 같다).
  날짜별 등급: 2026-02-11 `D5·B3·S1`(9), 2026-02-12 `B5·D2·S1`(8), 2026-09-21 `B7·S1`(8)

## 시나리오

### S-1. 누적성과가 모집단 기준을 적고 등급 합이 누적 추천수와 맞는다
- 조작: `/dashboard/kr/cumulative` 를 열어 등급 카드 아래 문구와 등급 칩, 누적 추천수를 읽는다.
- 기대: 문구 「전체 결과 파일에서 진입가가 있는 시그널을 셉니다. D(현행 기준 미달 또는 과거 등급)도 통계에 포함합니다(종가베팅 화면은 D 를 매수 목록에서 뺍니다).」.
  「등급 집합 밖의 거래」 줄은 없다(`other 0`). 칩 `S (19)`·`A (34)`·`B (174)`·`D (7)` 합 234 = `전체 (234)` = 누적 추천수 234. 승률 38.1%.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-2. 대시보드 종가베팅 카드가 30개 상한과 D 포함을 적는다
- 조작: `/dashboard/kr` 를 열어 종가베팅 전략 카드를 읽는다.
- 기대: 승률 `38.1`%, `234 trades`, 문구 「최근 결과 파일 30개(분석한 날) 기준 · D 포함」. 누적성과의 234건·38.1% 와 같다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-3. 종가베팅 화면이 D 를 뺀 수를 알린다 (2026-02-11)
- 조작: `/dashboard/kr/closing-bet` 에서 날짜 2026-02-11 을 고르고 목록과 안내를 읽는다.
- 기대: 안내 「D등급(현행 기준 미달 또는 과거 등급) 5종목은 매수 대상이 아니어서 목록에서 제외했습니다. 누적성과 통계에는 포함됩니다.」,
  종목 카드 4개(B3·S1), 카드에 D 등급 없음.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-4. D 가 없는 날짜에는 안내가 없다 (인접)
- 조작: 날짜 2026-02-12 로 바꿔 안내가 `2종목` 으로 바뀌는지 본 뒤 2026-09-21 로 바꾼다.
- 기대: 2026-02-12 는 「… 2종목은 …」과 카드 6개. 2026-09-21 은 안내 없음, 카드 8개.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음

### S-5. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-4 를 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와 `get_compilation_issues` 를 보낸다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용이라 이 시나리오가 소유한 자료 없음
