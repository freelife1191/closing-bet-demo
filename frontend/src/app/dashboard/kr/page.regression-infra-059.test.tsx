// Regression: [INFRA-059] 관리자 전용 조작 세 자리의 노출
//
// 서버가 require_admin 으로 POST /api/kr/refresh 와 /market-gate/update 와
// /config/interval 셋을 닫았다. 화면이 같은 조건을 지키지 않으면 비관리자에게 버튼이
// 보이고 눌러도 403 만 돌아오는데, refreshData 와 refreshMarketGate 의 catch 가
// console.error 뿐이라 화면에는 아무 반응도 없다. [INFRA-042] 라운드가 data-status 의
// 중지 버튼에서 정확히 그 상태를 남겼고 리뷰가 잡았다. 같은 것을 사람에게 두 번
// 의지하지 않으려고 이 검사를 둔다.
//
// 감추는 쪽만 재면 게이트가 관리자에게까지 전부를 감춰도 통과하므로 두 갈래를 잰다.
// 백엔드도 같은 이유로 tests/app/test_admin_gated_routes.py 에서 거부와 통과를 함께 잰다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KRDashboardPage from './page';

const { mockUseAdmin } = vi.hoisted(() => ({
  mockUseAdmin: vi.fn(() => ({ isAdmin: false, isLoading: false })),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => mockUseAdmin(),
}));

const fetchAPIMock = vi.fn();

vi.mock('@/lib/api', () => ({
  fetchAPI: (...args: unknown[]) => fetchAPIMock(...args),
  krAPI: {
    getMarketGate: vi.fn(async () => ({ status: 'GREEN', score: 70, message: '' })),
    getSignals: vi.fn(async () => ({ signals: [], count: 0 })),
    getDataStatus: vi.fn(async () => ({ data: {} })),
  },
}));

beforeEach(() => {
  fetchAPIMock.mockReset();
  fetchAPIMock.mockResolvedValue({
    vcp: { status: 'GOOD', count: 12, win_rate: 55, avg_return: 3.1 },
    closing_bet: { status: 'GOOD', count: 8, win_rate: 62, avg_return: 2.4, candidates: [] },
  });
  // 화면이 마운트되면서 주기 설정을 직접 fetch 로 읽는다. 목하지 않으면 jsdom 이
  // 상대 경로를 URL 로 만들지 못해 매 검사마다 예외가 찍힌다.
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) })));
  mockUseAdmin.mockImplementation(() => ({ isAdmin: false, isLoading: false }));
});

describe('[INFRA-059] 관리자 전용 조작의 노출', () => {
  it('비관리자에게는 세 자리가 모두 보이지 않는다', async () => {
    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    expect(screen.queryByText('Refresh Data')).toBeNull();
    expect(screen.queryByTitle('Refresh Market Gate Only')).toBeNull();
    // 이 화면의 유일한 select 가 주기 선택이다. 다른 select 가 생기면 이 단언이
    // 의미를 잃으므로 그때는 접근성 이름으로 바꾼다.
    expect(container.querySelector('select')).toBeNull();
    // select 만 감추면 드롭다운 화살표가 남는다. 그 아이콘은 group-hover 로만 보이므로
    // 비관리자가 「매크로 지표」 줄에 마우스를 올릴 때 없는 드롭다운의 화살표가 뜬다.
    expect(container.querySelector('i.fa-chevron-down')).toBeNull();
    // 값 자체는 계속 보인다. GET /api/kr/config/interval 은 열려 있고, 이 값으로
    // 화면 자동 갱신도 그대로 돈다.
    expect(screen.queryByText('30분')).not.toBeNull();
  });

  it('관리자에게는 세 자리가 모두 보인다', async () => {
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false }));

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    expect(screen.queryByText('Refresh Data')).not.toBeNull();
    expect(screen.queryByTitle('Refresh Market Gate Only')).not.toBeNull();
    expect(container.querySelector('select')).not.toBeNull();
  });

  it('주기 변경이 실패하면 화면 값을 되돌린다', async () => {
    // 이 값은 서버 전역 스케줄러 주기다. 낙관적 갱신만 하고 실패를 되돌리지 않으면
    // 화면 값만 바뀌어 서버와 갈린다.
    //
    // 403 이 아니라 500 을 쓰는 이유가 있다. 403 은 permissionRevoked 를 세워 select 를
    // 통째로 거두므로 롤백이 아니라 노출 조건을 재게 된다. 권한과 무관한 실패로 롤백만
    // 잰다. 403 갈래는 아래 「403 을 받으면」 검사가 따로 본다.
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false }));
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === 'POST'
          ? { ok: false, status: 500, json: async () => ({}) }
          : { ok: true, json: async () => ({ interval: 30 }) }
      )
    );

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    const select = container.querySelector('select') as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('30'));

    fireEvent.change(select, { target: { value: '5' } });

    await waitFor(() => expect(select.value).toBe('30'));
  });

  it('요청이 겹쳐 둘 다 실패하면 서버가 받아들인 값으로 되돌린다', async () => {
    // 30 → 5(실패) → 60(실패). 「직전 호출이 세운 값」으로 되돌리면 서버에 반영된 적
    // 없는 5 가 화면에 남는다. 되돌릴 곳은 서버가 확정한 30 이다.
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false }));
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === 'POST'
          ? { ok: false, status: 500, json: async () => ({}) }
          : { ok: true, json: async () => ({ interval: 30 }) }
      )
    );

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    const select = container.querySelector('select') as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe('30'));

    fireEvent.change(select, { target: { value: '5' } });
    fireEvent.change(select, { target: { value: '60' } });

    await waitFor(() => expect(select.value).toBe('30'));
  });

  it('403 을 받으면 화면이 권한 없음을 알린다', async () => {
    // 버튼을 감추는 것만으로는 모자란다. useAdmin 은 [session, status] 가 바뀔 때만
    // 재판정하므로 ADMIN_EMAILS 에서 빠진 뒤에도 열려 있는 탭에는 계속 보인다.
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: false }));
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === 'POST'
          ? { ok: false, status: 403, json: async () => ({ error: 'Forbidden' }) }
          : { ok: true, json: async () => ({ interval: 30 }) }
      )
    );

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    const select = container.querySelector('select') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: '5' } });

    await waitFor(() => expect(screen.queryByText('권한 없음')).not.toBeNull());

    // 알리는 데서 그치지 않고 세 자리를 함께 거둔다. 알림만 띄우고 버튼을 남기면
    // 같은 사용자가 계속 눌러 같은 403 을 반복해서 받는다.
    expect(screen.queryByText('Refresh Data')).toBeNull();
    expect(screen.queryByTitle('Refresh Market Gate Only')).toBeNull();
    expect(container.querySelector('select')).toBeNull();
  });

  it('관리자 판정이 끝나기 전에는 감춘 쪽으로 떨어진다', async () => {
    // isLoading 동안 버튼을 먼저 보이면, 판정이 false 로 끝나는 순간 버튼이 사라진다.
    // 그 사이에 누른 요청은 403 을 받고 화면에는 아무 반응도 없다.
    mockUseAdmin.mockImplementation(() => ({ isAdmin: true, isLoading: true }));

    const { container } = render(<KRDashboardPage />);

    await waitFor(() => expect(screen.getAllByText('12 trades').length).toBeGreaterThan(0));

    expect(screen.queryByText('Refresh Data')).toBeNull();
    expect(screen.queryByTitle('Refresh Market Gate Only')).toBeNull();
    expect(container.querySelector('select')).toBeNull();
  });
});
