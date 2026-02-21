'use client';

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ThinkingProcessProps {
  reasoning: string;
  isStreaming: boolean;
  className?: string;
}

const normalizeOrderedListMarkdown = (text: string): string => {
  if (!text) return text;

  let normalized = text.replace(/\r\n/g, '\n');

  // Break dense inline numbering into line-based list items.
  normalized = normalized.replace(
    /(?<=\S)\s+(?=(?:\*\*|__)?\d+[.)](?:\s|(?=\*\*|__|[가-힣A-Za-z(])))/g,
    '\n'
  );

  const lines = normalized.split('\n');
  const output: string[] = [];

  for (const line of lines) {
    const trimmed = line.trimStart();
    const orderedMarker = trimmed.match(/^(\d+)[.)]\s*(.*)$/);

    if (!orderedMarker) {
      output.push(line);
      continue;
    }

    const [, num, body] = orderedMarker;
    const previousLine = output[output.length - 1] ?? '';
    const previousTrimmed = previousLine.trim();
    const previousIsOrderedItem = /^\d+\.\s/.test(previousTrimmed);

    // Add a blank line before list start so markdown reliably parses ordered lists.
    if (previousTrimmed && !previousIsOrderedItem) {
      output.push('');
    }

    output.push(`${num}. ${body.trimStart()}`);
  }

  return output.join('\n');
};

export default function ThinkingProcess({ reasoning, isStreaming, className = '' }: ThinkingProcessProps) {
  // If streaming, force open. If done, user can toggle.
  const [isOpen, setIsOpen] = useState(isStreaming);
  const prevStreamingRef = useRef(isStreaming);

  useEffect(() => {
    // If it just started streaming, auto-open it
    if (isStreaming && !prevStreamingRef.current) {
      setIsOpen(true);
    }
    // If it just finished streaming, auto-close it (optional, but requested behavior usually implies this is collapsed by default after done)
    if (!isStreaming && prevStreamingRef.current) {
      setIsOpen(false);
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming]);

  // If we're not streaming anymore, and there's absolutely no reasoning generated, hide it completely.
  if (!reasoning && !isStreaming) return null;

  const normalizedReasoning = normalizeOrderedListMarkdown(reasoning);

  return (
    <div className={`mb-4 overflow-hidden ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors rounded-lg 
                ${isStreaming ? 'text-blue-400 bg-blue-500/10' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'}
            `}
      >
        {isStreaming ? (
          <>
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
            </span>
            생각하는 과정 표시...
          </>
        ) : (
          <>
            <i className="fas fa-brain"></i>
            생각하는 과정 표시
          </>
        )}

        <i className={`fas fa-chevron-down text-xs transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}></i>
      </button>

      {isOpen && reasoning && (
        <div className={`mt-2 p-4 rounded-xl border border-white/5 bg-black/20 text-[13px] leading-relaxed flex flex-col gap-2
                ${isStreaming ? 'animate-pulse opacity-80' : 'text-gray-300'}
            `}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ node, ...props }) => <p className="mb-3 last:mb-0 text-[#b5b5b6]" {...props} />,
              strong: ({ node, ...props }) => <strong className="font-bold text-gray-200" {...props} />,
              ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4 space-y-2 text-[#b5b5b6]" {...props} />,
              ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-4 space-y-2 text-[#b5b5b6]" {...props} />,
              li: ({ node, ...props }) => <li className="text-[#b5b5b6] mb-2 last:mb-0" {...props} />,
              h3: ({ node, ...props }) => <h3 className="font-bold text-gray-200 mb-2 mt-4 text-[14px]" {...props} />,
              h4: ({ node, ...props }) => <h4 className="font-bold text-gray-300 mb-2 mt-3 text-[13px]" {...props} />,
            }}
          >
            {normalizedReasoning}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
