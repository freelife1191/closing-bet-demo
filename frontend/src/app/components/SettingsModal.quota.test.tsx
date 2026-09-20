import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SettingsModal from './SettingsModal';

interface TestSessionState {
  data: { user: { name: string; email: string } } | null;
  status: 'loading' | 'authenticated' | 'unauthenticated';
}

const sessionState = vi.hoisted((): { value: TestSessionState } => ({
  value: {
    data: { user: { name: '테스터', email: 'tester@example.com' } },
    status: 'authenticated',
  },
}));

vi.mock('next-auth/react', () => ({
  useSession: () => sessionState.value,
  signIn: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/lib/session', () => ({ getBrowserSessionId: () => 'quota-test' }));

const profile = { name: '테스터', email: 'tester@example.com', persona: '' };

function renderModal(isOpen = true) {
  return render(
    <SettingsModal isOpen={isOpen} onClose={() => {}} profile={profile} onSave={async () => {}} />
  );
}

function mockQuotaResponses(...responses: Response[]): void {
  const quotaResponses = [...responses];
  global.fetch = vi.fn(async (url: RequestInfo | URL) => {
    if (String(url) === '/api/kr/user/quota') {
      const response = quotaResponses.shift();
      if (!response) throw new Error('사용량 응답이 남아 있지 않습니다');
      return response;
    }
    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionState.value = {
    data: { user: { name: '테스터', email: 'tester@example.com' } },
    status: 'authenticated',
  };
});

describe('[FE-043] SettingsModal 사용량 오류', () => {
  it('세션이 로딩 중이면 기본 10회 대신 사용량 확인 중을 표시한다', () => {
    sessionState.value = { data: null, status: 'loading' };
    mockQuotaResponses();

    renderModal();

    expect(screen.getByText('사용량 확인 중')).toBeTruthy();
    expect(screen.queryByText('✨ 무료 10회 AI 사용 가능')).toBeNull();
  });

  it.each([
    ['HTML 200', new Response('<!doctype html>', { status: 200 })],
    ['HTML 404', new Response('<!doctype html>', { status: 404 })],
    ['HTML 502', new Response('<!doctype html>', { status: 502 })],
    ['JSON 401', new Response(JSON.stringify({ message: 'unauthorized' }), { status: 401 })],
    ['JSON 403', new Response(JSON.stringify({ message: 'forbidden' }), { status: 403 })],
    ['JSON 500', new Response(JSON.stringify({ message: 'server error' }), { status: 500 })],
  ])('%s 실패를 사용량 없음으로 표시한다', async (_label, response) => {
    mockQuotaResponses(response);

    renderModal();

    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);
    expect(screen.queryByText('✨ 무료 10회 AI 사용 가능')).toBeNull();
  });

  it('닫았다 다시 열어 성공한 최신 응답으로 복구한다', async () => {
    mockQuotaResponses(
      new Response('<!doctype html>', { status: 502 }),
      new Response(
        JSON.stringify({ usage: 2, limit: 10, remaining: 8 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    const view = renderModal();
    expect(await screen.findAllByText('사용량을 불러올 수 없습니다')).toHaveLength(2);

    view.rerender(
      <SettingsModal isOpen={false} onClose={() => {}} profile={profile} onSave={async () => {}} />
    );
    view.rerender(
      <SettingsModal isOpen onClose={() => {}} profile={profile} onSave={async () => {}} />
    );

    expect(await screen.findByText('8회 남음')).toBeTruthy();
    expect(screen.queryAllByText('사용량을 불러올 수 없습니다')).toHaveLength(0);
  });
});
