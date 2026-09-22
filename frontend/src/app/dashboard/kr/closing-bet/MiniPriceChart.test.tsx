// Regression: [JONGGA-041] — 카드의 작은 차트를 실제 시세로 되살린다
// 근거: docs/dev-cycle/TODO.md [JONGGA-041]
//
// [JONGGA-024] 가 상승·하락 두 모양뿐인 가짜 polyline 을 지우고 버튼만 남겼다. 이 컴포넌트는
// 기존 `/api/kr/stock-chart` 응답의 종가로 선을 그리고, 응답이 비거나 실패하면 그 버튼
// 문구로 돌아간다. 상자 전체가 「{종목} 차트 크게 보기」 버튼이라 확대 모달 진입은 그대로다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import MiniPriceChart, { miniChartPoints } from './MiniPriceChart';

const api = vi.hoisted(() => ({ fetchAPI: vi.fn() }));

vi.mock('@/lib/api', () => ({ fetchAPI: api.fetchAPI }));

const candle = (date: string, close: number) => ({ date, open: close, high: close, low: close, close, volume: 1 });

describe('[JONGGA-041] miniChartPoints', () => {
  it('종가를 viewBox 안에 고르게 펼치고 최고가를 위, 최저가를 아래에 둔다', () => {
    expect(miniChartPoints([10, 20, 15])).toBe('3,37 50,3 97,20');
  });

  it('값이 하나뿐이거나 전부 같으면 가운데 높이의 평평한 선이다', () => {
    expect(miniChartPoints([10, 10])).toBe('3,20 97,20');
    expect(miniChartPoints([7])).toBe('');
  });
});

describe('[JONGGA-041] MiniPriceChart', () => {
  it('신호일까지 한 달 종가를 받아 선을 그리고, 누르면 확대 차트를 연다', async () => {
    api.fetchAPI.mockResolvedValueOnce({
      ticker: '009150',
      data: [candle('2026-09-18', 1_400_000), candle('2026-09-21', 1_450_000), candle('2026-09-22', 1_477_000)],
    });
    const onOpenChart = vi.fn();

    render(<MiniPriceChart code="009150" name="삼성전기" signalDate="2026-09-22" onOpenChart={onOpenChart} />);

    const polyline = await waitFor(() => {
      const node = document.querySelector('polyline');
      if (!node) throw new Error('polyline not rendered yet');
      return node;
    });
    expect(polyline.getAttribute('points')).toBe(miniChartPoints([1_400_000, 1_450_000, 1_477_000]));
    expect(api.fetchAPI).toHaveBeenCalledWith('/api/kr/stock-chart/009150?period=1m&end=2026-09-22');

    fireEvent.click(screen.getByRole('button', { name: '삼성전기 차트 크게 보기' }));
    expect(onOpenChart).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('실제 차트 크게 보기')).toBeNull();
  });

  it('응답에 종가가 없으면 종전 버튼 문구로 돌아간다', async () => {
    api.fetchAPI.mockResolvedValueOnce({ ticker: '009150', data: [], message: '해당 종목 데이터가 없습니다.' });

    render(<MiniPriceChart code="009150" name="삼성전기" onOpenChart={() => {}} />);

    expect(await screen.findByText('실제 차트 크게 보기')).toBeInTheDocument();
    expect(document.querySelector('polyline')).toBeNull();
    expect(api.fetchAPI).toHaveBeenCalledWith('/api/kr/stock-chart/009150?period=1m');
  });

  it('요청이 실패해도 버튼은 남고 문구로 대체한다', async () => {
    api.fetchAPI.mockRejectedValueOnce(new Error('network'));

    render(<MiniPriceChart code="009150" name="삼성전기" signalDate="2026-09-22" onOpenChart={() => {}} />);

    expect(await screen.findByText('실제 차트 크게 보기')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '삼성전기 차트 크게 보기' })).toBeInTheDocument();
  });
});
