// 종가베팅 화면이 값을 화면 문자열로 바꿀 때 쓰는 순수 함수들이다. page.tsx 에 두면
// 컴포넌트가 아닌 export 가 섞여 React Fast Refresh 가 편집마다 전체 리마운트로
// 떨어진다. 이 저장소는 이런 헬퍼를 형제 파일에 둔다(retryHelpers.ts, vcp/aiHelpers.ts).

// 종목 차트. 네이버 금융이 종목코드로 직접 만들어 주는 이미지를 그대로 쓴다.
// 앞서 쓰던 TradingView 임베드 위젯은 무료 등급이 KRX 시세를 제공하지 않아, 심볼이
// 실재해도 기본 심볼(애플)로 조용히 바꿔 그렸다. iframe 이 교차 출처라서 앱이 그
// 대체를 감지할 수도 없었다. 이미지 주소는 종목코드로 조립되므로 다른 종목이 섞이지
// 않고, 없는 종목에는 404 가 오므로 실패를 화면에 드러낼 수 있다.
export const CHART_PERIODS = [
  { key: 'day', label: '일봉' },
  { key: 'week', label: '주봉' },
  { key: 'month', label: '월봉' },
] as const;

export type ChartPeriod = (typeof CHART_PERIODS)[number]['key'];

// 카드와 상세 모달이 같은 금액을 같은 문자열로 적도록 두 자리가 이 함수를 함께 쓴다.
export function formatBigNumber(num: number | undefined | null) {
  // 0 과 NaN 도 자리를 비운다. 값을 구하지 못했다는 뜻으로 읽히는 편이 「NaN」보다 낫다.
  if (!num) return '-';

  const abs = Math.abs(num);
  const sign = num < 0 ? '-' : '';

  if (abs >= 10000000000000000) return `${sign}${(abs / 10000000000000000).toFixed(1)}경`;
  if (abs >= 1000000000000) return `${sign}${(abs / 1000000000000).toFixed(1)}조`;
  if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(0)}억`;
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(0)}만`;

  return num.toLocaleString();
}

// 종목코드는 백엔드 응답에서 오는 값이므로 경로에 끼우기 전에 인코딩한다. 형식을
// 여섯 자리 숫자로 좁히지는 않는다. KRX 가 아크릴(0007C0)처럼 영문자가 든 코드를
// 이미 쓰고 있어서, 좁히는 쪽이 오히려 멀쩡한 종목을 떨어뜨린다.
export function stockChartUrl(symbol: string, period: ChartPeriod) {
  return `https://ssl.pstatic.net/imgfinance/chart/item/candle/${period}/${encodeURIComponent(symbol)}.png`;
}

// 시세 자리에 그릴 수 있는 값인지 판정한다. 백엔드는 시세를 못 받았을 때 값을 비우는
// 대신 0 으로 채우므로, 0 을 값 없음으로 읽어야 「₩0」을 정상 시세처럼 적지 않는다.
// 주가에 0 원은 없다. 액면가가 가장 낮은 종목도 100 원부터 시작한다.
export function isPositivePrice(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}
