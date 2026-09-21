# 승인 범위 및 실행 경계

2026-09-21 사용자 「승인」은 직전 bounded 설계 JONGGA-033·018 두 건에 대한 승인이다.
재무 기간은 확인된 원본 기간만 전달하고 EPS 미확인은 표시한다. 음수 PER 설명을 보완한다.
기존 보너스 계산은 최대7이며 변경하지 않는다. 초과 저장값과 총점은 유지하고 현재 기준과 구분한다.
예상 제품 변경은 상세 payload와 closing-bet 표시 및 작은 helper, 300줄 이내. 위험 경로는 변경하지 않는 T2.
TODO018의 종전 T3 근거는 scorer 수정이었으나 승인된 이번 범위에는 해당하지 않는다. 구현 후 재판정한다.
brainstorming bounded 승인 → TDD → ponytail → code-review/architect → 전체 검증 → UltraQA App 대응/ego-browser → 마감.
원본 package.json 보존, .env/data 읽기·쓰기 및 원본3500/5501/live 접속 금지. 실행은 기록된 scratch에서만.
새 종속성 없음. Next 번들 server-and-client-components 문서 읽음. useEffect/서버경계 변경 없음.
명령별120~300초, 리뷰 각10분, QA 각5분, 같은실패3회/QA5회 제한. 전체 작업은 체크포인트로 재개 가능.
