// Regression: ISSUE-004 — 백엔드가 내려준 stale_warning 을 VCP 페이지가 표시하지 않던 문제
// Found by /qa on 2026-09-01
// Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-01.md

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const STALE_MESSAGE =
  '오늘(2026-09-01) 기준 VCP 시그널이 없습니다. 최신 저장 데이터는 2026-05-05입니다.';

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({
      signals: [],
      total_scanned: 1997,
      source: 'no_data',
      stale_warning: STALE_MESSAGE,
    })),
    getSignalDates: vi.fn(async () => []),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
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

describe('VCPPage - stale warning', () => {
  it('시그널이 비어 있으면 백엔드의 stale_warning 문구를 화면에 표시한다', async () => {
    render(<VCPPage />);

    await waitFor(() => {
      expect(screen.queryByText(STALE_MESSAGE)).not.toBeNull();
    });
  });
});
