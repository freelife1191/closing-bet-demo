const tests = [
  "[추론 과정]",
  "\\[추론 과정\\]",
  "\\\\[추론 과정\\\\]",
  "**[추론 과정]**",
  "**\\[추론 과정\\]**",
  "[ 답변 ]",
  "**[답변]**"
];

const reasonRegex = /(?:\*\*|__)?\\*\[\s*추론\s*과정\s*\\*\](?:\*\*|__)?([\s\S]*?)(?=(?:\*\*|__)?\\*\[\s*답변\s*\\*\](?:\*\*|__)?|$)/i;
const answerRegex = /(?:\*\*|__)?\\*\[\s*답변\s*\\*\](?:\*\*|__)?\s*\n*/gi;

tests.forEach(t => {
  let matched = false;
  if(t.match(reasonRegex)) matched = true;
  if(t.match(answerRegex)) matched = true;
  console.log(`${t} -> ${matched}`);
});

