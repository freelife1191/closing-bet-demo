# 테스트 격리 묶음: FE-042 · INFRA-035

- 기준 c24d9c7, T2 (테스트 전용 변경 합산 50~300줄, 위험 제품 경로 변경 없음).
- 실제 대화 근거: 사용자의 2026-09-09 「연관된 라운드들 쭉 이어서 진행」「최대한 한번에 묶어서」 요청과 AGENTS AUTO-CONTINUE. 제한된 테스트 개선 설계를 대화로 제시하고 진행. 별도의 승인 응답/시각을 만들지 않음.
- FE-042: 기본 Vitest 안의 빌드 2회/tsc를 별도 npm run test:build로 이동. 빌드 1회 결과로 기존 성공/라우트 검증 유지, TypeScript 별도 실행. 기본 출력의 허위 빌드 성공 표시 제거.
- INFRA-035: 공통 helper는 이미 임시 디렉터리를 쓰고 AutoClosingSQLiteConnection이 with 종료시 닫음. 남은 직접 생성 5개만 tmp_path로 변경; 자신이 만든 DB/WAL/SHM 정리. 원본 data에 쌓인 자료 삭제는 범위 제외, TODO에 미결 상태로 유지.
- 원본 package.json 보존. .env/원본 data 복사 안 함. 원본3500/5501 및 라이브 접근·재시작 없음. 외부 네트워크 차단, 원본 repo 쓰기 차단 scratch에서 검사. OMX state 조작 없음.
- brainstorming bounded / frontend 스킬 매핑 / 설치 Next 번들 testing/vitest.md 확인. UI·API·저장 스키마 변경 없어 browser_applicability=not-applicable, browser_driver=none. 검증 CLI가 실제 대상.
- 각 리뷰 5분, 전체 실행 30분, 명령별 60~300초. 같은 QA실패3회/최대5cycle.
- 최근 완료 FE-038,CHAT-005,INFRA-021. 시작 TODO49(P1 11/P2 38), 사용자 package.json만 untracked. 배포 정책 INFRA045/046 정보대기, 이전 완료와 동일 ID 다른 제목 QA는 재개로 간주하지 않음.
- 변경 전 재현: 기존 should successfully build the application + 별도 npm build 동시 실행 → Another next build process is already running, 스모크 exit1/빌드exit0. 과거 09-08 실패와 동일 원인이라고 소급 단정하지 않음.

- 정적 결과: pytest2279passed/3skip(기존수동2 + 비밀없는격리 .env대조1), Vitest459passed/67files(기존3개는별도Node검증으로이동), Node빌드검증3passed/0skip, tsc0, lint0error194warning, PythonAST/Node문법검사 통과. Python전용LSP는확인되지않아성공주장하지않음.

- 최초 tests/build/ 경로는 저장소 build/ ignore 규칙에 걸려, 소스 누락 방지를 위해 tests/build-checks/로 이름만 변경. Node 파일 내용은 동일, package.json 호출 경로만 갱신. 변경 후 리뷰 입력 해시 갱신 및 독립 리뷰에 전달.

- 원문 실행 로그는 손실 없이 .log.gz로 압축 보존한다. 리뷰의 .log 참조는 같은 이름 .log.gz의 원문을 뜻한다. 최종 리뷰 SHIP/APPROVE/CLEAR, 초기ignore BLOCK 수정 원문 보존.
