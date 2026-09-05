import { getBrowserSessionId } from '@/lib/session';

export const STORED_MODEL_KEY = 'chatbot_current_model';

export function shouldSendOnEnter(
  key: string,
  shiftKey: boolean,
  isComposing: boolean
): boolean {
  if (key !== 'Enter') return false;
  if (shiftKey) return false;
  if (isComposing) return false;
  return true;
}

export function getStoredModel(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(STORED_MODEL_KEY);
    return value && value.trim().length > 0 ? value : null;
  } catch {
    return null;
  }
}

export function setStoredModel(model: string | null | undefined): void {
  if (typeof window === 'undefined') return;
  try {
    if (model && model.trim().length > 0) {
      window.localStorage.setItem(STORED_MODEL_KEY, model);
    } else {
      window.localStorage.removeItem(STORED_MODEL_KEY);
    }
  } catch {
    // ignore quota / privacy errors
  }
}

export function getAuthHeaders(): Record<string, string> {
  const sessionId = getBrowserSessionId();

  const headers: Record<string, string> = {
    'X-Session-Id': sessionId
  };

  // User Profile Email
  const savedProfile = localStorage.getItem('user_profile');
  if (savedProfile) {
    try {
      const p = JSON.parse(savedProfile);
      if (p.email && p.email !== 'user@example.com') {
        headers['X-User-Email'] = p.email;
      }
    } catch (e) { }
  }

  return headers;
}

// 저장된 프로필이 없을 때 화면이 그리는 폴백. 서버 렌더와 첫 클라이언트 렌더가 같은 값을
// 그리도록 `useState` 의 초기값으로도 쓴다.
export const DEFAULT_USER_PROFILE = {
  name: '흑기사',
  email: 'user@example.com',
  persona: ''
};

// 프로필을 서버에 저장하고, 성공했을 때만 로컬 캐시와 화면을 갱신한다. 거절되면 던진다.
// `SettingsModal.handleSave` 가 그 예외를 받아 오류 모달을 띄운다.
export async function saveUserProfile(
  name: string,
  email: string,
  persona: string
): Promise<void> {
  const res = await fetch('/api/kr/chatbot/profile', {
    method: 'POST',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, persona })
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.error || `프로필 저장 실패 (HTTP ${res.status})`);
  }

  // 서버가 받아들인 뒤에 갱신한다. 먼저 쓰면 저장이 실패했을 때 화면과 서버가 어긋난 채
  // 남는다.
  localStorage.setItem('user_profile', JSON.stringify({ name, email, persona }));
  window.dispatchEvent(new Event('user-profile-updated'));
}
