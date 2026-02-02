import os
import logging
import uuid
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from engine.config import app_config
from engine.llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)

class HistoryManager:
    def __init__(self):
        self.sessions = {} # {session_id: {created_at, messages: [], model: str}}

    def create_session(self, model_name: str = None) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'created_at': datetime.now().isoformat(),
            'messages': [],
            'model': model_name or app_config.GEMINI_MODEL
        }
        return session_id

    def get_all_sessions(self) -> List[Dict]:
        return [
            {'id': k, **v} for k, v in self.sessions.items()
        ]

    def get_messages(self, session_id: str) -> List[Dict]:
        if session_id in self.sessions:
            return self.sessions[session_id]['messages']
        return []

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.sessions:
            self.create_session() # Fallback if session doesn't exist (or just ignore?)
            # Usually better to ensure session exists. For now, rely on caller to create/pass valid ID.
            if session_id not in self.sessions: return
            
        self.sessions[session_id]['messages'].append({
            'role': role,
            'parts': [content],
            'timestamp': datetime.now().isoformat()
        })

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def clear_all(self):
        self.sessions = {}

class Chatbot:
    _instance = None

    def __init__(self):
        self.history = HistoryManager()
        self.analyzer = LLMAnalyzer() 
        self.current_model_name = app_config.GEMINI_MODEL
        self.user_profile = {"name": "User", "persona": "Conservative"}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Chatbot()
        return cls._instance

    def get_welcome_message(self) -> str:
        return f"안녕하세요! {self.user_profile['name']}님, 스마트머니봇입니다. 무엇을 도와드릴까요?"

    def get_available_models(self) -> List[str]:
        return ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gpt-4o"]

    def get_daily_suggestions(self, watchlist=None, persona=None) -> List[str]:
        return [
            "오늘의 마켓 게이트 상태는?",
            "VCP 패턴 종목 추천해줘",
            "삼성전자 분석해줘"
        ]

    def get_user_profile(self) -> Dict:
        return self.user_profile

    def update_user_profile(self, name: str, persona: str) -> Dict:
        self.user_profile["name"] = name
        self.user_profile["persona"] = persona
        return self.user_profile

    def chat(self, message: str, session_id: str = None, model: str = None, files=None, watchlist=None, persona=None) -> Any:
        # Session handling
        if not session_id or session_id not in self.history.sessions:
            session_id = self.history.create_session(model)
        
        # User message history
        self.history.add_message(session_id, 'user', message)

        try:
            # Here we would call the actual LLM API via self.analyzer
            # Since LLMAnalyzer is focused on analysis, we might need a direct chat method.
            # For debugging/recovery purposes, we'll try to use analyzer's client if possible, 
            # OR just mock it for now to fix the crash, OR implement a simple specialized call.
            
            # Simple interaction:
            response_text = ""
            
            # Using LLMAnalyzer's client if available (Gemini)
            if self.analyzer.client:
                 try:
                    # Construct prompt with context
                    prompt = f"User: {message}\n"
                    if watchlist:
                        prompt += f"Watchlist: {watchlist}\n"
                    
                    if self.analyzer.provider == 'gemini':
                        resp = self.analyzer.client.models.generate_content(
                            model=model or self.current_model_name,
                            contents=prompt
                        )
                        response_text = resp.text
                    elif self.analyzer.provider == 'zai':
                        # Z.ai / OpenAI style
                         resp = self.analyzer.client.chat.completions.create(
                            model=app_config.ZAI_MODEL,
                            messages=[{"role": "user", "content": prompt}]
                        )
                         response_text = resp.choices[0].message.content
                    else:
                        response_text = "LLM Provider not configured properly."
                 except Exception as e:
                     logger.error(f"Generate content failed: {e}")
                     response_text = "죄송합니다. AI 응답 생성 중 오류가 발생했습니다."
            else:
                 response_text = "AI Client initialized failed."

            self.history.add_message(session_id, 'model', response_text)
            
            return {
                "response": response_text,
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"error": str(e)}

def get_chatbot():
    return Chatbot.get_instance()
