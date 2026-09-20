import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchAPI } from './api';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('fetchAPI response body deadline', () => {
  it.each([
    [200, 'Request timed out'],
    [500, 'API Error: 500'],
  ])('keeps the deadline while a %s response body is stalled', async (status, message) => {
    vi.useFakeTimers();
    let bodyController!: ReadableStreamDefaultController<Uint8Array>;
    let aborted = false;
    const body = new ReadableStream<Uint8Array>({ start(controller) { bodyController = controller; } });
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => {
      options.signal?.addEventListener('abort', () => {
        aborted = true;
        bodyController.error(new DOMException('Response aborted', 'AbortError'));
      });
      // Headers arrive immediately; the actual Response.json() waits for the body.
      return new Response(body, { status, headers: { 'Content-Type': 'application/json' } });
    }));
    let failure: unknown;
    const settled = fetchAPI('/api/kr/refresh', { timeout: 10 }).catch(error => { failure = error; });
    try {
      await vi.advanceTimersByTimeAsync(10);
      expect(failure).toMatchObject({ message });
      expect(aborted).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      if (!aborted) bodyController.error(new Error('Test cleanup'));
      await settled;
    }
  });
});
