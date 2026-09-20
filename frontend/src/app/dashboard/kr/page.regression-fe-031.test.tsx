// Regression: [FE-031] 관리자 갱신 실패가 콘솔에만 남던 문제
//
// Market Gate 갱신의 일반 오류와 Refresh Data의 HTTP/본문/네트워크/timeout 오류가
// 사용자에게 보이지 않았다. Refresh Data도 공용 fetchAPI를 거쳐야 같은 10초 timeout과
// 오류 계약을 쓰며, 403은 기존 권한 회수 모달을 계속 사용한다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KRDashboardPage from './page';

const { mockUseAdmin, mockUpdateMarketGate } = vi.hoisted(() => ({
  mockUseAdmin: vi.fn(() => ({ isAdmin: true, isLoading: false })),
  mockUpdateMarketGate: vi.fn(),
}));

const fetchAPIMock = vi.fn();

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => mockUseAdmin(),
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: (...args: unknown[]) => fetchAPIMock(...args),
  krAPI: {
    getMarketGate: vi.fn(async () => ({ status: 'GREEN', score: 70, message: '' })),
    getSignals: vi.fn(async () => ({ signals: [], count: 0 })),
    getDataStatus: vi.fn(async () => ({ data: {} })),
    updateMarketGate: (...args: unknown[]) => mockUpdateMarketGate(...args),
  },
}));

const BACKTEST_SUMMARY = {
  vcp: { status: 'GOOD', count: 12, win_rate: 55, avg_return: 3.1 },
  closing_bet: { status: 'GOOD', count: 8, win_rate: 62, avg_return: 2.4, candidates: [] },
};

const apiError = (message: string, status?: number) =>
  status === undefined ? new Error(message) : Object.assign(new Error(message), { status });

const refreshButton = (): HTMLButtonElement =>
  screen.getByRole('button', { name: /Refresh Data/ });

const renderReadyDashboard = async (): Promise<void> => {
  render(<KRDashboardPage />);
  await screen.findByRole('button', { name: /Refresh Data/ });
  await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));
};

beforeEach(() => {
  fetchAPIMock.mockReset();
  fetchAPIMock.mockResolvedValue(BACKTEST_SUMMARY);
  mockUpdateMarketGate.mockReset();
  mockUpdateMarketGate.mockResolvedValue({});
  mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false }));
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ interval: 30 }) })));
});

describe('[FE-031] 관리자 갱신 실패 안내', () => {
  it('Market Gate 갱신의 일반 오류를 alert로 알리고 스피너를 푼다', async () => {
    mockUpdateMarketGate.mockRejectedValueOnce(new Error('갱신 실패'));
    await renderReadyDashboard();

    fireEvent.click(screen.getByRole('button', { name: 'Market Gate 새로고침' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('갱신 실패');
    expect(screen.getByRole('button', { name: 'Market Gate 새로고침' })).not.toBeDisabled();
  });

  it.each([
    ['HTTP 500', apiError('API Error: 500', 500)],
    ['HTML 500', apiError('API Error: 500', 500)],
    ['네트워크', new TypeError('Network failed')],
    ['10초 timeout', new Error('Request timed out')],
  ])('Refresh Data %s 오류를 alert로 알리고 공용 fetchAPI를 사용한다', async (_kind, error) => {
    fetchAPIMock.mockImplementation(async (path: string) => {
      if (path === '/api/kr/refresh') throw error;
      return BACKTEST_SUMMARY;
    });
    await renderReadyDashboard();

    fireEvent.click(refreshButton());

    expect(await screen.findByRole('alert')).toHaveTextContent('데이터 갱신');
    expect(fetchAPIMock).toHaveBeenCalledWith(
      '/api/kr/refresh',
      expect.objectContaining({ method: 'POST' })
    );
    expect(refreshButton()).not.toBeDisabled();
  });

  it('실패 뒤 재시도가 성공하면 오류를 지운다', async () => {
    fetchAPIMock.mockImplementationOnce(async (path: string) => {
      if (path === '/api/kr/backtest-summary') return BACKTEST_SUMMARY;
      return BACKTEST_SUMMARY;
    }).mockRejectedValueOnce(new Error('Request timed out')).mockResolvedValue(BACKTEST_SUMMARY);
    await renderReadyDashboard();

    const button = refreshButton();
    fireEvent.click(button);
    await screen.findByRole('alert');

    fireEvent.click(button);

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    expect(refreshButton()).not.toBeDisabled();
  });

  it('Refresh Data 403은 기존 권한 회수 동작을 보존한다', async () => {
    fetchAPIMock.mockImplementation(async (path: string) => {
      if (path === '/api/kr/refresh') throw apiError('Forbidden', 403);
      return BACKTEST_SUMMARY;
    });
    await renderReadyDashboard();

    fireEvent.click(refreshButton());

    expect(await screen.findByRole('dialog')).toHaveTextContent('권한 없음');
    expect(screen.queryByRole('button', { name: /Refresh Data/ })).toBeNull();
  });
});
