import { describe, it, expect } from 'vitest';
import { shouldScheduleAutoRetry, MAX_AUTO_RETRIES } from './retryHelpers';

describe('shouldScheduleAutoRetry', () => {
  it('returns false when isInitializing=false regardless of count', () => {
    expect(shouldScheduleAutoRetry(0, MAX_AUTO_RETRIES, false)).toBe(false);
    expect(shouldScheduleAutoRetry(5, MAX_AUTO_RETRIES, false)).toBe(false);
    expect(shouldScheduleAutoRetry(MAX_AUTO_RETRIES + 1, MAX_AUTO_RETRIES, false)).toBe(false);
  });

  it('returns true when isInitializing=true and count is below max', () => {
    expect(shouldScheduleAutoRetry(1, MAX_AUTO_RETRIES, true)).toBe(true);
    expect(shouldScheduleAutoRetry(MAX_AUTO_RETRIES - 1, MAX_AUTO_RETRIES, true)).toBe(true);
  });

  it('returns true when isInitializing=true and count is exactly at max (boundary)', () => {
    expect(shouldScheduleAutoRetry(MAX_AUTO_RETRIES, MAX_AUTO_RETRIES, true)).toBe(true);
  });

  it('returns false when isInitializing=true and count is above max', () => {
    expect(shouldScheduleAutoRetry(MAX_AUTO_RETRIES + 1, MAX_AUTO_RETRIES, true)).toBe(false);
    expect(shouldScheduleAutoRetry(MAX_AUTO_RETRIES + 100, MAX_AUTO_RETRIES, true)).toBe(false);
  });

  it('returns false when count is Infinity (defensive)', () => {
    expect(shouldScheduleAutoRetry(Infinity, MAX_AUTO_RETRIES, true)).toBe(false);
  });

  it('returns false when maxRetries is 0 and count is 1', () => {
    expect(shouldScheduleAutoRetry(1, 0, true)).toBe(false);
  });

  it('returns true when count is 0 (pre-first-call baseline)', () => {
    expect(shouldScheduleAutoRetry(0, MAX_AUTO_RETRIES, true)).toBe(true);
  });
});
