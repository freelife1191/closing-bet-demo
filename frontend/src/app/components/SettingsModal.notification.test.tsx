import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsModal from './SettingsModal';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(), signOut: vi.fn(),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: true, isLoading: false }) }));
vi.mock('@/lib/session', () => ({ getBrowserSessionId: () => 'anon_notification_test' }));

let saveReply: () => Promise<Response>;
let sendReply: () => Promise<Response>;
let calls: string[];

beforeEach(() => {
  calls = [];
  saveReply = async () => Response.json({ status: 'ok' });
  sendReply = async () => Response.json({ status: 'success' });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'POST' && url === '/api/system/env') {
      calls.push('save');
      return saveReply();
    }
    if (url === '/api/notification/send') {
      calls.push('send');
      return sendReply();
    }
    return Response.json({ SMTP_HOST: 'smtp.example.test', DISCORD_WEBHOOK_URL: '********' });
  }));
});

afterEach(() => vi.unstubAllGlobals());

async function sendTest() {
  render(<SettingsModal isOpen onClose={() => {}}
    profile={{ name: 'QA', email: 'qa@example.test', persona: '' }} onSave={async () => {}} />);
  fireEvent.click(screen.getByText('알림 센터'));
  await screen.findByDisplayValue('smtp.example.test');
  fireEvent.click(screen.getAllByRole('button', { name: '테스트 발송' })[1]);
}

describe('알림 설정 저장 후 테스트 발송', () => {
  it.each([400, 403, 502])('설정 저장 HTTP %i이면 발송하지 않는다', async (status) => {
    saveReply = async () => Response.json({ status: 'error' }, { status });
    await sendTest();
    await screen.findByText('설정 저장 실패');
    expect(calls).toEqual(['save']);
  });

  it('설정 저장 네트워크 실패를 구분하고 발송하지 않는다', async () => {
    saveReply = async () => { throw new TypeError('Network failed'); };
    await sendTest();
    await screen.findByText('설정 저장 실패');
    expect(calls).toEqual(['save']);
  });

  it.each(['error-status', 'invalid-json'])('설정의 거짓 성공 %s를 차단한다', async (kind) => {
    saveReply = async () => kind === 'error-status'
      ? Response.json({ status: 'error' }) : new Response('not-json');
    await sendTest();
    await screen.findByText('설정 저장 실패');
    expect(calls).toEqual(['save']);
  });

  it.each([null, 0, true, 'ok', [], {}])('설정 성공이 아닌 JSON %j를 차단한다', async (body) => {
    saveReply = async () => Response.json(body);
    await sendTest();
    await screen.findByText('설정 저장 실패');
    expect(calls).toEqual(['save']);
    for (const button of screen.getAllByRole('button', { name: '테스트 발송' })) {
      expect(button.matches(':disabled')).toBe(false);
    }
  });

  it('저장 실패 후 설정을 고쳐 다시 발송할 수 있다', async () => {
    saveReply = async () => Response.json({ status: 'error' }, { status: 400 });
    await sendTest();
    await screen.findByText('설정 저장 실패');
    fireEvent.click(screen.getAllByRole('button', { name: '닫기' })[1]);
    saveReply = async () => Response.json({ status: 'ok' });
    fireEvent.click(screen.getAllByRole('button', { name: '테스트 발송' })[1]);
    await screen.findByText('발송 성공');
    expect(calls).toEqual(['save', 'save', 'send']);
  });

  it('설정 저장이 끝난 뒤에만 발송한다', async () => {
    let finishSave: (response: Response) => void = () => {};
    saveReply = () => new Promise<Response>((resolve) => { finishSave = resolve; });
    await sendTest();
    await waitFor(() => expect(calls).toEqual(['save']));
    finishSave(Response.json({ status: 'ok' }));
    await screen.findByText('발송 성공');
    expect(calls).toEqual(['save', 'send']);
  });

  it.each([502, 503, 200])('발송 실패 상태 %i를 성공으로 표시하지 않는다', async (status) => {
    sendReply = async () => Response.json({ status: 'error', message: 'Delivery failed' }, { status });
    await sendTest();
    await screen.findByText('발송 실패');
    expect(calls).toEqual(['save', 'send']);
  });

  it.each([null, 0, true, 'success', [], {}])('발송 성공이 아닌 JSON %j를 실패로 표시한다', async (body) => {
    sendReply = async () => Response.json(body);
    await sendTest();
    await screen.findByText('발송 실패');
    expect(calls).toEqual(['save', 'send']);
  });

  it.each(['network', 'invalid-json'])('발송 %s 오류에서 값 노출 없이 재시도를 허용한다', async (kind) => {
    sendReply = async () => {
      if (kind === 'network') throw new TypeError('PRIVATE_SEND_CANARY');
      return new Response('PRIVATE_SEND_CANARY');
    };
    await sendTest();
    await screen.findByText('발송 실패');
    expect(screen.queryByText(/PRIVATE_SEND_CANARY/)).toBeNull();
    expect(calls).toEqual(['save', 'send']);
    for (const button of screen.getAllByRole('button', { name: '테스트 발송' })) {
      expect(button.matches(':disabled')).toBe(false);
    }
  });
});
