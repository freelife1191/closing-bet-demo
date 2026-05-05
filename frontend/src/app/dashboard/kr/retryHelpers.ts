/**
 * Maximum number of auto-retries before giving up on initializing state.
 * 10 retries × 5s = 50 seconds total polling window.
 */
export const MAX_AUTO_RETRIES = 10;

/**
 * Pure helper that decides whether to schedule an auto-retry.
 *
 * @param retryCount    - Current value of retryCountRef (already incremented before this call).
 *                        Returns true while retryCount <= maxRetries; stops returning true
 *                        once retryCount > maxRetries (i.e. exhausted).
 * @param maxRetries    - Upper bound (inclusive) for retryCount
 * @param isInitializing - Whether the market gate is still initializing
 * @returns true iff a retry should be scheduled
 */
export function shouldScheduleAutoRetry(
  retryCount: number,
  maxRetries: number,
  isInitializing: boolean
): boolean {
  return isInitializing && retryCount <= maxRetries;
}
