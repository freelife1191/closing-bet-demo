import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataStatusPage from './page';

// [INFRA-103] 진행 폴링은 조회가 연속 3번 실패하면 멈추고 알려야 하며, 앞선 요청이
// 끝나지 않았으면 다음 요청을 겹쳐 보내지 않아야 한다.
type Outcome = 'running' | 'fail' | 'pending';

const backend = vi.hoisted(() => ({
  outcomes: [] as string[],
  fallback: 'running' as string,
  statusCalls: 0,
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/system/update-status') {
      backend.statusCalls += 1;
      const outcome = backend.outcomes.shift() ?? backend.fallback;
      if (outcome === 'fail') throw new Error('Failed to fetch');
      if (outcome === 'pending') return new Promise(() => {});
      return { isRunning: true, startTime: '2026-09-25T09:40:00', currentItem: 'Daily Prices', items: [] };
    }
    if (path === '/api/system/data-status') {
      return { files: [], update_status: { isRunning: false, lastRun: '', progress: '' } };
    }
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false }),
}));

const setBackend = (outcomes: Outcome[], fallback: Outcome) => {
  backend.outcomes = [...outcomes];
  backend.fallback = fallback;
};

const pause = (ms: number) => new Promise(r => setTimeout(r, ms));

describe('DataStatusPage 진행 폴링 실패 처리 [INFRA-103]', () => {
  beforeEach(() => {
    backend.statusCalls = 0;
  });

  it('조회가 연속 3번 실패하면 폴링을 멈추고 「업데이트 오류」 모달로 알린다', async () => {
    setBackend(['running'], 'fail');
    render(<DataStatusPage />);

    expect(await screen.findByText('업데이트 오류', {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByText(/진행 상황을 확인하지 못해 자동 확인을 멈췄습니다/)).toBeTruthy();
    expect(screen.queryByText('Daily Prices 업데이트 중...')).toBeNull();
    const calls = backend.statusCalls;
    expect(calls).toBe(4);

    await pause(1200);
    expect(backend.statusCalls).toBe(calls);
  });

  it('중간에 한 번 성공하면 실패 횟수를 처음부터 다시 센다', async () => {
    setBackend(['running', 'fail', 'fail', 'running', 'fail', 'fail', 'fail'], 'running');
    render(<DataStatusPage />);

    expect(await screen.findByText('업데이트 오류', {}, { timeout: 6000 })).toBeTruthy();
    expect(backend.statusCalls).toBe(7);
  }, 10000);

  it('앞선 조회가 끝나지 않았으면 다음 조회를 보내지 않는다', async () => {
    setBackend(['running'], 'pending');
    render(<DataStatusPage />);

    await waitFor(() => expect(backend.statusCalls).toBe(2), { timeout: 2000 });
    await pause(1500);
    expect(backend.statusCalls).toBe(2);
  });
});
