// [JONGGA-008] 확신도 파싱은 두 화면이 함께 쓴다. 한쪽에서만 규칙이 낡지 않도록
// 헬퍼 단위로 검사를 남긴다.

import { describe, expect, it } from 'vitest';

import { parseAIConfidence } from './aiConfidence';

describe('parseAIConfidence', () => {
  it.each([
    [null, null],
    [undefined, null],
    ['', null],
    ['분석 실패', null],
    [78, 78],
    ['78', 78],
    [0, 0],
    [150, 100],
    [-5, 0],
    // 캐시에 남은 소수를 그대로 돌려준다. 두 화면 모두 toFixed(0) 으로 그린다.
    [78.6, 78.6],
  ])('%o 를 %o 로 읽는다', (value, expected) => {
    expect(parseAIConfidence(value)).toBe(expected);
  });
});
