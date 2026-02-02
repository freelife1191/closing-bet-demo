#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 애플리케이션 진입점
기존 호환성을 위해 유지 - 내부적으로 Blueprint 기반 app 사용

원본 파일은 flask_app_backup.py 에 백업됨
"""
import warnings

# 비동기 자원 관련 경고 억제 (Gemini 클라이언트 비동기 종료 관련)
warnings.filterwarnings('ignore', message='.*Task was destroyed but it is pending.*')

from app import create_app

# Create Flask app using factory
app = create_app()

if __name__ == '__main__':
    import os
    from config import config

    print("\n" + "="*60)
    print("🚀 KR Market Package Flask App Starting")
    print("="*60)
    print(f"   Debug Mode: {config.FLASK_DEBUG}")
    print(f"   Port: {config.FLASK_PORT}")
    print(f"   Host: {config.FLASK_HOST}")
    print("="*60)
    
    # 설정값 로드 확인을 위한 진단 출력
    from engine.config import app_config
    
    provider = app_config.LLM_PROVIDER
    if provider == 'zai':
        active_key = app_config.ZAI_API_KEY
        active_model = app_config.ZAI_MODEL
    else:
        active_key = app_config.GOOGLE_API_KEY
        active_model = app_config.GEMINI_MODEL
        
    masked_key = active_key[:6] + "*"*10 if active_key else "None"
    
    print(f"📡 [DIAGNOSTIC] LLM Provider: {provider}")
    print(f"🔑 [DIAGNOSTIC] Active API Key: {masked_key}")
    print(f"🤖 [DIAGNOSTIC] Active Model:   {active_model}")
    print("="*60 + "\n")

    # Start Scheduler
    try:
        from services import scheduler
        scheduler.start_scheduler()
    except Exception as e:
        print(f"Failed to start scheduler: {e}")

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        use_reloader=False  # Avoid duplicate scheduler starts
    )
