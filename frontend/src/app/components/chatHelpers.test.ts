import { describe, it, expect, beforeEach } from 'vitest';
import {
  STORED_MODEL_KEY,
  shouldSendOnEnter,
  getStoredModel,
  setStoredModel,
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
