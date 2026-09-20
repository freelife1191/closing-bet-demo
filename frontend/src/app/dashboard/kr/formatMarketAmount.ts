/**
 * 원 단위 금액을 한국 시장 화면에서 쓰는 단위로 줄인다.
 *
 * 0의 의미는 호출 화면이 정한다. VCP 수급은 실제 0을 표시하고, 종가베팅의 재무·시세
 * 자리는 0을 값 없음으로 읽으므로 두 번째 인자로 그 표기만 넘긴다.
 */
export function formatMarketAmount(
  value: number | null | undefined,
  zeroText = '0',
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  if (value === 0) return zeroText;

  const absoluteValue = Math.abs(value);
  const sign = value < 0 ? '-' : '';

  if (absoluteValue >= 10_000_000_000_000_000) {
    return `${sign}${(absoluteValue / 10_000_000_000_000_000).toFixed(1)}경`;
  }

  if (absoluteValue >= 1_000_000_000_000) {
    const roundedEok = Math.round(absoluteValue / 100_000_000);
    const jo = Math.floor(roundedEok / 10_000);
    const eok = roundedEok % 10_000;
    return eok > 0 ? `${sign}${jo}조 ${eok}억` : `${sign}${jo}조`;
  }

  if (absoluteValue >= 100_000_000) {
    return `${sign}${Math.round(absoluteValue / 100_000_000)}억`;
  }

  if (absoluteValue >= 10_000) {
    return `${sign}${Math.round(absoluteValue / 10_000)}만`;
  }

  return value.toLocaleString();
}
