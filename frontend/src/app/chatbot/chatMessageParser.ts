// 챗봇 응답 텍스트를 다루는 순수 함수 모음.
// 화면 상태나 브라우저 API 에 기대지 않으므로 단위 검사가 직접 부를 수 있다.
// [CHAT-004] 가 page.tsx 에서 옮겨 왔다.

export interface Message {
  role: 'user' | 'model';
  parts: (string | { text: string })[];
  timestamp?: string;
  isStreaming?: boolean;
  reasoning?: string;
}

export const getTurnIndicesFromMessage = (messages: Message[], index: number): number[] => {
  const current = messages[index];
  if (!current) return [];

  const prev = messages[index - 1];
  const next = messages[index + 1];

  if (current.role === 'user' && next?.role === 'model') {
    return [index, index + 1];
  }

  if (current.role === 'model' && prev?.role === 'user') {
    return [index - 1, index];
  }

  // 비정상 히스토리 대비
  return [index];
};

export const getMessagePartText = (part: Message['parts'][number] | undefined): string => {
  if (!part) return '';
  return typeof part === 'string' ? part : part.text;
};

const splitDenseNumberedLists = (text: string): string => text
  .split('\n')
  .map((line) => {
    if (/^\s*#{1,6}\s/.test(line)) return line;
    return line.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');
  })
  .join('\n');

// Helper to fix CJK markdown issues and malformed AI output
export const preprocessMarkdown = (text: string) => {
  let processed = text;
  const removeLastUnmatchedMarker = (line: string, markerRegex: RegExp, markerLength: number): string => {
    const matches = [...line.matchAll(markerRegex)];
    if (matches.length % 2 === 1) {
      const idx = matches[matches.length - 1].index;
      if (typeof idx === 'number') {
        return line.slice(0, idx) + line.slice(idx + markerLength);
      }
    }
    return line;
  };

  // 1. Remove stray emphasis markers before ordered list starts (e.g. "****1. ")
  processed = processed.replace(/^\s*\*{3,}(?=\d+[.)]\s)/gm, '');

  // 2. Split section labels and first ordered item when they are stuck together.
  processed = processed.replace(/((?:\*\*|__)?\[[^\]\n]{1,20}\](?:\*\*|__)?)\s*(?=[1-9]\d?[.)])/g, '$1\n');

  // 3. Ensure space after ordered-list marker (e.g. "1.조선", "1.**제목**" -> "1. 조선", "1. **제목**")
  processed = processed.replace(/(?<!\d)([1-9]\d?[.)])(?=\*\*|__|[가-힣A-Za-z(])/g, '$1 ');

  // 4. Ensure emphasis opening marker is separated from previous word (opening marker only).
  // Avoid touching closing markers before punctuation (e.g. "**텍스트**:")
  processed = processed.replace(/([가-힣A-Za-z0-9])(?=(\*\*|__)\s*[가-힣A-Za-z0-9(])/g, '$1 ');

  // 5. Trim inner spaces in emphasis markers (covers both-sided or one-sided spaces).
  processed = processed.replace(/\*\*([^*\n]+)\*\*/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `**${trimmed}**` : m;
  });
  processed = processed.replace(/__([^_\n]+)__/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `__${trimmed}__` : m;
  });

  // 5-1. Remove trailing unmatched emphasis marker in a line.
  processed = processed
    .split('\n')
    .map((line) => {
      const balancedAsterisk = removeLastUnmatchedMarker(line, /(?<!\*)\*\*(?!\*)/g, 2);
      return removeLastUnmatchedMarker(balancedAsterisk, /(?<!_)__(?!_)/g, 2);
    })
    .join('\n');

  // 6. Normalize quoted emphasis wrappers: **"텍스트"** / **'텍스트'** -> **텍스트**
  processed = processed.replace(/\*\*\s*['"“”‘’]\s*([^*\n]+?)\s*['"“”‘’]\s*\*\*/g, '**$1**');
  processed = processed.replace(/__\s*['"“”‘’]\s*([^_\n]+?)\s*['"“”‘’]\s*__/g, '__$1__');

  // 7. Ensure spacing after closing emphasis marker when attached to text.
  processed = processed.replace(/(?<=\S)(\*\*|__)(?=[가-힣A-Za-z0-9])/g, '$1 ');

  // 8. Fix CJK boundary issues: "**Bold**Suffix" -> "**Bold** Suffix"
  processed = processed.replace(/\*\*([A-Za-z0-9가-힣(][^*\n]*?)\*\*([가-힣])/g, '**$1** $2');
  processed = processed.replace(/__([A-Za-z0-9가-힣(][^_\n]*?)__([가-힣])/g, '__$1__ $2');

  return processed;
};

export const extractSuggestions = (text: string, isStreaming: boolean = false, streamReasoning?: string) => {
  let processed = text;
  let suggestions: string[] = [];
  // 이 메시지가 SSE 로 온 것인지 판정한다. 스트리밍 경로는 reasoning 을 빈 문자열로
  // 초기화하므로 값이 언제나 문자열이고, 히스토리 복원과 비스트리밍 JSON 응답은
  // reasoning 자체가 없다. 길이를 조건에 넣으면 추론 없는 스트리밍 응답이 히스토리로
  // 오판정되어, 답변에 [추론 과정] 이라는 문구만 들어 있어도 그 뒤가 통째로 숨는다.
  const hasStreamReasoning = typeof streamReasoning === 'string';
  let reasoning = hasStreamReasoning ? streamReasoning : "";

  const suggestionMatch = processed.match(/(?:\*\*|__)?\\*\[\s*추천\s*질문\s*\\*\](?:\*\*|__)?[\s\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\n');
    suggestions = lines
      .map(l => l.replace(/^(?:\d+\.|\-|\*)\s*/, '').trim())
      .filter(l => l.length > 0 && !l.replace(/\*/g, '').includes('[추천 질문]'))
      .map(l => l.replace(/\*\*/g, ''))
      .map(l => Array.from(l).slice(0, 120).join(''))
      .slice(0, 3); // 별표 제거·유니코드 안전 길이·표시 상한
  }

  const reasonStartRegex = /(?:\*\*|__)?\**\[\s*추론\s*과정\s*\]\**(?:\*\*|__)?/i;
  const reasonEndRegex = /(?:---|___|\*\*\*|)\s*(?:\n)*\s*(?:\*\*|__)?\**\[\s*답변\s*\]\**(?:\*\*|__)?/i;

  if (!hasStreamReasoning) {
    // Fallback parser for legacy/history messages where reasoning and answer are mixed in one text.
    const startMatch = processed.match(reasonStartRegex);
    const endMatch = processed.match(reasonEndRegex);

    if (startMatch) {
      if (endMatch) {
        // Both start and end exist (fully generated or streaming past reasoning)
        const reasoningBlock = processed.substring(startMatch.index!, endMatch.index!);
        reasoning = reasoningBlock;
        processed = processed.substring(0, startMatch.index!) + processed.substring(endMatch.index!); // Remove the reasoning block from the visible chat
      } else if (isStreaming) {
        // Stream is active, and only start tag exists. Everything after start is reasoning.
        reasoning = processed.substring(startMatch.index!);
        processed = processed.substring(0, startMatch.index!); // The visible text is empty (or whatever was before the reasoning)
      } else {
        // Non-streaming fallback:
        // If [답변] header is missing, do not hide the whole body as reasoning-only.
        // Keep full text in answer area to prevent empty final answer.
        reasoning = "";
      }
    } else if (isStreaming) {
      // FALLBACK: Aggressively match incomplete reasoning tags during early streaming
      if (!endMatch && processed.trim().length > 0 && processed.trim().length < 50) {
        // If the stream just started and starts with typical tag characters
        if (processed.trim().startsWith('*') || processed.trim().startsWith('[')) {
          reasoning = processed;
          processed = '';
        }
      }
    }
  }

  // Strip '[답변]' markers and horizontal rules just before it
  processed = processed.replace(reasonEndRegex, '');

  // FORCE newlines before numbered lists inside dense text
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  processed = splitDenseNumberedLists(processed);

  const reasoningHeaderRegex = /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|__)?\s*\n?/i;
  let cleanReasoning = preprocessMarkdown(reasoning).replace(reasoningHeaderRegex, '').trim();

  // Cleanup trailing broken markdown
  if (isStreaming) {
    cleanReasoning = cleanReasoning.replace(/[\*\_\[\]]+$/, '');
  }

  // FORCE newlines before numbered lists inside dense text (e.g., "내용 2. ")
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  cleanReasoning = splitDenseNumberedLists(cleanReasoning);

  return { content: processed.trim(), suggestions, reasoning: cleanReasoning };
};
