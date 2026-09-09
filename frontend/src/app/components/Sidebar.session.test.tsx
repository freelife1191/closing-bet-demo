import { render, screen, fireEvent, act } from '@testing-library/react';
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
  global.fetch = vi.fn(async () => ({
    json: async () => ({ usage: 0, limit: 10, remaining: 10 }),
  })) as any;
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
