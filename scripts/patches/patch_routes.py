import sys

with open('app/routes/kr_market.py', 'r') as f:
    content = f.read()

# Find bot = get_chatbot() in kr_chatbot
target_str = "        bot = get_chatbot()"
start_idx = content.find(target_str, content.find('def kr_chatbot():'))
if start_idx == -1:
    print("Could not find start idx")
    sys.exit(1)

end_str = "logger.error(f\"[{usage_key}] Chat log error: {e}\")"
end_idx = content.find(end_str, start_idx) + len(end_str)
if end_idx < start_idx:
    print("Could not find end idx")
    sys.exit(1)

new_code = """        bot = get_chatbot()

        from flask import Response, stream_with_context
        import json

        def generate():
            full_response = ""
            usage_metadata = {}
            for chunk in bot.chat_stream(
                message, 
                session_id=session_id, 
                model=model_name, 
                files=files if files else None, 
                watchlist=watchlist,
                persona=persona,
                api_key=user_api_key,
                owner_id=usage_key
            ):
                if "chunk" in chunk:
                    full_response += chunk["chunk"]
                if "usage_metadata" in chunk:
                    usage_metadata = chunk["usage_metadata"]
                
                # Server-Sent Events format
                yield f"data: {json.dumps(chunk)}\\n\\n"
            
            # [Log] Chat Activity after streaming completes
            try:
                from services.activity_logger import activity_logger
                ua_string = request.user_agent.string
                device_type = 'WEB'
                if request.user_agent.platform in ('android', 'iphone', 'ipad') or 'Mobile' in ua_string:
                    device_type = 'MOBILE'

                real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if real_ip and ',' in real_ip:
                    real_ip = real_ip.split(',')[0].strip()

                activity_logger.log_action(
                    user_id=usage_key,
                    action='CHAT_MESSAGE',
                    details={
                        'session_id': session_id,
                        'model': model_name,
                        'user_message': message[:2000] if message else "",
                        'bot_response': full_response[:2000] if full_response else "",
                        'token_usage': usage_metadata,
                        'has_files': bool(files),
                        'device': device_type,
                        'user_agent': ua_string[:150]
                    },
                    ip_address=real_ip
                )
            except Exception as e:
                logger.error(f"[{usage_key}] Chat log error: {e}")

        return Response(stream_with_context(generate()), content_type='text/event-stream')"""

content = content[:start_idx] + new_code + content[end_idx:]

with open('app/routes/kr_market.py', 'w') as f:
    f.write(content)

print("Patch applied.")
