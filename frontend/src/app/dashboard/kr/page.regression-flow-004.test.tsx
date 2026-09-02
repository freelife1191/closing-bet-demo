// Regression: [FLOW-004] 백테스트 상태 어휘와 소비자가 어긋나 있던 문제
//
// 두 전략 카드의 확인 아이콘은 status === 'OK' 일 때만 켜졌다. 그런데 'OK' 는 VCP 쪽
// 임시값이라 거래가 0건일 때만 살아남았고, 종가베팅 쪽은 그 값을 아예 내지 않았다.
// 그래서 성적을 판정받은 전략에는 확인 표시가 붙지 않고, 집계할 것이 없는 구간에만
// 붙었다. 이제는 판정이 끝난 세 값에서만 켜진다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KRDashboardPage from './page';

const fetchAPIMock = vi.fn();

vi.mock('@/lib/api', () => ({
  fetchAPI: (...args: unknown[]) => fetchAPIMock(...args),
  krAPI: {
    getMarketGate: vi.fn(async () => ({ status: 'GREEN', score: 70, message: '' })),
    getSignals: vi.fn(async () => ({ signals: [], count: 0 })),
    getDataStatus: vi.fn(async () => ({ data: {} })),
  },
}));

beforeEach(() => {
  fetchAPIMock.mockReset();
  // 화면이 마운트되면서 폴링 간격 설정을 직접 fetch 로 읽는다. 목하지 않으면
  // jsdom 이 상대 경로를 URL 로 만들지 못해 매 검사마다 예외가 찍힌다.
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) })));
});

describe('[FLOW-004] 백테스트 확인 아이콘', () => {
  it.each([
    // BAD 는 성적이 나쁘다는 판정이지 미집계가 아니므로 표시가 켜져야 한다.
    ['GOOD', 'EXCELLENT', 2],
    ['BAD', 'BAD', 2],
    ['PENDING', 'OK (New)', 0],
    // 캐시에 남아 있던 예전 응답이 그대로 도착해도 판정 집합 밖이라 켜지지 않는다.
    ['OK', 'OK', 0],
  ])('vcp=%s, closing_bet=%s 이면 확인 표시가 %i 개', async (vcp, closingBet, expected) => {
    fetchAPIMock.mockResolvedValue({
      vcp: { status: vcp, count: 12, win_rate: 55, avg_return: 3.1 },
      closing_bet: { status: closingBet, count: 8, win_rate: 62, avg_return: 2.4, candidates: [] },
    });

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));
    expect(container.querySelectorAll('i.fa-check-circle')).toHaveLength(expected);
  });
});
