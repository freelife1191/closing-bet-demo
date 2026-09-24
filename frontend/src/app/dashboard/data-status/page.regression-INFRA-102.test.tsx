import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataStatusPage from './page';

// [INFRA-102] 개별 업데이트의 시작 실패(403·500 등)는 「업데이트 오류」 모달로 보여야 하고,
// 409 로 거부되면 다른 세션이 시작한 실행의 진행 상황을 보도록 폴링을 시작해야 한다.
const backend = vi.hoisted(() => ({
  startError: null as (Error & { status?: number }) | null,
  running: false,
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/system/start-update') {
      // 409 는 화면을 연 뒤 다른 세션이 실행을 시작한 경우다
      if (backend.startError?.status === 409) backend.running = true;
      if (backend.startError) throw backend.startError;
      return { status: 'started' };
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
      return backend.running
        ? { isRunning: true, startTime: '2026-09-25T06:00:00', currentItem: 'Daily Prices', items: [] }
        : { isRunning: false, startTime: null, currentItem: null, items: [] };
    }
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false }),
}));

const httpError = (status: number, message: string) => Object.assign(new Error(message), { status });

describe('DataStatusPage 시작 실패 표시 [INFRA-102]', () => {
  beforeEach(() => {
    backend.startError = null;
    backend.running = false;
  });

  it.each([
    [403, '관리자 권한이 필요합니다'],
    [500, 'API Error: 500'],
  ])('개별 업데이트가 %i 를 받으면 「업데이트 오류」 모달에 사유를 띄운다', async (status, message) => {
    backend.startError = httpError(status, message);
    render(<DataStatusPage />);
    await screen.findByText('Daily Prices');

    fireEvent.click(screen.getByRole('button', { name: '업데이트' }));

    expect(await screen.findByText('업데이트 오류')).toBeTruthy();
    expect(screen.getByText(message)).toBeTruthy();
  });

  it.each([['업데이트'], ['전체 데이터 업데이트']])(
    '「%s」가 409 를 받으면 중복 모달과 함께 진행 중인 실행을 폴링해 보여준다',
    async (buttonName) => {
      backend.startError = httpError(409, 'Already running');
      render(<DataStatusPage />);
      await screen.findByText('Daily Prices');

      fireEvent.click(screen.getByRole('button', { name: buttonName }));

      expect(await screen.findByText('업데이트 중복')).toBeTruthy();
      expect(await screen.findByText('Daily Prices 업데이트 중...', {}, { timeout: 2000 })).toBeTruthy();
    },
  );
});
