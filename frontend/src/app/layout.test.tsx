import type { ReactElement } from 'react';
import { describe, expect, it } from 'vitest';

import RootLayout from './layout';

describe('RootLayout', () => {
  // 화면 문구가 한국어이므로 낭독기와 번역 제안이 한국어로 판단하게 한다.
  it('declares the document language as Korean', () => {
    const html = RootLayout({ children: null }) as ReactElement<{ lang?: string }>;
    expect(html.props.lang).toBe('ko');
  });
});
