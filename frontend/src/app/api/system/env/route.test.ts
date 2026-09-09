import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// [INFRA-025] 인가 판정 회귀 검사. 「이 요청자가 관리자인가」를 정하는 코드는
// resolveAdminToken 하나뿐이다. Flask 의 토큰 대조는 그 결과를 옮겨 받을 뿐이므로,
// 여기서 세션 확인이 빠지면 게이트가 통째로 무력해지는데도 다른 검사는 전부 통과한다.

const { mockGetServerSession } = vi.hoisted(() => ({
  mockGetServerSession: vi.fn<() => Promise<unknown>>(async () => null),
}));

vi.mock('next-auth', () => ({
  getServerSession: () => mockGetServerSession(),
}));

vi.mock('@/lib/auth', () => ({
  authOptions: {},
}));

import { GET, POST, resolveAdminToken } from './route';

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('ADMIN_EMAILS', 'admin@example.com');
  vi.stubEnv('ADMIN_API_TOKEN', 's3cret-token');
});

describe('resolveAdminToken', () => {
  it('세션이 없으면 토큰을 내주지 않는다', async () => {
    mockGetServerSession.mockImplementation(async () => null);

    expect(await resolveAdminToken()).toBeNull();
  });

  it('관리자 목록에 없는 이메일에는 토큰을 내주지 않는다', async () => {
    mockGetServerSession.mockImplementation(async () => ({
      user: { email: 'intruder@example.com' },
    }));

    expect(await resolveAdminToken()).toBeNull();
  });

  it('관리자에게는 토큰을 내준다', async () => {
    mockGetServerSession.mockImplementation(async () => ({
      user: { email: 'ADMIN@example.com' },
    }));

    expect(await resolveAdminToken()).toBe('s3cret-token');
  });

  it('토큰이 설정되지 않았으면 관리자에게도 내주지 않는다', async () => {
    vi.stubEnv('ADMIN_API_TOKEN', '');
    mockGetServerSession.mockImplementation(async () => ({
      user: { email: 'admin@example.com' },
    }));

    expect(await resolveAdminToken()).toBeNull();
  });
});

afterEach(() => vi.unstubAllGlobals());

describe('env proxy upstream failures', () => {
  beforeEach(() => {
    mockGetServerSession.mockResolvedValue({ user: { email: 'admin@example.com' } });
  });

  it.each(['GET', 'POST'])('%s upstream 연결 실패를 비밀 없는 502로 반환한다', async (method) => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('PRIVATE_UPSTREAM_CANARY')));
    const response = method === 'GET' ? await GET()
      : await POST(new Request('http://localhost/api/system/env', { method: 'POST', body: '{}' }));
    expect(response.status).toBe(502);
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(await response.json()).toEqual({ status: 'error', message: 'Settings service unavailable' });
  });

  it.each(['GET', 'POST'])('%s upstream 응답 본문 읽기 실패도 502이며 캐시되지 않는다', async (method) => {
    const body = new ReadableStream({ start(controller) { controller.error(new Error('PRIVATE_BODY_CANARY')); } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)));
    const response = method === 'GET' ? await GET()
      : await POST(new Request('http://localhost/api/system/env', { method: 'POST', body: '{}' }));
    expect(response.status).toBe(502);
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(await response.json()).toEqual({ status: 'error', message: 'Settings service unavailable' });
  });

  it('upstream 검증 거부 상태와 키 결과를 그대로 전달한다', async () => {
    const result = { status: 'error', rejected: { SMTP_HOST: 'unsafe_value' } };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(result, { status: 400 })));
    const response = await POST(new Request('http://localhost/api/system/env', { method: 'POST', body: '{}' }));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual(result);
    expect(response.headers.get('cache-control')).toBe('no-store');
  });

  it('익명 요청은 upstream에 접근하지 않는다', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);
    expect((await GET()).status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
  });
});
