# [INFRA-085] restart 를 거치지 않는 기동에서 `logs/` 가 0755 로 생긴다 — QA 시나리오

- 대상: 격리 사본에서 `restart_all.sh` 를 거치지 않고 gunicorn(backend 58121)과 `npm run dev`(frontend 58120)를 직접 띄운 뒤, http://localhost:58120/dashboard/kr 에서 활동 로그를 남기는 요청 `POST /api/system/log-event`
- 구성 근거: `[INFRA-085]` 설계 승인(2026-09-24 00:12, `ActivityLogger` 의 `os.makedirs(log_dir, mode=0o700, exist_ok=True)`, 기존 디렉터리는 건드리지 않음)
- 구성 2026-09-24 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code. 사용자 진입 흐름은 운영자가 `restart_all.sh` 없이 서버를 띄우는 것과, 방문자의 화면 요청이 활동 로그를 남기는 것 둘이다. 활동 로그는 GET 을 기록하지 않으므로(`app/__init__.py:192`) 대시보드 페이지 안에서 `/api/system/log-event` 로 무해한 이벤트 한 건을 보낸다(사본의 로그 파일에만 쓰인다). 하네스:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/`·`venv`·`frontend/node_modules` 를 APFS clone 으로 둔다. 사본에는 `logs/` 가 없다(추적되지 않음). `.env` 계열은 두지 않고, 사본의 `secrets/` 는 만들자마자 지운다.
  `env -i` 로 `SCHEDULER_ENABLED=false` 와 더미 `NEXTAUTH_*`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 를 준다. backend 는 `venv/bin/gunicorn flask_app:app --bind 127.0.0.1:58121 --workers 2 --threads 8 --keep-alive 0`, frontend 는 `API_URL=http://127.0.0.1:58121 PORT=58120 npm run dev`. 두 출력은 사본 밖 scratchpad 파일로 보낸다(`logs/` 를 만들지 않기 위해). umask 는 022.
  원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고 LLM·발송·저장 조작은 하지 않는다. 브라우저는 gstack `browse`, 익명 사용자
- 기대값 출처: 설계 승인 범위, `restart_all.sh:73` 의 같은 0700 규칙
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 필수 여부(required): 예
- 결과: (미실행)

## 시나리오

### S-1. 직접 기동한 backend 가 없는 `logs/` 를 0700 으로 만든다 (결함 재현)
- 조작: `logs/` 가 없는 사본에서 gunicorn 을 직접 띄우고 `curl -X POST http://127.0.0.1:58121/api/system/log-event -d '{"action":"QA_INFRA_085_S1"}'` 를 보낸다.
- 기대: 응답 200 `{"status":"ok"}`, `stat -f %Lp logs` 가 `700`, `logs/user_activity.log` 가 `600` 이고 `QA_INFRA_085_S1` 을 담는다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 화면에서 보낸 요청도 같은 `logs/` 에 기록되고 권한이 유지된다 (브라우저)
- 조작: frontend 를 직접 띄우고 browse 로 /dashboard/kr 를 연다. 로딩이 끝난 뒤 같은 페이지에서 `fetch('/api/system/log-event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'QA_INFRA_085_S2'})})` 를 실행하고 콘솔 오류를 읽는다.
- 기대: 페이지 200, fetch 200, `logs/` 가 여전히 `700`, 활동 로그에 `QA_INFRA_085_S2`, 콘솔 오류 없음.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 이미 있는 0755 `logs/` 는 좁히지 않는다 (경계)
- 조작: 서비스를 내리고 `logs/` 를 지운 뒤 `mkdir -m 755 logs` 로 다시 만들고 gunicorn 만 띄워 S-1 의 요청(`QA_INFRA_085_S3`)을 보낸다.
- 기대: 200, `logs/` 는 `755` 그대로(좁히기는 `restart_all.sh` 몫이라는 승인 범위), 활동 로그 파일은 `600`.
- 필수 여부(required): 예
- 실제:
- 결과:

## 실행 결과

- (미실행)
