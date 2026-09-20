import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import BuyStockModal from './BuyStockModal';

const sessionState = vi.hoisted(() => ({
  data: { user: { email: 'buyer@example.test' } },
  status: 'authenticated',
}));
const api = vi.hoisted(() => ({ getPortfolio: vi.fn() }));

vi.mock('next-auth/react', () => ({ useSession: () => sessionState }));
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    isAuthenticationError: () => false,
    paperTradingAPI: { ...actual.paperTradingAPI, getPortfolio: api.getPortfolio },
  };
});

function renderModal(): void {
  render(
    <BuyStockModal
      isOpen
      onClose={vi.fn()}
      stock={{ ticker: '005930', name: '삼성전자', price: 70_000, entry_price: 70_000 }}
      onBuy={vi.fn(async () => true)}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getPortfolio.mockResolvedValue({ cash: 1_000_000 });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('[JONGGA-031] 매수 모달 가격 출처', () => {
  it('조회 성공을 거래소 실시간 시세로 단정하지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ prices: { '005930': 76_200 } })));

    renderModal();

    expect(await screen.findByText('가격 조회값 적용 (실시간 시세 보장 아님)')).toBeTruthy();
    expect(screen.queryByText('실시간 시세 적용')).toBeNull();
  });

  it('가격 조회가 실패하면 신호일 종가 또는 기본가를 쓴다고 밝힌다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ error: '가격 조회 실패' })));

    renderModal();

    await waitFor(() => {
      expect(screen.getByText('⚠ 저장된 가격 적용 (시세 조회 실패 또는 값 없음)')).toBeTruthy();
    });
  });

  it('조회가 끝나기 전에는 저장된 가격을 쓰는 진행 상태를 보인다', async () => {
    let resolveResponse: (value: Response) => void = () => undefined;
    vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { resolveResponse = resolve; })));

    renderModal();

    expect(await screen.findByText('시세 조회 중 · 저장된 가격으로 표시')).toBeTruthy();
    await act(async () => {
      resolveResponse(Response.json({ prices: { '005930': 76_200 } }));
    });
    expect(await screen.findByText('가격 조회값 적용 (실시간 시세 보장 아님)')).toBeTruthy();
  });

  it('조회 거부도 값 없음과 같은 저장된 가격 안내로 끝낸다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new Error('network error'))));

    renderModal();

    await waitFor(() => {
      expect(screen.getByText('⚠ 저장된 가격 적용 (시세 조회 실패 또는 값 없음)')).toBeTruthy();
    });
  });

  it('HTTP 실패를 공용 fetchAPI 오류 계약으로 끝내고 저장 가격으로 돌아간다', async () => {
    const fetchMock = vi.fn(async () => Response.json({ error: '가격 조회 실패' }, { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);

    renderModal();

    expect(await screen.findByText('⚠ 저장된 가격 적용 (시세 조회 실패 또는 값 없음)')).toBeTruthy();
    expect(screen.getByText('70,000원')).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/kr/realtime-prices',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('10초 timeout 뒤 스피너를 끝내고 저장 가격으로 돌아간다', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          const abortError = new Error('The operation was aborted.');
          abortError.name = 'AbortError';
          reject(abortError);
        });
      }))
    );

    await act(async () => { renderModal(); });
    expect(screen.getByText('시세 조회 중 · 저장된 가격으로 표시')).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(screen.getByText('⚠ 저장된 가격 적용 (시세 조회 실패 또는 값 없음)')).toBeTruthy();
  });

  it('중첩 prices 응답이 아닌 legacy 평면 가격도 정상 가격으로 쓴다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ '005930': 76_200 })));

    renderModal();

    expect(await screen.findByText('가격 조회값 적용 (실시간 시세 보장 아님)')).toBeTruthy();
    expect(screen.getByText('76,200원')).toBeTruthy();
  });

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, '76200'])('유효하지 않은 prices 값 %s은 저장 가격으로 되돌린다', async (price) => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ prices: { '005930': price } })));

    renderModal();

    expect(await screen.findByText('⚠ 저장된 가격 적용 (시세 조회 실패 또는 값 없음)')).toBeTruthy();
    expect(screen.getByText('70,000원')).toBeTruthy();
  });
});
