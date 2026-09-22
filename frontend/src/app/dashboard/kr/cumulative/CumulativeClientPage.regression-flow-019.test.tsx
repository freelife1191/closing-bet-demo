// Regression: [FLOW-019] 등급 집합 밖의 거래가 누적 추천수에만 잡히고 화면에 드러나지 않던 문제
//
// 등급 카드와 칩은 S·A·B·D 만 센다. 저장 자료에 C 같은 값이 섞이면 누적 추천수와 등급 합이
// 어긋나는데 알려 주는 자리가 없었다. 서버가 그 건수를 counts.other 로 보내면 안내를 띄운다.

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

function stubFetch(other: number) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({
      kpi: {},
      trades: [],
      pagination: { total: 0, page: 1, limit: 50, totalPages: 1 },
      counts: {
        total: 10 + other,
        outcome: { WIN: 4, LOSS: 4, OPEN: 2 + other },
        grade: { S: 1, A: 2, B: 6, D: 1 },
        other,
      },
    }),
  })));
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-019] 누적성과 모집단 안내', () => {
  it('등급 집합 밖의 거래가 있으면 그 건수를 알린다', async () => {
    stubFetch(2);
    render(<CumulativeClientPage />);

    expect(await screen.findByText('등급 집합 밖의 거래 2건은 누적 추천수에만 포함됩니다.')).toBeTruthy();
    expect(screen.getByText(/D\(현행 기준 미달 또는 과거 등급\)도 통계에 포함합니다/)).toBeTruthy();
  });

  it('등급 집합 밖의 거래가 없으면 그 안내를 띄우지 않는다', async () => {
    stubFetch(0);
    render(<CumulativeClientPage />);

    await screen.findByText(/D\(현행 기준 미달 또는 과거 등급\)도 통계에 포함합니다/);
    expect(screen.queryByText(/등급 집합 밖의 거래/)).toBeNull();
  });
});
