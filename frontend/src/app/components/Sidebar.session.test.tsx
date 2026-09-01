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
});

describe('사용량 조회', () => {
  it('세션이 로딩 중이면 조회하지 않는다', async () => {
    mockSession(null, 'loading');
    await renderSidebar();

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('세션이 확정되면 세션 이메일로 조회한다', async () => {
    mockSession({ user: { name: '세션이름', email: 'session@example.com' } }, 'authenticated');
    await renderSidebar();

    const requested: string[] = (global.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(requested.some((url) => url.includes('email=session%40example.com') || url.includes('email=session@example.com'))).toBe(true);
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
