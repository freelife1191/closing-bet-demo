import { beforeEach, describe, expect, it, vi } from 'vitest';

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

import { resolveAdminToken } from './route';

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
