import { createHmac } from 'node:crypto';
import { describe, expect, it } from 'vitest';

// [INFRA-027] 서명 형식 회귀 검사. `services/identity_helpers.py` 의
// verify_identity_header 와 같은 문자열을 만들어야 한다. 한쪽만 바뀌면 검증이 전부
// 실패해 로그인 사용자가 조용히 익명으로 떨어진다.

import { IDENTITY_TTL_SECONDS, signIdentity } from './identity';

describe('signIdentity', () => {
  it('b64url(email).exp.hmac 세 마디를 만든다', () => {
    const signed = signIdentity('owner@example.com', 'test-identity-secret', 2000);
    const parts = signed.split('.');

    expect(parts).toHaveLength(3);
    expect(Buffer.from(parts[0], 'base64url').toString('utf8')).toBe('owner@example.com');
    expect(parts[1]).toBe('2000');
  });

  it('base64url 에 패딩을 남기지 않는다', () => {
    // 'a@b.co' 는 6바이트라 표준 base64 라면 '=' 두 개가 붙는다.
    const signed = signIdentity('a@b.co', 'test-identity-secret', 2000);

    expect(signed.split('.')[0]).not.toContain('=');
  });

  it('HMAC 은 앞 두 마디만을 입력으로 삼는다', () => {
    const signed = signIdentity('owner@example.com', 'test-identity-secret', 2000);
    const [encoded, exp, mac] = signed.split('.');
    const expected = createHmac('sha256', 'test-identity-secret')
      .update(`${encoded}.${exp}`)
      .digest('hex');

    expect(mac).toBe(expected);
  });

  it('비밀이 다르면 서명이 달라진다', () => {
    const a = signIdentity('owner@example.com', 'secret-a', 2000);
    const b = signIdentity('owner@example.com', 'secret-b', 2000);

    expect(a).not.toBe(b);
  });

  it('만료는 120초다', () => {
    expect(IDENTITY_TTL_SECONDS).toBe(120);
  });
});
