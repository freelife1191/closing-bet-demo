import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SettingsModal from './SettingsModal';
import { apiKeyFieldProps } from './settingsEnv';

// [FE-006] 회귀 검사. AUDIT-FE §1.4 의 결함은 함수가 아니라 배선에 있었다. 두 API 키
// 입력이 각자 다른 경로로 값을 얻고 있어서 한쪽만 복원되었다. 검사할 것은 두 필드가
// 같은 결과를 낸다는 것과, 서버가 마스킹해 보낸 문자열이 입력 값으로도 화면 문구로도
// 새어 나오지 않는다는 것이다. 한쪽 필드를 envVars 직접 참조로 되돌리면 여기서 걸린다.

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false, userEmail: null }),
}));

vi.mock('@/lib/session', () => ({
  getBrowserSessionId: () => 'anon_test',
}));

const MASKED_OPENAI = 'sk-1***************abcd';
const MASKED_PERPLEXITY = 'pplx****************wxyz';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  global.fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      String(url).includes('/api/system/env')
        ? { OPENAI_API_KEY: MASKED_OPENAI, PERPLEXITY_API_KEY: MASKED_PERPLEXITY }
        : { usage: 0, limit: 10, remaining: 10 },
  })) as unknown as typeof fetch;
});

// 저장된 키가 있을 때 두 필드에 함께 걸려야 하는 문구. 문구가 바뀌어도 따라가도록
// 검사 대상 함수에서 직접 얻는다.
const STORED_HINT = apiKeyFieldProps('****', '').placeholder;

/**
 * API 탭을 열고 서버 응답이 상태에 반영될 때까지 기다린다.
 *
 * 이 대기가 없으면 응답 도착 전의 빈 필드를 보고 어떤 검사든 통과한다. 두 필드가
 * 모두 STORED_HINT 를 갖는 것이 반영 완료의 신호이자, 두 필드가 같은 경로를 거쳤다는
 * 증거다. 한쪽이 envVars 를 직접 참조하면 그쪽 문구가 `pplx-...` 로 남아 여기서 멈춘다.
 */
async function openApiTabWithStoredKeys() {
  const { container } = render(
    <SettingsModal
      isOpen
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona: '' }}
      onSave={async () => {}}
    />
  );
  fireEvent.click(screen.getByText('API & 기능'));
  await waitFor(() => {
    expect(screen.getAllByPlaceholderText(STORED_HINT)).toHaveLength(2);
  });
  return container;
}

describe('SettingsModal API 키 필드', () => {
  it('마스킹된 서버 값을 두 입력 어느 쪽에도 값으로 넣지 않는다', async () => {
    const container = await openApiTabWithStoredKeys();

    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="password"]');
    expect(inputs).toHaveLength(2);
    for (const input of inputs) {
      expect(input.value).toBe('');
    }
  });

  it('마스킹 문자열을 화면 문구로도 내보내지 않는다', async () => {
    const container = await openApiTabWithStoredKeys();

    expect(container.textContent).not.toContain('abcd');
    expect(container.textContent).not.toContain('wxyz');
    for (const input of container.querySelectorAll<HTMLInputElement>('input[type="password"]')) {
      expect(input.placeholder).not.toContain('*');
    }
  });

  it('API 키를 localStorage 에 남기지 않는다', async () => {
    await openApiTabWithStoredKeys();

    expect(localStorage.getItem('OPENAI_API_KEY')).toBeNull();
    expect(localStorage.getItem('PERPLEXITY_API_KEY')).toBeNull();
  });
});
