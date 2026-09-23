# [INFRA-081] 활동 로그 밖의 로그 세 개가 0644 로 남는다 — QA 시나리오

- 대상: 격리 사본에서 실제 `restart_all.sh`·`stop_all.sh` 실행(backend 58121, frontend 58120), 화면 http://localhost:58120/privacy
- 구성 근거: `[INFRA-081]` 설계 승인(2026-09-23 23:43, `restart_all.sh` 가 `logs/` 를 0700 으로 좁힘, 방침 10항 「로그 파일과 데이터베이스 파일은」) + 코드 리뷰 F4(chmod 실패 시 ❌ 안내)
- 구성 2026-09-23 23:47 | 실행 2026-09-23 23:49 (1회차)
- 검증 기준 커밋: `122a74c` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 사본의 `restart_all.sh` 가 작업 트리와 같음을 실행 전 `diff` 로 확인했다. 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름은 운영자의 `./restart_all.sh` 실행과 이용자의 방침 페이지 열람 둘이다. 방침 문구가 화면에 보이므로 브라우저 실측을 필수로 둔다. 하네스:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/`·`venv`·`frontend/node_modules` 를 APFS clone 으로 둔다. `.env` 계열은 두지 않고, 사본의 `secrets/` 는 만들자마자 지운다.
  `env -i` 로 `FLASK_PORT=58121 FRONTEND_PORT=58120 SCHEDULER_ENABLED=false API_URL=http://127.0.0.1:58121` 와 더미 `NEXTAUTH_*`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 를 주고 사본의 `./restart_all.sh` 를 실행한다(NEXT_MODE 미설정 → dev).
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 LLM·발송·저장 조작은 하지 않는다. 브라우저는 gstack `browse`, 익명 사용자
- 기대값 출처: 설계 승인 범위와 `frontend/src/app/(legal)/privacy/page.tsx` 의 새 문구
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 하네스 실수 둘은 판정 전에 바로잡았다: (가) `env -i` 의 PATH 에 npm 이 없어 첫 실행이 의존성 단계에서 exit 1(그 전에 chmod 는 실행되어 `logs` 700). PATH 에 `/opt/homebrew/bin:/usr/local/bin` 을 넣어 `logs` 를 755 로 되돌린 뒤 S-1 을 다시 실행했다. (나) zsh 가 환경 변수 묶음 `$E` 를 나누지 않아 S-4·S-3 첫 시도가 exit 127(아무것도 실행되지 않음). 그 사이 S-3 준비의 `chmod 755 logs` 가 먼저 돌았으므로 S-1 직후 상태인 700 으로 되돌리고 `${=E}` 로 다시 실행했다
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄(명령 출력 원문) · 스크린샷 `docs/dev-cycle/evidence/INFRA-081/infra081-s2.png`(전체 페이지)·`infra081-s2-section10.png`(10항 목록, 열어서 새 문구 확인)
- 정리(cleanup): 사본의 서비스는 S-4 의 `stop_all.sh` 로 종료(리스너 0, `pgrep -fl infra081` 0건), S-3 의 불변 플래그 해제(`chflags nouchg`, 플래그 `-`), browse 서버 정지, 사본 삭제. 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. 이미 있는 0755 `logs/` 를 기동 때 0700 으로 좁힌다 (결함 재현)
- 조작: 사본에 `logs/` 를 0755 로, 그 안에 `backend.log` 를 0644 로 미리 만든 뒤 `./restart_all.sh` 를 실행한다.
- 기대: exit 0, 「🎉 Ready!」, `stat -f %Lp logs` 가 `700`. 58121 `/api/kr/market-gate`·58120 `/` 가 200.
- 필수 여부(required): 예
- 실제: 23:49:48 실행 전 `logs 755`·`logs/backend.log 644` → 23:49:58 exit 0, 「✅ 프론트엔드 의존성 변경 없음」·「🎉 Ready!」(backend PID 50718, frontend PID 50837), 실행 뒤 `logs 700`(파일 `backend.log` 는 644 그대로, 디렉터리가 막는 설계), `backend 200`, `frontend 200`
- 결과: 통과

### S-2. 방침 페이지에 넓힌 문구가 보인다 (문구 변경)
- 조작: browse 로 http://localhost:58120/privacy 를 열어 10항 본문을 읽는다.
- 기대: 「로그 파일과 데이터베이스 파일은 서버를 실행하는 계정만 읽고 쓸 수 있도록」이 있고 「활동 로그와 데이터베이스 파일은」은 없다. 콘솔 오류 없음.
- 필수 여부(required): 예
- 실제: `/privacy` 200. 첫 판정 `body.innerText` 기준 `newText:false` 는 첫 스크린샷에 보인 「로딩 중…」 오버레이가 덮은 시점이었다. 오버레이가 사라진 뒤 `innerText` 공백 정규화 → `true`, `textContent` 공백 정규화 → `{"newText":true,"oldText":false}`. 10항 목록의 항목 원문: 「… 서버에 로그인할 수 있는 사람을 운영자로 제한합니다. 로그 파일과 데이터베이스 파일은 서버를 실행하는 계정만 읽고 쓸 수 있도록 파일 권한을 제한합니다.」 `console --errors` → `(no console errors)`
- 결과: 통과

### S-3. 좁힐 수 없는 `logs/` 면 아무것도 기동하지 않고 거부한다 (적대적)
- 조작: S-4 로 서비스를 내린 뒤 `chmod 755 logs && chflags uchg logs` 로 모드를 바꿀 수 없게 만들고 `./restart_all.sh` 를 실행한다. 끝나면 `chflags nouchg logs` 로 푼다. 다른 계정 소유 디렉터리는 sudo 가 필요해서 불변 플래그로 같은 EPERM 을 만든다. 사전 실험(scratchpad): 불변 디렉터리에서 `chmod 700` 은 「Operation not permitted」 exit 1 이고, 이미 있는 잠금 파일 `exec 9>` 는 열린다. 그래서 잠금 단계가 아니라 chmod 단계에서 거부된다.
- 기대: exit 1, stderr 에 「❌ logs/ 권한을 0700 으로 좁히지 못했습니다.」, 「🎉 Ready!」 없음, 58120·58121 리스너 없음.
- 필수 여부(required): 예
- 실제: 23:51:01 `logs 755 uchg` → exit 1, stderr 「chmod: Unable to change file mode on logs: Operation not permitted」·「❌ logs/ 권한을 0700 으로 좁히지 못했습니다.」, stdout 비어 있음(`ready-count=0`), 리스너 없음. 해제 뒤 `logs 755 -`
- 결과: 통과

### S-4. 종료 뒤에도 권한이 되돌아가지 않는다 (인접)
- 조작: S-1·S-2 뒤 사본의 `./stop_all.sh` 를 같은 환경 변수로 실행한다.
- 기대: exit 0, 두 포트 리스너 없음, `logs/` 는 여전히 `700`.
- 필수 여부(required): 예
- 실제: 23:50:58 `logs=700` → exit 0, 「🛑 frontend PID 50837 를 정상 종료합니다...」·「🛑 backend PID 50718 를 정상 종료합니다...」·「✅ 이 프로젝트가 관리하던 서비스가 종료되었습니다.」, 리스너 없음, `logs 700`
- 결과: 통과

## 실행 결과

- 1회차(2026-09-23 23:49, 기준 `122a74c`): 필수 4/4 통과
- 이월한 발견: `[INFRA-085]`(코드 리뷰 F1)
