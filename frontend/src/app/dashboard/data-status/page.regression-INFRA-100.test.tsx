import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DataStatusPage from './page';

// [INFRA-100] 이미 실행 중이면 /api/system/start-update 가 409 "Already running" 을 돌려준다.
// 개별·전체 업데이트 모두 영어 문구의 오류가 아니라 「업데이트 중복」 모달을 띄워야 한다.
vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/system/start-update') {
      throw Object.assign(new Error('Already running'), { status: 409 });
    }
    if (path === '/api/system/data-status') {
      return {
        files: [
          {
            name: 'Daily Prices',
            path: 'data/daily_prices.csv',
            exists: true,
            lastModified: '2026-03-07T18:24:03.525438',
            size: '1.0 KB',
            rowCount: 1,
            dataDate: '2026-03-06',
            dataTimestamp: '2026-03-07T18:24:03.525438',
            link: '/dashboard/kr/vcp',
            menu: 'VCP Signals',
          },
        ],
        update_status: { isRunning: false, lastRun: '', progress: '' },
      };
    }
    if (path === '/api/system/update-status') {
      return { isRunning: false, startTime: null, currentItem: null, items: [] };
    }
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false }),
}));

describe('DataStatusPage 중복 시작 [INFRA-100]', () => {
  it('개별 업데이트가 409 를 받으면 「업데이트 중복」 모달을 띄운다', async () => {
    render(<DataStatusPage />);
    await screen.findByText('Daily Prices');

    fireEvent.click(screen.getByRole('button', { name: '업데이트' }));

    expect(await screen.findByText('업데이트 중복')).toBeTruthy();
  });

  it('전체 업데이트가 409 를 받으면 「업데이트 중복」 모달을 띄우고 영어 문구를 보이지 않는다', async () => {
    render(<DataStatusPage />);
    await screen.findByText('Daily Prices');

    fireEvent.click(screen.getByRole('button', { name: '전체 데이터 업데이트' }));

    expect(await screen.findByText('업데이트 중복')).toBeTruthy();
    expect(screen.queryByText('업데이트 오류')).toBeNull();
    expect(screen.queryByText('Already running')).toBeNull();
  });
});
