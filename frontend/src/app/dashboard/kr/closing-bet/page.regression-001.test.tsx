// Regression: ISSUE-001 — DataStatusBox가 조회 완료 후에도 LOADING...에 영구 고착됨
// Found by /qa on 2026-09-01
// Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-01.md

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') {
      return { dates: [] };
    }
    if (path === '/api/kr/jongga-v2/latest') {
      // 데이터가 오래되어 숨겨진 상태: 200이지만 updated_at이 없다.
      return {
        status: 'stale',
        is_stale: true,
        updated_at: null,
        date: '2026-09-01',
        latest_available_date: '2026-05-22',
        message: '오래된 종가베팅 데이터가 최신 리포트로 표시되지 않도록 숨겼습니다.',
        signals: [],
      };
    }
    if (path === '/api/kr/jongga-v2/status') {
      return { is_running: false };
    }
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

describe('JonggaV2Page - Data Status', () => {
  it('조회가 끝나고 데이터가 없으면 LOADING이 아니라 NO DATA를 표시한다', async () => {
    render(<JonggaV2Page />);

    await waitFor(() => {
      expect(screen.queryByText('NO DATA')).not.toBeNull();
    });

    expect(screen.queryByText('LOADING...')).toBeNull();
  });
});
