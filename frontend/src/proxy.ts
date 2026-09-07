import { getToken } from 'next-auth/jwt';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { IDENTITY_TTL_SECONDS, signIdentity } from '@/lib/identity';

/**
 * Flask 는 NextAuth 세션 쿠키를 읽지 못한다. 그래서 신원 확정을 여기서 끝내고,
 * 서버끼리만 아는 비밀로 서명한 헤더만 넘긴다.
 *
 * 종전에는 브라우저가 보낸 `X-User-Email` 이 그대로 신원이었다. 그 값은 설정 모달의
 * 자유 입력 칸에서 왔고 NextAuth 세션과 대조되지 않았으므로, 남의 이메일을 아는
 * 사람은 헤더 한 줄로 그 사람의 대화와 쿼터에 닿았다.
 *
 * 파일 이름은 `proxy.ts` 다. Next.js 16 에서 `middleware.js` 규약은 폐지되고 이 이름으로
 * 바뀌었다(01-app/03-api-reference/03-file-conventions/proxy.md).
 *
 * 실행 순서는 Proxy(3) → afterFiles rewrites(6) 이므로 이 파일이 next.config.js 의
 * rewrite 보다 먼저 돈다. 그래서 rewrite 는 그대로 두어도 된다.
 */

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export async function proxy(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  // 클라이언트가 무엇을 보내든 지운다. 세션 확인보다 먼저 지워야 한다. 나중에 지우면
  // 세션이 없는 요청에서 위조한 값이 그대로 Flask 에 닿는다.
  requestHeaders.delete('x-user-email');
  requestHeaders.delete('x-auth-identity');

  // getToken 은 NEXTAUTH_SECRET 을 읽으며 INTERNAL_IDENTITY_SECRET 과 무관하다. 쿠키가
  // 없거나 복호화에 실패하면 예외 없이 null 을 돌려준다(next-auth/jwt/index.js:89,95).
  const token = await getToken({ req: request });
  const email = token?.email;

  // 신원이 쿠키에서 나오므로 브라우저가 자동으로 붙인다. 다른 사이트의 페이지가 이
  // 요청을 일으켰는지 여기서 직접 본다. Sec-Fetch-Site 는 브라우저가 붙이는 금지
  // 헤더라 스크립트가 덮어쓸 수 없고, 없으면 없는 대로 막는다.
  //
  // 이 검사는 아래 서명 블록 밖에 있어야 한다. INTERNAL_IDENTITY_SECRET 은 Flask 로
  // 신원을 넘기는 용도일 뿐 「이 요청이 인증되었는가」와 무관하다. 안쪽에 두면 그 값이
  // 빈 배포에서 차단이 통째로 꺼지는데, app/api/system/env/route.ts 의 관리자 게이트는
  // 그 값을 보지 않고 NextAuth 세션만 보므로 살아 있다. 그 라우트는 .env 에 쓰기까지
  // 하므로 차단이 꺼진 채로 열려서는 안 된다.
  //
  // 익명 요청을 막지 않는 이유는 「어차피 익명이라」가 아니다. 익명 신원인
  // X-Session-Id 는 브라우저가 자동으로 붙이는 값이 아니라 localStorage 에서 읽어 JS 가
  // 붙이는 값이라(lib/session.ts:7) 교차 출처 페이지가 피해자의 값을 실을 수 없다.
  // 누군가 그 값을 쿠키로 옮기면 이 전제가 깨진다.
  //
  // 지금까지는 next-auth 세션 쿠키의 sameSite: 'lax' 기본값이 이것을 막고 있었다.
  // lib/auth.ts 에 cookies 설정을 더하며 그 값을 바꾸면 이 검사만 남는다.
  //
  // 사파리는 16.4(2023-03)부터 이 헤더를 보낸다. iOS 16.3 이하와 그 계열 인앱 웹뷰에서는
  // 로그인한 사용자의 쓰기가 전부 여기서 막힌다. 그 문의가 들어오면 헤더가 없을 때만
  // Origin 의 호스트를 request.nextUrl.host 와 대조하는 갈래를 더한다. 프로토콜까지
  // 비교하면 x-forwarded-proto 를 붙이지 않는 앞단에서 모든 쓰기가 막히므로 호스트만 본다.
  if (
    email &&
    UNSAFE_METHODS.has(request.method.toUpperCase()) &&
    request.headers.get('sec-fetch-site') !== 'same-origin'
  ) {
    // 본문 문구가 화면에 그대로 뜬다. lib/api.ts:33 이 error 를 Error.message 로 올린다.
    return NextResponse.json(
      { error: '교차 출처 요청은 처리하지 않습니다' },
      { status: 403 }
    );
  }

  const secret = (process.env.INTERNAL_IDENTITY_SECRET || '').trim();
  if (secret && email) {
    const expiresAt = Math.floor(Date.now() / 1000) + IDENTITY_TTL_SECONDS;
    requestHeaders.set('X-Auth-Identity', signIdentity(email, secret, expiresAt));
  }

  // request 안에 넣어야 rewrite 목적지로 간다. NextResponse.next({ headers }) 로 쓰면
  // 브라우저에게 돌려주는 응답 헤더가 되어 신원이 그대로 노출된다.
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  // NextAuth 자체 경로는 제외한다. 세션을 발급하는 자리에 세션 확인을 걸 이유가 없다.
  // 슬래시까지 적는다. `auth` 만 적으면 `auth` 로 시작하는 모든 경로가 빠지므로,
  // 나중에 `/api/authors` 같은 경로가 생기면 게이트에서 조용히 벗어난다.
  matcher: ['/api/((?!auth/).*)'],
};
