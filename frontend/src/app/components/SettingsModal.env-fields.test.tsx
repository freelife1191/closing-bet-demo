import '@testing-library/jest-dom/vitest';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SettingsModal from './SettingsModal';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false, userEmail: 'admin@example.com' }),
}));

vi.mock('@/lib/session', () => ({
  getBrowserSessionId: () => 'anon_env_fields_test',
}));

const STORED_HINT = '저장되어 있습니다. 바꾸려면 새 값을 입력하세요';
const MASKED_ENV = {
  OPENAI_API_KEY: 'sk-1***************abcd',
  PERPLEXITY_API_KEY: 'pplx****************wxyz',
  TELEGRAM_BOT_TOKEN: '1234****************token',
  TELEGRAM_CHAT_ID: '-100**********7890',
  DISCORD_WEBHOOK_URL: 'http****************hook',
  SMTP_HOST: 'smtp**********test',
  SMTP_PORT: '587',
  SMTP_USER: 'user**********test',
  SMTP_PASSWORD: 'pass********word',
  EMAIL_RECIPIENTS: 'mail**********test',
  GOOGLE_SEARCH_ENGINE_ID: 'engi**********neid',
  AI_PROVIDER: 'gemini',
};

const MASKED_NOTIFICATION_LABELS = [
  'TELEGRAM_BOT_TOKEN',
  'TELEGRAM_CHAT_ID',
  'DISCORD_WEBHOOK_URL',
  'SMTP Host',
  'SMTP User (Email)',
  'SMTP Password (App Password)',
  '수신 이메일 (콤마로 구분)',
];

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).startsWith('/api/system/env') && init?.method !== 'POST') {
      return Response.json(MASKED_ENV);
    }
    if (String(input) === '/api/system/env' && init?.method === 'POST') {
      return Response.json({ status: 'ok' });
    }
    return Response.json({ usage: 0, limit: 10, remaining: 10 });
  });
  global.fetch = fetchMock as unknown as typeof fetch;
});

function renderModal() {
  render(
    <SettingsModal
      isOpen
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona: '' }}
      onSave={async () => {}}
    />
  );
}

async function openNotificationTab() {
  renderModal();
  fireEvent.click(screen.getByText('알림 센터'));
  await waitFor(() => {
    expect(screen.getByLabelText('TELEGRAM_BOT_TOKEN')).toHaveAttribute('placeholder', STORED_HINT);
  });
}

function savedEnvPayload(): Record<string, string> {
  const call = fetchMock.mock.calls.find(([input, init]) =>
    String(input) === '/api/system/env' && (init as RequestInit | undefined)?.method === 'POST'
  );
  expect(call).toBeTruthy();
  const init = call?.[1] as RequestInit | undefined;
  return JSON.parse(String(init?.body)) as Record<string, string>;
}

describe('SettingsModal 저장 환경값 입력', () => {
  it('마스킹된 알림 값을 입력값 대신 고정 안내로 보여 준다', async () => {
    await openNotificationTab();

    for (const label of MASKED_NOTIFICATION_LABELS) {
      expect(screen.getByLabelText(label)).toHaveValue('');
      expect(screen.getByLabelText(label)).toHaveAttribute('placeholder', STORED_HINT);
    }
    expect(screen.getByLabelText('SMTP Port')).toHaveValue('587');
  });

  it('검색 엔진 ID도 마스킹 문자열을 입력값으로 노출하지 않는다', async () => {
    renderModal();
    fireEvent.click(screen.getByText('시스템'));

    const input = await screen.findByLabelText('Google Custom Search Engine ID');
    expect(input).toHaveValue('');
    expect(input).toHaveAttribute('placeholder', STORED_HINT);
  });

  it('새로 입력한 값만 바꾸고 손대지 않은 마스킹 값은 저장 payload에 보존한다', async () => {
    await openNotificationTab();
    fireEvent.change(screen.getByLabelText('TELEGRAM_BOT_TOKEN'), {
      target: { value: 'new-telegram-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(true);
    });
    expect(savedEnvPayload()).toMatchObject({
      TELEGRAM_BOT_TOKEN: 'new-telegram-token',
      TELEGRAM_CHAT_ID: MASKED_ENV.TELEGRAM_CHAT_ID,
      DISCORD_WEBHOOK_URL: MASKED_ENV.DISCORD_WEBHOOK_URL,
      SMTP_PASSWORD: MASKED_ENV.SMTP_PASSWORD,
      GOOGLE_SEARCH_ENGINE_ID: MASKED_ENV.GOOGLE_SEARCH_ENGINE_ID,
    });
  });
});
