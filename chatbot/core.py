#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Stock Chatbot Core - 메인 챗봇 클래스
Gemini AI 연동 및 대화 처리 로직 (지원 모델 설정 가능)
"""

import os
import logging
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from datetime import datetime
import json

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .prompts import build_system_prompt, get_welcome_message, SYSTEM_PERSONA

logger = logging.getLogger(__name__)

# 기본 설정 (env에서 오버라이드 가능)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"

# ... import lines ...

# 데이터 저장 경로 설정
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

class MemoryManager:
    """간단한 인메모리 메모리 매니저 (JSON 파일 영구 저장)"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = DATA_DIR / "chatbot_memory.json"
        self.memories = self._load()
    
    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
        return {}

    def _save(self):
        try:
            if not DATA_DIR.exists():
                DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def view(self):
        return self.memories
        
    def get(self, key):
        return self.memories.get(key)
        
    def add(self, key, value):
        self.memories[key] = {"value": value, "updated_at": datetime.now().isoformat()}
        self._save()
        return f"✅ 메모리 저장: {key} = {value}"
        
    def remove(self, key):
        if key in self.memories:
            del self.memories[key]
            self._save()
            return f"🗑️ 메모리 삭제: {key}"
        return "⚠️ 해당 키를 찾을 수 없습니다."
        
    def update(self, key, value):
        if key in self.memories:
            self.memories[key]["value"] = value
            self.memories[key]["updated_at"] = datetime.now().isoformat()
            self._save()
            return f"✅ 메모리 수정: {key} = {value}"
        return self.add(key, value)
        
    def clear(self):
        self.memories = {}
        self._save()
        return "🧹 메모리가 초기화되었습니다."
        
    def format_for_prompt(self):
        if not self.memories:
            return ""
        text = "## 사용자 정보 (Long-term Memory)\n"
        for k, v in self.memories.items():
            text += f"- **{k}**: {v['value']}\n"
        return text
        
    def to_dict(self):
        return self.memories

import uuid

class HistoryManager:
    """대화 히스토리 매니저 (세션별 관리 + JSON 영구 저장)"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file_path = DATA_DIR / "chatbot_history.json"
        
        # Structure: { session_id: { id, title, messages, created_at, updated_at, model } }
        self.sessions = self._load()
        
    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Migration: if list (old format), convert to default session
                    if isinstance(data, list):
                        default_id = str(uuid.uuid4())
                        return {
                            default_id: {
                                "id": default_id,
                                "title": "이전 대화",
                                "messages": data,
                                "created_at": datetime.now().isoformat(),
                                "updated_at": datetime.now().isoformat(),
                                "model": "gemini-2.0-flash-lite"
                            }
                        }
                    return data
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
        return {}

    def _save(self):
        try:
            if not DATA_DIR.exists():
                DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def create_session(self, model_name: str = "gemini-2.0-flash-lite", save_immediate: bool = True) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "title": "새로운 대화",
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "model": model_name
        }
        if save_immediate:
            self._save()
        return session_id

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save()
            return True
        return False

    def clear_all(self):
        self.sessions = {}
        self._save()

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def get_all_sessions(self):
        # Filter out empty or ephemeral-only sessions
        valid_sessions = []
        for s in self.sessions.values():
            msgs = s.get("messages", [])
            if not msgs:
                continue
            
            # Check if has any meaningful user message
            has_meaningful = False
            for m in msgs:
                if m["role"] == "user":
                    # Handle both string and object parts (legacy/new mix)
                    content = ""
                    parts = m.get("parts", [])
                    if parts:
                        p = parts[0]
                        if isinstance(p, dict):
                            content = p.get("text", "")
                        else:
                            content = str(p)
                    
                    # Ephemeral commands that shouldn't persist session
                    if not content.strip().startswith(("/status", "/help", "/memory view", "/clear")):
                        has_meaningful = True
                        break
            
            if has_meaningful:
                valid_sessions.append(s)

        # Sort by updated_at desc
        return sorted(
            valid_sessions, 
            key=lambda x: x.get("updated_at", ""), 
            reverse=True
        )

    def add_message(self, session_id: str, role: str, message: str, save: bool = True):
        if session_id not in self.sessions:
            # Fallback (Ephemeral check handled in chat, but here strictly requires existence or auto-create)
            # Since chat method handles ephemeral, if we reach here, we must modify a session.
            # If logic is correct, this might be rare, but let's be safe.
            self.create_session() # Auto-recover
            
        session = self.sessions[session_id]
        
        # FIX: Store parts as objects for Gemini SDK compatibility
        # parts=[{"text": "message"}] instead of parts=["message"]
        # Add timestamp
        session["messages"].append({
            "role": role, 
            "parts": [{"text": message}],
            "timestamp": datetime.now().isoformat()
        })
        session["updated_at"] = datetime.now().isoformat()
        
        # Auto-title (first user message)
        if len(session["messages"]) == 1 and role == "user":
            clean_msg = message.strip().replace("\n", " ")
            session["title"] = clean_msg[:30] + "..." if len(clean_msg) > 30 else clean_msg
        elif len(session["messages"]) == 2 and role == "user": 
             clean_msg = message.strip().replace("\n", " ")
             session["title"] = clean_msg[:30] + "..." if len(clean_msg) > 30 else clean_msg

        # Limit per session (optional, kept 50 for now)
        if len(session["messages"]) > 50:
             session["messages"] = session["messages"][-50:]
             
        if save:
            self._save()

    def get_messages(self, session_id: str):
        session = self.sessions.get(session_id)
        if session:
            # FIX: Sanitize legacy messages where parts might be strings
            sanitized = []
            for i, msg in enumerate(session["messages"]):
                new_parts = []
                for p in msg["parts"]:
                    if isinstance(p, str):
                        new_parts.append({"text": p})
                    else:
                        new_parts.append(p)
                
                # Create sanitized message object
                sanitized_msg = {
                    "role": msg["role"], 
                    "parts": new_parts
                }
                
                # Preserve timestamp if exists, else backfill with session time
                if "timestamp" in msg:
                    sanitized_msg["timestamp"] = msg["timestamp"]
                else:
                    # Fallback for legacy messages
                    if i == 0:
                        sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())
                    elif i == len(session["messages"]) - 1:
                        sanitized_msg["timestamp"] = session.get("updated_at", datetime.now().isoformat())
                    else:
                        # For middle messages, just use created_at or interpolate if needed. 
                        # Using created_at is safe enough for history.
                        sanitized_msg["timestamp"] = session.get("created_at", datetime.now().isoformat())
                    
                sanitized.append(sanitized_msg)
            return sanitized
        return []

class KRStockChatbot:
    """
    VCP 기반 한국 주식 분석 챗봇
    """
    
    def __init__(
        self, 
        user_id: str,
        api_key: str = None,
        data_fetcher: Optional[Callable] = None
    ):
        self.user_id = user_id
        self.memory = MemoryManager(user_id)
        self.history = HistoryManager(user_id)
        self.data_fetcher = data_fetcher
        
        # Cache initialization
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60
        
        # Data maps initialization
        self.stock_map = {} 
        self.ticker_map = {}
        self._load_stock_map()
        
        # .env에서 사용자 프로필 초기화 (기본값이 없을 때만 설정)
        self._init_user_profile_from_env()

        # Gemini 초기화 - ZAI_API_KEY도 확인 (무료 티어 지원)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "") or os.getenv("ZAI_API_KEY", "")
        self.available_models = []
        self.current_model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.client = None
        
        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._init_models()
                logger.info(f"Gemini initialized for user: {user_id} (KeyLen: {len(self.api_key)})")
            except Exception as e:
                logger.error(f"Gemini initialization failed: {e}")
        else:
            logger.warning(f"Gemini not available or API Config missing (GEMINI_AVAILABLE={GEMINI_AVAILABLE}, api_key={bool(self.api_key)})")

    def close(self):
        """Gemini 클라이언트 리소스 정리 (asyncio Task pending 오류 방지)"""
        if self.client:
            try:
                # google-genai SDK의 내부 HTTP 클라이언트 세션을 닫기 위해 시도
                # SDK 구조상 명시적인 close()가 없을 경우 하위 속성이나 세션 정리를 고려
                if hasattr(self.client, '_api_client') and hasattr(self.client._api_client, 'aclose'):
                     # 동기 close 내에서 비동기 close 호출은 복잡할 수 있으나, 
                     # SDK가 내부적으로 리소스를 확보하도록 유도
                     pass
                self.client = None
                logger.info("Gemini client resources released.")
            except Exception as e:
                logger.debug(f"Error during Gemini client close: {e}")
            
        # 데이터 캐시
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60 # 60 seconds TTL
        
        # 전체 종목 리스트 로드 (이름/코드 매핑용)
        self.stock_map = {} # name -> ticker
        self.ticker_map = {} # ticker -> name
        self._load_stock_map()

    def _load_stock_map(self):
        """korean_stocks_list.csv 로드하여 매핑 생성"""
        try:
            path = DATA_DIR / "korean_stocks_list.csv"
            if path.exists():
                import pandas as pd
                df = pd.read_csv(path, dtype={'ticker': str})
                for _, row in df.iterrows():
                    name = row['name']
                    ticker = row['ticker']
                    self.stock_map[name] = ticker
                    self.ticker_map[ticker] = name
                logger.info(f"Loaded {len(self.stock_map)} stocks from list")
            else:
                logger.warning("korean_stocks_list.csv not found")
        except Exception as e:
            logger.error(f"Failed to load stock map: {e}")

    def _init_user_profile_from_env(self):
        """환경변수에서 초기 사용자 프로필 설정"""
        profile = os.getenv("USER_PROFILE")
        if profile and not self.memory.memories: # 메모리가 비어있을 때만 초기화
            self.memory.add("user_profile", {"name": "흑기사", "persona": profile})
            logger.info("Initialized user profile from env")

    def get_user_profile(self) -> Dict[str, Any]:
        """사용자 프로필 조회"""
        profile = self.memory.get("user_profile")
        if profile and isinstance(profile, dict) and "value" in profile:
             # Legacy or wrapped format check
             val = profile["value"]
             if isinstance(val, dict): return val
             return {"name": "흑기사", "persona": str(val)}
        return {"name": "흑기사", "persona": "주식 투자를 배우고 있는 열정적인 투자자"}

    def update_user_profile(self, name: str, persona: str):
        """사용자 프로필 업데이트"""
        data = {"name": name, "persona": persona}
        self.memory.update("user_profile", data)
        return data

    def _init_models(self):
        """Available models setup from env"""
        env_models = os.getenv("CHATBOT_AVAILABLE_MODELS", "gemini-2.0-flash-lite,gemini-1.5-flash")
        model_names = [m.strip() for m in env_models.split(",") if m.strip()]
        
        if not model_names:
            model_names = [DEFAULT_GEMINI_MODEL]
            
        self.available_models = model_names
        
        if self.current_model_name not in self.available_models and self.available_models:
            self.current_model_name = self.available_models[0]

    def get_available_models(self) -> List[str]:
        return self.available_models

    def set_model(self, model_name: str):
        if model_name in self.available_models:
            self.current_model_name = model_name
            return True
        return False
        
    def _get_cached_data(self) -> Dict[str, Any]:
        """Fetch market data with caching"""
        now = datetime.now()
        if (self._data_cache is None or 
            self._cache_timestamp is None or
            (now - self._cache_timestamp).seconds > self._cache_ttl):
            
            try:
                if self.data_fetcher:
                    self._data_cache = self.data_fetcher()
                else:
                    self._data_cache = self._fetch_mock_data() # Use fallback/mock if no fetcher provided
                self._cache_timestamp = now
            except Exception as e:
                logger.error(f"Data fetch error: {e}")
                if self._data_cache is None:
                    self._data_cache = {"market": {}, "vcp_stocks": [], "sector_scores": {}}
        
        return self._data_cache

    def _fetch_mock_data(self):
        """폴백용 Mock 데이터 (실제 데이터 로드 실패 시)"""
        return {
            "market": {"kospi": "2600.00", "kosdaq": "850.00", "usd_krw": 1350, "market_gate": "YELLOW"},
            "vcp_stocks": [],
            "sector_scores": {}
        }

    def _fetch_market_gate(self) -> Dict[str, Any]:
        """market_gate.json에서 최신 시장 상태 조회"""
        try:
            json_path = DATA_DIR / "market_gate.json"
            if not json_path.exists():
                return {}
            
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return data
        except Exception as e:
            logger.error(f"Market Gate fetch error: {e}")
            return {}

    def _fetch_vcp_ai_analysis(self) -> str:
        """kr_ai_analysis.json에서 VCP AI 분석 결과 조회 (상위 5개)"""
        try:
            json_path = DATA_DIR / "kr_ai_analysis.json"
            if not json_path.exists():
                json_path = DATA_DIR / "ai_analysis_results.json"
                if not json_path.exists():
                    return ""
            
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            signals = data.get("signals", [])
            if not signals:
                return ""
            
            # BUY 추천 필터링 및 상위 5개 추출
            result_text = ""
            count = 0
            for sig in signals:
                gemini_rec = sig.get("gemini_recommendation", {})
                perplexity_rec = sig.get("perplexity_recommendation", {})
                
                # 둘 중 하나라도 BUY면 출력
                action = gemini_rec.get("action") if gemini_rec else None
                if not action and perplexity_rec:
                    action = perplexity_rec.get("action")
                
                if action == "BUY":
                    name = sig.get("name", sig.get("stock_name", "N/A"))
                    score = sig.get("score", sig.get("vcp_score", 0))
                    reason = gemini_rec.get("reason", "") if gemini_rec else ""
                    if not reason and perplexity_rec:
                        reason = perplexity_rec.get("reason", "")
                    
                    result_text += f"- **{name}**: {score}점 (매수 추천)\n  - AI 분석: {reason[:120]}...\n"
                    count += 1
                    if count >= 5:
                        break
            
            return result_text
        except Exception as e:
            logger.error(f"VCP AI analysis fetch error: {e}")
            return ""

    def get_daily_suggestions(self, watchlist: list = None, persona: str = None) -> List[Dict[str, str]]:
        """
        현재 시장 상황과 데이터, 페르소나를 기반으로 AI 추천 질문 5가지를 생성
        (1시간 캐싱 적용 - 페르소나별 분리)
        """
        # 0. 캐시 확인
        now = datetime.now()
        cache_key = f"daily_suggestions_{persona if persona else 'default'}"
        cached = self.memory.get(cache_key)
        
        # Watchlist가 있으면 개인화되므로 캐시 무시 (또는 별도 키 사용)
        if not watchlist and cached:
            updated_at = datetime.fromisoformat(cached["updated_at"])
            # 1시간 TTL
            if (now - updated_at).total_seconds() < 3600:
                return cached["value"]

        try:
            # 1. 컨텍스트 수집
            market_gate = self._fetch_market_gate()
            vcp_text = self._fetch_vcp_ai_analysis()
            news_text = self._fetch_latest_news()
            
            market_summary = f"Status: {market_gate.get('status', 'N/A')}, Score: {market_gate.get('total_score', 0)}"
            
            watchlist_text = ""
            if watchlist:
                watchlist_details = []
                # Limit to top 5 to avoid context overflow
                for item in watchlist[:5]:
                     # Try to resolve ticker
                     ticker = self.stock_map.get(item)
                     if not ticker:
                          ticker = item if item.isdigit() else None
                     
                     if ticker:
                         # Fetch minimal context for suggestion generation (don't need full history to save tokens? 
                         # Actually user wants "Optimized suggestions based on collected data". 
                         # Let's give summary: latest price + latest VCP score)
                         
                         # Check VCP score
                         vcp_match = next((s for s in self._get_cached_data().get("vcp_stocks", []) if s.get('code') == ticker), None)
                         vcp_info = f"{vcp_match.get('score')}점" if vcp_match else "N/A"
                         
                         # Fetch latest price only (custom minimal fetch or just parse from full context)
                         # Let's use full context but truncate lines to save token space if needed.
                         # Actually, _format_stock_context is fine, it's 5 lines per section.
                         context = self._format_stock_context(item, ticker)
                         watchlist_details.append(context)
                
                if watchlist_details:
                    watchlist_text = f"\n## 사용자 관심종목 상세 데이터:\n" + "\n".join(watchlist_details)
                else:
                    watchlist_text = f"\n사용자 관심종목: {', '.join(watchlist)} (데이터 없음)"
            
            # Fetch Jongga Data for General Persona
            jongga_text = ""
            if persona != 'vcp':
                 jongga_text = self._fetch_jongga_data()
                 if jongga_text:
                     jongga_text = f"\n## 종가베팅 데이터:\n{jongga_text[:1000]}..." # Truncate

            # 2. 프롬프트 구성 (페르소나별 차별화)
            if persona == 'vcp':
                prompt = f"""
너는 'VCP(변동성 축소 패턴) 주식 투자 전문가' AI야.
현재 시장 데이터, VCP 분석 결과, 수급 현황을 심도 있게 분석해서, 전문 트레이더가 관심을 가질 만한 **핵심 질문 5가지**를 제안해줘.
일반적인 시장 질문보다는 '차트 패턴', '수급', '매수 타점', '리스크 관리'에 초점을 맞춰야 해.

## 현재 시장 상황
- Market Gate: {market_summary}
- VCP 추천주 분석:
{vcp_text[:800]}...
- 주요 뉴스:
{news_text[:300]}...
{watchlist_text}
"""
            else:
                prompt = f"""
너는 친절하고 명확한 '한국 주식 투자 어드바이저' AI야.
현재 시장 흐름, 주요 뉴스, 종가베팅 데이터, 관심 종목의 상태를 종합해서, 일반 투자자가 가장 궁금해할 만한 **핵심 질문 5가지**를 제안해줘.
'시장 전망', '뉴스 분석', '종목 상담', '종가베팅 전략' 등 균형 잡힌 주제로 구성해줘.

## 현재 시장 상황
- Market Gate: {market_summary}
- VCP 추천주 분석:
{vcp_text[:500]}...
{jongga_text}
- 주요 뉴스:
{news_text[:500]}...
{watchlist_text}
"""

            prompt += """
## 요청 사항
1. JSON 포맷으로 반환해줘.
2. 각 항목은 `title`(버튼용 짧은 제목), `prompt`(실제 질문 내용), `desc`(설명), `icon`(FontAwesome 클래스)을 포함해야 해.
3. 총 5개 생성.
4. 예시:
[
  {{ "title": "시장 급락 대응", "prompt": "오늘 코스닥 급락의 주 원인과 향후 대응 전략은?", "desc": "시장 하락 원인 분석", "icon": "fas fa-chart-line" }},
  {{ "title": "VCP 종목 추천", "prompt": "오늘 포착된 VCP 종목 중 가장 점수가 높은 종목 상세 분석해줘", "desc": "AI 선정 베스트 종목", "icon": "fas fa-search-dollar" }}
]
"""
            # 3. Gemini 호출
            if not self.client:
                return []
                
            response = self.client.models.generate_content(
                model=self.current_model_name,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            suggestions = json.loads(response.text)
            
            # 4. 캐싱 (개인화 요청이 아닐 경우만)
            if not watchlist:
                self.memory.add(cache_key, suggestions)
                
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            # Fallback (기본 정적 추천)
            return [
                { "title": "시장 현황", "prompt": "오늘 마켓게이트 상태와 투자 전략 알려줘", "desc": "마켓게이트 상태와 투자 전략", "icon": "fas fa-chart-pie" },
                { "title": "VCP 추천", "prompt": "VCP AI 분석 결과 매수 추천 종목 알려줘", "desc": "AI 분석 기반 매수 추천 종목", "icon": "fas fa-search-dollar" },
                { "title": "종가 베팅", "prompt": "오늘의 종가베팅 S급, A급 추천해줘", "desc": "오늘의 S/A급 종가베팅 추천", "icon": "fas fa-chess-knight" },
                { "title": "뉴스 분석", "prompt": "최근 주요 뉴스와 시장 영향 분석해줘", "desc": "최근 주요 뉴스와 시장 영향", "icon": "fas fa-newspaper" },
                { "title": "내 관심종목", "prompt": "내 관심종목 리스트 기반으로 현재 상태 진단해줘", "desc": "관심종목 진단 및 리스크 점검", "icon": "fas fa-heart" }
            ]

    def _fetch_latest_news(self) -> str:
        """jongga_v2_latest.json 내 뉴스 데이터 조회 (최근 5개)"""
        try:
            json_path = DATA_DIR / "jongga_v2_latest.json"
            if not json_path.exists():
                return ""
            
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            signals = data.get("signals", [])
            if not signals:
                return ""
            
            # 모든 시그널에서 뉴스 아이템 수집
            all_news = []
            for sig in signals:
                news_items = sig.get("news_items", [])
                for news in news_items:
                    title = news.get("title", "")
                    source = news.get("source", "")
                    if title:
                        all_news.append(f"- [{source}] {title}")
            
            # 상위 5개만 반환
            if not all_news:
                return ""
            
            return "\n".join(all_news[:5])
        except Exception as e:
            logger.error(f"News fetch error: {e}")
            return ""

    def _fetch_stock_history(self, ticker: str) -> str:
        """daily_prices.csv에서 최근 5일 주가 조회"""
        try:
            import pandas as pd
            path = DATA_DIR / "daily_prices.csv"
            if not path.exists(): return ""
            
            # Efficient reading: using chunks probably overkill for 3MB but good practice.
            # actually 3MB is small enough to load. check cache? NO, just load for now.
            df = pd.read_csv(path, dtype={'ticker': str})
            df['date'] = pd.to_datetime(df['date'])
            target = df[df['ticker'] == ticker].sort_values('date', ascending=False).head(5)
            
            if target.empty: return "주가 데이터 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['date'].strftime('%Y-%m-%d')
                lines.append(f"- {d}: 종가 {row['close']:,.0f} | 거래량 {row['volume']:,.0f} | 등락 {(row['close'] - row['open']):+,.0f}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Price fetch error for {ticker}: {e}")
            return "데이터 조회 실패"

    def _fetch_institutional_trend(self, ticker: str) -> str:
        """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
        try:
            import pandas as pd
            path = DATA_DIR / "all_institutional_trend_data.csv"
            if not path.exists(): return ""
            
            df = pd.read_csv(path, dtype={'ticker': str})
            df['date'] = pd.to_datetime(df['date'])
            target = df[df['ticker'] == ticker].sort_values('date', ascending=False).head(5)
            
            if target.empty: return "수급 데이터 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['date'].strftime('%Y-%m-%d')
                fb = row['foreign_buy']
                inst = row['inst_buy']
                lines.append(f"- {d}: 외인 {fb:+,.0f} | 기관 {inst:+,.0f}")
            return "\n".join(lines)
        except Exception as e:
            return "데이터 조회 실패"

    def _fetch_signal_history(self, ticker: str) -> str:
        """signals_log.csv에서 VCP 시그널 이력 조회"""
        try:
            import pandas as pd
            path = DATA_DIR / "signals_log.csv"
            if not path.exists(): return ""
            
            df = pd.read_csv(path, dtype={'ticker': str})
            target = df[df['ticker'] == ticker].sort_values('signal_date', ascending=False)
            
            if target.empty: return "과거 VCP 포착 이력 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['signal_date']
                s = row['score']
                lines.append(f"- {d}: {s}점 VCP 포착")
            return "\n".join(lines)
        except Exception as e:
            return "조회 실패"

    def _format_stock_context(self, name: str, ticker: str) -> str:
        """종목 관련 모든 데이터 통합"""
        price_txt = self._fetch_stock_history(ticker)
        trend_txt = self._fetch_institutional_trend(ticker)
        signal_txt = self._fetch_signal_history(ticker)
        
        return f"""
## [종목 상세 데이터: {name} ({ticker})]
### 1. 최근 주가 (5일)
{price_txt}

### 2. 수급 현황 (5일)
{trend_txt}

### 3. VCP 시그널 이력
{signal_txt}
"""

    def _detect_stock_query(self, message: str) -> Optional[str]:
        """종목 관련 질문 감지 및 상세 정보 반환 (전체 종목 대상)"""
        # 1. Watchlist 우선 검색 (Context Optimization)
        # (This is handled in chat method but helpful to do full lookup here too if specifically asked)
        
        detected_name = None
        detected_ticker = None
        
        # 이름/코드 매핑 사용
        for name, ticker in self.stock_map.items():
            if name in message:
                detected_name = name
                detected_ticker = ticker
                break
        
        if not detected_ticker:
            for ticker, name in self.ticker_map.items():
                if ticker in message:
                    detected_name = name
                    detected_ticker = ticker
                    break
        
        if detected_name and detected_ticker:
            logger.info(f"Detected stock query: {detected_name}")
            return self._format_stock_context(detected_name, detected_ticker)
            
        return None

    def chat(self, user_message: str, session_id: str = None, model: str = None, files: list = None, watchlist: list = None, persona: str = None, api_key: str = None) -> Dict[str, Any]:
        """
        사용자 메시지 처리 및 응답 생성
        
        Args:
            user_message: 사용자 입력
            session_id: 세션 ID (없으면 생성)
            model: 사용할 모델명 (없으면 기본값)
            files: 첨부 파일 리스트
            watchlist: 사용자 관심종목 리스트
            persona: 특정 페르소나 지정 ('vcp' 등)
            api_key: (Optional) 사용자 제공 API Key
        """
        target_model_name = model or self.current_model_name
        
        # [Client Selection]
        # 사용자 제공 Key가 있으면 임시 Client 생성, 없으면 기본 self.client 사용
        active_client = self.client
        if api_key:
            try:
                from google import genai
                active_client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.error(f"Temp client init failed: {e}")
                return {"response": f"⚠️ API Key 오류: {str(e)}", "session_id": session_id}

        if not active_client:
             debug_info = f"KeyLen: {len(str(api_key))} " if api_key else "Key: None "
             return {"response": f"⚠️ AI 모델이 설정되지 않았습니다. ({debug_info}) [설정 > API & 기능]에서 API Key를 등록하거나, 구글 로그인을 진행해주세요. (데이터 초기화 후에는 재설정이 필요합니다)", "session_id": session_id}

        # Ephemeral check
        is_ephemeral = False
        if not files and user_message.strip().startswith(("/status", "/help", "/memory view")):
            is_ephemeral = True

        # 0. 세션 확인 및 생성
        # 세션이 없으면 새로 생성하되, Ephemeral 명령이면 바로 저장하지 않음 (Memory only)
        if not session_id or not self.history.get_session(session_id):
            session_id = self.history.create_session(model_name=target_model_name, save_immediate=not is_ephemeral)

        # 1. 명령어 체크 (파일이 없을 때만)
        if not files and user_message.startswith("/"):
            try:
                cmd_resp = self._handle_command(user_message, session_id)
                
                # Ephemeral 명령이어도 메모리에는 남겨야 함 (화면 표시용)
                # 단, save=False로 디스크 저장은 건너뜀
                should_save = not is_ephemeral
                
                # User Message 기록
                self.history.add_message(session_id, "user", user_message, save=should_save)
                
                # Model Response 기록
                self.history.add_message(session_id, "model", cmd_resp, save=should_save)
                
                return {"response": cmd_resp, "session_id": session_id}
            except Exception as e:
                logger.error(f"Command error: {e}")
                return {"response": f"⚠️ 명령어 처리 중 오류가 발생했습니다: {str(e)}", "session_id": session_id}
        # 2. 시장 데이터 가져오기 (챗봇 컨텍스트용) - 실제 데이터 사용
        # Market Gate 실제 데이터 로드
        market_gate_data = self._fetch_market_gate()
        
        # 기존 캐시 데이터도 가져오기 (VCP 종목 등)
        data = self._get_cached_data()
        vcp_data = data.get("vcp_stocks", [])
        sector_scores = data.get("sector_scores", {})
        
        # Market Gate 데이터를 market_data 형식으로 변환
        market_data = {
            "kospi": market_gate_data.get("kospi_close", "N/A"),
            "kosdaq": market_gate_data.get("kosdaq_close", "N/A"),
            "usd_krw": market_gate_data.get("usd_krw", "N/A"),
            "market_gate": market_gate_data.get("color", "UNKNOWN"),
            "market_status": market_gate_data.get("status", ""),
            "total_score": market_gate_data.get("total_score", 0)
        }
        
        # Sector Scores from Market Gate
        if market_gate_data.get("sectors"):
            sector_scores = {s["name"]: s["change_pct"] for s in market_gate_data.get("sectors", [])}

        # 3. 특정 종목 질문인지 확인 (텍스트 기반)
        stock_context = self._detect_stock_query(user_message)
        
        # 3.1 의도 감지 및 컨텍스트 구성
        additional_context = ""
        intent_instruction = ""
        jongga_context = False
        
        # 3.1.1 종가베팅 추천 질문 확인
        if any(kw in user_message for kw in ["종가베팅", "종가 베팅", "Closing Betting"]):
            jongga_context = True # Flag set
            self.memory.add("interest", "종가베팅")
            logger.info(f"Auto-saved interest: 종가베팅 for user {self.user_id}")
            
            jongga_data = self._fetch_jongga_data()
            if jongga_data:
                additional_context += f"\n\n## [종가베팅 추천 종목]\n{jongga_data}"
            else:
                additional_context += "\n\n## [종가베팅 데이터]\n현재 추천할 만한 종가베팅 시그널이 없습니다."
            
            from .prompts import INTENT_PROMPTS
            intent_instruction = INTENT_PROMPTS.get("closing_bet", "")
        
        # 3.1.2 시장/마켓게이트 질문 감지
        elif any(kw in user_message for kw in ["시장", "마켓게이트", "Market Gate", "시황", "장세", "지수"]):
            mg = market_gate_data
            if mg:
                gate_color = mg.get("color", "UNKNOWN")
                gate_status = mg.get("status", "")
                gate_score = mg.get("total_score", 0)
                gate_reason = mg.get("gate_reason", "")
                
                indices = mg.get("indices", {})
                sectors = mg.get("sectors", [])[:5]  # 상위 5개 섹터만
                
                indices_text = "\n".join([f"  - {k.upper()}: {v.get('value', 'N/A')} ({v.get('change_pct', 0):+.2f}%)" for k, v in indices.items()])
                sectors_text = "\n".join([f"  - {s['name']}: {s['change_pct']:+.2f}% ({s['signal']})" for s in sectors])
                
                additional_context += f"""
## [Market Gate 상세 분석]
- **상태**: {gate_color} ({gate_status})
- **점수**: {gate_score}점
- **판단 근거**: {gate_reason}

### 주요 지수


### 섹터 동향
{sectors_text}
"""
                intent_instruction = "위 Market Gate 데이터를 참고하여 현재 시장 상황과 투자 전략을 상세히 분석해주세요."
        
        # 3.1.3 VCP/수급/추천 종목 질문 감지
        elif any(kw in user_message for kw in ["VCP", "수급", "추천", "뭐 살", "매수", "시그널"]):
            vcp_analysis = self._fetch_vcp_ai_analysis()
            if vcp_analysis:
                additional_context += f"\n\n## [VCP AI 분석 결과 - 매수 추천 종목]\n{vcp_analysis}"
            else:
                additional_context += "\n\n## [VCP 분석]\n현재 분석된 VCP 시그널이 없습니다."
            
            intent_instruction = "위 VCP AI 분석 결과를 참고하여 투자 추천과 근거를 설명해주세요."
        
        # 3.1.4 뉴스/이슈 질문 감지
        elif any(kw in user_message for kw in ["뉴스", "호재", "이슈", "속보", "소식"]):
            news_data = self._fetch_latest_news()
            if news_data:
                additional_context += f"\n\n## [최근 뉴스]\n{news_data}"
            else:
                additional_context += "\n\n## [뉴스]\n최근 수집된 주요 뉴스가 없습니다."
            
            intent_instruction = "위 뉴스 데이터를 참고하여 시장에 미칠 영향을 분석해주세요."

        # 3.1.5 관심종목 질문 감지 (또는 watchlist가 있고 '내 종목' 등을 물어볼 때)
        if watchlist and any(kw in user_message for kw in ["내 종목", "관심 종목", "관심종목", "포트폴리오", "가지고 있는"]):
             # Watchlist items analysis (Full Data Injection)
             watchlist_context = "\n\n## [내 관심종목 상세 분석 데이터]\n"
             
             for stock_name in watchlist:
                 # 1. Try to resolve ticker
                 ticker = self.stock_map.get(stock_name)
                 if not ticker:
                      # If watchlist item IS a ticker?
                      ticker = stock_name if stock_name.isdigit() else None
                      
                 if ticker:
                     # 2. Fetch Full Context (Price, Trend, Signal)
                     stock_detail = self._format_stock_context(stock_name, ticker)
                     watchlist_context += stock_detail + "\n"
                     
                     # Check VCP score as well
                     match = next((s for s in vcp_data if s.get('code') == ticker), None)
                     if match:
                         watchlist_context += f"-> [VCP 상태]: 현재 VCP 패턴 포착됨 ({match.get('score')}점)\n"
                 else:
                     watchlist_context += f"- {stock_name}: (종목 코드를 찾을 수 없음)\n"
            
             additional_context += watchlist_context
             intent_instruction = "위 [내 관심종목 상세 분석 데이터]를 바탕으로, 각 종목의 현재 주가 흐름, 수급 상태, VCP 패턴 여부를 종합하여 상세히 진단해주세요."

        # 3.1.6 기본 Watchlist Context 주입
        elif watchlist:
            wl_summary = []
            for stock_name in watchlist:
                match = next((s for s in vcp_data if s.get('name') == stock_name or s.get('code') == stock_name), None)
                if match:
                    score = match.get('score', 0)
                    wl_summary.append(f"{stock_name}({score}점)")
            
            if wl_summary:
                additional_context += f"\n\n## [관심종목 VCP 요약]\n{', '.join(wl_summary)}\n"

        # 4. 시스템 프롬프트 구성
        system_prompt = build_system_prompt(
            memory_text=self.memory.format_for_prompt(),
            market_data=market_data,
            vcp_data=vcp_data,
            sector_scores=sector_scores,
            current_model=target_model_name,
            persona=persona,
            watchlist=watchlist
        )
        
        if stock_context:
            system_prompt += f"\n\n## 질문 대상 종목 상세\n{stock_context}"
            
        if additional_context:
            system_prompt += additional_context
        
        # 5. Gemini 호출
        try:
            # 채팅 히스토리 로드
            chat_history = self.history.get_messages(session_id)
            
            # FIX: Gemini SDK Pydantic Validation Error (Extra inputs are not permitted)
            # Remove 'timestamp' and other extra fields before passing to SDK
            api_history = []
            for msg in chat_history:
                clean_msg = {
                    "role": msg["role"],
                    "parts": msg["parts"]
                }
                api_history.append(clean_msg)
            
            # 멀티모달 프롬프트 구성
            content_parts = []
            
            if files:
                for file in files:
                    content_parts.append({
                        "mime_type": file["mime_type"],
                        "data": file["data"]
                    })
            
            # 프롬프트에 종가베팅 의도 명시
            intent_instruction = ""
            if jongga_context:
                from .prompts import INTENT_PROMPTS
                intent_instruction = INTENT_PROMPTS.get("closing_bet", "")
                
            full_user_content = f"{system_prompt}\n{intent_instruction}\n\n[사용자 메시지]: {user_message}"
            content_parts.append(full_user_content)

            chat_session = active_client.chats.create(
                model=target_model_name,
                history=api_history
            )
            
            response = chat_session.send_message(content_parts)
            bot_response = response.text
            
            # 6. 히스토리 저장
            user_history_msg = user_message
            if files:
                user_history_msg += f" [파일 {len(files)}개 첨부됨]"
                
            self.history.add_message(session_id, "user", user_history_msg)
            self.history.add_message(session_id, "model", bot_response)
            
            return {"response": bot_response, "session_id": session_id}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Chat error: {error_msg}")
            
            # [Error Handling] 429 Resource Exhausted (Google API Rate Limit)
            if "429" in error_msg or "Resource exhausted" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                friendly_msg = (
                    "⚠️ **AI 서버 요청 한도 초과**\n\n"
                    "Google AI 서버의 분당 요청 한도에 도달했습니다.\n"
                    "**약 30초~1분 후에 다시 시도해주세요.**\n\n"
                    "💡 안정적인 사용을 위해 **[설정] > [API Key]** 메뉴에서 개인 API Key를 등록하시면 이 제한을 피할 수 있습니다."
                )
                return {"response": friendly_msg, "session_id": session_id}

            # [Error Handling] 400 Invalid Argument (API Key Invalid)
            if "400" in error_msg or "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
                friendly_msg = (
                    "⚠️ **API Key 설정 오류**\n\n"
                    "시스템에 설정된 API Key가 유효하지 않습니다.\n"
                    "관리자에게 문의하거나 **[설정] > [API Key]** 메뉴에서 올바른 API Key를 다시 등록해주세요.\n"
                    "(Google 서비스 문제일 수도 있습니다.)"
                )
                return {"response": friendly_msg, "session_id": session_id}

            return {"response": f"⚠️ 오류가 발생했습니다: {error_msg}", "session_id": session_id}

    def _fetch_jongga_data(self) -> str:
        """jongga_v2_latest.json에서 최신 S/A급 종목 조회"""
        try:
            json_path = DATA_DIR / "jongga_v2_latest.json"
            if not json_path.exists():
                return ""
            
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            signals = data.get("signals", [])
            if not signals:
                return ""
                
            # 최신순이 아닐 수 있으므로 확인 (보통 생성 순). 여기선 리스트 순서대로 처리
            # S/A급 필터링
            candidates = []
            for sig in signals:
                grade = sig.get("grade", "D")
                if grade in ['S', 'A']:
                    candidates.append(sig)
            
            # 점수순 정렬 (높은 점수 우선)
            # score는 딕셔너리일 수도 있고 객체일 수도 있음 (JSON 로드시 딕셔너리)
            # sig['score'] -> {'total': 12, ...}
            candidates.sort(key=lambda x: x.get("score", {}).get("total", 0), reverse=True)
            
            if not candidates:
                 return ""

            result_text = ""
            for sig in candidates[:3]: # 상위 3개만
                name = sig.get("stock_name", "N/A")
                code = sig.get("stock_code", "")
                grade = sig.get("grade", "")
                score_val = sig.get("score", {}).get("total", 0)
                date = sig.get("signal_date", "")
                
                # AI 코멘트 추출
                reason = "정보 없음"
                score_details = sig.get("score_details", {})
                if score_details:
                     ai_eval = score_details.get("ai_evaluation", {})
                     if ai_eval:
                         reason = ai_eval.get("reason", "정보 없음")
                
                result_text += f"- **{name}** ({code}): {grade}급, 점수 {score_val}점 ({date})\n  - AI 분석: {reason[:100]}...\n"
            
            return result_text
            
        except Exception as e:
            logger.error(f"Jongga data fetch error: {e}")
            return ""

    def _fallback_response(self, user_message: str, vcp_data: list) -> str:
        """AI 사용 불가 시 폴백 응답"""
        lower_msg = user_message.lower()
        if any(kw in lower_msg for kw in ['뭐 살', '추천', '종목', 'top']):
            if vcp_data:
                response = "📊 **오늘의 수급 상위 종목**\n\n"
                for i, stock in enumerate(vcp_data[:5], 1):
                    name = stock.get('name', 'N/A')
                    score = stock.get('supply_demand_score', 0)
                    response += f"{i}. **{name}**: {score}점\n"
                return response
            return "현재 데이터를 불러올 수 없습니다."
        return "질문을 이해하지 못했습니다."

    def _detect_stock_query(self, message: str) -> Optional[str]:
        """종목 관련 질문 감지 및 상세 정보 반환"""
        data = self._get_cached_data()
        vcp_stocks = data.get("vcp_stocks", [])
        
        # Explicit context provided by frontend (e.g. "[삼성전자(005930)] 전망")
        # Or simple scan
        for stock in vcp_stocks:
            name = stock.get('name', '')
            ticker = stock.get('ticker', '')
            
            if name and (name in message or ticker in message):
                return self._format_stock_info(stock)
        return None

    def _format_stock_info(self, stock: Dict) -> str:
        """종목 정보 포맷팅"""
        name = stock.get('name', 'N/A')
        ticker = stock.get('ticker', '')
        score = stock.get('supply_demand_score', 0)
        stage = stock.get('supply_demand_stage', '')
        double = "✅ 쌍끌이" if stock.get('is_double_buy') else ""
        
        foreign_5d = stock.get('foreign_5d', 0)
        inst_5d = stock.get('inst_5d', 0)
        
        return f"""**{name}** ({ticker})
- 수급 점수: {score}점 ({stage})
- 외국인 5일: {foreign_5d}주
- 기관 5일: {inst_5d}주
{double}"""

    def _handle_command(self, command: str, session_id: str = None) -> str:
        """명령어 처리"""
        parts = command.split(maxsplit=3)
        cmd = parts[0].lower()
        
        if cmd == "/memory":
            return self._handle_memory_command(parts[1:])
        
        elif cmd == "/clear":
            if len(parts) > 1 and parts[1] == "all":
                self.history.clear_all()
                self.memory.clear()
                return "✅ 모든 데이터가 초기화되었습니다."
            else:
                if session_id:
                     # Clear messages in current session
                     session = self.history.get_session(session_id)
                     if session:
                         session["messages"] = []
                         self.history._save()
                         return "🧹 현재 대화 세션이 초기화되었습니다."
                return "⚠️ 세션 ID가 없어 초기화할 수 없습니다."
        
        elif cmd == "/status":
            return self._get_status_message()
        
        elif cmd == "/help":
            return self._get_help()
        
        elif cmd == "/refresh":
            self._data_cache = None
            return "✅ 데이터 캐시가 새로고침되었습니다."

        elif cmd == "/model":
            if len(parts) > 1:
                if self.set_model(parts[1]):
                    # Update session model too if we want persistence preference
                    if session_id:
                        sess = self.history.get_session(session_id)
                        if sess:
                             sess["model"] = parts[1]
                             self.history._save()
                    return f"✅ 모델이 '{parts[1]}'로 변경되었습니다."
                return f"⚠️ 유효하지 않은 모델입니다. 가능한 모델: {', '.join(self.get_available_models())}"
            else:
                available_models = '\n'.join([f"- {m}" for m in self.get_available_models()])
                return f"""🤖 **모델 설정**
━━━━━━━━━━━━━━━━━━━━

📌 **현재 모델**: {self.current_model_name}

📋 **사용 가능 모델**:
{available_models}

━━━━━━━━━━━━━━━━━━━━"""
        
        else:
            return f"❓ 알 수 없는 명령어: {cmd}\n/help로 명령어를 확인하세요."
    
    def _handle_memory_command(self, args: list) -> str:
        """메모리 명령어 처리"""
        if not args:
            args = ["view"]
        
        action = args[0].lower()
        
        if action == "view":
            memories = self.memory.view()
            if not memories:
                return "📭 저장된 메모리가 없습니다."
            
            result = "📝 **저장된 메모리**\n"
            for i, (key, data) in enumerate(memories.items(), 1):
                result += f"{i}. **{key}**: {data['value']}\n"
            return result
        
        elif action == "add" and len(args) >= 3:
            key = args[1]
            value = " ".join(args[2:])
            return self.memory.add(key, value)
        
        elif action == "remove" and len(args) >= 2:
            return self.memory.remove(args[1])
        
        elif action == "update" and len(args) >= 3:
            key = args[1]
            value = " ".join(args[2:])
            return self.memory.update(key, value)
        
        elif action == "clear":
            return self.memory.clear()
        
        else:
            return """**사용법:**
`/memory view` - 저장된 메모리 보기
`/memory add 키 값` - 메모리 추가
`/memory update 키 값` - 메모리 수정  
`/memory remove 키` - 메모리 삭제
`/memory clear` - 전체 삭제"""
    
    def _get_status_message(self) -> str:
        """현재 상태 확인 메시지"""
        status = self.get_status()
        return f"""📊 **현재 상태**
━━━━━━━━━━━━━━━━━━━━

- 👤 **사용자**: {status['user_id']}
- 🖥️ **모델**: {status['model']}
- 💾 **저장된 메모리**: {status['memory_count']}개
- 💬 **대화 히스토리**: {status['history_count']}개

━━━━━━━━━━━━━━━━━━━━"""
    
    def _get_help(self) -> str:
        """도움말"""
        return """🤖 **스마트머니봇 도움말**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **일반 대화**

그냥 질문하면 됩니다!

* "오늘 뭐 살까?"
* "삼성전자 어때?"
* "반도체 섹터 상황은?"

📌 **명령어**

* `/memory view` - 저장된 정보 보기
* `/memory add 키 값` - 정보 저장
* `/memory remove 키` - 정보 삭제
* `/clear` - 대화 히스토리 초기화
* `/clear all` - 모든 데이터 초기화
* `/status` - 현재 상태 확인
* `/refresh` - 데이터 새로고침
* `/help` - 도움말

📌 **저장 추천 정보**

* 투자성향: 공격적/보수적/중립
* 관심섹터: 반도체, 2차전지 등
* 보유종목: 삼성전자, SK하이닉스 등

━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def get_welcome_message(self) -> str:
        """웰컴 메시지 반환 (VCP 데이터 기반)"""
        # Fetch current data to make welcome message dynamic
        data = self._get_cached_data()
        vcp_data = data.get("vcp_stocks", [])
        return get_welcome_message(vcp_data)

    def get_memory(self):
        return self.memory.to_dict()
        
    def update_memory(self, data):
        for k, v in data.items():
            self.memory.add(k, v)
            
    def clear_memory(self):
        self.memory.clear()
        
    def get_history(self):
        return self.history.to_dict()
    
    def clear_history(self):
        self.history.clear()
        
    def get_status(self):
        return {
            "user_id": self.user_id,
            "model": self.current_model_name,
            "available_models": self.get_available_models(),
            "memory_count": len(self.memory.view()),
            "history_count": len(self.history.get_all_sessions())
        }
