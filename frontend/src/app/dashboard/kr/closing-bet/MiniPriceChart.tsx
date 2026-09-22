'use client';

import { useEffect, useState } from 'react';
import { fetchAPI, type KRChartResponse } from '@/lib/api';

// 카드 상자에 맞춘 좌표계. 선이 테두리에 닿지 않도록 PAD 만큼 안쪽에 그린다.
const WIDTH = 100;
const HEIGHT = 40;
const PAD = 3;

const round1 = (value: number) => Math.round(value * 10) / 10;

// 종가 배열을 polyline 의 points 문자열로 바꾼다. 최고가가 위, 최저가가 아래에 놓이고 x 는
// 고르게 펼친다. 값이 둘 미만이면 선이 될 수 없어 빈 문자열이다.
export function miniChartPoints(closes: number[]): string {
  if (closes.length < 2) return '';
  const max = Math.max(...closes);
  const min = Math.min(...closes);
  const span = max - min;
  const stepX = (WIDTH - PAD * 2) / (closes.length - 1);
  return closes
    .map((close, index) => {
      const y = span > 0 ? PAD + ((max - close) / span) * (HEIGHT - PAD * 2) : HEIGHT / 2;
      return `${round1(PAD + stepX * index)},${round1(y)}`;
    })
    .join(' ');
}

interface MiniPriceChartProps {
  code: string;
  name: string;
  signalDate?: string;
  onOpenChart: () => void;
}

// [JONGGA-041] 카드의 작은 차트. VCP 화면의 확대 차트가 쓰는 `/api/kr/stock-chart` 에서 신호일까지
// 한 달 종가를 받아 선으로 그린다. 이 화면의 확대 모달은 네이버 이미지를 쓰므로 이 API 의 첫 호출자다. 상자 전체가 「{종목} 차트 크게 보기」 버튼이다. 응답이 비거나
// 실패하면 [JONGGA-024] 가 남긴 버튼 문구로 돌아간다. closes 가 undefined 면 받는 중이다.
export default function MiniPriceChart({ code, name, signalDate, onOpenChart }: MiniPriceChartProps) {
  const [closes, setCloses] = useState<number[] | null | undefined>(undefined);

  useEffect(() => {
    let ignore = false;
    const end = signalDate ? `&end=${encodeURIComponent(signalDate)}` : '';
    fetchAPI<KRChartResponse>(`/api/kr/stock-chart/${encodeURIComponent(code)}?period=1m${end}`)
      .then((res) => {
        if (ignore) return;
        // 백엔드가 close > 0 인 행만 돌려주므로 여기서 다시 거르지 않는다.
        const values = (res.data ?? []).map((row) => row.close);
        setCloses(values.length >= 2 ? values : null);
      })
      .catch(() => {
        if (!ignore) setCloses(null);
      });
    return () => {
      ignore = true;
    };
  }, [code, signalDate]);

  const points = closes ? miniChartPoints(closes) : '';
  // 카드의 상승률과 같은 색. 한 달 전보다 올랐으면 rose, 내렸으면 blue.
  const stroke = closes && closes[closes.length - 1] < closes[0] ? '#60a5fa' : '#fb7185';

  return (
    <button
      type="button"
      data-testid="mini-chart"
      aria-label={`${name} 차트 크게 보기`}
      onClick={onOpenChart}
      className="group/chart relative flex h-24 w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-[#131722] text-xs font-semibold text-gray-300 transition-colors hover:bg-white/5 hover:text-white"
    >
      {points ? (
        <>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true" className="absolute inset-0 h-full w-full">
            <polyline fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" points={points} />
          </svg>
          <span className="absolute bottom-1.5 left-2 text-[10px] font-normal text-gray-500">최근 1개월 종가</span>
          <span className="absolute top-1.5 right-2 rounded bg-gray-800/80 px-2 py-0.5 text-[10px] text-white opacity-0 transition-opacity group-hover/chart:opacity-100">
            <i className="fas fa-expand-arrows-alt mr-1"></i>크게 보기
          </span>
        </>
      ) : closes === null ? (
        <>
          <i className="fas fa-chart-line text-indigo-400"></i>
          실제 차트 크게 보기
        </>
      ) : null}
    </button>
  );
}
