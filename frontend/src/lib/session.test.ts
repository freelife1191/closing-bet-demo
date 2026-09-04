// 익명 세션 ID 발급을 세 화면이 각자 구현하던 것을 헬퍼 하나로 모았다.
// 근거: docs/dev-cycle/TODO.md [FE-005], AUDIT-FE §2.3
//
// 사본 셋 가운데 `crypto.randomUUID` 부재를 대비한 것은 챗봇 화면 하나뿐이었다. 통합하면서
// 그쪽 구현을 기준으로 삼았으므로, 폴백이 실제로 동작하는지 고정해 둔다.

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getBrowserSessionId } from './session';

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('getBrowserSessionId', () => {
  it('한 번 발급하면 다음 호출에서 같은 값을 돌려준다', () => {
    const first = getBrowserSessionId();

    expect(first).toMatch(/^anon_/);
    expect(localStorage.getItem('browser_session_id')).toBe(first);
    expect(getBrowserSessionId()).toBe(first);
  });

  it('crypto.randomUUID 가 없는 브라우저에서도 발급한다', () => {
    // http 로 열면 보안 컨텍스트가 아니라서 randomUUID 가 없다. 이때 예외가 나면
    // 사용량 집계가 통째로 멈춘다.
    vi.stubGlobal('crypto', {});

    const sessionId = getBrowserSessionId();

    expect(sessionId).toMatch(/^anon_.+/);
    expect(localStorage.getItem('browser_session_id')).toBe(sessionId);
  });
});
