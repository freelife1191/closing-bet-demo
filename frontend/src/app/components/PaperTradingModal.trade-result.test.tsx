import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import PaperTradingModal from './PaperTradingModal';

// [FE-003] 회귀 검사. 백엔드는 잔고 부족이나 보유 수량 초과 같은 거절을 예외가 아니라
// HTTP 200 + {status:'error'} 로 돌려준다. 응답 본문을 읽지 않으면 거절이 완료로 보인다.

vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addCandlestickSeries: () => ({ setData: vi.fn() }),
    addLineSeries: () => ({ setData: vi.fn() }),
    addSeries: () => ({ setData: vi.fn(), priceToCoordinate: vi.fn(() => 0) }),
    timeScale: () => ({ fitContent: vi.fn() }),
    subscribeCrosshairMove: vi.fn(),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }),
  ColorType: { Solid: 'solid' },
  LineStyle: { Solid: 0 },
  AreaSeries: {},
  LineSeries: {},
}));

// 두 주문 모달을 핸들러 호출 버튼으로 대체한다. 입력 화면을 거치지 않고
// handleBuySubmit·handleSellSubmit 의 응답 처리만 확인하기 위해서다.
vi.mock('./BuyStockModal', () => ({
  default: ({ onBuy }: any) => (
    <button onClick={() => onBuy('005930', '삼성전자', 70_000, 1)}>매수요청</button>
  ),
}));
vi.mock('./SellStockModal', () => ({
  default: ({ onSell }: any) => (
    <button onClick={() => onSell('005930', '삼성전자', 70_000, 1)}>매도요청</button>
  ),
}));
vi.mock('./ConfirmationModal', () => ({ default: () => null }));

const mockPortfolio = {
  holdings: [],
  cash: 100_000_000,
  total_asset_value: 100_000_000,
  total_stock_value: 0,
  total_profit: 0,
  total_profit_rate: 0,
  total_principal: 100_000_000,
};

vi.mock('@/lib/api', () => ({
  paperTradingAPI: {
    getPortfolio: vi.fn(async () => mockPortfolio),
    getChartData: vi.fn(async () => ({ data: [] })),
    getAssetHistory: vi.fn(async () => ({ history: [] })),
    getTradeHistory: vi.fn(async () => ({ trades: [] })),
    deposit: vi.fn(async () => ({})),
    reset: vi.fn(async () => ({})),
    buy: vi.fn(async () => ({ status: 'success', message: 'ok' })),
    sell: vi.fn(async () => ({ status: 'success', message: 'ok' })),
  },
}));

import { paperTradingAPI } from '@/lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
});

function renderOpen() {
  return render(<PaperTradingModal isOpen onClose={vi.fn()} />);
}

async function clickTrade(label: string) {
  await act(async () => {
    fireEvent.click(screen.getByText(label));
  });
}

describe('매수 결과 처리', () => {
  it('HTTP 200 으로 도착한 거절을 실패로 표시한다', async () => {
    (paperTradingAPI.buy as any).mockResolvedValueOnce({
      status: 'error',
      message: '잔고 부족 (필요: 70,000원, 보유: 0원)',
    });
    renderOpen();

    await clickTrade('매수요청');

    expect(window.alert).toHaveBeenCalledWith(
      '매수 실패: 잔고 부족 (필요: 70,000원, 보유: 0원)',
    );
    expect(window.alert).not.toHaveBeenCalledWith(
      expect.stringContaining('매수 완료'),
    );
  });

  it('성공 응답에는 완료를 표시한다', async () => {
    renderOpen();

    await clickTrade('매수요청');

    expect(window.alert).toHaveBeenCalledWith('삼성전자 1주 매수 완료');
  });

  it('예외로 올라온 실패에는 응답 본문의 메시지를 우선 보여 준다', async () => {
    const error: any = new Error('API Error: 400');
    error.data = { status: 'error', message: 'Missing data' };
    (paperTradingAPI.buy as any).mockRejectedValueOnce(error);
    renderOpen();

    await clickTrade('매수요청');

    expect(window.alert).toHaveBeenCalledWith('매수 실패: Missing data');
  });
});

describe('매도 결과 처리', () => {
  it('HTTP 200 으로 도착한 거절을 실패로 표시한다', async () => {
    (paperTradingAPI.sell as any).mockResolvedValueOnce({
      status: 'error',
      message: 'Not enough shares to sell',
    });
    renderOpen();

    await clickTrade('매도요청');

    expect(window.alert).toHaveBeenCalledWith('매도 실패: Not enough shares to sell');
    expect(window.alert).not.toHaveBeenCalledWith(
      expect.stringContaining('매도 완료'),
    );
  });

  it('성공 응답에는 완료를 표시한다', async () => {
    renderOpen();

    await clickTrade('매도요청');

    expect(window.alert).toHaveBeenCalledWith('삼성전자 1주 매도 완료');
  });
});
