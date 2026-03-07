import { render, screen, waitFor } from '@testing-library/react';
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
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/app/components/Modal', () => ({
  default: () => null,
}));

describe('DataStatusPage', () => {
  it('renders logical data date when provided by data-status API', async () => {
    render(<DataStatusPage />);

    await waitFor(() => {
      expect(screen.queryByText('AI Analysis')).not.toBeNull();
    });

    expect(screen.queryByText('데이터 기준일')).not.toBeNull();
    expect(screen.queryByText('2026-03-06')).not.toBeNull();
  });
});
