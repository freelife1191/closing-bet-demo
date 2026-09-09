import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  STORED_MODEL_KEY,
  shouldSendOnEnter,
  getStoredModel,
  normalizeUserProfile,
  resolveUserProfile,
  setStoredModel,
  saveUserProfile,
} from './chatHelpers';

describe('shouldSendOnEnter', () => {
  it('returns true for plain Enter outside IME composition', () => {
    expect(shouldSendOnEnter('Enter', false, false)).toBe(true);
  });

  it('returns false during IME composition (Korean input)', () => {
    expect(shouldSendOnEnter('Enter', false, true)).toBe(false);
  });

  it('returns false when Shift is held (newline shortcut)', () => {
    expect(shouldSendOnEnter('Enter', true, false)).toBe(false);
  });

  it('returns false for non-Enter keys', () => {
    expect(shouldSendOnEnter('a', false, false)).toBe(false);
    expect(shouldSendOnEnter('Tab', false, false)).toBe(false);
    expect(shouldSendOnEnter('Escape', false, false)).toBe(false);
  });

  it('IME guard wins over Shift state', () => {
    expect(shouldSendOnEnter('Enter', true, true)).toBe(false);
  });
});

describe('resolveUserProfile', () => {
  it('세션 표기는 우선하되 저장 프로필의 페르소나는 유지한다', () => {
    expect(resolveUserProfile(
      { name: '저장된 이름', email: 'saved@example.com', persona: '사용자 페르소나' },
      { name: '세션 이름', email: 'session@example.com' },
    )).toEqual({
      name: '세션 이름',
      email: 'session@example.com',
      persona: '사용자 페르소나',
    });
  });

  it('저장값이 없거나 비어 있으면 공통 기본 프로필을 쓴다', () => {
    expect(resolveUserProfile(null)).toEqual({
      name: 'User',
      email: 'user@example.com',
      persona: '',
    });
  });

  it('손상된 캐시는 공통 기본 프로필로 정규화한다', () => {
    expect(normalizeUserProfile(null)).toEqual({
      name: 'User',
      email: 'user@example.com',
      persona: '',
    });
  });
});

describe('getStoredModel / setStoredModel', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('returns null when nothing is stored', () => {
    expect(getStoredModel()).toBeNull();
  });

  it('round-trips a model name', () => {
    setStoredModel('gemini-2.0-flash');
    expect(getStoredModel()).toBe('gemini-2.0-flash');
    expect(window.localStorage.getItem(STORED_MODEL_KEY)).toBe('gemini-2.0-flash');
  });

  it('removes the key when given null or empty string', () => {
    setStoredModel('gpt-4o');
    setStoredModel(null);
    expect(getStoredModel()).toBeNull();

    setStoredModel('gpt-4o');
    setStoredModel('   ');
    expect(getStoredModel()).toBeNull();
  });

  it('treats whitespace-only stored value as null', () => {
    window.localStorage.setItem(STORED_MODEL_KEY, '   ');
    expect(getStoredModel()).toBeNull();
  });
});

describe('saveUserProfile', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  const okResponse = () => ({ ok: true, status: 200, json: async () => ({}) }) as Response;

  it('서버가 받아들이면 로컬 캐시를 갱신하고 갱신 이벤트를 발행한다', async () => {
    const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => okResponse());
    vi.stubGlobal('fetch', fetchMock);
    const listener = vi.fn();
    window.addEventListener('user-profile-updated', listener);

    await saveUserProfile('홍길동', 'hong@example.com', '가치투자자');

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/kr/chatbot/profile');
    expect(init.method).toBe('POST');
    // 소유자 헤더가 실려야 서버가 프로필을 누구 것으로 저장할지 판정할 수 있다.
    expect((init.headers as Record<string, string>)['X-Session-Id']).toBeTruthy();
    expect(JSON.parse(init.body as string)).toEqual({ name: '홍길동', persona: '가치투자자' });

    expect(JSON.parse(window.localStorage.getItem('user_profile') as string)).toEqual({
      name: '홍길동',
      email: 'hong@example.com',
      persona: '가치투자자',
    });
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener('user-profile-updated', listener);
  });

  it('서버가 거절하면 던지고 로컬 캐시를 건드리지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Session is required' }),
    }) as Response));

    await expect(saveUserProfile('홍길동', 'hong@example.com', '')).rejects.toThrow(
      'Session is required'
    );
    expect(window.localStorage.getItem('user_profile')).toBeNull();
  });

  it('오류 본문을 읽을 수 없어도 상태 코드를 담아 던진다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => { throw new Error('not json'); },
    }) as unknown as Response));

    await expect(saveUserProfile('홍길동', 'hong@example.com', '')).rejects.toThrow('HTTP 500');
  });
});
