/**
 * ADMIN_EMAILS 목록에 이 이메일이 있는지 판정한다.
 *
 * 「누가 관리자인가」를 정하는 자리는 이것 하나뿐이다. Flask 의 토큰 검사는
 * 「Next 를 거쳤는가」만 확인하므로 이 판정이 어긋나도 그쪽에서는 걸리지 않는다.
 *
 * `services/admin_helpers.py` 의 `is_admin_email` 과 같은 규칙을 쓴다. 쉼표로 나누고,
 * 앞뒤 공백을 없애고, 소문자로 맞추고, 기본 프로필 이메일을 거부한다. 두 언어에 같은
 * 규칙이 두 벌 있으므로 한쪽을 고치면 다른 쪽도 고친다.
 */
const DEFAULT_PROFILE_EMAIL = 'user@example.com';

export function isAdminEmail(
  email: string | null | undefined,
  rawList: string | undefined
): boolean {
  const normalized = email?.trim().toLowerCase();
  if (!normalized || normalized === DEFAULT_PROFILE_EMAIL) {
    return false;
  }
  return (rawList || '')
    .split(',')
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean)
    .includes(normalized);
}
