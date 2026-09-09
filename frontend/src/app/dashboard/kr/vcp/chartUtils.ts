export interface ChartPoint {
  date: string;
  close: number;
}

export interface SMADataPoint {
  time: string;
  value: number;
}

export function calculateSMA(data: ChartPoint[], period: number): SMADataPoint[] {
  if (period <= 0 || data.length === 0) {
    return [];
  }

  const smaData: SMADataPoint[] = [];
  let runningSum = 0;

  for (let i = 0; i < data.length; i++) {
    const close = Number(data[i].close);
    if (!Number.isFinite(close)) {
      continue;
    }

    runningSum += close;

    if (i >= period) {
      const removed = Number(data[i - period].close);
      if (Number.isFinite(removed)) {
        runningSum -= removed;
      }
    }

    const windowSize = Math.min(i + 1, period);
    smaData.push({
      time: data[i].date,
      value: runningSum / windowSize,
    });
  }

  return smaData;
}

export interface ChartDateGap {
  from: string;
  to: string;
  days: number;
}

// 거래일 달력이 없으므로 누락 여부 대신 응답에서 관측된 긴 달력 간격만 알린다.
export function findChartDateGaps(data: { date: string }[]): ChartDateGap[] {
  const gaps: ChartDateGap[] = [];
  for (let i = 1; i < data.length; i++) {
    const from = data[i - 1].date;
    const to = data[i].date;
    const start = Date.parse(`${from}T00:00:00Z`);
    const end = Date.parse(`${to}T00:00:00Z`);
    if (!Number.isFinite(start) || !Number.isFinite(end)
      || new Date(start).toISOString().slice(0, 10) !== from
      || new Date(end).toISOString().slice(0, 10) !== to) continue;
    const days = (end - start) / 86_400_000;
    if (days > 7) gaps.push({ from, to, days });
  }
  return gaps;
}
