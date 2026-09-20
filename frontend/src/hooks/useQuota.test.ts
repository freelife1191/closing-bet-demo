import { describe, expect, it } from 'vitest';

import { parseQuota } from './useQuota';

describe('parseQuota', () => {
  it('유한 정수 사용량만 받고 recharge 응답의 합계는 강제하지 않는다', () => {
    expect(parseQuota({ usage: 12, limit: 10, remaining: 4, recharge: true })).toEqual({
      usage: 12,
      limit: 10,
      remaining: 4,
    });
  });

  it.each([
    { usage: '0', limit: 10, remaining: 10 },
    { usage: 0, limit: '10', remaining: 10 },
    { usage: 0, limit: 10, remaining: 1.5 },
    { usage: -1, limit: 10, remaining: 10 },
    { usage: 0, limit: 0, remaining: 10 },
    null,
  ])('숫자 shape가 올바르지 않으면 명시적인 오류를 낸다', (value) => {
    expect(() => parseQuota(value)).toThrow('사용량 응답이 올바르지 않습니다');
  });
});
