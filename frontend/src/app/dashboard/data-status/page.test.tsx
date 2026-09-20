import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DataStatusPage from './page';

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/system/data-status') {
      return {
        files: [
          {
            name: 'AI Analysis',
            path: 'data/kr_ai_analysis.json',
            exists: true,
            lastModified: '2026-03-07T18:24:03.525438',
            size: '1.0 KB',
            rowCount: 0,
            dataDate: '2026-03-06',
            dataTimestamp: '2026-03-07T18:24:03.525438',
            link: '/dashboard/kr/vcp',
            menu: 'VCP Signals',
          },
          {
            name: 'AI Jongga V2',
            path: 'data/kr_jongga_v2_latest.json',
            exists: true,
            lastModified: '2026-03-07T18:24:03.525438',
            size: '2.0 KB',
            rowCount: 1,
            dataDate: '2026-03-06',
            dataTimestamp: '2026-03-07T18:24:03.525438',
            link: '/dashboard/kr/closing-bet',
            menu: 'Closing Bet',
          },
        ],
        update_status: {
          isRunning: false,
          lastRun: '2026-03-07T18:20:54.354974',
          progress: '',
        },
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

describe('DataStatusPage', () => {
  it('renders logical data date when provided by data-status API', async () => {
    render(<DataStatusPage />);

    await waitFor(() => {
      expect(screen.queryByText('AI Analysis')).not.toBeNull();
    });

    expect(screen.queryAllByText('데이터 기준일')).toHaveLength(2);
    expect(screen.queryAllByText('2026-03-06')).toHaveLength(2);
  });

  it('날짜 입력과 아이콘 전송 버튼에 정확한 이름을 제공한다', async () => {
    render(<DataStatusPage />);
    await screen.findByText('AI Jongga V2');

    fireEvent.click(screen.getByRole('button', { name: '날짜 지정' }));

    expect(screen.getByLabelText('수집 기준 날짜')).toBeTruthy();
    const send = screen.getByRole('button', { name: 'AI Jongga V2 메시지 발송' });
    expect(send.getAttribute('aria-label')).toBe('AI Jongga V2 메시지 발송');
  });
});
