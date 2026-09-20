'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchAPI } from '@/lib/api';

export interface Quota {
  usage: number;
  limit: number;
  remaining: number;
}

export type QuotaStatus = 'idle' | 'pending' | 'ready' | 'unavailable';

interface QuotaSnapshot {
  identity: string | null;
  quota: Quota | null;
  status: QuotaStatus;
}

interface UseQuotaOptions {
  enabled: boolean;
  identity: string;
  getRequestOptions?: () => RequestInit;
  refreshKey?: unknown;
}

interface UseQuotaResult {
  quota: Quota | null;
  quotaStatus: QuotaStatus;
  refreshQuota: () => Promise<void>;
  setQuota: (value: unknown) => void;
}

const QUOTA_ENDPOINT = '/api/kr/user/quota';

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 0;
}

export function parseQuota(value: unknown): Quota {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('사용량 응답이 올바르지 않습니다');
  }

  const quota = value as { usage?: unknown; limit?: unknown; remaining?: unknown };
  if (
    !isNonNegativeInteger(quota.usage)
    || !isNonNegativeInteger(quota.remaining)
    || typeof quota.limit !== 'number'
    || !Number.isFinite(quota.limit)
    || !Number.isInteger(quota.limit)
    || quota.limit <= 0
  ) {
    throw new Error('사용량 응답이 올바르지 않습니다');
  }

  return { usage: quota.usage, limit: quota.limit, remaining: quota.remaining };
}

export function useQuota({ enabled, identity, getRequestOptions, refreshKey }: UseQuotaOptions): UseQuotaResult {
  const generation = useRef(0);
  const latestIdentity = useRef(identity);
  const [snapshot, setSnapshot] = useState<QuotaSnapshot>({
    identity: null,
    quota: null,
    status: 'idle',
  });

  const refreshQuota = useCallback(async () => {
    if (!enabled || latestIdentity.current !== identity) return;

    const requestGeneration = ++generation.current;
    const requestIdentity = identity;
    setSnapshot({ identity: requestIdentity, quota: null, status: 'pending' });

    try {
      const response = await fetchAPI<unknown>(QUOTA_ENDPOINT, getRequestOptions?.());
      const quota = parseQuota(response);
      if (generation.current !== requestGeneration || latestIdentity.current !== requestIdentity) return;
      setSnapshot({ identity: requestIdentity, quota, status: 'ready' });
    } catch {
      if (generation.current !== requestGeneration || latestIdentity.current !== requestIdentity) return;
      setSnapshot({ identity: requestIdentity, quota: null, status: 'unavailable' });
    }
  }, [enabled, getRequestOptions, identity]);

  useEffect(() => {
    latestIdentity.current = identity;
  }, [identity]);

  useEffect(() => {
    if (!enabled) {
      generation.current += 1;
      setSnapshot({ identity, quota: null, status: 'idle' });
      return;
    }

    void refreshQuota();
    return () => {
      generation.current += 1;
    };
  }, [enabled, identity, refreshKey, refreshQuota]);

  const setQuota = useCallback((value: unknown) => {
    if (!enabled || latestIdentity.current !== identity) return;

    generation.current += 1;
    try {
      setSnapshot({ identity, quota: parseQuota(value), status: 'ready' });
    } catch {
      setSnapshot({ identity, quota: null, status: 'unavailable' });
    }
  }, [enabled, identity]);

  if (!enabled || snapshot.identity !== identity) {
    return {
      quota: null,
      quotaStatus: enabled ? 'pending' : 'idle',
      refreshQuota,
      setQuota,
    };
  }

  return {
    quota: snapshot.quota,
    quotaStatus: snapshot.status,
    refreshQuota,
    setQuota,
  };
}
