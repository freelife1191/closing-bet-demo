import { describe, expect, it } from 'vitest';

import { decideSecondaryAI } from './aiHelpers';

describe('decideSecondaryAI', () => {
  it('returns perplexity when both hasPerplexity and hasGpt are true (perplexity wins)', () => {
    expect(decideSecondaryAI(true, true)).toBe('perplexity');
  });

  it('returns perplexity when only hasPerplexity is true', () => {
    expect(decideSecondaryAI(true, false)).toBe('perplexity');
  });

  it('returns gpt when only hasGpt is true', () => {
    expect(decideSecondaryAI(false, true)).toBe('gpt');
  });

  it('returns gpt (safe default) when both flags are false', () => {
    expect(decideSecondaryAI(false, false)).toBe('gpt');
  });

  it.each([
    { hasPerplexity: true,  hasGpt: true,  expected: 'perplexity' },
    { hasPerplexity: true,  hasGpt: false, expected: 'perplexity' },
    { hasPerplexity: false, hasGpt: true,  expected: 'gpt' },
    { hasPerplexity: false, hasGpt: false, expected: 'gpt' },
  ])(
    'table-driven: hasPerplexity=$hasPerplexity hasGpt=$hasGpt → $expected',
    ({ hasPerplexity, hasGpt, expected }) => {
      expect(decideSecondaryAI(hasPerplexity, hasGpt)).toBe(expected);
    },
  );
});
