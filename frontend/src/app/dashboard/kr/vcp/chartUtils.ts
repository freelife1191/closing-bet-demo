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
