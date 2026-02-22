#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Application Factory
"""

import os
import sys
import logging
import json
import importlib
from datetime import datetime

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv
from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)

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

NOISY_ACTIVITY_PATHS = [
    '/health',
    '/api/system/update-status',
    '/api/system/data-status',
    '/api/kr/jongga-v2/status',
    '/api/kr/status',
    '/api/kr/realtime-prices',
    '/api/kr/market-gate',
    '/api/kr/signals',
    '/api/kr/backtest-summary',
    '/api/kr/user/quota',
    '/api/admin/check',
    '/api/kr/config/interval',
    '/api/kr/jongga-v2/dates',
    '/api/kr/jongga-v2/latest',
    '/static',
    '/favicon.ico',
]


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True,
    )
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('google_genai').setLevel(logging.WARNING)
    logging.getLogger('google_genai.models').setLevel(logging.WARNING)
    logging.getLogger('google_genai._api_client').setLevel(logging.ERROR)


def _reset_startup_status_files() -> None:
    """서버 재시작 시 실행 상태 파일을 안전하게 초기화한다."""
    try:
        data_dir = 'data'
        os.makedirs(data_dir, exist_ok=True)
        common_status_file = os.path.join(data_dir, 'update_status.json')
        v2_status_file = os.path.join(data_dir, 'v2_screener_status.json')

        if os.path.exists(common_status_file):
            try:
                status = load_json_payload_from_path(common_status_file)

                if isinstance(status, dict) and status.get('isRunning', False):
                    status['isRunning'] = False
                    status['items'] = []
                    atomic_write_text(
                        common_status_file,
                        json.dumps(status, ensure_ascii=False, indent=2),
                    )
                    print("[Startup] 🧹 Reset stuck update_status.json")
            except Exception as error:
                print(f"[Startup] Error reading/writing update_status.json: {error}")

        atomic_write_text(
            v2_status_file,
            json.dumps({'isRunning': False}, ensure_ascii=False, indent=2),
        )
        logging.debug("[Startup] 🧹 Reset v2_screener_status.json")
    except Exception as error:
        print(f"[Startup] Failed to reset status files: {error}")


def _start_scheduler() -> None:
    app_logger = logging.getLogger(__name__)
    try:
        scheduler_module = importlib.import_module("services.scheduler")
    except ImportError as error:
        if "schedule" in str(error):
            app_logger.warning(
                "Scheduler dependency 'schedule' is missing. Skipping scheduler start."
            )
        else:
            app_logger.error(f"Failed to import scheduler module: {error}")
        return
    except Exception as error:
        app_logger.error(f"Unexpected scheduler import failure: {error}")
        return

    try:
        scheduler_module.start_scheduler()
    except Exception as error:
        app_logger.error(f"Failed to start scheduler: {error}")


def _configure_app(app: Flask) -> None:
    app.config['JSON_AS_ASCII'] = False
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1']


def _configure_cors(app: Flask) -> None:
    cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS(app, resources={r"/*": {"origins": cors_origins}})


def _register_request_context(app: Flask) -> None:
    @app.before_request
    def check_api_key():
        if request.method == 'OPTIONS':
            return
        g.user_api_key = request.headers.get('X-Gemini-Key')
        g.user_email = request.headers.get('X-User-Email')
        g.session_id = request.headers.get('X-Session-Id')


def _should_skip_activity_logging(method: str, path: str) -> bool:
    if method in ['OPTIONS', 'GET']:
        return True
    return any(path.startswith(prefix) for prefix in NOISY_ACTIVITY_PATHS)


def _resolve_user_id() -> str | None:
    user_id = getattr(g, 'user_email', None)
    if not user_id or user_id == 'user@example.com':
        user_id = getattr(g, 'session_id', None)
    return user_id


def _resolve_device_type() -> str:
    user_agent = request.user_agent.string
    if request.user_agent.platform in ('android', 'iphone', 'ipad') or 'Mobile' in user_agent:
        return 'MOBILE'
    return 'WEB'


def _resolve_real_ip() -> str | None:
    real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if real_ip and ',' in real_ip:
        return real_ip.split(',')[0].strip()
    return real_ip


def _register_activity_logging(app: Flask) -> None:
    @app.after_request
    def log_activity(response):
        try:
            path = request.path
            if _should_skip_activity_logging(request.method, path):
                return response

            from services.activity_logger import activity_logger

            ua_string = request.user_agent.string
            details = {
                'method': request.method,
                'path': path,
                'status': response.status_code,
                'device': _resolve_device_type(),
                'session_id': getattr(g, 'session_id', None),
                'user_agent': ua_string[:150] if ua_string else None,
            }
            activity_logger.log_action(
                user_id=_resolve_user_id(),
                action='API_ACCESS',
                details=details,
                ip_address=_resolve_real_ip(),
            )
        except Exception as error:
            print(f"Activity Log Error: {error}")
        return response


def _register_blueprints(app: Flask) -> None:
    from app.routes import kr_bp, common_bp

    app.register_blueprint(kr_bp, url_prefix='/api/kr')
    app.register_blueprint(common_bp, url_prefix='/api')


def _register_core_routes(app: Flask) -> None:
    @app.route('/')
    def index():
        return jsonify({'status': 'OK', 'app': 'KR Market API'})

    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'})


def _register_global_error_handler(app: Flask) -> None:
    @app.errorhandler(Exception)
    def handle_exception(error):
        import traceback

        error_msg = f"Unhandled Exception: {str(error)}\n{traceback.format_exc()}"
        print(f"\nCRITICAL SERVER ERROR:\n{error_msg}\n", flush=True)

        try:
            with open('logs/critical_errors.log', 'a', encoding='utf-8') as file:
                file.write(f"\n[{datetime.now().isoformat()}] {error_msg}\n")
        except Exception as file_error:
            logging.getLogger(__name__).error(
                f"critical_errors.log write failed: {file_error}"
            )

        return jsonify({
            'error': 'Internal Server Error',
            'message': str(error),
            'type': type(error).__name__,
        }), 500


def create_app():
    _configure_logging()
    app = Flask(__name__)
    _reset_startup_status_files()
    _start_scheduler()
    _configure_app(app)
    _configure_cors(app)
    _register_request_context(app)
    _register_activity_logging(app)
    _register_blueprints(app)
    _register_core_routes(app)
    _register_global_error_handler(app)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5501, debug=True)
