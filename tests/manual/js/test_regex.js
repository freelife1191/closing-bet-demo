const text = `[추론 과정]1. 시장 상태 분석: 제공된 데이터에 따르면
결론: 비중을 확대하는 전략이 유효합니다.

[답변]현재 마켓게이트는 GREEN 상태입니다.
`;

const reasonRegex = /(?:\*\*|)?\[추론\s*과정\](?:\*\*|)?([\s\S]*?)(?=(?:\*\*|)?\[답변\](?:\*\*|)?|$)/i;
const reasonMatch = text.match(reasonRegex);

console.log("reasonMatch:", reasonMatch ? reasonMatch[0] : null);

let processed = text;
if (reasonMatch) {
    processed = processed.replace(reasonRegex, '');
}
console.log("Processed:", processed);
