/**
 * [JONGGA-008] AI 확신도를 화면에 그릴 수 있는 값으로 읽는다.
 *
 * 백엔드는 확신도가 없는 상태를 0 이 아니라 값 없음으로 보낸다. 0 으로 채우면 AI 가
 * 실제로 0 을 낸 종목과 구분되지 않는다. 캐시에 남은 옛 자료가 "80" 같은 문자열을
 * 담고 있을 수 있어 숫자로 읽히는 값만 살리고, 상한과 하한을 함께 조여 막대 너비나
 * 원호 길이가 음수가 되지 않게 한다.
 */
export function parseAIConfidence(value: unknown): number | null {
  const parsed = typeof value === 'number'
    ? value
    : (typeof value === 'string' ? parseFloat(value) : NaN);
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 0), 100) : null;
}
