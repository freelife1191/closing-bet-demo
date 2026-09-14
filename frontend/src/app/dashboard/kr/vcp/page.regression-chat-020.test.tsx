// Regression: [CHAT-020] — VCP 종목별 채팅 삭제가 실패·세션 교체 뒤에도 화면을 지우던 문제

import type { ReactNode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const ALPHA = {
  ticker: '000001',
  name: '알파',
  signal_date: '2026-09-14',
  score: 90,
  is_vcp: true,
  entry_price: 100_000,
  current_price: 110_000,
};
const BETA = { ...ALPHA, ticker: '000002', name: '베타' };
const ALPHA_SESSION = 'alpha-session';
const BETA_SESSION = 'beta-session';

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({ signals: [ALPHA, BETA], total_scanned: 2, source: 'test' })),
    getSignalDates: vi.fn(async () => []),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
    getStockChart: vi.fn(async () => ({ ticker: ALPHA.ticker, data: [] })),
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock('remark-gfm', () => ({ default: () => null }));

interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

interface FetchReply {
  status: number;
  body?: Record<string, unknown>;
}

const reply = ({ status, body = {} }: FetchReply): Response => new Response(JSON.stringify(body), { status });

let fetchMock: ReturnType<typeof vi.fn>;

const historyReply = (content: string): Response => reply({
  status: 200,
  body: { history: [{ role: 'user', content }] satisfies ChatMessage[] },
});

const pendingSseReply = () => ({
  ok: true,
  status: 200,
  body: {
    getReader: () => ({ read: () => new Promise(() => {}) }),
  },
});

const sseReply = (events: Record<string, unknown>[]): Response =>
  new Response(events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''), { status: 200 });

const openStock = async (name: string): Promise<void> => {
  fireEvent.click((await screen.findByText(name)).closest('tr')!);
};

const sendVcpChat = async (message: string): Promise<void> => {
  const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
  const sendButton = input.parentElement?.querySelector('button');
  if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
  fireEvent.change(input, { target: { value: message } });
  fireEvent.click(sendButton);
};

const isBefore = (first: HTMLElement, second: HTMLElement): boolean =>
  Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);

const confirmDelete = async (): Promise<void> => {
  fireEvent.click(screen.getByTitle('대화 내역 비우기'));
  fireEvent.click(await screen.findByRole('button', { name: '삭제' }));
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(`vcp_chat_session_id_${ALPHA.ticker}`, ALPHA_SESSION);
  localStorage.setItem(`vcp_chat_session_id_${BETA.ticker}`, BETA_SESSION);
  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
    if (init?.method === 'DELETE') return reply({ status: 200 });
    if (url.includes(ALPHA_SESSION)) return historyReply('알파 기존 대화');
    if (url.includes(BETA_SESSION)) return historyReply('베타 기존 대화');
    return reply({ status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);
});

describe('[CHAT-020] VCP 채팅 삭제 완료와 세션 경합', () => {
  it('삭제가 500이면 기존 대화를 유지하고 오류 모달을 표시한다', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'DELETE') return reply({ status: 500, body: { error: 'delete failed' } });
      if (String(input).includes('realtime-prices')) return reply({ status: 200, body: {} });
      return historyReply('알파 기존 대화');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');

    await confirmDelete();

    expect(await screen.findByText('알파 기존 대화')).toBeTruthy();
    expect(await screen.findByText('대화 삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.')).toBeTruthy();
  });

  it('메시지 삭제의 404는 최신 이력을 다시 읽어 이미 지워진 메시지를 화면에서 제거한다', async () => {
    let historyReads = 0;
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (init?.method === 'DELETE') return reply({ status: 404, body: { error: 'Message not found' } });
      historyReads += 1;
      return historyReads === 1
        ? reply({ status: 200, body: { history: [{ role: 'user', content: '이미 삭제된 질문' }] } })
        : reply({ status: 200, body: { history: [] } });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('이미 삭제된 질문');

    fireEvent.click(screen.getByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));

    await waitFor(() => expect(historyReads).toBe(2));
    expect(screen.queryByText('이미 삭제된 질문')).toBeNull();
    expect(localStorage.getItem(`vcp_chat_session_id_${ALPHA.ticker}`)).toBe(ALPHA_SESSION);
  });

  it('404 재조회도 세션이 없으면 그 종목 키만 버리고 환영 문구를 보인다', async () => {
    let wasDeleted = false;
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (init?.method === 'DELETE') {
        wasDeleted = true;
        return reply({ status: 404, body: { error: 'Session not found' } });
      }
      return wasDeleted ? reply({ status: 404, body: { error: 'Session not found' } }) : historyReply('알파 기존 대화');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');

    await confirmDelete();

    expect(await screen.findByText(/알파.*종목의 VCP 패턴/)).toBeTruthy();
    expect(localStorage.getItem(`vcp_chat_session_id_${ALPHA.ticker}`)).toBeNull();
    expect(localStorage.getItem(`vcp_chat_session_id_${BETA.ticker}`)).toBe(BETA_SESSION);
  });

  it('알파 삭제가 늦게 끝나도 이미 연 베타의 대화와 세션 키를 바꾸지 않는다', async () => {
    let resolveDelete!: (value: Response) => void;
    const delayedDelete = new Promise<Response>((resolve) => { resolveDelete = resolve; });
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return Promise.resolve(reply({ status: 200, body: {} }));
      if (init?.method === 'DELETE') return delayedDelete;
      if (url.includes(ALPHA_SESSION)) return Promise.resolve(historyReply('알파 기존 대화'));
      return Promise.resolve(historyReply('베타 기존 대화'));
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');
    await confirmDelete();

    await openStock(BETA.name);
    await screen.findByText('베타 기존 대화');
    await act(async () => resolveDelete(reply({ status: 200 })));

    expect(screen.getByText('베타 기존 대화')).toBeTruthy();
    expect(localStorage.getItem(`vcp_chat_session_id_${BETA.ticker}`)).toBe(BETA_SESSION);
  });

  it('첫 대화의 합성 환영문구는 서버 메시지 인덱스에 포함하지 않는다', async () => {
    const firstSessionId = 'first-alpha-session';
    localStorage.removeItem(`vcp_chat_session_id_${ALPHA.ticker}`);
    vi.stubGlobal('crypto', { randomUUID: () => firstSessionId });
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        return new Response(`data: ${JSON.stringify({ session_id: firstSessionId, answer_chunk: '첫 답변', done: true })}\n\n`, { status: 200 });
      }
      if (init?.method === 'DELETE') return reply({ status: 200 });
      if (url.includes(firstSessionId)) {
        return reply({
          status: 200,
          body: { history: [{ role: 'user', content: '첫 질문' }, { role: 'model', content: '첫 답변' }] },
        });
      }
      return reply({ status: 200, body: {} });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText(/알파.*종목의 VCP 패턴/);

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)');
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '첫 질문' } });
    fireEvent.click(sendButton);
    await screen.findByText('첫 답변');

    fireEvent.click(await screen.findByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, init]) =>
        String(url).includes('/api/kr/chatbot/history') && (init as RequestInit | undefined)?.method === 'DELETE');
      expect(deleteCall).toBeTruthy();
      expect(String(deleteCall?.[0])).toContain(`session_id=${firstSessionId}&index=0`);
    });
  });

  it('/help 뒤 첫 저장형 질문도 재동기화된 서버 인덱스로 삭제한다', async () => {
    const sessionId = 'command-then-question-session';
    localStorage.removeItem(`vcp_chat_session_id_${ALPHA.ticker}`);
    vi.stubGlobal('crypto', { randomUUID: () => sessionId });
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        const body = typeof init.body === 'string' ? JSON.parse(init.body) as { message: string } : { message: '' };
        const answer = body.message === '/help' ? '도움말 응답' : '저장형 답변';
        return new Response(`data: ${JSON.stringify({ session_id: sessionId, answer_chunk: answer, done: true })}\n\n`, { status: 200 });
      }
      if (init?.method === 'DELETE') return reply({ status: 200 });
      if (url.includes(sessionId)) {
        return reply({
          status: 200,
          body: { history: [{ role: 'user', content: '저장형 질문' }, { role: 'model', content: '저장형 답변' }] },
        });
      }
      return reply({ status: 200, body: {} });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText(/알파.*종목의 VCP 패턴/);

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '/help' } });
    fireEvent.click(sendButton);
    await screen.findByText('도움말 응답');

    fireEvent.change(input, { target: { value: '저장형 질문' } });
    fireEvent.click(sendButton);
    fireEvent.click(await screen.findByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, request]) =>
        String(url).includes('/api/kr/chatbot/history') && (request as RequestInit | undefined)?.method === 'DELETE');
      expect(String(deleteCall?.[0])).toContain(`session_id=${sessionId}&index=0`);
    });
  });

  it('/model은 비저장 명령으로 남기지 않고 EOF 이력에서 한 번만 확정한다', async () => {
    const sessionId = 'model-command-session';
    localStorage.removeItem(`vcp_chat_session_id_${ALPHA.ticker}`);
    vi.stubGlobal('crypto', { randomUUID: () => sessionId });
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        return new Response(`data: ${JSON.stringify({ session_id: sessionId, answer_chunk: '모델 응답', done: true })}\n\n`, { status: 200 });
      }
      if (init?.method === 'DELETE') return reply({ status: 200 });
      if (url.includes(sessionId)) {
        return reply({
          status: 200,
          body: { history: [{ role: 'user', content: '/model' }, { role: 'model', content: '모델 응답' }] },
        });
      }
      return reply({ status: 200, body: {} });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText(/알파.*종목의 VCP 패턴/);

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '/model' } });
    fireEvent.click(sendButton);
    await screen.findByTitle('이 질문 지우기');

    expect(screen.getAllByText('/model')).toHaveLength(1);
    fireEvent.click(screen.getByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));
    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, request]) =>
        String(url).includes('/api/kr/chatbot/history') && (request as RequestInit | undefined)?.method === 'DELETE');
      expect(String(deleteCall?.[0])).toContain(`session_id=${sessionId}&index=0`);
    });
  });

  it('50개 보관 이력도 GET이 부여한 마지막 서버 인덱스를 삭제에 쓴다', async () => {
    const history = Array.from({ length: 50 }, (_, serverMessageIndex) => ({
      role: 'user' as const,
      content: `질문 ${serverMessageIndex}`,
    }));
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (init?.method === 'DELETE') return reply({ status: 200 });
      if (url.includes(ALPHA_SESSION)) return reply({ status: 200, body: { history } });
      return reply({ status: 200, body: {} });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    const lastMessage = await screen.findByText('질문 49');
    const deleteButton = lastMessage.closest('.group')?.querySelector('[title="이 질문 지우기"]');
    if (!deleteButton) throw new Error('마지막 서버 메시지의 삭제 버튼을 찾을 수 없습니다.');
    fireEvent.click(deleteButton);
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, request]) =>
        String(url).includes('/api/kr/chatbot/history') && (request as RequestInit | undefined)?.method === 'DELETE');
      expect(String(deleteCall?.[0])).toContain(`session_id=${ALPHA_SESSION}&index=49`);
    });
  });

  it('확인 삭제가 진행 중일 때 /clear가 같은 세션을 두 번 삭제하지 않는다', async () => {
    const pendingDelete = new Promise<Response>(() => {});
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return Promise.resolve(reply({ status: 200, body: {} }));
      if (init?.method === 'DELETE') return pendingDelete;
      return Promise.resolve(historyReply('알파 기존 대화'));
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');
    await confirmDelete();

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)');
    fireEvent.change(input, { target: { value: '/clear' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      const deleteCalls = fetchMock.mock.calls.filter(([url, init]) =>
        String(url).includes('/api/kr/chatbot/history') && (init as RequestInit | undefined)?.method === 'DELETE');
      expect(deleteCalls).toHaveLength(1);
    });
  });

  it('스트리밍 중에는 미확정 메시지를 삭제할 수 없고 기존 서버 메시지 삭제도 비활성화한다', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return Promise.resolve(reply({ status: 200, body: {} }));
      if (url === '/api/kr/chatbot' && init?.method === 'POST') return Promise.resolve(pendingSseReply());
      return Promise.resolve(historyReply('알파 기존 대화'));
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button') as HTMLButtonElement | null;
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '스트리밍 중 질문' } });
    fireEvent.click(sendButton);
    await screen.findByText('스트리밍 중 질문');

    const storedDeleteButton = screen.getByTitle('이 질문 지우기') as HTMLButtonElement;
    expect(input.disabled).toBe(true);
    expect(storedDeleteButton.disabled).toBe(true);
    expect(screen.getAllByTitle('이 질문 지우기')).toHaveLength(1);
  });

  it('SSE 오류 뒤 EOF는 과거 이력으로 질문과 오류를 덮지 않고 입력을 다시 연다', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') return sseReply([{ error: '합성 서버 오류' }]);
      return historyReply('과거 이력');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('과거 이력');

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '오류가 난 질문' } });
    fireEvent.click(sendButton);

    await waitFor(() => expect(input.disabled).toBe(false));
    expect(screen.getByText('오류가 난 질문')).toBeTruthy();
    expect(screen.getByText('합성 서버 오류')).toBeTruthy();
  });

  it('done 없는 EOF는 부분 응답을 보존하고 스트리밍 잠금을 푼다', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') return sseReply([{ answer_chunk: '부분 응답' }]);
      return historyReply('과거 이력');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('과거 이력');

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '부분 응답 질문' } });
    fireEvent.click(sendButton);

    await waitFor(() => expect(input.disabled).toBe(false));
    expect(screen.getByText('부분 응답 질문')).toBeTruthy();
    expect(screen.getByText('부분 응답')).toBeTruthy();
  });

  it('SSE reader 실패는 스트리밍 placeholder를 정리해 입력 잠금을 남기지 않는다', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        return {
          ok: true,
          status: 200,
          body: { getReader: () => ({ read: () => Promise.reject(new Error('synthetic reader failure')) }) },
        };
      }
      return historyReply('과거 이력');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('과거 이력');

    const input = screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement;
    const sendButton = input.parentElement?.querySelector('button');
    if (!sendButton) throw new Error('VCP 채팅 전송 버튼을 찾을 수 없습니다.');
    fireEvent.change(input, { target: { value: '읽기 실패 질문' } });
    fireEvent.click(sendButton);

    await waitFor(() => expect(input.disabled).toBe(false));
    expect(screen.getByText('읽기 실패 질문')).toBeTruthy();
    expect(screen.getByText('⚠️ 서버와 통신이 원활하지 않습니다. 잠시 후 다시 시도해주세요.')).toBeTruthy();
  });

  it('서버 A 뒤 /help 뒤 서버 B는 화면에서도 A-help-B 순서를 유지한다', async () => {
    let historyReads = 0;
    const serverA = { role: 'user', content: '서버 A', timestamp: '2026-09-14T09:00:00Z' };
    const serverB = { role: 'user', content: '서버 B', timestamp: '2026-09-14T09:02:00Z' };
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        const body = typeof init.body === 'string' ? JSON.parse(init.body) as { message: string } : { message: '' };
        return sseReply([{ answer_chunk: body.message === '/help' ? '도움말 응답' : '서버 B 답변', done: true }]);
      }
      historyReads += 1;
      return reply({ status: 200, body: { history: historyReads === 1 ? [serverA] : [serverA, serverB] } });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('서버 A');

    await sendVcpChat('/help');
    await screen.findByText('도움말 응답');
    await sendVcpChat('서버 B 질문');
    await waitFor(() => expect(historyReads).toBe(2));

    const a = screen.getByText('서버 A');
    const help = screen.getByText('도움말 응답');
    const b = screen.getByText('서버 B');
    expect(isBefore(a, help)).toBe(true);
    expect(isBefore(help, b)).toBe(true);
  });

  it('도움말 앵커가 50개 보관 이력에서 잘려도 마지막 서버 메시지는 index 49로 삭제한다', async () => {
    let historyReads = 0;
    const initial = { role: 'user', content: '앵커 원본', timestamp: '2026-09-14T09:00:00Z' };
    const retained = Array.from({ length: 50 }, (_, index) => ({
      role: 'user',
      content: `보관 ${index}`,
      timestamp: `2026-09-14T10:${String(index).padStart(2, '0')}:00Z`,
    }));
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') {
        const body = typeof init.body === 'string' ? JSON.parse(init.body) as { message: string } : { message: '' };
        return sseReply([{ answer_chunk: body.message === '/help' ? '도움말 응답' : '동기화 답변', done: true }]);
      }
      if (init?.method === 'DELETE') return reply({ status: 200 });
      historyReads += 1;
      return reply({ status: 200, body: { history: historyReads === 1 ? [initial] : retained } });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('앵커 원본');
    await sendVcpChat('/help');
    await screen.findByText('도움말 응답');
    await sendVcpChat('동기화 질문');
    await waitFor(() => expect(historyReads).toBe(2));

    const lastMessage = screen.getByText('보관 49');
    const deleteButton = lastMessage.closest('.group')?.querySelector('[title="이 질문 지우기"]');
    if (!deleteButton) throw new Error('50개 보관 이력의 마지막 삭제 버튼을 찾을 수 없습니다.');
    fireEvent.click(deleteButton);
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));
    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, request]) =>
        String(url).includes('/api/kr/chatbot/history') && (request as RequestInit | undefined)?.method === 'DELETE');
      expect(String(deleteCall?.[0])).toContain(`session_id=${ALPHA_SESSION}&index=49`);
    });
  });

  it('앵커 메시지 삭제가 404여도 재조회된 서버 B는 index 0으로 삭제한다', async () => {
    let historyReads = 0;
    let deleteCalls = 0;
    const serverA = { role: 'user', content: '앵커 A', timestamp: '2026-09-14T09:00:00Z' };
    const serverB = { role: 'user', content: '재조회 B', timestamp: '2026-09-14T09:02:00Z' };
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (url === '/api/kr/chatbot' && init?.method === 'POST') return sseReply([{ answer_chunk: '도움말 응답', done: true }]);
      if (init?.method === 'DELETE') {
        deleteCalls += 1;
        return reply({ status: deleteCalls === 1 ? 404 : 200 });
      }
      historyReads += 1;
      return reply({ status: 200, body: { history: historyReads === 1 ? [serverA] : [serverB] } });
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('앵커 A');
    await sendVcpChat('/help');
    await screen.findByText('도움말 응답');

    fireEvent.click(screen.getByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));
    await screen.findByText('재조회 B');
    fireEvent.click(screen.getByTitle('이 질문 지우기'));
    fireEvent.click(await screen.findByRole('button', { name: '삭제' }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.filter(([url, request]) =>
        String(url).includes('/api/kr/chatbot/history') && (request as RequestInit | undefined)?.method === 'DELETE').at(-1);
      expect(String(deleteCall?.[0])).toContain(`session_id=${ALPHA_SESSION}&index=0`);
    });
  });

  it('삭제 확인을 연 뒤 종목이 바뀌어도 처음 선택한 종목 세션만 삭제한다', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return reply({ status: 200, body: {} });
      if (init?.method === 'DELETE') return reply({ status: 200 });
      if (url.includes(ALPHA_SESSION)) return historyReply('알파 기존 대화');
      return historyReply('베타 기존 대화');
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');
    fireEvent.click(screen.getByTitle('이 질문 지우기'));
    await screen.findByRole('button', { name: '삭제' });

    await openStock(BETA.name);
    fireEvent.click(screen.getByRole('button', { name: '삭제' }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([url, init]) =>
        String(url).includes('/api/kr/chatbot/history') && (init as RequestInit | undefined)?.method === 'DELETE');
      expect(String(deleteCall?.[0])).toContain(`session_id=${ALPHA_SESSION}&index=0`);
    });
  });

  it('종목 전환 중에는 이전 종목 이력을 남겨 삭제 대상으로 만들지 않는다', async () => {
    const pendingBetaHistory = new Promise<Response>(() => {});
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('realtime-prices')) return Promise.resolve(reply({ status: 200, body: {} }));
      if (init?.method === 'DELETE') return Promise.resolve(reply({ status: 200 }));
      if (url.includes(ALPHA_SESSION)) return Promise.resolve(historyReply('알파 기존 대화'));
      return pendingBetaHistory;
    });
    render(<VCPPage />);
    await openStock(ALPHA.name);
    await screen.findByText('알파 기존 대화');

    await openStock(BETA.name);
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes(BETA_SESSION))).toBe(true));

    expect(screen.queryByText('알파 기존 대화')).toBeNull();
    expect(screen.queryByTitle('이 질문 지우기')).toBeNull();
  });
});


it('POST 응답 대기 중 종목을 바꾸면 늦은 응답이 새 채팅을 잠그지 않는다', async () => {
  let resolvePost: ((response: Response) => void) | undefined;
  const pendingPost = new Promise<Response>((resolve) => { resolvePost = resolve; });
  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/api/kr/chatbot' && init?.method === 'POST') return pendingPost;
    if (url.includes(ALPHA_SESSION)) return historyReply('알파 저장 대화');
    if (url.includes(BETA_SESSION)) return historyReply('베타 저장 대화');
    return reply({ status: 200, body: {} });
  });
  render(<VCPPage />);
  await openStock(ALPHA.name);
  await screen.findByText('알파 저장 대화');
  await sendVcpChat('늦은 알파 질문');
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === '/api/kr/chatbot' && init?.method === 'POST')).toBe(true));
  fireEvent.click(screen.getAllByRole('button', { name: '차트 닫기' })[0]);
  await openStock(BETA.name);
  await screen.findByText('베타 저장 대화');
  await act(async () => {
    if (!resolvePost) throw new Error('pending POST missing');
    resolvePost(sseReply([{ answer_chunk: '늦은 알파 답변', done: true }]));
  });
  expect((screen.getByPlaceholderText('AI에게 질문하기... (/ 명령어)') as HTMLInputElement).disabled).toBe(false);
  expect(screen.queryByText('늦은 알파 답변')).toBeNull();
  expect(localStorage.getItem(`vcp_chat_session_id_${BETA.ticker}`)).toBe(BETA_SESSION);
});
