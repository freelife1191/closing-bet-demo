// `fetchAPI` 는 저장소의 모든 HTTP 호출이 지나는 자리인데 검사가 없었다.
// 근거: docs/dev-cycle/TODO.md [FE-005], AUDIT-FE §5.2
//
// 실패 응답을 다루는 방식이 이 함수의 전부다. 상태 코드와 본문을 예외에 실어 올리고,
// 본문에 적힌 사유를 Error.message 로 승격하며, 응답이 늦으면 스스로 끊는다. 세 갈래
// 모두 호출부가 화면에 무엇을 띄울지 결정하므로 하나씩 고정한다.

import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchAPI, krAPI } from './api';

// body 에 문자열 'not-json' 을 넘기면 본문 파싱이 실패하는 응답이 된다.
function mockResponse(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => {
        if (body === 'not-json') throw new SyntaxError('Unexpected token');
        return body;
      },
    }))
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchAPI', () => {
  it('성공하면 응답 본문을 그대로 돌려준다', async () => {
    mockResponse(200, { status: 'ok', signals: [] });

    await expect(fetchAPI('/api/kr/signals')).resolves.toEqual({ status: 'ok', signals: [] });
  });

  it('실패 본문의 message 를 예외 메시지로 올리고 상태 코드와 본문도 실어 준다', async () => {
    const body = { status: 'error', message: '잔고가 부족합니다.' };
    mockResponse(400, body);

    const error: any = await fetchAPI('/api/portfolio/buy').catch((e) => e);

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe('잔고가 부족합니다.');
    expect(error.status).toBe(400);
    expect(error.data).toEqual(body);
  });

  it('message 가 없으면 error 필드를 쓴다', async () => {
    // 백엔드가 두 형태를 섞어 쓴다. market-gate 계열은 error 에 사유를 적는다.
    mockResponse(500, { status: 'error', error: 'Market Gate 갱신 실패' });

    await expect(fetchAPI('/api/kr/market-gate/update')).rejects.toThrow('Market Gate 갱신 실패');
  });

  it('본문이 JSON 이 아니면 상태 코드만 가지고 간다', async () => {
    mockResponse(502, 'not-json');

    await expect(fetchAPI('/api/kr/signals')).rejects.toThrow('API Error: 502');
  });

  it('응답이 제한 시간을 넘기면 스스로 끊는다', async () => {
    // 서버가 답하지 않는 상황. AbortController 가 끊고 그 이름을 사람이 읽을 문구로 바꾼다.
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, options: any) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener('abort', () => {
              const abortError = new Error('The operation was aborted.');
              abortError.name = 'AbortError';
              reject(abortError);
            });
          })
      )
    );

    await expect(fetchAPI('/api/kr/signals', { timeout: 10 })).rejects.toThrow('Request timed out');
  });
});

describe('krAPI.updateMarketGate', () => {
  it('기본 10초 대신 120초를 기다린다', async () => {
    // 백엔드가 수급 수집과 Market Gate 분석을 동기로 돌린다. 이 지정이 사라지면 10초에
    // 끊기는데, 유일한 호출부가 catch 에서 console.error 만 하므로 화면에는 아무것도
    // 뜨지 않는다. 「눌러도 안 바뀐다」로만 보이므로 값을 검사로 붙들어 둔다.
    mockResponse(200, { status: 'success' });

    await krAPI.updateMarketGate('2026-09-04');

    const [, options] = (globalThis.fetch as any).mock.calls[0];
    expect(options.timeout).toBe(120000);
  });
});

describe('krAPI.runVCPScreener', () => {
  it('409 만 한국어 문구로 바꾼다', async () => {
    // 이 엔드포인트는 중복 실행을 영어로 알린다. 화면이 예외 메시지를 그대로 띄우므로
    // 여기서 바꾸지 않으면 사용자에게 "Already running" 이 보인다.
    mockResponse(409, { status: 'error', message: 'Already running' });

    await expect(krAPI.runVCPScreener()).rejects.toThrow('이미 분석이 진행 중입니다.');
  });

  it('409 가 아닌 실패는 서버가 적어 보낸 사유를 그대로 올린다', async () => {
    mockResponse(500, { status: 'error', error: 'VCP 엔진 초기화 실패' });

    await expect(krAPI.runVCPScreener()).rejects.toThrow('VCP 엔진 초기화 실패');
  });
});
