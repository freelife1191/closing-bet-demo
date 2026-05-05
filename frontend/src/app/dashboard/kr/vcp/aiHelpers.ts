export type SecondaryAI = 'gpt' | 'perplexity';

/**
 * Decide which secondary AI provider to surface in the VCP table.
 *
 * Priority:
 *   1. Perplexity — when data is available
 *   2. GPT        — when Perplexity data is absent but GPT data is available
 *   3. 'gpt'      — safe default when neither provider has data;
 *                   the column will simply render no badge rather than
 *                   defaulting to Perplexity and showing an empty column.
 */
export function decideSecondaryAI(hasPerplexity: boolean, hasGpt: boolean): SecondaryAI {
  if (hasPerplexity) return 'perplexity';
  if (hasGpt) return 'gpt';
  return 'gpt';
}
