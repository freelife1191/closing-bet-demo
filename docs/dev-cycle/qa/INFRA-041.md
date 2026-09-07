# [INFRA-041] QA 시나리오

`GET /api/admin/check` 의 관리자 판정 근거를 요청자가 정한 `?email=` 에서 서명으로 확정한
`g.user_email` 로 옮긴 변경의 검사 목록입니다.

## 대상과 범위

바꾼 자리는 셋입니다.

- `app/routes/common_admin_routes.py` — `request.args.get("email")` 을 `g.get("user_email")`
  로 바꾸고, `is_admin_email(None)` 이 이미 `False` 를 돌려주므로 400 분기를 지웠습니다.
- `frontend/src/hooks/useAdmin.ts` — 요청 URL 에서 `?email=` 을 지우고 `cache: 'no-store'`
  를 지정했습니다.
- `tests/app/test_common_routes_refactor.py` — 기존 검사의 판정 출처를 옮기고,
  `test_admin_check_ignores_email_query_parameter` 를 더했습니다.

권한 상승 결함은 아니었습니다. 실제 권한 게이트는 Next 쪽
`frontend/src/app/api/system/env/route.ts` 의 `resolveAdminToken` 이고 그것은 NextAuth
세션을 봅니다. 이 라운드가 닫는 것은 두 가지입니다. 누구든 이메일을 하나씩 넣어
`ADMIN_EMAILS` 에 누가 있는지 확인할 수 있던 오라클과, 브라우저 쪽 관리자 UI 게이트입니다.

## 실행 전 반드시 알아야 할 것

**판정 근거가 URL 에서 헤더로 옮겨지면서 캐시 성질이 함께 바뀌었습니다.** 종전에는 URL 이
`?email=` 로 갈려 어떤 HTTP 캐시도 사용자마다 키를 나눴습니다. 이제 URL 은 모두에게 같고
본문만 신원에 따라 다르므로, 앞단에 공유 캐시가 놓이면 관리자의 `true` 응답이 다른 사람에게
재사용됩니다. 보안 리뷰가 이것을 잡아 라우트 응답에 `Cache-Control: no-store` 를 붙였고
S-12 가 그 자리를 고정합니다. `frontend/src/app/api/system/env/route.ts:55-59` 가 같은
이유로 같은 조치를 이미 하고 있습니다.

**막는 것만 확인하면 통과 판정이 무의미합니다.** 「신원과 무관하게 언제나 false」를
돌려주는 코드도 S-1·S-2·S-5 를 통과합니다. 그래서 S-3 과 S-6 이 신원이 있을 때 `true` 가
나오는 것을 함께 잽니다. 두 방향이 함께 맞아야 이 변경이 옳습니다.

**세션 쿠키 없이는 신원 있는 경우를 실측할 수 없습니다.** 관리자 계정으로 로그인하지
않으므로, `NEXTAUTH_SECRET` 으로 서명한 QA 전용 세션 토큰을 만들어 씁니다. **비밀과 관리자
이메일은 셸 변수로만 넘기고 어디에도 출력하지 않습니다.**

**토큰 유효기간을 넉넉히 잡습니다.** `[INFRA-040]` 사이클에서 `maxAge: 300` 토큰이 실측
도중 만료되어, 결과가 통째로 달라진 것을 코드 결함으로 오판할 뻔했습니다. 30분으로 잡고,
여러 경우가 한꺼번에 달라지면 코드보다 토큰을 먼저 의심합니다.

**이 엔드포인트는 상태를 바꾸지 않습니다.** `GET /api/admin/check` 는 환경 변수를 읽어
비교할 뿐이라 몇 번을 불러도 서버 상태가 그대로입니다. `[INFRA-040]` 처럼 존재하지 않는
경로를 쓸 필요가 없습니다.

**실측 전에 Flask 를 재기동합니다.** Next 개발 서버는 `useAdmin.ts` 변경을 자동으로 다시
컴파일하지만 Flask 는 그렇지 않습니다. 재기동 전에 `?email=` 없이 부르면 옛 코드가
`400 Email required` 를 돌려주므로, 그 응답이 보이면 재기동이 아직 안 된 것입니다.

**비용이 들거나 되돌릴 수 없는 조작은 하지 않습니다.** 알림 테스트 발송, 재분석, 모의투자
주문, Market Gate 갱신을 실행하지 않습니다.

### 토큰 만들기

    cd frontend
    set -a; . ../.env; set +a
    ADMIN=$(printf '%s' "$ADMIN_EMAILS" | cut -d, -f1 | tr -d ' ')

`$ADMIN` 은 출력하지 않고 이후 명령에 변수로만 넘깁니다.

    mktoken() {
      EMAIL="$1" node --input-type=module -e "
        import { encode } from 'next-auth/jwt';
        const t = await encode({
          token: { email: process.env.EMAIL, name: 'QA', sub: 'qa-infra041' },
          secret: process.env.NEXTAUTH_SECRET, maxAge: 1800 });
        process.stdout.write(t);
      "
    }
    ADMIN_TOKEN=$(mktoken "$ADMIN")
    PLAIN_TOKEN=$(mktoken "qa-infra041@example.com")

토큰이 제대로 나왔는지는 길이가 아니라 **모양으로** 확인합니다. JWE 는 점 네 개로 나뉜
다섯 조각입니다. `[INFRA-040]` 사이클에서 1113자짜리 `ERR_MODULE_NOT_FOUND` 메시지를
길이 검사로 통과시킨 일이 있었습니다.

    printf '%s\n%s\n' "$ADMIN_TOKEN" "$PLAIN_TOKEN" | awk -F. '{print NF}'   # 5 두 줄

요청은 Next(3500)로 보냅니다. `proxy.ts` 가 쿠키를 읽어 `X-Auth-Identity` 를 붙이는
경로를 함께 지나야 실제 배포와 같습니다.

    call() {  # $1=쿠키(없으면 빈 문자열) $2=쿼리(없으면 빈 문자열)
      curl -s -w ' [%{http_code}]' \
        ${1:+-H "Cookie: next-auth.session-token=$1"} \
        "http://127.0.0.1:3500/api/admin/check$2"
    }

## 시나리오

### S-1. 신원 없이 관리자 이메일을 쿼리에 넣어도 관리자가 아니다 (회귀)
- 조작: `call "" "?email=$ADMIN"`
- 기대: `{"isAdmin":false} [200]`
- 필수 여부(required): 예

### S-2. 신원도 쿼리도 없으면 400 이 아니라 200 이다 (회귀)
- 조작: `call "" ""`
- 기대: `{"isAdmin":false} [200]`. 종전에는 `{"isAdmin":false,"error":"Email required"}` 와
  400 이었습니다.
- 필수 여부(required): 예

### S-3. 관리자 신원이면 쿼리 없이도 관리자다
- 조작: `call "$ADMIN_TOKEN" ""`
- 기대: `{"isAdmin":true} [200]`
- 필수 여부(required): 예

### S-4. 관리자가 아닌 신원은 관리자가 아니다
- 조작: `call "$PLAIN_TOKEN" ""`
- 기대: `{"isAdmin":false} [200]`
- 필수 여부(required): 예

### S-5. 쿼리가 신원을 이기지 못한다 (회귀)
- 조작: `call "$PLAIN_TOKEN" "?email=$ADMIN"`
- 기대: `{"isAdmin":false} [200]`. 신원이 관리자가 아니므로 쿼리에 무엇을 넣어도 false 입니다.
- 필수 여부(required): 예

### S-6. 쿼리가 신원을 깎지도 못한다
- 조작: `call "$ADMIN_TOKEN" "?email=nobody-infra041@example.com"`
- 기대: `{"isAdmin":true} [200]`. 쿼리를 완전히 무시하는 것이지 병합하는 것이 아닙니다.
- 필수 여부(required): 예

### S-7. 같은 신원을 쓰는 다른 라우트가 함께 깨지지 않았다 (인접)
- 조작: `GET /api/kr/user/quota` 를 `$ADMIN_TOKEN` 과 쿠키 없음으로 각각 부른다.
- 기대: 두 응답의 본문이 서로 다르다. 신원이 붙은 쪽은 관리자 면제 또는 이메일 기준
  쿼터를, 익명 쪽은 세션 기준 쿼터를 돌려준다. 둘이 완전히 같으면 신원이 통째로 사라진
  것이므로 이 라운드가 아니라 `[INFRA-027]` 경로가 깨진 것이다.
- 필수 여부(required): 예

### S-8. 화면이 정상으로 뜬다 (인접)
- 조작: agent-browser 로 `http://localhost:3500/dashboard/kr/vcp` 를 연다. 이 화면이
  `useAdmin` 을 쓰는 자리다(`page.tsx:230`).
- 기대: 표가 그려지고 콘솔 오류가 0건이다. 비로그인 상태이므로 관리자 전용 요소는 보이지
  않는다.
- 필수 여부(required): 예

### S-9. pytest 전체가 통과한다
- 조작: `source venv/bin/activate && pytest`
- 기대: 종료 코드 0. 새 검사 `test_admin_check_ignores_email_query_parameter` 포함.
- 필수 여부(required): 예

### S-10. vitest 전체와 타입 검사가 통과한다
- 조작: `cd frontend && npx vitest run` 과 `npm run type-check`
- 기대: 둘 다 종료 코드 0.
- 필수 여부(required): 예

### S-12. 응답이 캐시되지 않는다 (리포트)
- 조작: `curl -si http://127.0.0.1:3500/api/admin/check | grep -i cache-control`
- 기대: `Cache-Control: no-store`. 보안 리뷰가 지적한 자리다.
- 필수 여부(required): 예

### S-11. 관리자로 로그인해 관리자 전용 UI 가 보인다 (선택)
- 조작: 실제 관리자 계정으로 로그인해 VCP 화면의 관리자 전용 요소를 확인한다.
- 필수 여부(required): 아니요. 이 사이클은 관리자 계정으로 로그인하지 않습니다.

## 결과 (2026-09-07 실행)

기준 커밋은 `85c4fd7` 입니다. `useAdmin.ts` 변경은 Next 개발 서버가 자동으로 다시
컴파일했고, Flask 는 gunicorn 마스터(PID 30113)에 `SIGHUP` 을 보내 워커를 교체해
반영했습니다. 반영 전에는 `?email=` 없는 요청이 `400 Email required` 를 돌려주었고
반영 후에는 `200 {"isAdmin":false}` 로 바뀌어, 재기동이 실제로 걸린 것을 확인했습니다.

| ID | 결과 | 증거 |
|---|---|---|
| S-1 | **통과** | 신원 없이 `?email=<관리자>` → `{"isAdmin":false}[200]` |
| S-2 | **통과** | 신원도 쿼리도 없음 → `{"isAdmin":false}[200]`. 400 이 아닙니다 |
| S-3 | **통과** | 관리자 신원 + 쿼리 없음 → `{"isAdmin":true}[200]` |
| S-4 | **통과** | 비관리자 신원 → `{"isAdmin":false}[200]` |
| S-5 | **통과** | 비관리자 신원 + `?email=<관리자>` → `{"isAdmin":false}[200]` |
| S-6 | **통과** | 관리자 신원 + `?email=nobody-infra041@example.com` → `{"isAdmin":true}[200]` |
| S-7 | **통과** | `GET /api/kr/user/quota` 가 신원 있는 요청에 `is_admin: True, unlimited: True, limit: -1`, 익명에 `limit: 10, remaining: 10` 을 돌려주어 신원 경로가 살아 있습니다 |
| S-8 | **통과** | `localhost:3500/dashboard/kr/vcp` 가 정상으로 뜨고 콘솔 오류 0건(React DevTools 안내와 HMR 연결 로그만). 비로그인이므로 `Free Tier Plan`, `무료 사용량 10회 남음` |
| S-9 | **통과** | `pytest` 1795 통과 · 2 skip, 종료 코드 0 |
| S-10 | **통과** | `npx vitest run` 335 통과(54 파일), `npm run type-check` 종료 코드 0 |
| S-12 | **통과** | 응답 헤더에 `cache-control: no-store` |
| S-11 | 미실행 | 선택 항목입니다. 이 사이클은 관리자 계정으로 로그인하지 않습니다 |

필수 11건이 모두 통과했습니다.

### 관리자 UI 게이트가 버튼을 감추지 않는다 (S-8 보충)

`page.tsx:714` 와 `:1254` 의 `isAdmin` 게이트는 버튼을 숨기지 않고 **누르면 권한 모달을
띄우는** 방식입니다. 그래서 비로그인 화면에도 「실패 AI 재분석」과 「Refresh VCP」 버튼이
그대로 보이는 것이 정상이며 회귀가 아닙니다. 이 사이클은 그 버튼을 누르지 않았습니다.
누르면 실제 LLM 호출과 비용이 따르기 때문입니다.

### 접근 로그로는 확인할 수 없다

`?email=` 이 URL 에서 사라진 효과를 접근 로그로 재기 위해 `logs/backend.log` 를 봤으나
`/api/admin/check` 가 한 줄도 없습니다. `app/__init__.py:58-74` 의 `NOISY_ACTIVITY_PATHS`
에 이 경로가 들어 있어 `PollingLogFilter` 가 werkzeug 로그를 거릅니다. `logs/frontend.log`
에도 없습니다. **다음 사이클이 같은 확인을 반복하지 않도록 적어 둡니다.** 이 경로의 URL
변화는 로그가 아니라 코드로만 확인할 수 있습니다.

### 실측 도중 겪은 오판

**신원이 붙은 네 경우가 전부 400 으로 나왔으나 코드 결함이 아니었습니다.** 원인은 QA
하네스입니다. zsh 는 파라미터 확장 결과를 단어 분리하지 않으므로

    call() { curl -s ${1:+-H "Cookie: next-auth.session-token=$1"} "$url"; }

의 `${1:+...}` 가 통째로 **인자 하나**가 되어 curl 에 전달됩니다. curl 이 그것을 옵션으로
해석하지 못해 400 이 났습니다. 같은 요청을 `if [ -n "$1" ]` 조건 분기로 보내니 200 이
나왔습니다. `browser-notes.md` 가 agent-browser 에 대해 적어 둔 것과 같은 성질의 함정이며,
zsh 를 쓰는 이 환경에서는 curl 인자에도 그대로 해당합니다.

판별 요령은 `[INFRA-040]` 이 남긴 것과 같습니다. **막아야 할 것과 막지 말아야 할 것이
함께 무너지면 코드가 아니라 요청을 먼저 의심합니다.** 여기서는 신원이 붙은 넷이 전부
400 이고 신원 없는 둘은 정상이었으므로, 쿠키 헤더를 붙이는 경로만 망가진 것이 분명했습니다.

### 정리(cleanup)

- agent-browser 탭을 원래 상태인 `about:blank` 로 되돌렸습니다. 다른 탭은 건드리지
  않았습니다.
- QA 전용 세션 토큰은 `maxAge: 1800` 이라 30분 뒤 스스로 만료됩니다. 저장한 파일이 없고
  서버에 남긴 상태도 없습니다.
- 스크래치패드에 만든 응답 본문 파일 하나를 지웠습니다.
- gunicorn 은 `SIGHUP` 으로 워커만 교체했으므로 마스터 프로세스와 포트 바인딩이
  그대로입니다. 이 사이클이 새로 띄운 프로세스는 없습니다.
