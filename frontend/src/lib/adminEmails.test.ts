import { describe, expect, it } from 'vitest';

import { isAdminEmail } from './adminEmails';

describe('isAdminEmail', () => {
  const LIST = ' Alpha@Example.com , beta@example.com ';

  it('대소문자와 공백을 무시하고 대조한다', () => {
    expect(isAdminEmail('ALPHA@example.com', LIST)).toBe(true);
    expect(isAdminEmail('  beta@example.com  ', LIST)).toBe(true);
  });

  it('목록에 없는 이메일을 거부한다', () => {
    expect(isAdminEmail('gamma@example.com', LIST)).toBe(false);
  });

  it('빈 값과 기본 프로필 이메일을 거부한다', () => {
    expect(isAdminEmail(null, LIST)).toBe(false);
    expect(isAdminEmail(undefined, LIST)).toBe(false);
    expect(isAdminEmail('', LIST)).toBe(false);
    expect(isAdminEmail('user@example.com', 'user@example.com')).toBe(false);
  });

  it('목록이 비어 있으면 아무도 통과시키지 않는다', () => {
    expect(isAdminEmail('alpha@example.com', '')).toBe(false);
    expect(isAdminEmail('alpha@example.com', undefined)).toBe(false);
    expect(isAdminEmail('alpha@example.com', ' , , ')).toBe(false);
  });
});
