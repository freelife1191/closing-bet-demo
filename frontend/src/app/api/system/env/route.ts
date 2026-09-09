import { getServerSession } from 'next-auth';
import { NextResponse } from 'next/server';

import { isAdminEmail } from '@/lib/adminEmails';
import { authOptions } from '@/lib/auth';

/**
 * Flask 는 NextAuth 세션을 알지 못하므로 신원 확인을 여기서 끝낸다. 세션에서 얻은
 * 이메일이 ADMIN_EMAILS 에 있을 때만 서버끼리 공유하는 토큰을 붙여 넘긴다.
 *
 * ADMIN_API_TOKEN 은 이 파일이 서버에서만 실행되기 때문에 안전하다. NEXT_PUBLIC_
 * 접두사를 붙이면 브라우저 번들에 실려 이 게이트가 무의미해진다.
 */
// NEXT_PUBLIC_API_URL 은 브라우저에 공개되라고 만든 변수다. 그것이 비밀 토큰을 실어
// 보낼 호스트를 정하면, 프론트를 분리 배포하며 http 오리진을 넣는 순간 토큰이 평문으로
// 망을 건넌다. 이 fetch 만은 서버 전용 API_URL 로 한정한다.
const FLASK_BASE = process.env.API_URL || 'http://127.0.0.1:5501';

/**
 * 「이 요청자가 관리자인가」를 판정하는 자리는 저장소 전체에서 이 함수 하나뿐이다.
 * Flask 의 `verify_admin_api_token` 은 토큰 문자열만 대조하므로 판정이 아니라 판정
 * 결과를 옮겨 받는 자리다. 그래서 이 함수를 내보내 직접 검사한다. 세션 확인을
 * 빼고 토큰만 돌려주도록 바뀌면 게이트가 통째로 무력해지는데, 그것을 잡는 검사는
 * `route.test.ts` 뿐이다.
 */
export async function resolveAdminToken(): Promise<string | null> {
  const session = await getServerSession(authOptions);
  if (!isAdminEmail(session?.user?.email, process.env.ADMIN_EMAILS)) {
    return null;
  }
  const token = (process.env.ADMIN_API_TOKEN || '').trim();
  return token || null;
}

async function proxy(method: 'GET' | 'POST', body?: string) {
  const token = await resolveAdminToken();
  if (!token) {
    return NextResponse.json(
      { error: 'Forbidden' },
      { status: 403, headers: { 'Cache-Control': 'no-store' } }
    );
  }

  try {
    const response = await fetch(`${FLASK_BASE}/api/system/env`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': token,
      },
      body,
      cache: 'no-store',
    });

    const text = await response.text();
    // 200 본문에는 부분적으로 가려진 비밀이 담기므로 공유 캐시를 막는다.
    return new NextResponse(text, {
      status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  } catch {
    return NextResponse.json(
      { status: 'error', message: 'Settings service unavailable' },
      { status: 502, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}

export async function GET() {
  return proxy('GET');
}

export async function POST(request: Request) {
  return proxy('POST', await request.text());
}
