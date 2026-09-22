import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SettingsModal from './SettingsModal';

const signOut = vi.hoisted(() => vi.fn());
const fetchAPI = vi.hoisted(() => vi.fn());

vi.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { name: '테스터', email: 'tester@example.com' } },
    status: 'authenticated',
  }),
  signIn: vi.fn(),
  signOut,
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/lib/session', () => ({ getBrowserSessionId: () => 'delete-test' }));
vi.mock('@/lib/api', () => ({ fetchAPI }));

function mockServer(deleteResult: () => Promise<unknown>) {
  fetchAPI.mockImplementation(async (url: string) => {
    if (url === '/api/kr/user/data') return deleteResult();
    // useQuota 도 fetchAPI 를 쓴다. 사용량 조회는 실패로 두어 「사용량을 불러올 수 없습니다」
    // 상태가 되고 삭제 흐름과 무관하다. 한 번짜리 mock 은 그 조회가 먼저 소비한다.
    throw new Error('사용량 응답 없음');
  });
}

function clickConfirmDelete() {
  render(
    <SettingsModal
      isOpen
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona: '' }}
      onSave={async () => {}}
    />
  );
  fireEvent.click(screen.getAllByRole('button', { name: '계정 삭제' })[0]);
  fireEvent.click(screen.getByRole('button', { name: '삭제 (복구 불가)' }));
}

describe('[FE-045] 계정 삭제는 서버 기록을 먼저 지운다', () => {
  beforeEach(() => {
    signOut.mockReset();
    fetchAPI.mockReset();
    localStorage.clear();
  });

  it('서버 삭제가 실패하면 로그아웃하지 않고 실패 사유를 보인다', async () => {
    mockServer(async () => {
      throw new Error('일부 기록을 지우지 못했습니다. 잠시 후 다시 시도해 주세요.');
    });
    localStorage.setItem('probe', '1');

    clickConfirmDelete();

    await waitFor(() => expect(screen.getByText('계정 삭제 실패')).toBeTruthy());
    expect(fetchAPI).toHaveBeenCalledWith('/api/kr/user/data', { method: 'DELETE', timeout: 30000 });
    expect(signOut).not.toHaveBeenCalled();
    expect(localStorage.getItem('probe')).toBe('1');
    expect(screen.getByText(/일부 기록을 지우지 못했습니다/)).toBeTruthy();
  });

  it('요청이 도는 동안 확인 버튼이 비활성화되고 진행 문구를 보인다', async () => {
    mockServer(() => new Promise(() => {}));

    clickConfirmDelete();

    const button = await screen.findByRole('button', { name: '삭제 중…' });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(signOut).not.toHaveBeenCalled();
  });

  it('서버 삭제가 성공하면 브라우저 저장소를 비우고 로그아웃한다', async () => {
    mockServer(async () => ({ status: 'deleted' }));
    localStorage.setItem('probe', '1');

    clickConfirmDelete();

    await waitFor(() => expect(signOut).toHaveBeenCalledWith({ callbackUrl: '/' }));
    expect(fetchAPI).toHaveBeenCalledWith('/api/kr/user/data', { method: 'DELETE', timeout: 30000 });
    expect(localStorage.getItem('probe')).toBeNull();
  });
});
