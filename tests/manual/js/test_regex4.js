const text1 = `[추론 과정]

시장 상황 분석: 현재 Market Gate는 🟢 GREEN 상태 입니다. 코스피와 코스닥 지수가 견고하며, 공격적인 진입이 가능한 시장 환경입니다. 환율이 1,450원으로 다소 높으나 수급이 이를 상쇄하고 있습니다.
섹터 강도 확인: ** 조선(4.31), 은행(3.4), 자동차(2.88)** 섹터가 시장을 주도하고 있습니다. 추천 종목 중 '기아'가 주도 섹터인 자동차군에 속해 있어 신뢰도가 높습니다.
VCP 데이터 분석:
기아 & 셀트리온: VCP 점수 72점으로 가장 높습니다. 특히 외국인과 기관의 '쌍끌이' 매수가 5일 연속 지속되고 있다는 점이 핵심입니다.
SK하이닉스: 점수는 70점으로 소폭 낮으나, 반도체 섹터 내에서 독보적인 수급 우위를 점하고 있어 추세 돌파 가능성이 큽니다.
결론: 시장 상태가 GREEN이므로, 제공된 AI 분석 결과 중 수급 점수가 높고 VCP 수축 비율이 양호한 3개 종목을 중심으로 매수 전략을 수립합니다.

[답변]
현재 시장은 GREEN...`;

function parseAIResponse(text, isStreaming = false) {
  let processed = text;
  let suggestions = [];
  let reasoning = "";

  const suggestionMatch = processed.match(/(?:\*\*|)?\\?\[\s*추천\s*질문\s*\\?\](?:\*\*|)?[\s\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');
  }

  const reasonRegex = /(?:\*\*|)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|)?([\s\S]*?)(?=(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?|$)/i;
  const reasonMatch = processed.match(reasonRegex);

  if (reasonMatch) {
    reasoning = reasonMatch[0] || "";
    processed = processed.replace(reasonRegex, '');
  }

  processed = processed.replace(/(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?\s*\n*/gi, '');

  return { cleanText: processed.trim(), reasoning: reasoning };
}

console.log("=== Text 1 ===");
const result = parseAIResponse(text1);
console.log("cleanText:\n", result.cleanText);
console.log("\nreasoning:\n", result.reasoning);

