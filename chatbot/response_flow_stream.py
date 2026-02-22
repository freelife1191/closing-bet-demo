#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 응답 처리: 스트림 파싱/델타 방출 유틸
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, Tuple

from .markdown_utils import (
    ANSWER_HEADER_REGEX,
    REASONING_START_REGEX,
    _compute_stream_delta,
)


_STREAM_HEADER_TAIL_GUARD = 20
_STREAM_HEADER_PROBE_LIMIT = 40
_STREAM_HEADER_PREFIXES = ("[", "\\[", "*[", "**[", "__[")
_STREAM_HEADER_HINTS = ("[", "\\[")


@dataclass
class _StreamParseState:
    mode: str = "detect"  # detect -> reasoning -> answer
    pending: str = ""
    streamed_reasoning: str = ""
    streamed_answer: str = ""


def yield_stream_deltas(
    session_id: str,
    streamed_reasoning: str,
    streamed_answer: str,
    current_reasoning: str,
    current_answer: str,
) -> Generator[Dict[str, Any], None, Tuple[str, str]]:
    """스트리밍 중 추론/답변 델타를 계산하고 이벤트를 방출한다."""
    reasoning_reset, reasoning_delta = _compute_stream_delta(
        streamed_reasoning,
        current_reasoning,
    )
    if reasoning_reset:
        streamed_reasoning = ""
        yield {"reasoning_clear": True, "session_id": session_id}
    if reasoning_delta:
        streamed_reasoning = current_reasoning
        yield {
            "reasoning_chunk": reasoning_delta,
            "session_id": session_id,
        }

    answer_reset, answer_delta = _compute_stream_delta(
        streamed_answer,
        current_answer,
    )
    if answer_reset:
        streamed_answer = ""
        yield {"answer_clear": True, "session_id": session_id}
    if answer_delta:
        streamed_answer = current_answer
        yield {
            "chunk": answer_delta,
            "answer_chunk": answer_delta,
            "session_id": session_id,
        }

    return streamed_reasoning, streamed_answer


def _looks_like_incomplete_header_probe(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) >= _STREAM_HEADER_PROBE_LIMIT:
        return False
    return stripped.startswith(_STREAM_HEADER_PREFIXES)


def _split_emit_and_tail(text: str) -> Tuple[str, str]:
    if len(text) <= _STREAM_HEADER_TAIL_GUARD:
        return "", text
    return text[:-_STREAM_HEADER_TAIL_GUARD], text[-_STREAM_HEADER_TAIL_GUARD:]


def _trim_stream_tail_noise(text: str) -> str:
    if not text:
        return text
    return text.rstrip("*_[]\\")


def _search_reasoning_and_answer_headers(text: str) -> tuple[Any, Any]:
    if not text:
        return None, None
    if not any(hint in text for hint in _STREAM_HEADER_HINTS):
        return None, None
    return REASONING_START_REGEX.search(text), ANSWER_HEADER_REGEX.search(text)


def _search_answer_header(text: str):
    if not text:
        return None
    if not any(hint in text for hint in _STREAM_HEADER_HINTS):
        return None
    return ANSWER_HEADER_REGEX.search(text)


def _consume_pending_text(state: _StreamParseState, chunk_text: str) -> str:
    combined = state.pending + chunk_text
    state.pending = ""
    return combined


def _emit_reasoning_piece(
    session_id: str,
    streamed_reasoning: str,
    piece: str,
) -> Generator[Dict[str, Any], None, str]:
    if not piece:
        return streamed_reasoning

    current_reasoning = streamed_reasoning + piece
    reset, delta = _compute_stream_delta(streamed_reasoning, current_reasoning)
    if reset:
        streamed_reasoning = ""
        yield {"reasoning_clear": True, "session_id": session_id}
        delta = current_reasoning

    if delta:
        streamed_reasoning = current_reasoning
        yield {"reasoning_chunk": delta, "session_id": session_id}

    return streamed_reasoning


def _emit_answer_piece(
    session_id: str,
    streamed_answer: str,
    piece: str,
) -> Generator[Dict[str, Any], None, str]:
    if not piece:
        return streamed_answer

    current_answer = streamed_answer + piece
    reset, delta = _compute_stream_delta(streamed_answer, current_answer)
    if reset:
        streamed_answer = ""
        yield {"answer_clear": True, "session_id": session_id}
        delta = current_answer

    if delta:
        streamed_answer = current_answer
        yield {
            "chunk": delta,
            "answer_chunk": delta,
            "session_id": session_id,
        }

    return streamed_answer


def _handle_detect_mode(
    session_id: str,
    state: _StreamParseState,
    combined: str,
) -> Generator[Dict[str, Any], None, None]:
    reasoning_match, answer_match = _search_reasoning_and_answer_headers(combined)

    if reasoning_match and (
        not answer_match or reasoning_match.start() <= answer_match.start()
    ):
        answer_prefix = combined[: reasoning_match.start()]
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=answer_prefix,
        )
        combined = combined[reasoning_match.end() :]
        state.mode = "reasoning"

    elif answer_match:
        answer_prefix = combined[: answer_match.start()]
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=answer_prefix,
        )
        answer_rest = combined[answer_match.end() :]
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=answer_rest,
        )
        state.mode = "answer"
        return

    else:
        if _looks_like_incomplete_header_probe(combined):
            state.pending = combined
            return

        emit_part, state.pending = _split_emit_and_tail(combined)
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=emit_part,
        )
        return

    answer_in_reasoning = _search_answer_header(combined)
    if answer_in_reasoning:
        reasoning_part = combined[: answer_in_reasoning.start()]
        state.streamed_reasoning = yield from _emit_reasoning_piece(
            session_id=session_id,
            streamed_reasoning=state.streamed_reasoning,
            piece=reasoning_part,
        )
        answer_part = combined[answer_in_reasoning.end() :]
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=answer_part,
        )
        state.mode = "answer"
        return

    emit_part, state.pending = _split_emit_and_tail(combined)
    state.streamed_reasoning = yield from _emit_reasoning_piece(
        session_id=session_id,
        streamed_reasoning=state.streamed_reasoning,
        piece=emit_part,
    )


def _handle_reasoning_mode(
    session_id: str,
    state: _StreamParseState,
    combined: str,
) -> Generator[Dict[str, Any], None, None]:
    answer_match = _search_answer_header(combined)
    if answer_match:
        reasoning_part = combined[: answer_match.start()]
        state.streamed_reasoning = yield from _emit_reasoning_piece(
            session_id=session_id,
            streamed_reasoning=state.streamed_reasoning,
            piece=reasoning_part,
        )
        answer_part = combined[answer_match.end() :]
        state.streamed_answer = yield from _emit_answer_piece(
            session_id=session_id,
            streamed_answer=state.streamed_answer,
            piece=answer_part,
        )
        state.mode = "answer"
        return

    emit_part, state.pending = _split_emit_and_tail(combined)
    state.streamed_reasoning = yield from _emit_reasoning_piece(
        session_id=session_id,
        streamed_reasoning=state.streamed_reasoning,
        piece=emit_part,
    )


def _handle_answer_mode(
    session_id: str,
    state: _StreamParseState,
    combined: str,
) -> Generator[Dict[str, Any], None, None]:
    state.streamed_answer = yield from _emit_answer_piece(
        session_id=session_id,
        streamed_answer=state.streamed_answer,
        piece=combined,
    )


def _flush_pending_piece(
    session_id: str,
    state: _StreamParseState,
) -> Generator[Dict[str, Any], None, None]:
    if not state.pending:
        return

    pending = _trim_stream_tail_noise(state.pending)
    state.pending = ""
    if state.mode == "reasoning":
        state.streamed_reasoning = yield from _emit_reasoning_piece(
            session_id=session_id,
            streamed_reasoning=state.streamed_reasoning,
            piece=pending,
        )
        return

    state.streamed_answer = yield from _emit_answer_piece(
        session_id=session_id,
        streamed_answer=state.streamed_answer,
        piece=pending,
    )


def stream_single_model_response(
    response_stream: Any,
    session_id: str,
) -> Generator[Dict[str, Any], None, Tuple[str, str, str]]:
    """단일 모델 응답 스트림을 증분 파싱으로 처리한다."""
    bot_response_parts: list[str] = []
    state = _StreamParseState()

    for chunk in response_stream:
        chunk_text = getattr(chunk, "text", "")
        if not chunk_text:
            continue

        bot_response_parts.append(chunk_text)
        combined = _consume_pending_text(state=state, chunk_text=chunk_text)

        if state.mode == "detect":
            yield from _handle_detect_mode(
                session_id=session_id,
                state=state,
                combined=combined,
            )
            continue

        if state.mode == "reasoning":
            yield from _handle_reasoning_mode(
                session_id=session_id,
                state=state,
                combined=combined,
            )
            continue

        yield from _handle_answer_mode(
            session_id=session_id,
            state=state,
            combined=combined,
        )

    yield from _flush_pending_piece(session_id=session_id, state=state)

    bot_response = "".join(bot_response_parts)
    return bot_response, state.streamed_reasoning, state.streamed_answer


__all__ = [
    "yield_stream_deltas",
    "stream_single_model_response",
]
