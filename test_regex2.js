const text = "\\[추론 과정\\]1. 시장 상태 분석...";
const temp = /(?:\*\*|)?\[추론\s*과정\](?:\*\*|)?/i;
console.log(text.match(temp));

const temp2 = /(?:\*\*|)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|)?/i;
console.log(text.match(temp2));
