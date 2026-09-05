// 자산 개요와 수익 차트가 함께 쓴다. 컴포넌트를 나누기 전에는 한 파일 안에 있었다.

// 작은 비율을 0.0%/0.00%로 잘라버리지 않도록 자릿수를 동적으로 조정한다.
// 입력 value 는 이미 퍼센트 단위 숫자다 (예: 1.23 = 1.23%, 0.000429 = 0.000429%).
// 임계값도 같은 단위로 비교한다: 0.01 = 0.01%, 0.0001 = 0.0001%.
// 예) 0.000429 (=0.000429%) → "0.000429" 부근 6자리 / 12.34 → "12.34"
export const formatSmartPercent = (value: number, defaultDigits = 2): string => {
  if (!Number.isFinite(value)) return (0).toFixed(defaultDigits);
  const abs = Math.abs(value);
  if (abs === 0) return value.toFixed(defaultDigits);
  if (abs < 0.0001) return value.toFixed(6);
  if (abs < 0.01) return value.toFixed(4);
  if (abs < 0.1) return value.toFixed(3);
  return value.toFixed(defaultDigits);
};
