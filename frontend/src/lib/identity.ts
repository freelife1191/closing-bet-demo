import { createHmac } from 'node:crypto';

/**
 * 신원 서명을 만든다. 검증하는 자리는 `services/identity_helpers.py` 의
 * `verify_identity_header` 하나뿐이며, 두 구현이 같은 문자열을 만들어야 한다.
 *
 * 형식: `<base64url(email, 패딩 없음)>.<exp 유닉스 초>.<hex 소문자 HMAC-SHA256>`
 * HMAC 의 입력은 앞 두 마디이며 서명 자체는 포함하지 않는다.
 */
export const IDENTITY_TTL_SECONDS = 120;

export function signIdentity(email: string, secret: string, expiresAt: number): string {
  // Buffer 의 base64url 은 패딩을 붙이지 않는다. 파이썬 쪽은 디코딩 전에 패딩을 채운다.
  const encoded = Buffer.from(email, 'utf8').toString('base64url');
  const payload = `${encoded}.${expiresAt}`;
  const mac = createHmac('sha256', secret).update(payload).digest('hex');
  return `${payload}.${mac}`;
}
