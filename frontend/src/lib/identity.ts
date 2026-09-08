import { createHmac } from 'node:crypto';

/**
 * 신원 서명을 만든다. 검증하는 자리는 `services/identity_helpers.py` 의
 * `verify_identity_header` 하나뿐이며, 두 구현이 같은 문자열을 만들어야 한다.
 *
 * 형식: `v2.<base64url(email, 패딩 없음)>.<exp 유닉스 초>.<hex 소문자 HMAC-SHA256>`
 * HMAC 의 입력에는 실제 HTTP method와 한 번 decode한 pathname을 포함한다.
 */
export const IDENTITY_TTL_SECONDS = 120;

export function signIdentity(
  email: string,
  secret: string,
  expiresAt: number,
  method: string,
  path: string
): string {
  // Buffer 의 base64url 은 패딩을 붙이지 않는다. 파이썬 쪽은 디코딩 전에 패딩을 채운다.
  const encoded = Buffer.from(email, 'utf8').toString('base64url');
  const encodedPath = Buffer.from(path, 'utf8').toString('base64url');
  const payload = `v2.${encoded}.${expiresAt}.${method.toUpperCase()}.${encodedPath}`;
  const mac = createHmac('sha256', secret).update(payload).digest('hex');
  return `v2.${encoded}.${expiresAt}.${mac}`;
}
