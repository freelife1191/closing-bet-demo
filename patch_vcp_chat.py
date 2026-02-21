import sys
import re

with open('frontend/src/app/dashboard/kr/vcp/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Message interface (if it has one) or just ensure isStreaming is there
# vcp/page.tsx has interface ChatMessage { role: 'user'|'model', text: string, timestamp?: string }
# Let's add isStreaming?: boolean;
content = content.replace("  timestamp?: string;\n}", "  timestamp?: string;\n  isStreaming?: boolean;\n}")

# 2. Update parseAIResponse
old_parse = """const parseAIResponse = (text: string) => {
  let processed = text;
  let extractedSuggestions: string[] = [];

  const suggestionMatch = processed.match(/(?:\\*\\*|)?\\[추천\\s*질문\\](?:\\*\\*|)?[\\s\\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\\n');
    extractedSuggestions = lines
      .map(l => l.replace(/^(?:\\d+\\.|\\-|\\*)\\s*/, '').trim())
      .filter(l => l.length > 0 && !l.replace(/\\*/g, '').includes('[추천 질문]'));
  }

  const reasonRegex = /(?:\\*\\*|)?\\[추론\\s*과정\\](?:\\*\\*|)?[\\s\\S]*?(?=(?:\\*\\*|)?\\[답변\\](?:\\*\\*|)?)/i;
  processed = processed.replace(reasonRegex, '');
  processed = processed.replace(/(?:\\*\\*|)?\\[답변\\](?:\\*\\*|)?\\s*\\n*/gi, '');

  processed = preprocessMarkdown(processed);

  return { cleanText: processed.trim(), extractedSuggestions };
};"""

new_parse = """const parseAIResponse = (text: string, isStreaming: boolean = false) => {
  let processed = text;
  let extractedSuggestions: string[] = [];
  let reasoning = "";

  const suggestionMatch = processed.match(/(?:\\*\\*|)?\\[추천\\s*질문\\](?:\\*\\*|)?[\\s\\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\\n');
    extractedSuggestions = lines
      .map(l => l.replace(/^(?:\\d+\\.|\\-|\\*)\\s*/, '').trim())
      .filter(l => l.length > 0 && !l.replace(/\\*/g, '').includes('[추천 질문]'));
  }

  const reasonRegex = /(?:\\*\\*|)?\\[추론\\s*과정\\](?:\\*\\*|)?([\\s\\S]*?)(?=(?:\\*\\*|)?\\[답변\\](?:\\*\\*|)?|$)/i;
  const reasonMatch = processed.match(reasonRegex);
  
  if (reasonMatch) {
    reasoning = reasonMatch[0] || "";
    processed = processed.replace(reasonRegex, '');
  }

  processed = processed.replace(/(?:\\*\\*|)?\\[답변\\](?:\\*\\*|)?\\s*\\n*/gi, '');
  processed = preprocessMarkdown(processed);

  return { cleanText: processed.trim(), extractedSuggestions, reasoning: preprocessMarkdown(reasoning).trim() };
};"""
content = content.replace(old_parse, new_parse)

# 3. Update handleVCPChatSend
search_str = """      const res = await fetch('/api/kr/chatbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Email': userEmail || '',
          'X-Gemini-Key': apiKey || '',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({ message: text, persona: 'vcp' }),
      });

      const data = await res.json();
      
      if (res.status === 401 || res.status === 402) {
        setChatHistory(prev => [...prev, { role: 'model', text: `⚠️ ${data.error}` }]);
        return;
      }

      if (data.response) {
        setChatHistory(prev => [...prev, { role: 'model', text: data.response }]);
      } else if (data.error) {
        setChatHistory(prev => [...prev, { role: 'model', text: `⚠️ 오류: ${data.error}` }]);
      } else {
        setChatHistory(prev => [...prev, { role: 'model', text: '⚠️ 응답 없음' }]);
      }"""

new_fetch = """      const res = await fetch('/api/kr/chatbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Email': userEmail || '',
          'X-Gemini-Key': apiKey || '',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({ message: text, persona: 'vcp' }),
      });

      if (!res.ok) {
        let errStr = "서버 통신 오류가 발생했습니다.";
        try {
            const errData = await res.json();
            if(errData.error) errStr = errData.error;
        } catch(e) {}
        setChatHistory(prev => [...prev, { role: 'model', text: `⚠️ ${errStr}` }]);
        setChatLoading(false);
        return;
      }

      if (res.body) {
        setChatLoading(false); // Stop block indicator
        
        // Setup a new streaming message
        setChatHistory(prev => [...prev, { role: 'model', text: "", isStreaming: true }]);
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let done = false;
        let buffer = "";
        
        while (!done) {
            const { value, done: readerDone } = await reader.read();
            done = readerDone;
            if (value) {
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\\n\\n");
                buffer = parts.pop() || "";
                
                for (const part of parts) {
                    if (part.startsWith("data: ")) {
                        const dataStr = part.substring(6);
                        if (!dataStr.trim()) continue;
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.error) {
                                setChatHistory(prev => {
                                    const newMsgs = [...prev];
                                    newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], text: `⚠️ 오류: ${data.error}`, isStreaming: false };
                                    return newMsgs;
                                });
                            }
                            if (data.chunk) {
                                setChatHistory(prev => {
                                    const newMsgs = [...prev];
                                    const lastMsg = newMsgs[newMsgs.length - 1];
                                    lastMsg.text += data.chunk;
                                    return newMsgs;
                                });
                            }
                            if (data.done) {
                                setChatHistory(prev => {
                                    const newMsgs = [...prev];
                                    newMsgs[newMsgs.length - 1].isStreaming = false;
                                    return newMsgs;
                                });
                            }
                        } catch (e) {
                            console.error("SSE Parse logic error", e);
                        }
                    }
                }
            }
        }
      }"""
content = content.replace(search_str, new_fetch)

# 4. Update renderer in vcp/page.tsx
old_render = """                        (() => {
                          const { cleanText, extractedSuggestions } = parseAIResponse(msg.text);
                          return (
                            <div className="flex flex-col gap-2 relative z-10 w-full overflow-hidden">
                              <ReactMarkdown"""

new_render = """                        (() => {
                          const { cleanText, extractedSuggestions, reasoning } = parseAIResponse(msg.text, msg.isStreaming);
                          return (
                            <div className="flex flex-col gap-2 relative z-10 w-full overflow-hidden">
                              {msg.isStreaming && reasoning && (
                                <div className="p-3 bg-black/20 rounded-xl mb-2 animate-pulse border border-white/5 flex flex-col gap-2">
                                    <div className="text-xs font-bold text-blue-400 mb-1 flex items-center gap-2">
                                        <i className="fas fa-brain"></i> 내용을 분석하고 있습니다...
                                    </div>
                                    <div className="text-xs text-transparent bg-clip-text bg-gradient-to-b from-gray-300 to-gray-500 leading-relaxed whitespace-pre-wrap">
                                        {reasoning.replace(/\\[추론\\s*과정\\]/g, '').trim() || ""}
                                    </div>
                                </div>
                              )}

                              <ReactMarkdown"""
content = content.replace(old_render, new_render)

with open('frontend/src/app/dashboard/kr/vcp/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to vcp/page.tsx.")
