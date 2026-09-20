import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { signOut, useSession } from 'next-auth/react';
import Sidebar from './Sidebar';

// [FE-004] 회귀 검사. 사이드바가 보여 주는 계정은 권한 판정과 사용량 집계가 쓰는 세션
// 계정과 같아야 하고, 로그아웃 버튼은 실제로 세션을 끊어야 한다. 세션 대신 localStorage
// 프로필로 되돌아가거나 signOut 호출이 사라지면 이 검사가 실패한다.

vi.mock('next-auth/react', () => ({
  useSession: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/kr',
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false, userEmail: null }),
}));

// 사이드바가 여는 두 모달은 이 검사의 대상이 아니다.
vi.mock('./SettingsModal', () => ({ default: () => null }));
vi.mock('./PaperTradingModal', () => ({ default: () => null }));

const savedProfile = { name: '저장된이름', email: 'saved@example.com', persona: '' };

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem('user_profile', JSON.stringify(savedProfile));
  global.fetch = vi.fn(async () => new Response(
    JSON.stringify({ usage: 0, limit: 10, remaining: 10 }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  )) as unknown as typeof fetch;
});

function mockSession(session: any, status: string) {
  (useSession as any).mockReturnValue({ data: session, status });
}

async function renderSidebar() {
  await act(async () => {
    render(<Sidebar />);
  });
}

describe('사이드바의 계정 표기', () => {
  it('세션이 인증 상태이면 세션의 이름과 이메일을 보여 준다', async () => {
    mockSession({ user: { name: '세션이름', email: 'session@example.com' } }, 'authenticated');
    await renderSidebar();

    expect(screen.getAllByText('세션이름').length).toBeGreaterThan(0);
    expect(screen.queryByText('저장된이름')).toBeNull();
  });

  it('세션이 없으면 localStorage 프로필을 보여 준다', async () => {
    mockSession(null, 'unauthenticated');
    await renderSidebar();

    expect(screen.getAllByText('저장된이름').length).toBeGreaterThan(0);
  });

  it('프로필 갱신 이벤트에서 캐시가 없으면 공통 기본 프로필로 되돌린다', async () => {
    mockSession(null, 'unauthenticated');
    await renderSidebar();
    localStorage.removeItem('user_profile');

    await act(async () => {
      window.dispatchEvent(new Event('user-profile-updated'));
    });

    expect(screen.getAllByText('User').length).toBeGreaterThan(0);
    expect(screen.queryByText('저장된이름')).toBeNull();
  });
});

describe('사용량 조회', () => {
  it('세션이 로딩 중이면 조회하지 않는다', async () => {
    mockSession(null, 'loading');
    await renderSidebar();

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('세션이 로딩 중이면 기본 10회 대신 사용량 확인 중을 표시한다', async () => {
    mockSession(null, 'loading');
    await renderSidebar();

    expect(screen.getAllByText('사용량 확인 중')).toHaveLength(2);
    expect(screen.queryByText('Free Tier (무료 10회)')).toBeNull();
  });

  it('[INFRA-027] 조회 URL 에 신원을 싣지 않는다', async () => {
    // 종전에는 화면이 이메일을 쿼리 파라미터로 넘겼고, 서버가 그 값을 그대로 믿었다.
    // 그래서 URL 한 줄로 남의 사용량을 조회할 수 있었다. 이제 신원은 proxy.ts 가
    // NextAuth 세션에서 확정하므로, 화면이 무엇을 보내든 서버는 보지 않는다.
    mockSession({ user: { name: '세션이름', email: 'session@example.com' } }, 'authenticated');
    await renderSidebar();

    const requested: string[] = (global.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    const quotaCalls = requested.filter((url) => url.includes('/api/kr/user/quota'));

    expect(quotaCalls.length).toBeGreaterThan(0);
    expect(quotaCalls.every((url) => !url.includes('email='))).toBe(true);
    expect(quotaCalls.every((url) => !url.includes('session_id='))).toBe(true);
    // 이전 사용자의 값이 새어 나가지 않는다는 원래 보장은 그대로 유지된다.
    expect(requested.some((url) => url.includes('saved@example.com'))).toBe(false);
  });

  it('충전 버튼의 목적과 제한을 이름으로 알린다', async () => {
    mockSession(null, 'unauthenticated');
    await renderSidebar();

    expect(screen.getByRole('button', { name: '무료 사용량 5회 충전 (하루 1회)' })).toBeTruthy();
  });
});

describe('로그아웃 버튼', () => {
  it('signOut 을 호출한다', async () => {
    mockSession({ user: { name: '세션이름', email: 'session@example.com' } }, 'authenticated');
    await renderSidebar();

    // 사용자 메뉴를 먼저 연다. 로그아웃 버튼은 그 안에 있다.
    await act(async () => {
      fireEvent.click(screen.getAllByText('세션이름')[0]);
    });
    await act(async () => {
      fireEvent.click(screen.getByText('로그아웃'));
    });

    expect(signOut).toHaveBeenCalledWith({ callbackUrl: '/' });
  });
});


it('익명 사용량 조회와 갱신은 챗봇과 같은 브라우저 세션을 보낸다', async () => {
  mockSession(null, 'unauthenticated');
  await renderSidebar();
  const sessionId = localStorage.getItem('browser_session_id');
  expect(sessionId).toMatch(/^anon_/);
  expect(global.fetch).toHaveBeenCalledWith('/api/kr/user/quota', expect.objectContaining({
    headers: { 'X-Session-Id': sessionId },
  }));
  vi.mocked(global.fetch).mockClear();
  await act(async () => { window.dispatchEvent(new Event('quota-updated')); });
  expect(global.fetch).toHaveBeenCalledWith('/api/kr/user/quota', expect.objectContaining({
    headers: { 'X-Session-Id': sessionId },
  }));
});

function quotaResponse(usage: number, remaining: number): Response {
  return new Response(
    JSON.stringify({ usage, limit: 10, remaining }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  );
}

function deferredResponse(): {
  promise: Promise<Response>;
  resolve: (response: Response) => void;
} {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe('[FE-043] 사용량 오류와 신원 경계', () => {
  it.each([
    ['HTML 200', new Response('<!doctype html>', { status: 200 })],
    ['HTML 404', new Response('<!doctype html>', { status: 404 })],
    ['HTML 502', new Response('<!doctype html>', { status: 502 })],
    ['JSON 401', new Response(JSON.stringify({ message: 'unauthorized' }), { status: 401 })],
    ['JSON 403', new Response(JSON.stringify({ message: 'forbidden' }), { status: 403 })],
    ['JSON 500', new Response(JSON.stringify({ message: 'server error' }), { status: 500 })],
  ])('%s 실패에서 기본 10회 대신 불러오기 실패를 표시한다', async (_label, response) => {
    mockSession(null, 'unauthenticated');
    global.fetch = vi.fn(async () => response) as unknown as typeof fetch;

    await renderSidebar();

    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);
    expect(screen.queryByText('Free Tier (무료 10회)')).toBeNull();
  });

  it('잘못된 숫자 형태는 사용량으로 표시하지 않는다', async () => {
    mockSession(null, 'unauthenticated');
    global.fetch = vi.fn(async () => new Response(
      JSON.stringify({ usage: '0', limit: 10, remaining: 10 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )) as unknown as typeof fetch;

    await renderSidebar();

    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);
    expect(screen.queryByText('10회 남음')).toBeNull();
  });

  it('실패 뒤 최신 갱신이 성공하면 실제 남은 횟수로 복구한다', async () => {
    mockSession(null, 'unauthenticated');
    global.fetch = vi.fn()
      .mockResolvedValueOnce(new Response('<!doctype html>', { status: 502 }))
      .mockResolvedValueOnce(quotaResponse(3, 7)) as unknown as typeof fetch;

    await renderSidebar();
    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);

    await act(async () => {
      window.dispatchEvent(new Event('quota-updated'));
    });

    expect(await screen.findByText('7회 남음')).toBeTruthy();
    expect(screen.queryAllByText('사용량을 불러올 수 없습니다')).toHaveLength(0);
  });

  it('성공 뒤 최신 갱신이 실패하면 이전 사용량을 숨긴다', async () => {
    mockSession(null, 'unauthenticated');
    global.fetch = vi.fn()
      .mockResolvedValueOnce(quotaResponse(3, 7))
      .mockResolvedValueOnce(new Response('<!doctype html>', { status: 502 })) as unknown as typeof fetch;

    await renderSidebar();
    expect(await screen.findByText('7회 남음')).toBeTruthy();

    await act(async () => {
      window.dispatchEvent(new Event('quota-updated'));
    });

    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);
    expect(screen.queryByText('7회 남음')).toBeNull();
  });

  it.each([
    ['다른 계정', { user: { name: 'B', email: 'b@example.com' } }, 'authenticated'],
    ['로그아웃', null, 'unauthenticated'],
  ])('늦은 A 응답은 %s 뒤의 최신 신원 사용량을 덮어쓰지 않는다', async (_label, nextSession, nextStatus) => {
    const delayedA = deferredResponse();
    global.fetch = vi.fn()
      .mockImplementationOnce(() => delayedA.promise)
      .mockResolvedValueOnce(quotaResponse(4, 6)) as unknown as typeof fetch;
    mockSession({ user: { name: 'A', email: 'a@example.com' } }, 'authenticated');

    const view = render(<Sidebar />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    mockSession(nextSession, nextStatus);
    view.rerender(<Sidebar />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('6회 남음')).toBeTruthy();

    await act(async () => {
      delayedA.resolve(quotaResponse(1, 9));
    });

    expect(screen.queryByText('9회 남음')).toBeNull();
    expect(screen.getByText('6회 남음')).toBeTruthy();
  });

  it('같은 신원의 연속 갱신에서 늦은 첫 응답을 버린다', async () => {
    const delayedFirst = deferredResponse();
    global.fetch = vi.fn()
      .mockImplementationOnce(() => delayedFirst.promise)
      .mockResolvedValueOnce(quotaResponse(4, 6)) as unknown as typeof fetch;
    mockSession(null, 'unauthenticated');

    await renderSidebar();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(new Event('quota-updated'));
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('6회 남음')).toBeTruthy();

    await act(async () => {
      delayedFirst.resolve(quotaResponse(1, 9));
    });

    expect(screen.queryByText('9회 남음')).toBeNull();
    expect(screen.getByText('6회 남음')).toBeTruthy();
  });
});
