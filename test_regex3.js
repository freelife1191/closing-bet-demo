const text1 = `[추론 과정]1. 시장 상태 분석: 제공된 데이터에 따르면 현재 마켓게이트(Market Gate)는 85점 으로, 상태는 🟢 GREEN(강세장, Bullish) 입니다...
[답변] 현재 마켓게이트는 🟢 GREEN (강세장) 상태입니다.`;

const text2 = `반갑습니다! VCP 기반 한국 주식 투자 어드바이저 '스마트머니봇' 입니다.
현재 시장의 흐름과 수급, 그리고 기술적 패턴을 종합하여 최적의 매수 기회를 분석해 드리겠습니다.
---
[추론 과정]
시장 상황 분석: 현재 Market Gate는 🟢 GREEN 상태 입니다...
결론: 시장 상태가 GREEN이므로... 매수 전략을 수립합니다.`;

function parseAIResponse(text) {
  let processed = text;
  let reasoning = "";

  const reasonRegex = /(?:\*\*|)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|)?([\s\S]*?)(?=(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?|$)/i;
  const reasonMatch = processed.match(reasonRegex);
  
  if (reasonMatch) {
    reasoning = reasonMatch[0] || "";
    processed = processed.replace(reasonRegex, '');
  }

  processed = processed.replace(/(?:\*\*|)?\\?\[\s*답변\s*\\?\](?:\*\*|)?\s*\n*/gi, '');
  return processed;
}

console.log("=== Text 1 ===");
console.log(parseAIResponse(text1));
console.log("=== Text 2 ===");
console.log(parseAIResponse(text2));
