const text1 = `[추론 과정]
시장 상황 분석: 현재 Market Gate는 🟢 GREEN 상태 입니다. 코스피와 코스닥 지수가 견고하며, 공격적인 진입이 가능한 시장 환경입니다. 환율이 1,450원으로 다소 높으나 수급이 이를 상쇄하고 있습니다.
결론: 시장 상태가 GREEN이므로, 제공된 AI 분석 결과 중 수급 점수가 높고 VCP 수축 비율이 양호한 3개 종목을 중심으로 매수 전략을 수립합니다.

[답변]
현재 시장은 GREEN...`;

function parseAIResponse(text) {
  let processed = text;
  let reasoning = "";

  const reasonRegex = /(?:\*\*|)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|)?([\s\S]*?)(?=(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?|$)/i;
  const reasonMatch = processed.match(reasonRegex);

  if (reasonMatch) {
    reasoning = reasonMatch[0] || "";
    processed = processed.replace(reasonMatch[0], ''); // <-- THIS !!
  }

  processed = processed.replace(/(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?\s*\n*/gi, '');

  return { cleanText: processed.trim(), reasoning: reasoning };
}

console.log(parseAIResponse(text1));
