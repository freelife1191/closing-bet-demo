// Regression: [JONGGA-037, JONGGA-032] — 완료 상태와 화면 이탈 뒤 polling 수명

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;
interface StatusResponse {
  is_running?: boolean;
  isRunning?: boolean;
  message?: string;
}

const api = vi.hoisted(() => ({
  fetchAPI: vi.fn(),
  statusResponses: [] as Array<StatusResponse | Promise<StatusResponse>>,
  defaultStatus: { is_running: false } as StatusResponse | Promise<StatusResponse>,
  runRequest: () => Promise.resolve({ status: 'started' }),
}));

vi.mock('@/lib/api', () => ({ fetchAPI: api.fetchAPI }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: true, isLoading: false }) }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

function statusCallCount() {
  return api.fetchAPI.mock.calls.filter(([path]) => path === '/api/kr/jongga-v2/status').length;
}

async function renderAndStartUpdate() {
  const view = render(<JonggaV2Page />);
  await screen.findByRole('heading', { name: '태웅' });

  vi.useFakeTimers();
  fireEvent.click(screen.getByRole('button', { name: '스크리너 전체 업데이트' }));
  fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: '실행' }));
  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByText('RUNNING...')).toBeTruthy();
  return view;
}

beforeEach(() => {
  // [JONGGA-044] 고정 자료의 KST 날짜와 가짜 타이머가 앞당긴 시각이 자정을 넘어 어긋나지 않게 KST 정오에 고정한다.
  // 가짜 타이머 전이라 Date 만 고정되고, 뒤이은 useFakeTimers 가 이 시각에서 시작하며 afterEach 의 useRealTimers 가 되돌린다
  vi.setSystemTime(new Date(TODAY()));
  api.fetchAPI.mockReset();
  api.statusResponses = [];
  api.defaultStatus = { is_running: false };
  api.runRequest = () => Promise.resolve({ status: 'started' });
  api.fetchAPI.mockImplementation(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 1,
        filtered_count: 1,
        signals: [{
          stock_code: '044490',
          stock_name: '태웅',
          market: 'KOSDAQ',
          sector: '기계',
          grade: 'B',
          score: { total: 12, base_score: 12, bonus_score: 0 },
          checklist: { has_news: false, volume_surge: false, supply_positive: false },
          current_price: 37_250,
          entry_price: 37_200,
          stop_price: 36_084,
          target_price: 39_060,
          change_pct: 11.5,
          trading_value: 100_000_000_000,
          signal_date: KST_DATE.format(new Date()),
        }],
        updated_at: TODAY(),
        status: 'ok',
      };
    }
    if (path === '/api/kr/jongga-v2/run') return api.runRequest();
    if (path === '/api/kr/jongga-v2/status') {
      return api.statusResponses.shift() ?? api.defaultStatus;
    }
    return {};
  });
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe('[JONGGA-037] 완료 상태 polling', () => {
  it('완료 응답 뒤 버튼을 풀고 재조회한 뒤 polling을 멈춘다', async () => {
    api.statusResponses = [{ is_running: false }];
    await renderAndStartUpdate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(screen.getByText('UPDATED')).toBeTruthy();
    expect(api.fetchAPI.mock.calls.filter(([path]) => path === '/api/kr/jongga-v2/latest')).toHaveLength(2);
    expect(statusCallCount()).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(statusCallCount()).toBe(1);
  });

  it('409 뒤 진행 상태를 거쳐 완료하면 같은 방식으로 polling을 끝낸다', async () => {
    api.runRequest = () => Promise.reject(Object.assign(new Error('already running'), { status: 409 }));
    api.statusResponses = [
      { is_running: true, message: '스크리너 실행 중' },
      { is_running: false },
    ];
    await renderAndStartUpdate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText('RUNNING...')).toBeTruthy();
    expect(screen.getByText('스크리너 실행 중')).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText('UPDATED')).toBeTruthy();
    expect(statusCallCount()).toBe(2);
  });

  it('안전 timeout 뒤 늦은 상태 응답은 화면이나 polling을 되살리지 않는다', async () => {
    let resolveStatus: (value: StatusResponse) => void = () => undefined;
    const pendingStatus = new Promise<StatusResponse>((resolve) => {
      resolveStatus = resolve;
    });
    api.defaultStatus = pendingStatus;
    await renderAndStartUpdate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    const callsBeforeTimeout = statusCallCount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(348_000);
    });
    expect(screen.getByText('UPDATED')).toBeTruthy();
    expect(statusCallCount()).toBe(callsBeforeTimeout);
    expect(vi.getTimerCount()).toBe(0);
    const callsAfterTimeout = statusCallCount();

    await act(async () => {
      resolveStatus({ is_running: false });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(screen.getByText('UPDATED')).toBeTruthy();
    expect(statusCallCount()).toBe(callsAfterTimeout);
  });
});

describe('[JONGGA-032] 화면 이탈 polling 정리', () => {
  it('실행 중 status 응답이 늦어도 화면 이탈 뒤 재조회나 다음 polling을 만들지 않는다', async () => {
    let resolveStatus: (value: StatusResponse) => void = () => undefined;
    api.statusResponses = [new Promise<StatusResponse>((resolve) => {
      resolveStatus = resolve;
    })];
    const { unmount } = await renderAndStartUpdate();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(statusCallCount()).toBe(1);
    expect(api.fetchAPI.mock.calls.filter(([path]) => path === '/api/kr/jongga-v2/latest')).toHaveLength(1);

    unmount();
    await act(async () => {
      resolveStatus({ is_running: false });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(statusCallCount()).toBe(1);
    expect(api.fetchAPI.mock.calls.filter(([path]) => path === '/api/kr/jongga-v2/latest')).toHaveLength(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('늦은 run POST 응답 뒤 화면을 떠났으면 polling을 시작하지 않는다', async () => {
    let resolveRun: (value: { status: string }) => void = () => undefined;
    api.runRequest = () => new Promise<{ status: string }>((resolve) => {
      resolveRun = resolve;
    });
    const { unmount } = await renderAndStartUpdate();
    unmount();

    await act(async () => {
      resolveRun({ status: 'started' });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(statusCallCount()).toBe(0);
  });
});
