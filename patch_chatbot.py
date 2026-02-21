import sys

with open('chatbot/core.py', 'r') as f:
    content = f.read()

# Find def chat
start_idx = content.find('def chat(')
if start_idx == -1:
    print("Could not find chat()")
    sys.exit(1)

# Find end of chat method (def _fetch_jongga_data)
end_idx = content.find('def _fetch_jongga_data', start_idx)
if end_idx == -1:
    print("Could not find end of chat()")
    sys.exit(1)

chat_code = content[start_idx:end_idx]

# Rename def chat to def chat_stream
chat_stream_code = chat_code.replace('def chat(', 'def chat_stream(', 1)

# Inside chat_stream_code, change return {"response": ...} to yielding a generator
# since we want it to be a generator directly, all returns must become yields!
# No, if we yield anywhere, it becomes a generator. So return {"response": X} becomes:
# yield f"data: {{json.dumps({{'error': X}})}}\\n\\n"
# Actually, the easiest way is to yield the chunk dict directly, and the route formats it as SSE.
# Let's yield dicts from chat_stream.

# 1. API key missing
chat_stream_code = chat_stream_code.replace(
    'return {"response": f"⚠️ API Key 오류:', 
    'yield {"error": f"⚠️ API Key 오류:'
)
chat_stream_code = chat_stream_code.replace(
    'return {"response": f"⚠️ AI 모델이 설정되지',
    'yield {"error": f"⚠️ AI 모델이 설정되지'
)
chat_stream_code = chat_stream_code.replace(
    'return {"response": cmd_resp, "session_id": session_id}',
    'yield {"chunk": cmd_resp, "session_id": session_id}\n                return'
)
chat_stream_code = chat_stream_code.replace(
    'return {"response": f"⚠️ 명령어 처리 중',
    'yield {"error": f"⚠️ 명령어 처리 중'
)
# API Rate Limit error
chat_stream_code = chat_stream_code.replace(
    'return {"response": friendly_msg, "session_id": session_id}',
    'yield {"error": friendly_msg, "session_id": session_id}\n                return'
)
chat_stream_code = chat_stream_code.replace(
    'return {"response": f"⚠️ 오류가 발생했습니다: {error_msg}", "session_id": session_id}',
    'yield {"error": f"⚠️ 오류가 발생했습니다: {error_msg}", "session_id": session_id}\n            return'
)

# Now the actual generation part
gen_code_old = """            response = chat_session.send_message(content_parts)
            bot_response = response.text
"""
gen_code_new = """            bot_response = ""
            response_stream = chat_session.send_message_stream(content_parts)
            for chunk in response_stream:
                if chunk.text:
                    bot_response += chunk.text
                    yield {"chunk": chunk.text, "session_id": session_id}
"""
chat_stream_code = chat_stream_code.replace(gen_code_old, gen_code_new)

# Metadata return
ret_old = """            return {
                "response": bot_response, 
                "session_id": session_id,
                "usage_metadata": usage_metadata
            }"""
ret_new = """            # Yield final metadata
            yield {
                "done": True,
                "session_id": session_id,
                "usage_metadata": usage_metadata
            }
            return"""
chat_stream_code = chat_stream_code.replace(ret_old, ret_new)

# Insert it back
new_content = content[:end_idx] + chat_stream_code + content[end_idx:]

with open('chatbot/core.py', 'w') as f:
    f.write(new_content)

print("Patch applied.")
