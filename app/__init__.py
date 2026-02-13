#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Application Factory
"""

import os
import sys
import logging

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set path to project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Custom filter to suppress repetitive polling logs
class PollingLogFilter(logging.Filter):
    """Filter out repetitive polling API logs"""
    SUPPRESSED_PATHS = [
        '/api/system/update-status',
        '/api/system/data-status',
        '/api/kr/jongga-v2/status',
        '/api/kr/status',
        '/api/kr/stock-detail',  # 상세 조회 로그도 제외
        '/health',
    ]
    
    def filter(self, record):
        message = record.getMessage()
        for path in self.SUPPRESSED_PATHS:
            if path in message:
                return False  # Suppress this log
        return True  # Allow this log


# Apply filter to werkzeug logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(PollingLogFilter())

# Import Blueprints
try:
    from app.routes import kr_bp, common_bp
    blueprints = [kr_bp, common_bp]
except ImportError as e:
    print(f"Error importing blueprints: {e}")
    blueprints = []

def create_app():
    # Ensure logs are printed to stdout
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', force=True)
    
    # [FIX] Suppress repetitive logs from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('google_genai').setLevel(logging.WARNING)
    logging.getLogger('google_genai.models').setLevel(logging.WARNING)
    
    app = Flask(__name__)
    
    # [Middleware] ProxyFix for Real IP - Reverted in favor of manual check
    # from werkzeug.middleware.proxy_fix import ProxyFix
    # app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # -------------------------------------------------------------
    # [FIX] Reset Update Status on Startup (Prevents Ghost Updates)
    # -------------------------------------------------------------
    try:
        import json
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        common_status_file = os.path.join(data_dir, 'update_status.json')
        v2_status_file = os.path.join(data_dir, 'v2_screener_status.json')
        
        # 1. Reset Common Update Status
        if os.path.exists(common_status_file):
            try:
                with open(common_status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                
                # 강제 리셋 (서버 재시작 시 이전 실행 상태 무효화)
                # 실행 중이었거나 알 수 없는 상태라면 초기화
                updated = False
                if status.get('isRunning', False):
                    status['isRunning'] = False
                    status['items'] = [] 
                    updated = True
                
                if updated:
                    with open(common_status_file, 'w', encoding='utf-8') as f:
                        json.dump(status, f, indent=2)
                    print("[Startup] 🧹 Reset stuck update_status.json")
            except Exception as e:
                print(f"[Startup] Error reading/writing update_status.json: {e}")

        # 2. Reset V2 Screener Status
        # 항상 초기화 (서버 끄면 스레드도 죽으므로)
        with open(v2_status_file, 'w', encoding='utf-8') as f:
             json.dump({'isRunning': False}, f)
             logging.debug("[Startup] 🧹 Reset v2_screener_status.json")

    except Exception as e:
        print(f"[Startup] Failed to reset status files: {e}")

    # Start Scheduler (Singleton protected)
    try:
        from services import scheduler
        scheduler.start_scheduler()
    except Exception as e:
        print(f"Failed to start scheduler: {e}")

    # Config
    app.config['JSON_AS_ASCII'] = False
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1']

    # CORS
    # Render + Vercel 연동을 위해 구체적인 Origin 설정 또는 wildcard 사용
    # Vercel 환경에서 NEXT_PUBLIC_API_URL로 호출 시 CORS 이슈 발생 가능
    cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS(app, resources={r"/*": {"origins": cors_origins}})

    # Middleware: Request Hook for API Key Handling
    @app.before_request
    def check_api_key():
        # OPTIONS 요청은 통과 (CORS Preflight)
        if request.method == 'OPTIONS':
            return
            
        # 헤더에서 Key 추출 (없으면 None)
        g.user_api_key = request.headers.get('X-Gemini-Key')
        g.user_email = request.headers.get('X-User-Email') # 프론트에서 세션 이메일 전송
        g.session_id = request.headers.get('X-Session-Id') # 브라우저 세션 ID

    # Middleware: Activity Logging
    @app.after_request
    def log_activity(response):
        try:
            # Skip logging for OPTIONS and static polling paths
            if request.method == 'OPTIONS':
                return response
                
            path = request.path
            # Suppress noisy paths
            noisy_paths = [
                '/health',
                '/api/system/update-status',
                '/api/system/data-status',
                '/api/kr/jongga-v2/status',
                '/api/kr/status',
                '/api/kr/realtime-prices',
                '/static',
                '/favicon.ico'
            ]
            if any(path.startswith(p) for p in noisy_paths):
                return response
                
            # Determine User ID (Email > Session ID > IP)
            user_id = getattr(g, 'user_email', None)
            if not user_id or user_id == 'user@example.com':
                user_id = getattr(g, 'session_id', None)
            
            # Log Action
            from services.activity_logger import activity_logger
            
            status_code = response.status_code
            # only log errors or non-GET modification requests, OR major GET requests
            # For "Connection History", maybe log all non-noisy requests?
            # Let's log everything that isn't noisy.
            
            # Determine Device Type
            ua_string = request.user_agent.string
            device_type = 'WEB'
            if request.user_agent.platform in ('android', 'iphone', 'ipad') or 'Mobile' in ua_string:
                device_type = 'MOBILE'
            
            details = {
                'method': request.method,
                'path': path,
                'status': status_code,
                'device': device_type,
                'session_id': getattr(g, 'session_id', None),
                'user_agent': ua_string[:150] if ua_string else None
            }
            
            # Get Real IP (Trust X-Forwarded-For from Frontend/Proxy)
            real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if real_ip and ',' in real_ip:
                real_ip = real_ip.split(',')[0].strip()

            activity_logger.log_action(
                user_id=user_id,
                action='API_ACCESS',
                details=details,
                ip_address=real_ip
            )
            
        except Exception as e:
            # Logging should not break the request
            print(f"Activity Log Error: {e}")
            
        return response

    # Register Blueprints with URL prefixes
    from app.routes import kr_bp, common_bp
    app.register_blueprint(kr_bp, url_prefix='/api/kr')
    app.register_blueprint(common_bp, url_prefix='/api')

    # Routes
    @app.route('/')
    def index():
        return jsonify({'status': 'OK', 'app': 'KR Market API'})

    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'})

    # Global Error Handler for Diagnostics
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the full traceback to a special file
        import traceback
        error_msg = f"Unhandled Exception: {str(e)}\n{traceback.format_exc()}"
        print(f"\nCRITICAL SERVER ERROR:\n{error_msg}\n", flush=True)
        
        # Log to file
        try:
            with open('logs/critical_errors.log', 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now().isoformat()}] {error_msg}\n")
        except:
            pass

        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'type': type(e).__name__
        }), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5501, debug=True)
