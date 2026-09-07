# [INFRA-040] QA 시나리오

교차 출처 비안전 요청을 `proxy.ts` 에서 끊는 변경의 검사 목록입니다.

## 대상과 범위

바꾼 자리는 `frontend/src/proxy.ts` 입니다. 쿠키에서 이메일이 확정된 요청이 비안전
메서드(POST·PUT·PATCH·DELETE)이면서 `Sec-Fetch-Site` 가 `same-origin` 이 아니면 403 을
돌려줍니다. 헤더가 없어도 막고, 메서드가 소문자여도 막습니다.

`frontend/src/proxy.test.ts` 에 검사 일곱 개를 더했고,
`.claude/skills/dev-cycle/references/tier-rules.md` 의 위험 경로 목록에 「신원 확정」 절을
만들었습니다.

## 실행 전 반드시 알아야 할 것

**검사는 신원 서명 블록 밖에 있고 `email` 유무만 봅니다.** 세션 쿠키가 없는 요청은
차단하지 않습니다. 신원이 붙지 않는 요청은 CSRF 의 대상이 아니고, 그때 차단이 켜지면
익명 사용자가 아무것도 하지 못하기 때문입니다. S-5 와 S-6 이 이 설계를 고정합니다.

**처음에는 검사를 `if (secret)` 안에도 두었으나 보안 리뷰가 뒤집었습니다.**
`INTERNAL_IDENTITY_SECRET` 은 Flask 로 신원을 넘기는 용도일 뿐 「이 요청이 인증되었는가」와
무관합니다. 그 값이 빈 배포에서는 차단만 꺼지는데, `app/api/system/env/route.ts` 의 관리자
게이트는 그 값을 보지 않고 NextAuth 세션만 보므로 살아 있고 `.env` 쓰기까지 닿습니다.
S-7 이 이 자리를 고정합니다.

**세션 토큰의 유효기간을 넉넉히 잡습니다.** 이 사이클에서 `maxAge: 300` 으로 만든 토큰이
실측 도중 만료되어, 차단이 전부 사라진 것처럼 보이는 결과를 받았습니다. 코드 결함으로
오판할 뻔했습니다. 30분으로 잡고, 결과가 통째로 달라지면 먼저 토큰부터 다시 만듭니다.

**세션 쿠키 없이는 이 변경을 실측할 수 없습니다.** 관리자 계정으로 로그인하지 않으므로,
`NEXTAUTH_SECRET` 으로 서명한 QA 전용 세션 토큰을 만들어 씁니다. 만드는 명령은 아래
「토큰 만들기」에 있으며, **비밀은 셸 변수로만 넘기고 어디에도 출력하지 않습니다.**

**상태를 바꾸지 않으려고 존재하지 않는 경로로 시험합니다.** `/api/kr/qa-infra040-probe`
입니다. 차단되면 403 이고, 통과하면 Flask 까지 도달해 500 이 납니다(`[INFRA-017]` 이
없는 경로에 404 대신 500 을 냅니다). 두 값이 갈리므로 판정이 명확하고, 어느 쪽이든 서버
상태가 바뀌지 않습니다.

**비용이 들거나 되돌릴 수 없는 조작은 하지 않습니다.** 알림 테스트 발송, 재분석,
모의투자 주문, Market Gate 갱신을 실행하지 않습니다.

### 토큰 만들기

    cd frontend
    set -a; . ../.env; set +a
    TOKEN=$(node --input-type=module -e "
      import { encode } from 'next-auth/jwt';
      const t = await encode({
        token: { email: 'qa-infra040@example.com', name: 'QA', sub: 'qa-infra040' },
        secret: process.env.NEXTAUTH_SECRET, maxAge: 300 });
      process.stdout.write(t);
    ")

토큰이 제대로 나왔는지는 길이가 아니라 **모양으로** 확인합니다. JWE 는 점 네 개로 나뉜
다섯 조각입니다. 길이만 재면 오류 메시지를 토큰으로 착각합니다. 실제로 이 사이클에서
1113자짜리 `ERR_MODULE_NOT_FOUND` 메시지를 토큰으로 통과시킨 일이 있었습니다.

    echo "$TOKEN" | awk -F. '{print NF}'   # 5 여야 합니다

## 시나리오

접속 주소는 `http://localhost:3500` 입니다. `127.0.0.1:3500` 을 쓰면 `allowedDevOrigins`
때문에 브라우저 경로가 막히므로 쓰지 않습니다(`references/browser-notes.md`).

| ID | 조작 | 기대값 | 필수 |
|---|---|---|---|
| S-1 | 세션 있는 교차 출처 POST | 403 | 필수 |
| S-2 | 세션 있는 POST 인데 `Sec-Fetch-Site` 헤더가 없음 | 403 | 필수 |
| S-3 | 세션 있는 교차 출처 DELETE | 403 | 필수 |
| S-4 | 세션 있는 같은 오리진 POST | 403 이 아님 (Flask 도달) | 필수 |
| S-5 | 세션 있는 교차 출처 GET | 403 이 아님 (읽기는 막지 않음) | 필수 |
| S-6 | 세션 없는 교차 출처 POST | 403 이 아님 (익명은 대상이 아님) | 필수 |
| S-7 | `INTERNAL_IDENTITY_SECRET` 이 비었을 때 세션 있는 교차 출처 POST | 403 | 필수 |
| S-8 | 교차 출처 PUT·PATCH | 403 | 필수 |
| S-9 | 메서드를 소문자로 보낸 교차 출처 요청 | 403 (단위 검사) | 필수 |
| S-10 | 403 응답 본문의 문구 | 한국어 문구가 나옴 | 필수 |
| S-11 | 브라우저에서 대시보드 화면 | 자료가 정상 표시되고 콘솔 오류 없음 | 필수 |
| S-12 | `proxy.test.ts` 검사 열넷 | 전부 통과 | 필수 |
| S-13 | pytest 전체 | 종료 코드 0 | 필수 |
| S-14 | vitest 전체와 `tsc --noEmit` | 종료 코드 0 | 필수 |
| S-15 | 상태를 바꾸는 GET 라우트 전수 확인 | 신원으로 상태를 바꾸는 GET 이 없음 | 필수 |
| S-16 | 로그인 상태에서 설정 저장·대화 삭제 | 정상 동작 | 선택 |

S-4 부터 S-7 이 이 항목의 핵심입니다. 차단만 확인하면 「전부 막는 코드」도 통과하므로,
막지 않아야 하는 것(S-4·S-5·S-6)을 함께 재야 범위가 고정됩니다. S-7 은 반대로 차단이
좁아지는 것을 잡습니다. S-7 과 S-9 는 서버 환경을 바꾸거나 HTTP 파서를 우회해야 하므로
단위 검사로 확인합니다.

S-16 을 선택으로 둔 이유는 로그인이 필요하고 이 사이클이 관리자 계정으로 로그인하지 않기
때문입니다. 같은 오리진의 쓰기가 통과하는 것은 S-4 가 덮습니다.

## 결과 (2026-09-07 실행)

기준 커밋은 `e6313bc` 입니다. Next 개발 서버가 `proxy.ts` 변경을 자동으로 다시 컴파일하므로
재기동 없이 실측했고, `logs/frontend.log` 의 `✓ Compiled` 로 반영을 확인했습니다.

| ID | 결과 | 증거 |
|---|---|---|
| S-1 | **통과** | 세션 있는 교차 출처 POST 가 403 |
| S-2 | **통과** | `Sec-Fetch-Site` 없는 POST 가 403 |
| S-3 | **통과** | 세션 있는 교차 출처 DELETE 가 403 |
| S-4 | **통과** | 같은 오리진 POST 가 500 (Flask 도달). `Sec-Fetch-Site: Same-Origin` 처럼 대문자로 보내면 403 이며 브라우저는 항상 소문자를 보냅니다 |
| S-5 | **통과** | 교차 출처 GET 이 500 (Flask 도달) |
| S-6 | **통과** | 세션 없는 교차 출처 POST 가 500 (Flask 도달) |
| S-7 | **통과** | `proxy.test.ts` 의 「INTERNAL_IDENTITY_SECRET 이 비어도 로그인 사용자의 교차 출처 POST 는 막는다」 |
| S-8 | **통과** | 교차 출처 PUT 과 PATCH 가 각각 403 |
| S-9 | **통과** | `proxy.test.ts` 의 「메서드가 소문자여도 막는다」. 실제 서버에서는 소문자 메서드가 Node 와 gunicorn 의 HTTP 파서에 400 으로 먼저 끊깁니다 |
| S-10 | **통과** | 403 본문이 `{"error":"교차 출처 요청은 처리하지 않습니다"}` |
| S-11 | **통과** | `localhost:3500/dashboard/kr` 에서 Market Gate `55 Neutral`, KOSPI 200 섹터 지수 11개 표시. 콘솔 오류 0건 |
| S-12 | **통과** | `npx vitest run src/proxy.test.ts` 14개 통과 |
| S-13 | **통과** | `pytest` 1794 통과 · 2 skip, 종료 코드 0 |
| S-14 | **통과** | `npx vitest run` 335 통과(54 파일), `npm run type-check` 종료 코드 0 |
| S-15 | **통과** | 신원으로 상태를 바꾸는 GET 라우트 없음. 아래 절 참조 |
| S-16 | 미실행 | 선택 항목입니다. 이 사이클은 관리자 계정으로 로그인하지 않습니다 |

필수 15건이 모두 통과했습니다.

### 상태를 바꾸는 GET 라우트 전수 확인 (S-15)

백그라운드 작업을 띄우는 자리를 다음 명령으로 전수 조사했습니다.

    grep -rn "start_background\|trigger_.*background\|Thread(" app/routes/*.py

다섯 곳이 나왔고 그중 GET 라우트는 둘입니다. `GET /api/portfolio` 가
`paper_trading.start_background_sync()` 를(`common_portfolio_routes.py:61`),
`GET /api/kr/market-gate` 가 `trigger_market_gate_background_refresh()` 를
(`kr_market_system_http_routes.py:83`) 부릅니다.

**둘 다 요청자의 신원을 보지 않습니다.** 공격자가 자기 브라우저에서 직접 불러도 결과가
같고 피해자의 쿠키가 필요하지 않으므로 CSRF 가 아니며 이번 차단의 대상이 아닙니다. 다만
조회 요청이 외부 호출과 파일 쓰기를 일으키는 것은 별개의 설계 문제이므로 `[INFRA-047]` 로
이월했습니다.

`g.user_email` 을 읽는 GET 분기는 전부 조회만 합니다. `chatbot/sessions` 는
`get_all_sessions`, `chatbot/history` 는 `get_messages`, `chatbot/profile` 은
`get_user_profile`, `user/quota` 는 `build_quota_info_payload` 를 부르고, 생성과 삭제는
POST·DELETE 분기로 갈라져 있습니다(`services/kr_market_chatbot_request_helpers.py:36,63,105`).

### 실측 도중 겪은 오판

검사를 신원 서명 블록 밖으로 옮긴 뒤 재실측했더니 여섯 경우가 **전부 500** 으로 나왔습니다.
차단이 통째로 사라진 것으로 보여 구현 결함을 의심했습니다.

원인은 코드가 아니라 **QA 토큰의 만료**였습니다. 처음 만든 토큰의 `maxAge` 가 300초였고
그 사이 11분이 지났습니다. 만료된 토큰은 `getToken` 이 `null` 을 돌려주므로 모든 요청이
익명이 되어 차단 대상에서 빠집니다. 토큰을 30분짜리로 다시 만들자 여섯 경우가 모두 기대대로
나왔습니다.

**결과가 통째로 달라지면 코드보다 토큰을 먼저 의심합니다.** 차단이 부분적으로 실패하면
코드 문제이고, 막아야 할 것과 막지 말아야 할 것이 함께 무너지면 신원이 사라진 것입니다.

### 정리

- 브라우저 탭을 `about:blank` 로 되돌렸습니다. 다른 작업의 탭은 건드리지 않았습니다.
- QA 토큰과 생성 스크립트를 삭제했습니다. 스크린샷은 스크래치패드에만 두었습니다.
- 실측은 존재하지 않는 경로로만 보냈으므로 서버 상태가 바뀌지 않았습니다.
- 비용이 드는 조작을 하나도 실행하지 않았습니다. 알림 테스트 발송, 재분석, 모의투자,
  Market Gate 갱신 버튼을 누르지 않았습니다.
- 서버는 새 코드로 떠 있는 상태를 유지합니다.
