// Regression: [FLOW-009][VCP-025][JONGGA-036] 성과 판정 전 상태를 저조 성과처럼 보이게 한 문제
//
// 백테스트가 아직 거래를 축적하거나 종료 거래를 기다리는 동안에도 화면은 0%·미흡 배지와
// 보수적 대응 조언을 냈다. 수치가 없다는 사실을 나쁜 성과로 바꾸지 않도록, 두 전략 카드가
// 같은 상태 정책을 쓰고 판정이 끝난 뒤에만 실제 성과를 보이는지 고정한다.

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomePage from '@/app/page';
import KRDashboardPage from './page';

const fetchAPIMock = vi.fn();

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: (...args: unknown[]) => fetchAPIMock(...args),
  krAPI: {
    getMarketGate: vi.fn(async () => ({ status: 'GREEN', score: 70, message: '' })),
    getSignals: vi.fn(async () => ({ signals: [], count: 0 })),
    getDataStatus: vi.fn(async () => ({ data: {} })),
  },
}));

interface BacktestFixture {
  status?: string;
  count: number;
  winRate: number;
  avgReturn: number;
}

const getStrategyCard = (name: string): HTMLElement => {
  const card = screen.getByText(name).closest('div.group');
  if (!(card instanceof HTMLElement)) {
    throw new Error(`${name} 성과 카드를 찾지 못했습니다.`);
  }
  return card;
};

const getPerformanceThemeClass = (card: HTMLElement): string | undefined =>
  card.className.split(' ').find((className) => className.startsWith('hover:border-'));

const renderDashboardWith = async (fixture: BacktestFixture): Promise<[HTMLElement, HTMLElement]> => {
  fetchAPIMock.mockResolvedValue({
    vcp: {
      status: fixture.status,
      count: fixture.count,
      win_rate: fixture.winRate,
      avg_return: fixture.avgReturn,
    },
    closing_bet: {
      status: fixture.status,
      count: fixture.count,
      win_rate: fixture.winRate,
      avg_return: fixture.avgReturn,
      candidates: [],
    },
  });

  render(<KRDashboardPage />);

  await waitFor(() => expect(screen.getByText('VCP 전략')).toBeTruthy());

  return [getStrategyCard('VCP 전략'), getStrategyCard('종가베팅 전략')];
};

beforeEach(() => {
  fetchAPIMock.mockReset();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) })));
});

describe('[FLOW-009][VCP-025][JONGGA-036] 두 전략 카드의 성과 상태', () => {
  it.each([
    ['Accumulating', '축적 중', '데이터를 축적하고 있습니다.', 4, 62.5, 4.2],
    ['OK (New)', '신규 · 판정 전', '신규 자료를 모으고 있습니다.', 1, 62.5, 4.2],
    ['PENDING', '집계 전', '종료된 거래가 없어 집계 전입니다.', 6, 62.5, 4.2],
    [undefined, '확인 전', '상태를 확인하고 있습니다.', 0, 62.5, 4.2],
    // 외부 응답의 임의 문자열이 Object.prototype 키여도 중립 unknown으로 떨어져야 한다.
    ['toString', '확인 전', '상태를 확인하고 있습니다.', 0, 62.5, 4.2],
  ])(
    '%s 상태는 두 전략에 중립 라벨·건수만 보이고 성적 수치나 조언을 보이지 않는다',
    async (status, label, description, count, winRate, avgReturn) => {
      const [vcpCard, closingBetCard] = await renderDashboardWith({
        status,
        count,
        winRate,
        avgReturn,
      });

      expect(screen.getAllByText(label)).toHaveLength(2);
      for (const card of [vcpCard, closingBetCard]) {
        const cardText = card.textContent ?? '';
        expect(within(card).getByText(description)).toBeTruthy();
        // 기존 0건 표기는 No trades다. 상태 표시 변경은 이 공통 형식을 바꾸지 않는다.
        expect(within(card).getByText(count === 0 ? 'No trades' : `${count} trades`)).toBeTruthy();
        expect(cardText).not.toContain(`${winRate}%`);
        expect(cardText).not.toContain(`Avg. +${avgReturn}%`);
        expect(cardText).not.toContain('보수적 대응이 필요합니다.');
        expect(card.querySelector('i.fa-check-circle')).toBeNull();
      }
      expect(getPerformanceThemeClass(vcpCard)).toBe(getPerformanceThemeClass(closingBetCard));
    }
  );

  it.each([
    ['EXCELLENT', '우수', 62.5, 4.2],
    ['GOOD', '양호', 58.3, 3.8],
    ['BAD', '미흡', 0, -3],
  ])('%s 상태는 두 전략에 실제 성과와 같은 판정 아이콘을 보인다', async (status, label, winRate, avgReturn) => {
    const [vcpCard, closingBetCard] = await renderDashboardWith({
      status,
      count: 16,
      winRate,
      avgReturn,
    });

    expect(screen.getAllByText(label)).toHaveLength(2);
    for (const card of [vcpCard, closingBetCard]) {
      const cardText = card.textContent ?? '';
      expect(cardText).toContain(`${winRate}%`);
      expect(cardText).toContain(`Avg. ${avgReturn > 0 ? '+' : ''}${avgReturn}%`);
      expect(within(card).getByText('16 trades')).toBeTruthy();
      expect(card.querySelector('i.fa-check-circle')).not.toBeNull();
    }
    expect(getPerformanceThemeClass(vcpCard)).toBe(getPerformanceThemeClass(closingBetCard));
    expect(vcpCard.querySelector('i.fa-check-circle')?.className).toBe(
      closingBetCard.querySelector('i.fa-check-circle')?.className
    );
  });

  it('VCP의 백테스트 +15/-5와 시그널 기본 +5/-3을 서로 구분해 안내한다', async () => {
    const [vcpCard] = await renderDashboardWith({
      status: 'GOOD',
      count: 16,
      winRate: 58.3,
      avgReturn: 3.8,
    });

    const vcpCardText = vcpCard.textContent ?? '';
    expect(vcpCardText).toContain('VCP 백테스트는 익절 +15%, 손절 -5% 기준입니다.');
    expect(vcpCardText).toContain('개별 시그널의 기본 목표·손절은 +5%/-3%입니다.');
  });

  it('기준표는 OPEN을 승률에서 빼고 평균 손익에는 현재 평가를 넣는다고 안내한다', async () => {
    await renderDashboardWith({
      status: 'GOOD',
      count: 16,
      winRate: 58.3,
      avgReturn: 3.8,
    });

    fireEvent.click(screen.getAllByRole('button', { name: '기준표' })[0]);

    const guideText = screen.getByRole('dialog').textContent ?? '';
    expect(guideText).toContain('익절 횟수 / (익절+손절 횟수)');
    expect(guideText).toContain('(청산 수익률 합 + OPEN 평가수익률 합) / 전체 신호 수');
  });
});

describe('[JONGGA-036] 홈 랜딩의 종가베팅 설명', () => {
  it('저장 가격 우선, 누락 기본값, OPEN 처리와 가정 기대값을 함께 밝힌다', () => {
    render(<HomePage />);

    expect(screen.getByText('저장된 목표가·손절가를 우선 적용합니다.')).toBeTruthy();
    expect(screen.getByText('누락 시 기본 익절 +5%, 손절 -3%를 사용합니다.')).toBeTruthy();
    // 정정: OPEN의 현재 평가는 누적 ROI에 남는다. 승률의 분모에만 넣지 않는다.
    expect(screen.getByText('미청산(OPEN)은 계속 추적하며 승률 계산에서 제외합니다.')).toBeTruthy();
    expect(
      screen.getByText('승률 60% 가정 기대값은 +1.8%이며 수수료·세금 등 비용은 제외합니다.')
    ).toBeTruthy();
    expect(screen.getByText('+5% / -3%')).toBeTruthy();
    expect(screen.getByText('+1.8%')).toBeTruthy();
    expect(screen.queryByText(/익절 \+9% \/ 손절 -5% \/ 최대 보유 15일/)).toBeNull();
  });
});
