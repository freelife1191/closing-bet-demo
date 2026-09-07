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

export async function proxy(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  // 클라이언트가 무엇을 보내든 지운다. 세션 확인보다 먼저 지워야 한다. 나중에 지우면
  // 세션이 없는 요청에서 위조한 값이 그대로 Flask 에 닿는다.
  requestHeaders.delete('x-user-email');
  requestHeaders.delete('x-auth-identity');

  const secret = (process.env.INTERNAL_IDENTITY_SECRET || '').trim();
  if (secret) {
    const token = await getToken({ req: request });
    const email = token?.email;
    if (email) {
      const expiresAt = Math.floor(Date.now() / 1000) + IDENTITY_TTL_SECONDS;
      requestHeaders.set('X-Auth-Identity', signIdentity(email, secret, expiresAt));
    }
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
