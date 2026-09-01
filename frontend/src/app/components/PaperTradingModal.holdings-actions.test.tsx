import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import PaperTradingModal from './PaperTradingModal';

// [FE-009] 회귀 검사. 보유 종목 행 전체가 거래 내역을 여는 클릭 핸들러를 달고 있어서,
// 행 안쪽의 매수·매도 버튼이 e.stopPropagation() 을 잃으면 주문 모달과 상세 패널이
// 함께 열린다. 상세가 z-120 으로 주문 모달(z-110) 을 덮으므로 목록에서 주문을 넣을 수
// 없게 된다. 전파 차단이 사라지는 순간을 이 검사로 잡는다.

// 세 모달을 열림 여부만 드러내는 표식으로 대체한다. 어느 것이 열렸는지가 검사 대상이고
// 내부 입력 화면은 이 검사와 무관하다.
vi.mock('./BuyStockModal', () => ({
  default: ({ isOpen }: any) => (isOpen ? <div>매수모달</div> : null),
}));
vi.mock('./SellStockModal', () => ({
  default: ({ isOpen }: any) => (isOpen ? <div>매도모달</div> : null),
}));
vi.mock('./StockTradeHistoryModal', () => ({
  default: ({ isOpen }: any) => (isOpen ? <div>상세패널</div> : null),
}));

const mockPortfolio = {
  holdings: [
    {
      ticker: '016360',
      name: '삼성증권',
      quantity: 10,
      avg_price: 85_000,
      current_price: 87_000,
    },
  ],
  cash: 91_733_700,
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

beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
});

async function openHoldingsTab() {
  render(<PaperTradingModal isOpen onClose={vi.fn()} />);
  await act(async () => {
    fireEvent.click(screen.getByText('보유 종목'));
  });
}

describe('보유 종목 행의 주문 버튼', () => {
  it('매수 버튼은 매수 모달만 열고 상세 패널은 열지 않는다', async () => {
    await openHoldingsTab();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '매수' }));
    });

    expect(screen.getByText('매수모달')).toBeTruthy();
    expect(screen.queryByText('상세패널')).toBeNull();
  });

  it('매도 버튼은 매도 모달만 열고 상세 패널은 열지 않는다', async () => {
    await openHoldingsTab();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '매도' }));
    });

    expect(screen.getByText('매도모달')).toBeTruthy();
    expect(screen.queryByText('상세패널')).toBeNull();
  });

  it('버튼 바깥의 행을 누르면 상세 패널만 열린다', async () => {
    await openHoldingsTab();

    await act(async () => {
      fireEvent.click(screen.getByTitle('클릭하여 거래 내역 보기'));
    });

    expect(screen.getByText('상세패널')).toBeTruthy();
    expect(screen.queryByText('매수모달')).toBeNull();
    expect(screen.queryByText('매도모달')).toBeNull();
  });
});
