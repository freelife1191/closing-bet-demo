# 채팅 위젯 반응형 패턴

이 문서는 채팅 위젯 컴포넌트의 반응형 디자인 패턴을 다룹니다.

## 1. 전체 채팅 위젯 구조

```tsx
'use client';

import { useState, useRef, useEffect } from 'react';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) scrollToBottom();
  }, [messages, isOpen]);

  return (
    <>
      {/* Chat Window */}
      {isOpen && (
        <div className="
          fixed inset-0 z-[110] w-full h-[100dvh]
          md:fixed md:inset-auto md:bottom-24 md:right-6
          md:w-[430px] md:h-[730px] md:max-h-[80vh]
          bg-[#1c1c1e] md:border border-white/10 md:rounded-2xl
          shadow-2xl flex flex-col overflow-hidden
          animate-fade-in font-sans md:z-[110]
        ">
          {/* Header */}
          {/* Messages Area */}
          {/* Input Area */}
        </div>
      )}

      {/* Toggle Button (Floating) */}
      <div className="fixed bottom-3 right-3 md:bottom-6 md:right-6 z-[120]">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="
            w-11 h-11 md:w-14 md:h-14
            rounded-full shadow-lg
            flex items-center justify-center
            transition-all hover:scale-105 active:scale-95
          "
        >
          <i className={`fas fa-${isOpen ? 'times' : 'comment-dots'} text-lg md:text-2xl`}></i>
        </button>
      </div>
    </>
  );
}
```

### 반응형 크기

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 채팅창 위치 | `fixed inset-0` (전체 화면) | `fixed` (우하단) |
| 너비 | `w-full` | `w-[430px]` |
| 높이 | `h-[100dvh]` (동적 높이) | `h-[730px] max-h-[80vh]` |
| 토글 버튼 | `w-11 h-11` (44px) | `w-14 h-14` (56px) |
| 버튼 위치 | `bottom-3 right-3` | `bottom-6 right-6` |
| 테두리 | 없음 | `border rounded-2xl` |

## 2. 헤더 영역

```tsx
<div className="
  bg-[#2c2c2e] p-4
  flex items-center justify-between
  border-b border-white/5
  flex-shrink-0
">
  {/* Left: Avatar + Title */}
  <div className="flex items-center gap-2 overflow-hidden">
    <div className="
      w-8 h-8
      bg-gradient-to-br from-blue-500 to-purple-600
      rounded-xl flex items-center justify-center
      shadow-lg flex-shrink-0
    ">
      <i className="fas fa-robot text-sm text-white"></i>
    </div>
    <div className="min-w-0">
      <div className="font-bold text-white text-sm flex items-center gap-2 whitespace-nowrap">
        챗봇 이름
        {/* Status Indicator */}
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse flex-shrink-0"></span>
      </div>
      <div className="text-[10px] text-gray-400 truncate">
        상태 메시지
      </div>
    </div>
  </div>

  {/* Right: Action Buttons */}
  <div className="flex items-center gap-2">
    <button className="p-2 text-gray-400 hover:text-white transition-colors">
      <i className="fas fa-eraser text-xs"></i>
    </button>
    <div className="w-[1px] h-4 bg-white/10 mx-1"></div>
    <button
      onClick={toggleChat}
      className="p-2 text-gray-400 hover:text-white transition-colors"
    >
      <i className="fas fa-times"></i>
    </button>
  </div>
</div>
```

## 3. 메시지 영역

```tsx
<div className="
  flex-1 overflow-y-auto
  bg-[#151517] relative
  custom-scrollbar
">
  {/* Welcome Screen (Empty State) */}
  {messages.length === 0 ? (
    <div className="
      p-6 flex flex-col h-full
      justify-center items-center text-center
    ">
      <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <i className="fas fa-robot text-3xl text-white"></i>
      </div>
      <h2 className="text-xl md:text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
        안녕하세요!
      </h2>
      <p className="text-gray-400 text-sm max-w-[280px] mx-auto">
        챗봇이 도와드립니다.
      </p>

      {/* Suggestion Chips */}
      <div className="w-full mt-8 grid grid-cols-2 gap-2">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => handleSend(s)}
            className="
              bg-[#2c2c2e] hover:bg-[#3a3a3c]
              border border-white/5 hover:border-blue-500/30
              p-3 rounded-2xl text-xs text-gray-300 hover:text-white
              text-left flex items-center justify-between
              h-full min-h-[60px]
            "
          >
            <span className="line-clamp-2 leading-tight">{s}</span>
            <i className="fas fa-arrow-right text-[10px] opacity-0 group-hover:opacity-100 text-blue-400 ml-1"></i>
          </button>
        ))}
      </div>
    </div>
  ) : (
    /* Message List */
    <div className="p-4 space-y-4 pb-20">
      {messages.map((msg, idx) => (
        <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`
            max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed
            ${msg.role === 'user'
              ? 'bg-blue-600 text-white whitespace-pre-wrap'
              : 'bg-[#2c2c2e] text-gray-200'
            }
          `}>
            {msg.content}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>
  )}
</div>
```

### 메시지 버블 스타일

| 역할 | 배경색 | 텍스트색 | 최대너비 |
|------|--------|----------|----------|
| 사용자 | `bg-blue-600` | `text-white` | `max-w-[85%]` |
| 봇 | `bg-[#2c2c2e]` | `text-gray-200` | `max-w-[85%]` |

## 4. 입력 영역 (하단 고정)

```tsx
<div className="
  p-3 bg-[#1c1c1e] border-t border-white/5
  relative z-20 flex-shrink-0
">
  <div className="
    flex items-end gap-2
    bg-[#2c2c2e] rounded-3xl p-2 pl-4
    ring-1 ring-white/5 focus-within:ring-blue-500/50
  ">
    {/* Command Button */}
    <button
      onClick={() => setInput('/ ')}
      className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-blue-400"
    >
      <i className="fas fa-terminal text-xs"></i>
    </button>

    {/* Textarea (Auto-resize) */}
    <textarea
      ref={textareaRef}
      value={input}
      onChange={(e) => setInput(e.target.value)}
      placeholder="메시지를 입력하세요..."
      className="
        flex-1 bg-transparent text-white text-sm
        placeholder-gray-500 resize-none
        focus:outline-none py-1.5 leading-relaxed
        max-h-[100px] min-h-[36px]
      "
      rows={1}
      onInput={(e) => {
        const target = e.target as HTMLTextAreaElement;
        target.style.height = 'auto';
        target.style.height = `${Math.min(target.scrollHeight, 100)}px`;
      }}
    />

    {/* Send Button */}
    <button
      onClick={handleSend}
      disabled={!input.trim() || isLoading}
      className="w-8 h-8 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg flex items-center justify-center text-white"
    >
      {isLoading ? (
        <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
      ) : (
        <i className="fas fa-paper-plane text-xs"></i>
      )}
    </button>
  </div>
</div>
```

### 입력창 높이 동적 조절

```tsx
onInput={(e) => {
  const target = e.target as HTMLTextAreaElement;
  target.style.height = 'auto';  // 초기화
  target.style.height = `${Math.min(target.scrollHeight, 100)}px`;  // 최대 100px
}}
```

## 5. 제안 칩 (Suggestion Chips)

```tsx
{/* Persistent Suggestions (Bottom of Chat) */}
{messages.length > 0 && (
  <div className="
    bg-[#1c1c1e] border-t border-white/5
    py-3 px-4 flex-shrink-0
  ">
    <div className="flex gap-2 overflow-x-auto custom-scrollbar-hide">
      {suggestions.map((s, idx) => (
        <button
          key={idx}
          onClick={() => handleSend(s)}
          className="
            flex-shrink-0 px-3 py-1.5
            bg-[#2c2c2e] hover:bg-blue-600
            border border-white/5 rounded-full
            text-[11px] text-gray-400 hover:text-white
            transition-all whitespace-nowrap
          "
        >
          {s}
        </button>
      ))}
    </div>
  </div>
)}
```

### 제안 칩 스타일

| 클래스 | 설명 |
|--------|------|
| `flex-shrink-0` | 줄바꿈 방지 |
| `whitespace-nowrap` | 텍스트 줄바꿈 방지 |
| `overflow-x-auto` | 가로 스크롤 |
| `custom-scrollbar-hide` | 스크롤바 숨김 (CSS 정의 필요) |

## 6. 로딩 인디케이터

```tsx
{isLoading && (
  <div className="flex justify-start">
    <div className="bg-[#2c2c2e] rounded-xl px-4 py-3 border border-white/5">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
        <span className="text-xs text-gray-300 font-medium animate-pulse">
          {thinkingSteps[stepIndex]}
        </span>
      </div>
    </div>
  </div>
)}
```

## 7. 슬래시 커맨드 팝업

```tsx
{/* Command Suggestions Popup */}
{input.startsWith('/') && filteredCommands.length > 0 && (
  <div className="
    absolute bottom-[70px] left-2 right-2
    bg-[#1c1c1e] border border-white/10
    rounded-xl shadow-2xl overflow-hidden
    max-h-[200px] overflow-y-auto z-[60]
  ">
    <div className="px-3 py-2 bg-[#2c2c2e] border-b border-white/5 text-[10px] font-bold text-gray-400">
      사용 가능한 명령어
    </div>
    {filteredCommands.map((cmd, idx) => (
      <button
        key={idx}
        className={`
          w-full text-left px-4 py-2 text-xs
          flex justify-between items-center
          transition-colors group
          ${idx === selectedIndex
            ? 'bg-blue-600/20 text-white'
            : 'text-gray-200 hover:bg-blue-600/20'
          }
        `}
      >
        <span className={`font-mono font-bold ${idx === selectedIndex ? 'text-blue-300' : 'text-blue-400'}`}>
          {cmd.cmd}
        </span>
        <span className="text-gray-500 group-hover:text-gray-300">{cmd.desc}</span>
      </button>
    ))}
  </div>
)}
```

## 8. CSS 추가 (Scrollbar)

```css
/* globals.css */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

.custom-scrollbar-hide {
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
}

.custom-scrollbar-hide::-webkit-scrollbar {
  display: none;  /* Chrome, Safari, Opera */
}
```

## 요약

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 채팅창 | 전체 화면 | 430x730px (우하단) |
| 헤더 | 고정 높이 | 동일 |
| 메시지 영역 | 스크롤 가능 | 동일 |
| 입력창 | 하단 고정 | 동일 |
| 토글 버튼 | 44px | 56px |
| 제안 칩 | 가로 스크롤 | 동일 |
