import { createHmac } from 'node:crypto';
import { describe, expect, it } from 'vitest';

// [INFRA-027] 서명 형식 회귀 검사. `services/identity_helpers.py` 의
// verify_identity_header 와 같은 문자열을 만들어야 한다. 한쪽만 바뀌면 검증이 전부
// 실패해 로그인 사용자가 조용히 익명으로 떨어진다.

import { IDENTITY_TTL_SECONDS, signIdentity } from './identity';

describe('signIdentity', () => {
  it('v2.b64url(email).exp.hmac 네 마디를 만든다', () => {
    const signed = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'GET',
      '/api/portfolio'
    );
    const parts = signed.split('.');

    expect(parts).toHaveLength(4);
    expect(parts[0]).toBe('v2');
    expect(Buffer.from(parts[1], 'base64url').toString('utf8')).toBe('owner@example.com');
    expect(parts[2]).toBe('2000');
  });

  it('base64url 에 패딩을 남기지 않는다', () => {
    // 'a@b.co' 는 6바이트라 표준 base64 라면 '=' 두 개가 붙는다.
    const signed = signIdentity('a@b.co', 'test-identity-secret', 2000, 'GET', '/api/a');

    expect(signed.split('.')[1]).not.toContain('=');
  });

  it('HMAC 은 v2, 이메일, 만료, 대문자 메서드, decoded path를 입력으로 삼는다', () => {
    const signed = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'post',
      '/api/한글/%2F'
    );
    const [, encoded, exp, mac] = signed.split('.');
    const encodedPath = Buffer.from('/api/한글/%2F', 'utf8').toString('base64url');
    const expected = createHmac('sha256', 'test-identity-secret')
      .update(`v2.${encoded}.${exp}.POST.${encodedPath}`)
      .digest('hex');

    expect(mac === expected).toBe(true);
  });

  it('비밀이 다르면 서명이 달라진다', () => {
    const a = signIdentity('owner@example.com', 'secret-a', 2000, 'GET', '/api/a');
    const b = signIdentity('owner@example.com', 'secret-b', 2000, 'GET', '/api/a');

    expect(a).not.toBe(b);
  });

  it('만료는 120초다', () => {
    expect(IDENTITY_TTL_SECONDS).toBe(120);
  });

  it('다른 method 또는 path에 재사용할 수 없게 서로 다른 서명을 만든다', () => {
    const original = signIdentity('owner@example.com', 'test-identity-secret', 2000, 'GET', '/api/a');
    const otherMethod = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'POST',
      '/api/a'
    );
    const otherPath = signIdentity('owner@example.com', 'test-identity-secret', 2000, 'GET', '/api/b');

    expect(otherMethod === original).toBe(false);
    expect(otherPath === original).toBe(false);
  });

  it('method는 대문자로 정규화하지만 trailing slash는 보존한다', () => {
    const lowerCaseMethod = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'head',
      '/api/tail'
    );
    const upperCaseMethod = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'HEAD',
      '/api/tail'
    );
    const trailingSlash = signIdentity(
      'owner@example.com',
      'test-identity-secret',
      2000,
      'HEAD',
      '/api/tail/'
    );

    expect(lowerCaseMethod === upperCaseMethod).toBe(true);
    expect(trailingSlash === upperCaseMethod).toBe(false);
  });
});
