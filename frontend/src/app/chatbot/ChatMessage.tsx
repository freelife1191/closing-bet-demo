'use client';

import { memo, useMemo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import ThinkingProcess from '../components/ThinkingProcess';
import {
  extractSuggestions,
  getMessagePartText,
  preprocessMarkdown,
  type Message,
} from './chatMessageParser';

// 렌더마다 새로 만들면 react-markdown 이 프롭이 바뀐 것으로 보고 트리를 다시 만든다.
// 값이 고정이므로 모듈에서 한 번만 만든다.
const REMARK_PLUGINS = [remarkGfm];

const MARKDOWN_COMPONENTS: Components = {
  ul({ children }) { return <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-1">{children}</ul> },
  ol({ children }) { return <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-1">{children}</ol> },
  li({ children }) { return <li className="mb-1 leading-relaxed">{children}</li> },
  code({ node, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '')
    return match ? (
      <div className="relative bg-[#1e1f20] rounded-lg overflow-hidden border border-white/5 my-2 shadow-inner">
        <div className="px-4 py-1.5 bg-black/20 text-[10px] text-gray-500 font-mono border-b border-white/5 flex justify-between">
          <span>{match[1]}</span>
          <span className="cursor-pointer hover:text-white"><i className="far fa-copy"></i></span>
        </div>
        <pre className="p-4 overflow-x-auto m-0 !bg-transparent">
          <code className={className} {...props}>{children}</code>
        </pre>
      </div>
    ) : (
      <code className="bg-white/10 px-1.5 py-0.5 rounded text-blue-300 font-mono text-sm" {...props}>
        {children}
      </code>
    )
  },
  table({ children }) {
    return <div className="overflow-x-auto my-4 border border-white/10 rounded-lg"><table className="min-w-full divide-y divide-white/10">{children}</table></div>
  },
  thead({ children }) {
    return <thead className="bg-white/5">{children}</thead>
  },
  th({ children }) {
    return <th className="px-4 py-2 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">{children}</th>
  },
  td({ children }) {
    return <td className="px-4 py-2 text-sm text-gray-400 whitespace-nowrap border-t border-white/5">{children}</td>
  },
  a({ children, href }) {
    return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a>
  },
  strong({ children }) {
    return <strong className="text-white font-bold">{children}</strong>
  }
};

export interface ChatMessageProps {
  message: Message;
  index: number;
  onDeleteTurn: (e: React.MouseEvent, index: number) => void;
  onDeleteMessage: (e: React.MouseEvent, index: number) => void;
  onSuggestionClick: (text: string) => void;
}

// 메시지 한 건을 그린다. memo 로 감싸는 것이 성능 취향이 아니다. 스트리밍 델타가
// 도착할 때마다 setMessages 가 배열을 새로 만들고, memo 가 없으면 대화에 쌓인 모든
// 메시지가 정규식 스무 개짜리 파싱을 다시 돌린다. useMemo 는 map 콜백 안에서 부를 수
// 없으므로 컴포넌트로 떼어내는 것이 메모이제이션의 전제였다.
function ChatMessageInner({
  message,
  index,
  onDeleteTurn,
  onDeleteMessage,
  onSuggestionClick,
}: ChatMessageProps) {
  const rawText = getMessagePartText(message.parts[0]);

  const { content, suggestions, reasoning } = useMemo(() => {
    if (message.role !== 'model') {
      return { content: rawText, suggestions: [] as string[], reasoning: '' };
    }
    return extractSuggestions(rawText, !!message.isStreaming, message.reasoning);
  }, [message.role, message.isStreaming, message.reasoning, rawText]);

  const renderedMarkdown = useMemo(() => preprocessMarkdown(content), [content]);

  return (
    <div className="flex gap-4 group">
      <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-1 ${message.role === 'user'
        ? 'bg-gray-700 hidden'
        : 'bg-gradient-to-tr from-blue-500 to-purple-500 shadow-lg shadow-purple-500/20'
        }`}>
        {message.role === 'model' && <i className="fas fa-sparkles text-xs text-white"></i>}
      </div>

      <div className="flex-1 space-y-1 overflow-hidden">
        <div className="text-sm font-bold text-gray-400 mb-1 flex items-center gap-2">
          {message.role === 'model' && '스마트머니봇'}
          <span className="text-[10px] text-gray-500 font-normal ml-2">
            {message.timestamp ? new Date(message.timestamp).toLocaleString('ko-KR', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: true
            }) : ''}
          </span>
          {!message.isStreaming && (
            <span className="ml-1 inline-flex items-center gap-1">
              <button
                onClick={(e) => onDeleteTurn(e, index)}
                className="h-6 px-2 rounded-full text-[10px] font-bold text-gray-500 hover:text-amber-300 hover:bg-amber-500/10 transition-colors opacity-70 hover:opacity-100"
                title="이 질문과 답변 함께 삭제"
                aria-label="이 질문과 답변 함께 삭제"
              >
                질문/답변
              </button>
              <button
                onClick={(e) => onDeleteMessage(e, index)}
                className="w-6 h-6 rounded-full text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-70 hover:opacity-100"
                title="이 메시지 삭제"
                aria-label="이 메시지 삭제"
              >
                <i className="fas fa-trash-alt text-[11px]"></i>
              </button>
            </span>
          )}
        </div>
        <div className={`prose prose-sm prose-invert max-w-none leading-relaxed space-y-4 ${message.role === 'user' ? 'text-lg text-gray-100 font-medium' : 'text-gray-300'
          }`}>
          {message.role === 'model' && (
            <ThinkingProcess
              reasoning={reasoning}
              isStreaming={!!message.isStreaming}
            />
          )}
          <ReactMarkdown
            remarkPlugins={REMARK_PLUGINS}
            components={MARKDOWN_COMPONENTS}
          >
            {renderedMarkdown}
          </ReactMarkdown>

          {/* Render Extracted Suggestions */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4 pt-2 border-t border-white/5">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => onSuggestionClick(s)}
                  className="px-3 py-1.5 bg-[#1e1f20] hover:bg-blue-600/20 hover:text-blue-300 hover:border-blue-500/30 border border-white/10 rounded-full text-xs text-gray-300 transition-all text-left shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const ChatMessage = memo(ChatMessageInner);
