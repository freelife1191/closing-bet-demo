import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SettingsModal from './SettingsModal';

// [CHAT-026] 회귀 검사. 프로필 저장이 실패를 던지게 되면서 생긴 부작용을 막는다.
// 세 저장이 한 줄로 이어져 있으면 프로필이 400 을 받는 순간 API 설정과 관심종목까지
// 저장되지 않는데, 화면에는 어느 탭이 원인인지 나오지 않는다. 저장 셋을 다시 한 줄로
// 묶으면 여기서 걸린다.

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

// [INFRA-025] 이후 .env 를 다루는 탭과 저장 요청은 관리자에게만 열린다. 이 파일의
// 검사 대상은 그 탭 안의 동작이므로 관리자로 둔다.
vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false, userEmail: 'admin@example.com' }),
}));

vi.mock('@/lib/session', () => ({
  getBrowserSessionId: () => 'anon_test',
}));

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  global.fetch = fetchMock as unknown as typeof fetch;
});

function renderModal(onSave: (name: string, email: string, persona: string) => Promise<void>) {
  render(
    <SettingsModal
      isOpen
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona: '' }}
      onSave={onSave}
    />
  );
  fireEvent.click(screen.getByText('저장'));
}

const envSaveCalls = () =>
  fetchMock.mock.calls.filter(
    ([url, init]) => String(url).includes('/api/system/env') && (init as RequestInit)?.method === 'POST'
  );

describe('SettingsModal 저장 격리', () => {
  it('프로필 저장이 실패해도 환경 변수와 관심종목은 저장한다', async () => {
    renderModal(async () => {
      throw new Error('Name is required');
    });

    await waitFor(() => {
      expect(envSaveCalls()).toHaveLength(1);
    });
    expect(localStorage.getItem('watchlist')).not.toBeNull();
  });

  it('실패한 대상을 문구에 담아 알린다', async () => {
    renderModal(async () => {
      throw new Error('Name is required');
    });

    await waitFor(() => {
      expect(screen.getByText('일부 저장 실패')).toBeTruthy();
    });
    expect(screen.getByText(/프로필 저장에 실패했습니다/)).toBeTruthy();
  });

  it('모두 성공하면 저장 완료를 알린다', async () => {
    renderModal(async () => {});

    await waitFor(() => {
      expect(screen.getByText('저장 완료')).toBeTruthy();
    });
    expect(envSaveCalls()).toHaveLength(1);
  });
});
