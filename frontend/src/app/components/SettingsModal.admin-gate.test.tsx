import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import SettingsModal from './SettingsModal';

// [INFRA-025] 회귀 검사. 설정 버튼은 관리자 전용이 아니라 로그인한 모든 사용자에게
// 보인다. 서버가 /api/system/env 를 관리자 토큰으로 막았으므로, 화면이 비관리자에게도
// 그 요청을 보내면 모달을 열 때마다 403 이 나고 저장은 「API 설정」 실패로 끝난다.
// 탭이 다시 보이거나 요청이 되살아나면 여기서 걸린다.

const { mockUseAdmin } = vi.hoisted(() => ({
  mockUseAdmin: vi.fn(() => ({
    isAdmin: false,
    isLoading: false,
    // null 로만 두면 반환 타입이 null 로 고정되어 관리자 검사에서 문자열을 넣지
    // 못한다. next build 는 테스트 파일도 타입 검사한다.
    userEmail: null as string | null,
  })),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => mockUseAdmin(),
}));

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock('@/lib/session', () => ({
  getBrowserSessionId: () => 'anon_test',
}));

const PROFILE = { name: '테스터', email: 'tester@example.com', persona: '' };

function renderModal() {
  return render(
    <SettingsModal isOpen onClose={() => {}} profile={PROFILE} onSave={async () => {}} />
  );
}

function envCalls() {
  return (global.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(([url]) =>
    String(url).includes('/api/system/env')
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  global.fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({}),
  })) as unknown as typeof fetch;
});

describe('SettingsModal 관리자 게이트', () => {
  it('비관리자에게는 .env 를 다루는 탭을 보여주지 않는다', () => {
    mockUseAdmin.mockImplementation(() => ({
      isAdmin: false,
      isLoading: false,
      userEmail: null,
    }));

    renderModal();

    expect(screen.queryByText('API & 기능')).toBeNull();
    expect(screen.queryByText('알림 센터')).toBeNull();
    expect(screen.queryByText('시스템')).toBeNull();
    expect(screen.getByText('일반')).toBeTruthy();
  });

  it('비관리자에게는 환경 변수를 조회하지 않는다', async () => {
    mockUseAdmin.mockImplementation(() => ({
      isAdmin: false,
      isLoading: false,
      userEmail: null,
    }));

    renderModal();

    // render 가 act 로 감싸므로 이 시점에 조회 이펙트는 이미 flush 되었다. 아래
    // 관리자 검사가 같은 시점에 호출이 도착함을 보이므로 둘이 짝을 이룬다.
    await waitFor(() => {
      expect(screen.getByText('일반')).toBeTruthy();
    });
    expect(envCalls()).toHaveLength(0);
  });

  it('관리자에게는 탭을 보여주고 환경 변수를 조회한다', async () => {
    mockUseAdmin.mockImplementation(() => ({
      isAdmin: true,
      isLoading: false,
      userEmail: 'admin@example.com',
    }));

    renderModal();

    expect(screen.getByText('API & 기능')).toBeTruthy();
    await waitFor(() => {
      expect(envCalls().length).toBeGreaterThan(0);
    });
  });
});
