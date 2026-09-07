// Regression: [FE-015] — 모바일에서 VCP 표의 빈 상태 문구가 화면 밖에 놓이던 문제
//
// 문구를 표의 colSpan 셀 안에 두면 min-w-[1000px] 인 표 폭을 기준으로 가운데 정렬되어
// 중심이 x 좌표 500 부근에 놓이고, 375px 화면에서는 완전히 밖으로 밀려났다. 문구를
// 가로 스크롤 영역 밖으로 옮겨 카드 폭을 기준으로 정렬되게 고쳤다.
//
// jsdom 은 레이아웃을 계산하지 않으므로 위치 자체는 브라우저 실측으로 확인한다.
// 여기서는 문구가 그 스크롤 영역으로 되돌아가지 않는지만 지킨다.

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { krAPI } from '@/lib/api';

import VCPPage from './page';

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({ signals: [], total_scanned: 0, source: 'test' })),
    getSignalDates: vi.fn(async () => []),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
    getStockChart: vi.fn(async () => ({ ticker: '005930', data: [] })),
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

// 스크롤 영역 안에 있으면 표의 min-w-[1000px] 이 정렬 기준이 되어 좁은 화면에서 밀려난다.
const expectOutsideHorizontalScroller = (text: HTMLElement) => {
  expect(text.closest('.overflow-x-auto')).toBeNull();
};

describe('[FE-015] VCP 표의 빈 상태와 로딩 문구', () => {
  it('시그널이 없을 때 빈 상태 문구가 가로 스크롤 영역 밖에 있다', async () => {
    render(<VCPPage />);
    expectOutsideHorizontalScroller(await screen.findByText('No signals found.'));
  });

  it('불러오는 동안에도 같은 자리에 있다', async () => {
    // 해소하지 않는 약속을 돌려주어 loading 상태에 머무르게 한다.
    vi.mocked(krAPI.getSignals).mockImplementationOnce(() => new Promise(() => {}));
    render(<VCPPage />);
    expectOutsideHorizontalScroller(await screen.findByText('Loading signals...'));
  });
});
