// Regression: [VCP-002] — 조회 날짜를 바꿔도 현재가 갱신이 이전 목록의 종목을 조회하고,
// 스크리너 상태 폴링이 언마운트 뒤에도 계속 돌던 문제
// 근거: docs/dev-cycle/audits/AUDIT-VCP.md §1.2, §4.1
//
// 갱신 effect 의 의존성이 `signals.length` 라서, 목록이 통째로 교체되어도 개수가 같으면
// 다시 실행되지 않고 클로저가 이전 목록을 붙든다. 목록 상한이 20으로 고정되어 있어
// 개수가 일치하는 상황은 드물지 않다. 여기서는 양쪽 모두 한 종목으로 맞춰 재현한다.
//
// 다만 지금은 `loadSignals` 가 매번 `setLoading(true)` 로 시작해, loading 전환이 effect 를
// 대신 재실행시키므로 화면에 드러나지는 않았다. 방어가 우연이라 아래 첫 검사는 옛 의존성을
// 그대로 두어도 통과한다. 변이 검사로 경계를 확인했다. 옛 의존성에서 `setLoading(true)` 를
// 빼면 첫 검사가 실패하고, 새 의존성에서는 같은 조건에서도 통과한다.
//
// 폴링 쪽은 `checkRunningStatus` 와 스크리너 실행 버튼이 만드는 setInterval 핸들이 어떤
// ref 에도 담기지 않아, 언마운트 정리가 이 둘을 찾지 못했다.

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const baseSignal = {
  signal_date: '2026-05-05',
  score: 90,
  is_vcp: true,
  contraction_ratio: 0.41,
  entry_price: 100_000,
  current_price: 110_000,
};

// 최신과 과거의 개수를 똑같이 한 종목으로 맞춘다. 개수가 다르면 결함이 있는 코드도
// 우연히 통과하므로, 내용만 다르고 길이가 같은 상황이 이 검사의 핵심이다.
const LATEST = [{ ...baseSignal, ticker: '000001', name: '최신종목' }];
const HISTORY = [{ ...baseSignal, ticker: '000002', name: '과거종목' }];

const getVCPStatus = vi.hoisted(() => vi.fn(async () => ({ running: false })));
const runVCPScreener = vi.hoisted(() => vi.fn(async () => ({ status: 'started' })));

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async (date?: string) => ({
      signals: date ? HISTORY : LATEST,
      total_scanned: 1,
      source: 'test',
    })),
    getSignalDates: vi.fn(async () => ['2026-05-05']),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus,
    runVCPScreener,
    getStockChart: vi.fn(async () => ({ ticker: '000001', data: [] })),
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

let fetchMock: ReturnType<typeof vi.fn>;

const requestedTickers = (): string[][] =>
  fetchMock.mock.calls
    .filter(([url]) => String(url).includes('realtime-prices'))
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)).tickers);

beforeEach(() => {
  getVCPStatus.mockReset();
  getVCPStatus.mockResolvedValue({ running: false } as any);
  runVCPScreener.mockClear();
  fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('[VCP-002] 현재가 갱신 대상과 폴링 정리', () => {
  it('날짜를 바꿔 목록이 교체되면 개수가 같아도 새 종목의 현재가를 조회한다', async () => {
    render(<VCPPage />);

    await waitFor(() => expect(requestedTickers().length).toBeGreaterThan(0));
    expect(requestedTickers().at(-1)).toEqual(['000001']);

    fireEvent.click(screen.getByRole('button', { name: '과거' }));
    fireEvent.click(await screen.findByRole('button', { name: '2026-05-05' }));

    await waitFor(() => {
      expect(requestedTickers().at(-1)).toEqual(['000002']);
    });
  });

  it('현재가만 갱신되었을 때는 조회를 다시 걸지 않는다', async () => {
    // 응답이 오면 setSignals 가 돌아 signals 참조가 바뀐다. 의존성을 signals 로 두면
    // 여기서 effect 가 다시 실행되어 폴링이 무한히 재생성된다.
    fetchMock.mockImplementation(async () => ({
      ok: true,
      json: async () => ({ '000001': 120_000 }),
    }));

    render(<VCPPage />);
    await waitFor(() => expect(requestedTickers().length).toBeGreaterThan(0));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(requestedTickers()).toHaveLength(1);
  });

  it('언마운트하면 스크리너 상태 폴링이 멈춘다', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getVCPStatus.mockResolvedValue({ running: true, message: '분석 중', progress: 10 } as any);

    const { unmount } = render(<VCPPage />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    const whileMounted = getVCPStatus.mock.calls.length;
    expect(whileMounted).toBeGreaterThan(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(getVCPStatus.mock.calls.length).toBe(whileMounted);
  });

  it('스크리너 실행 버튼이 만든 폴링도 언마운트에서 멈춘다', async () => {
    // 앞 검사가 보는 것은 마운트 복구 경로의 폴링이다. 버튼이 만드는 폴링은 다른
    // 자리에 있고 같은 ref 를 공유하므로, 한쪽만 검사하면 다른 쪽 배선이 끊겨도
    // 드러나지 않는다. 여기서는 복구 경로를 쉬게 두고 버튼 쪽만 돌린다.
    const { unmount } = render(<VCPPage />);
    const runButton = await screen.findByRole('button', { name: 'Refresh VCP' });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    getVCPStatus.mockResolvedValue({ running: true, status: 'running', message: '분석 중', progress: 10 } as any);

    await act(async () => {
      fireEvent.click(runButton);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(runVCPScreener).toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    const whileMounted = getVCPStatus.mock.calls.length;
    expect(whileMounted).toBeGreaterThan(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(getVCPStatus.mock.calls.length).toBe(whileMounted);
  });
});
