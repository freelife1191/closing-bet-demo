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
from typing import Any

from flask import Flask, jsonify, request, g
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from dotenv import load_dotenv
from engine.pandas_utils_safe import sanitize_for_json
from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)
from services.identity_helpers import resolve_anonymous_id, verify_identity_header
from services.scheduler_runtime_status_service import reset_scheduler_runtime_status

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

# 이 목록에 담는 것은 「GET 이 아닌데도 소음인 경로」뿐이다. 폴링 GET 은
# _should_skip_activity_logging 첫 줄이 메서드만 보고 전부 거르므로 여기 적을 이유가 없다.
#
# [INFRA-059] 이전에는 폴링 GET 경로 열여섯이 들어 있었고 검사가 접두사 일치였다. GET 은
# 이미 걸러진 뒤이므로 그 접두사들이 실제로 한 일은 **그 아래 POST 를 거르는 것**뿐이었고,
# 그 바람에 관리자 전용 POST 다섯이 활동 로그에서 통째로 빠졌다. /api/kr/signals 접두사가
# signals/run·reanalyze-failed-ai·그 stop 셋을, /api/kr/market-gate 가 market-gate/update
# 를, /api/kr/config/interval 이 그 POST 를 먹었다. 인가 경계를 넘은 요청이야말로 누가
# 언제 실행했는지 남아야 하는 것들이다.
#
# 여기에 경로를 더할 때는 그 경로의 POST·PUT·DELETE 가 무엇인지 먼저 본다. 접두사 일치라
# 하위 경로까지 함께 먹는다. tests/app/test_admin_gated_routes.py 가 관리자 전용 라우트에
# 대해 그것을 잰다.
NOISY_ACTIVITY_PATHS = [
    # 60초 주기 시세 폴링이다(frontend/src/app/dashboard/kr/vcp/page.tsx 의 setInterval).
    # 이 목록에서 유일하게 GET 이 아닌 소음이며, 하위 경로가 없어 정확 일치처럼 동작한다.
    '/api/kr/realtime-prices',
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
                # 시작 시점에는 읽기 전용 접근이므로 deep_copy 비용을 줄인다.
                status = load_json_payload_from_path(common_status_file, deep_copy=False)

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
        reset_scheduler_runtime_status(data_dir=data_dir)
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


class NaNSafeJSONProvider(DefaultJSONProvider):
    """NaN 과 Infinity 를 null 로 바꿔 직렬화한다.

    파이썬은 이 세 토큰을 읽고 쓰지만 브라우저의 JSON.parse 는 거부하므로, 한 자리만
    섞여도 본문 전체가 파싱되지 않는다. 필드마다 막으면 새 필드에서 되풀이된다.
    """

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        return super().dumps(sanitize_for_json(obj), **kwargs)


def _configure_app(app: Flask) -> None:
    app.config['JSON_AS_ASCII'] = False
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1']
    app.json = NaNSafeJSONProvider(app)


def _configure_cors(app: Flask) -> None:
    cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS(app, resources={r"/*": {"origins": cors_origins}})


def _register_request_context(app: Flask) -> None:
    @app.before_request
    def check_api_key():
        if request.method == 'OPTIONS':
            return
        # Vertex AI 전환 후 X-Gemini-Key는 무시한다 (사용자별 API 키 기능 제거).
        # 하위 호환을 위해 g.user_api_key 속성은 None으로 유지.
        g.user_api_key = None
        # 브라우저가 보낸 X-User-Email 은 더 이상 읽지 않는다. 그 값은 설정 모달의 자유
        # 입력 칸에서 왔고 서명도 만료도 없었다. frontend/src/proxy.ts 가 NextAuth 세션을
        # 확인해 서명한 헤더만 신원으로 삼는다.
        g.user_email = verify_identity_header(
            request.headers.get('X-Auth-Identity'),
            method=request.method,
            path=request.path,
        )
        # 익명 ID 도 그대로 믿지 않는다. 이 값과 g.user_email 이 같은 문자열 공간에서
        # 챗봇 owner_id 와 쿼터 키가 되므로, 걸러 내지 않으면 헤더 이름만 바꿔 서명
        # 게이트를 우회할 수 있다.
        g.session_id = resolve_anonymous_id(request.headers.get('X-Session-Id'))


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
