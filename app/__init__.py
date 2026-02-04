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
    
    app = Flask(__name__)

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

        # 공용 키 사용량 체크 로직은 개별 Route 또는 Decorator에서 수행
        # 여기서는 전역 변수(g)에 세팅만 함

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
    app.run(host='0.0.0.0', port=5001, debug=True)
