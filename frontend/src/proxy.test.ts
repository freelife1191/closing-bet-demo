import { beforeEach, describe, expect, it, vi } from 'vitest';

// [INFRA-027] 신원 게이트 회귀 검사. 이 파일이 저장소에서 보안적으로 가장 중요한 자리인데
// 검사가 없으면, 아래 두 가지를 누가 뒤집어도 어떤 검사도 실패하지 않는다.
//
//   1. 클라이언트가 보낸 신원 헤더를 지우는 것이 세션 확인보다 먼저라는 순서
//   2. 서명을 응답이 아니라 요청 헤더에 넣는다는 것
//
// 2번이 특히 조용하다. `NextResponse.next({ headers })` 로 한 글자만 바꾸면 서명이 브라우저로
// 그대로 나가는데 화면은 멀쩡히 동작한다.

const { mockGetToken } = vi.hoisted(() => ({
  mockGetToken: vi.fn<() => Promise<unknown>>(async () => null),
}));

vi.mock('next-auth/jwt', () => ({
  getToken: () => mockGetToken(),
}));

import { proxy } from './proxy';

function requestWith(headers: Record<string, string>, method = 'GET') {
  return { headers: new Headers(headers), method } as never;
}

/** NextResponse.next({ request: { headers } }) 가 상류로 넘긴 요청 헤더를 꺼낸다. */
function forwardedHeaders(response: Response): Headers {
  // Next 는 넘길 요청 헤더를 x-middleware-override-headers 와 x-middleware-request-* 로
  // 실어 보낸다. 그 규약을 되짚어 원래 헤더 집합을 복원한다.
  const overridden = response.headers.get('x-middleware-override-headers');
  const result = new Headers();
  if (!overridden) return result;
  for (const name of overridden.split(',').map((n) => n.trim())) {
    const value = response.headers.get(`x-middleware-request-${name}`);
    if (value !== null) result.set(name, value);
  }
  return result;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('INTERNAL_IDENTITY_SECRET', 'test-identity-secret');
});

describe('proxy', () => {
  it('세션이 없어도 클라이언트가 보낸 X-User-Email 을 지운다', async () => {
    mockGetToken.mockImplementation(async () => null);

    const res = await proxy(requestWith({ 'X-User-Email': 'victim@example.com' }));

    expect(forwardedHeaders(res).get('x-user-email')).toBeNull();
  });

  it('세션이 없어도 클라이언트가 보낸 X-Auth-Identity 를 지운다', async () => {
    mockGetToken.mockImplementation(async () => null);

    const res = await proxy(requestWith({ 'X-Auth-Identity': 'forged.9999999999.deadbeef' }));

    expect(forwardedHeaders(res).get('x-auth-identity')).toBeNull();
  });

  it('세션이 있으면 위조 헤더를 지운 자리에 자기 서명을 넣는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(
      requestWith({ 'X-Auth-Identity': 'forged.9999999999.deadbeef' })
    );

    const signed = forwardedHeaders(res).get('x-auth-identity');
    expect(signed).toBeTruthy();
    expect(signed).not.toBe('forged.9999999999.deadbeef');
    expect(signed!.split('.')).toHaveLength(3);
    expect(Buffer.from(signed!.split('.')[0], 'base64url').toString('utf8')).toBe(
      'owner@example.com'
    );
  });

  it('서명을 브라우저에게 돌려주지 않는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({}));

    // 응답 헤더에 직접 실리면 아무나 서명을 읽어 만료 전까지 그 사람으로 행세한다.
    // x-middleware-request-* 는 Next 내부 규약이라 브라우저까지 가지 않는다.
    expect(res.headers.get('x-auth-identity')).toBeNull();
  });

  it('비밀이 없으면 서명을 붙이지 않는다', async () => {
    vi.stubEnv('INTERNAL_IDENTITY_SECRET', '');
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({}));

    expect(forwardedHeaders(res).get('x-auth-identity')).toBeNull();
  });

  it('세션에 이메일이 없으면 서명을 붙이지 않는다', async () => {
    mockGetToken.mockImplementation(async () => ({ name: '이름만 있는 토큰' }));

    const res = await proxy(requestWith({}));

    expect(forwardedHeaders(res).get('x-auth-identity')).toBeNull();
  });

  it('X-Session-Id 는 건드리지 않는다', async () => {
    mockGetToken.mockImplementation(async () => null);

    const res = await proxy(requestWith({ 'X-Session-Id': 'anon_abc' }));

    expect(forwardedHeaders(res).get('x-session-id')).toBe('anon_abc');
  });
});

// [INFRA-040] 교차 출처 차단 회귀 검사. 지금 이 경로가 뚫려 있지 않은 이유는 이 저장소의
// 코드가 아니라 next-auth 세션 쿠키의 sameSite: 'lax' 기본값이다. 아래 검사들이 그 방어를
// 이 파일의 코드로 옮겨 두었음을 고정한다.
describe('proxy 의 교차 출처 차단', () => {
  it('로그인한 사용자의 교차 출처 POST 를 403 으로 끊는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(403);
  });

  it('Sec-Fetch-Site 가 없는 비안전 요청도 끊는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({}, 'DELETE'));

    expect(res.status).toBe(403);
  });

  // 소문자 메서드는 지금 Node 와 gunicorn 의 HTTP 파서가 400 으로 끊는다. 그 방어가
  // 우리 코드 밖에 있으므로 여기서도 닫아 둔다. 이 항목이 고치는 결함 자체가 「방어의
  // 근거가 라이브러리 기본값에만 있다」였다.
  it('메서드가 소문자여도 막는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'post'));

    expect(res.status).toBe(403);
  });

  it('같은 오리진의 POST 에는 서명을 붙인다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'same-origin' }, 'POST'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeTruthy();
  });

  it('교차 출처라도 GET 은 막지 않는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'GET'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeTruthy();
  });

  // 아래 둘이 차단을 거는 위치를 고정한다. 첫째는 검사가 익명 요청까지 막지 않는 것을,
  // 둘째는 검사가 서명 블록 안으로 들어가지 않는 것을 잡는다. 둘째가 특히 조용하다.
  // INTERNAL_IDENTITY_SECRET 이 빈 배포에서 차단만 꺼지는데, app/api/system/env 의
  // 관리자 게이트는 그 값을 보지 않아 살아 있고 .env 쓰기까지 닿는다.
  it('세션이 없으면 교차 출처 POST 도 막지 않고 익명으로 넘긴다', async () => {
    mockGetToken.mockImplementation(async () => null);

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeNull();
  });

  it('INTERNAL_IDENTITY_SECRET 이 비어도 로그인 사용자의 교차 출처 POST 는 막는다', async () => {
    vi.stubEnv('INTERNAL_IDENTITY_SECRET', '');
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(403);
  });
});
