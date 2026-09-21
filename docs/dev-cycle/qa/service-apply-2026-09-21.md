# 기존 서비스 업그레이드 적용 QA

- 범위: INFRA-070/018 검증 완료 버전을 기존 venv/frontend node_modules에 적용, 기존 포트 기동.
- 사용자 명시 요청: 기존 실행 서비스 적용 및 검증 테스트 진행.
- engine: ultraqa; lifecycle: app-adapted; iteration: 1; phase: complete
- 기준: cb9fb4c; browser_driver: ego-browser; browser_applicability: required
- 시작 관측: 3500/5501 listener 없음. 기존 root package.json은 사용자 파일로 보존.
- 설정 파일은 해시만 비교하고 값은 출력하지 않는다. 원본 데이터 삭제/수정, AI 호출, 알림, 거래, 설정 저장은 QA에서 수행하지 않는다.
- 기존 승인 범위의 배포 후 검증이며 새 제품 구현 라운드가 아니다.

| ID | 의도/모델 | setup/실행 | 기대 | 실제 | 수정/증거/cleanup |
|---|---|---|---|---|---|
| A1 | 정상 설치 | 기존 venv pip, frontend npm ci | 목표 버전·pip check 통과 | PASS: 목표 버전 일치·pip check 0 | evidence/service-apply-20260921 |
| A2 | 쿠키 경계·NumPy | 실제 설치 패키지+합성 외부 transport 회귀 | 외부 요청 0·테스트 통과 | PASS: pytest 6/6, 실제 transport probe 3/3 | 임시 fixture 정리 |
| A3 | 실제 서비스 | 원래 포트 Gunicorn/Next 기동 | API JSON 및 대시보드 200 | PASS: backend/frontend API 200·대시보드 200 | 서비스는 요청 결과로 유지 |
| A4 | 잘못된 날짜·익명 접근 | GET invalid date/admin/auth | 400/403, JSON, 미처리 오류 없음 | PASS: invalid date 400·anonymous env 403·session 200, 모두 JSON | 무쓰기 요청만 |
| A5 | 브라우저 | ego-browser 실제 대시보드·탭 조회 | 화면 렌더·JSON 구문 오류 없음 | PASS: 화면 3개·콘솔/JS 오류0·컴파일 이슈0 | 소유 taskspace 종료 |
| A6 | 보존·정리 | 설정/root package 해시·git diff | 사용자 파일 보존 | PASS: 설정/root 사용자 파일 총9개 해시 일치 | 임시 파일 제거 |

중단/재시도는 최대5회, 동일 실패3회. 기존 서비스 운영에서 정상 스케줄러 동작은 복구하되 수동 분석/발송을 호출하지 않는다. Prompt injection·취소 상태 변조는 본 배포 작업에 해당 없음. 전체 격리 QA는 기존 보고서 참고, 이번에는 실제 설치와 기동 및 조회 경로를 재검증한다.

## 실행 결과와 증거

- `pip install -r requirements.txt`: exit0, 기존 venv NumPy2.4.6/pykrx1.2.9+cookie.1 적용.
- frontend `npm ci`: exit0, Next16.3.5/React19.2.8/NextAuth4.24.15/Vitest4.1.11 적용.
- `pip check`: exit0. 기존 실행 환경에서 회귀 pytest6 passed(18초), 합성 transport probe3개 exit0. 외부 API 전송은 probe에서 차단했다.
- Vitest84 files/641 tests passed(5.87초), type-check exit0.
- 이번에는 원래 실행 환경의 기동·조회 검증을 수행했다. 전체 Python2464/3skip 및 production build는 기존 격리 QA 결과이며 이번에 재실행했다고 주장하지 않는다.
- HTTP6개 검사: backend와 Next proxy market-gate200, invalid date400, 익명 env403, 익명 session200, 실제 dashboard200. JSON 경로5개 모두 파싱 성공.
- 실제 브라우저 조회: Overview score70/Bullish; VCP 오늘 결과 없음·최신2026-05-05 안내; 종가베팅 후보18·최신2026-09-09 안내와 저장 카드 표시.
- Overview → VCP → 종가베팅 실제 링크 클릭. browser.json의 조회 요청은 전부200. 페이지 예외/unhandled rejection/console.error 수집0. Next MCP configErrors/sessionErrors/compilation issues 모두 빈 배열.
- overview.png/vcp.png/closing-bet.png를 직접 열어 표시와 레이아웃 확인. 과거자료 경고는 현재 저장 자료의 상태이며 신규 데이터 생성 성공을 의미하지 않는다.
- 기존 실행 listener가 없었으므로 중지할 프로세스는 없었다. 기존 restart_all의 광범위 종료·로그 덮어쓰기·lock 삭제를 사용하지 않고 기존 기동 명령으로 시작했다. 로그는 append했다.
- Gunicorn master77981, worker2개, frontend launcher77982. 5501 loopback 및3500 listener 유지. 서비스는 사용자 요청 결과이므로 종료하지 않는다.
- `.env` 내용/키/사용자 자료를 증거로 복사하지 않았다. 설정과 root package.json 해시 일치. 서비스 정상 기동 자체의 실행상태 초기화와 기존 설정에 따른 스케줄러 작업은 정상 운영 범위이며 data 무변경을 주장하지 않는다.
- 수동 AI 분석·알림·매매·설정 저장·삭제는 실행하지 않았다. 실계정 로그인과 실KRX인증 호출은 미검증이며 합성 transport 회귀와 구분한다. 공개 도메인 원격 배포는 수행하지 않았다.
- 제품 소스 변경 없음. 새 TODO를 만들지 않은 기존 승인 업그레이드의 실행 적용 후속 작업이다.
- Native OMX runtime 대신 App 대응으로 실행, 숨은 상태 쓰기 없음. 브라우저 space26은 finish keep[]로1회 정리했다. 임시 해시 manifest는 비교 후 제거했다.

## 판정

ULTRAQA COMPLETE: Goal met after 1 cycle. 적용 후 조회 검증6/6 통과. 원본 서비스는 업그레이드 버전으로 실행 유지.
