import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { isAdminEmail } from './adminEmails';

// 파이썬 검사(tests/services/test_admin_helpers.py)와 같은 파일을 읽는다. 한쪽 규칙만
// 고치면 반대쪽이 실패한다. import.meta.url 을 쓰는 이유는 vitest 가 ESM 으로 돌아
// __dirname 을 주지 않기 때문이고, process.cwd() 는 실행 위치에 따라 달라진다.
const CASES_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../tests/fixtures/admin_email_cases.json'
);

const CASES: Array<{
  why: string;
  list: string;
  email: string;
  expected: boolean;
}> = JSON.parse(readFileSync(CASES_PATH, 'utf-8')).cases;

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

// 위 describe 는 그대로 둔다. undefined 처럼 JSON 이 표현하지 못하는 입력을 재고 있어
// 공유 케이스가 대체하지 못한다.
describe('isAdminEmail — 파이썬 구현과 공유하는 케이스', () => {
  it('케이스 파일이 비어 있지 않다', () => {
    // 파일을 못 읽거나 비면 아래 it.each 가 0건으로 조용히 통과한다.
    expect(CASES.length).toBeGreaterThanOrEqual(10);
  });

  it.each(CASES)('$why', ({ list, email, expected }) => {
    expect(isAdminEmail(email, list)).toBe(expected);
  });
});
