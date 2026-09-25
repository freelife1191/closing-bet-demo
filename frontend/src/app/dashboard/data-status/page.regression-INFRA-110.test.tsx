import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DataStatusPage from './page';

// [INFRA-110] 마운트 때 보낸 진행 조회가 전체 업데이트 시작보다 늦게 isRunning:false 로
// 도착해도, 시작 뒤에 붙은 진행 폴링을 끊거나 진행 표시를 지우면 안 된다.
const backend = vi.hoisted(() => ({
  statusCalls: 0,
  releaseMountPoll: null as ((value: unknown) => void) | null,
  holdStart: false,
  releaseStart: null as ((value: unknown) => void) | null,
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/system/update-status') {
      backend.statusCalls += 1;
      if (backend.statusCalls === 1) {
        return new Promise(resolve => {
          backend.releaseMountPoll = resolve;
        });
      }
      return { isRunning: true, startTime: '2026-09-25T12:40:00', currentItem: 'Daily Prices', items: [] };
    }
    if (path === '/api/system/start-update') {
      if (backend.holdStart) {
        return new Promise(resolve => {
          backend.releaseStart = resolve;
        });
      }
      return { status: 'ok' };
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

const pause = (ms: number) => new Promise(r => setTimeout(r, ms));

const idle = { isRunning: false, startTime: null, currentItem: null, items: [] };

describe('DataStatusPage 늦게 도착한 마운트 조회 [INFRA-110]', () => {
  beforeEach(() => {
    backend.statusCalls = 0;
    backend.releaseMountPoll = null;
    backend.holdStart = false;
    backend.releaseStart = null;
  });

  it('시작 전에 보낸 조회의 isRunning:false 는 새 진행 폴링을 끊지 않는다', async () => {
    render(<DataStatusPage />);
    await waitFor(() => expect(backend.releaseMountPoll).not.toBeNull());

    fireEvent.click(await screen.findByRole('button', { name: '전체 데이터 업데이트' }));
    await screen.findByText('업데이트 시작 요청 완료...');

    backend.releaseMountPoll?.(idle);
    await pause(1500);

    expect(backend.statusCalls).toBeGreaterThan(2);
    expect(screen.getByText('Daily Prices 업데이트 중...')).toBeTruthy();
    expect(screen.getByRole('button', { name: '업데이트 중...' })).toBeTruthy();
  });

  it('시작 요청의 응답보다 먼저 도착한 isRunning:false 도 진행 상태를 지우지 않는다', async () => {
    backend.holdStart = true;
    render(<DataStatusPage />);
    await waitFor(() => expect(backend.releaseMountPoll).not.toBeNull());

    fireEvent.click(await screen.findByRole('button', { name: '전체 데이터 업데이트' }));
    await waitFor(() => expect(backend.releaseStart).not.toBeNull());

    backend.releaseMountPoll?.(idle);
    await pause(300);
    expect(screen.getByRole('button', { name: '업데이트 중...' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '전체 데이터 업데이트' })).toBeNull();

    backend.releaseStart?.({ status: 'ok' });
    expect(await screen.findByText('Daily Prices 업데이트 중...', {}, { timeout: 2000 })).toBeTruthy();
  });
});
