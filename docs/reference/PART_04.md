# PART 4 (Core Logic)

> [!WARNING]
> **Reference Only**: This document contains reference code and backups.
> The actual source of truth is located in the `app/` and `engine/` directories.
> Do not modify this file directly for production changes.

### engine/generator.py (kr_market_package/engine/generator.py)
```python
"""
시그널 생성기 (Main Engine)
- Collector로부터 데이터 수집
- Scorer로 점수 계산
- PositionSizer로 자금 관리
- 최종 Signal 생성
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
import time
import sys
import os

# 모듈 경로 추가 (상위 디렉토리를 경로에 추가)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.config import SignalConfig, Grade
from engine.models import (
    StockData, Signal, SignalStatus, 
    ScoreDetail, ChecklistDetail, ScreenerResult, ChartData
)
from engine.collectors import KRXCollector, EnhancedNewsCollector
from engine.scorer import Scorer
from engine.position_sizer import PositionSizer
from engine.llm_analyzer import LLMAnalyzer


class SignalGenerator:
    """종가베팅 시그널 생성기 (v2)"""
    
    def __init__(
        self,
        config: SignalConfig = None,
        capital: float = 10_000_000,
    ):
        """
        Args:
            capital: 총 자본금 (기본 5천만원)
            config: 설정 (기본 설정 사용)
        """
        self.config = config or SignalConfig()
        self.capital = capital
        
        self.scorer = Scorer(self.config)
        self.position_sizer = PositionSizer(capital, self.config)
        self.llm_analyzer = LLMAnalyzer() # API Key from env
        
        self._collector: Optional[KRXCollector] = None
        self._news: Optional[EnhancedNewsCollector] = None
    
    async def __aenter__(self):
        self._collector = KRXCollector(self.config)
        await self._collector.__aenter__()
        
        self._news = EnhancedNewsCollector(self.config)
        await self._news.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._collector:
            await self._collector.__aexit__(exc_type, exc_val, exc_tb)
        if self._news:
            await self._news.__aexit__(exc_type, exc_val, exc_tb)
    
    async def generate(
        self,
        target_date: date = None,
        markets: List[str] = None,
        top_n: int = 30,
    ) -> List[Signal]:
        """
        시그널 생성
        
        Args:
            target_date: 대상 날짜 (기본: 오늘)
            markets: 대상 시장 (기본: KOSPI, KOSDAQ)
            top_n: 상승률 상위 N개 종목
        
        Returns:
            Signal 리스트 (등급순 정렬)
        """
        target_date = target_date or date.today()
        # markets = markets or ["KOSPI", "KOSDAQ"]
        markets = markets or ["KOSPI", "KOSDAQ"] 
        
        all_signals = []
        
        for market in markets:
            print(f"\n[{market}] 상승률 상위 종목 스크리닝...")
            
            # 1. 상승률 상위 종목 조회
            candidates = await self._collector.get_top_gainers(market, top_n)
            print(f"  - 1차 필터 통과: {len(candidates)}개")
            
            # 2. 각 종목 분석
            for i, stock in enumerate(candidates):
                print(f"  [{i+1}/{len(candidates)}] {stock.name}({stock.code}) 분석 중...", end='\r')
                
                signal = await self._analyze_stock(stock, target_date)
                
                if signal and signal.grade != Grade.C:
                    all_signals.append(signal)
                    print(f"\n    ✅ {stock.name}: {signal.grade.value}급 시그널 생성! (점수: {signal.score.total})")
                
                # Rate limiting
                # await asyncio.sleep(0.1) # 너무 느려지면 제거
        
        # 3. 등급순 정렬 (S > A > B)
        grade_order = {Grade.S: 0, Grade.A: 1, Grade.B: 2, Grade.C: 3}
        all_signals.sort(key=lambda s: (grade_order[s.grade], -s.score.total))
        
        # 4. 최대 포지션 수 제한
        if len(all_signals) > self.config.max_positions:
            all_signals = all_signals[:self.config.max_positions]
        
        print(f"\n총 {len(all_signals)}개 시그널 생성 완료")
        return all_signals
    
    async def _analyze_stock(
        self,
        stock: StockData,
        target_date: date
    ) -> Optional[Signal]:
        """개별 종목 분석"""
        try:
            # 1. 상세 정보 조회 (이미 top_gainers에서 대부분 가져왔으나 52주 고가 등 보완)
            detail = await self._collector.get_stock_detail(stock.code)
            if detail:
                # 병합 로직 (필요한 정보만 업데이트)
                stock.high_52w = detail.high_52w
            
            # 2. 차트 데이터 조회
            charts = await self._collector.get_chart_data(stock.code, 60)
            
            # 3. 뉴스 조회 (본문 포함, 종목명 전달)
            # EnhancedNewsCollector: get_stock_news(code, limit, name)
            news_list = await self._news.get_stock_news(stock.code, 3, stock.name)
            print(f"    -> News fetched: {len(news_list)}")
            
            # 4. LLM 뉴스 분석 (Rate Limit 방지 Sleep)
            llm_result = None
            if news_list and self.llm_analyzer.model:
                # Gemini Rate Limit 방지 (3.0 유료 모델 테스트: 2초)
                await asyncio.sleep(2)
                
                print(f"    [LLM] Analyzing {stock.name} news...")
                news_dicts = [{"title": n.title, "summary": n.summary} for n in news_list]
                llm_result = await self.llm_analyzer.analyze_news_sentiment(stock.name, news_dicts)
                if llm_result:
                   print(f"      -> Score: {llm_result.get('score')}, Reason: {llm_result.get('reason')}")

            # 5. 수급 데이터 조회 (CSV에서 로드, 5일 누적)
            supply = await self._collector.get_supply_data(stock.code)
            if supply:
                print(f"      -> Supply 5d: Foreign {supply.foreign_buy_5d}, Inst {supply.inst_buy_5d}")
            
            # 6. 점수 계산 (LLM 결과 반영)
            score, checklist = self.scorer.calculate(stock, charts, news_list, supply, llm_result)
            
            # 7. 등급 결정
            grade = self.scorer.determine_grade(stock, score)
            
            # C등급은 제외
            if grade == Grade.C:
                print(f"    ❌ 탈락 {stock.name}: 점수 {score.total} (뉴스{score.news}, 수급{score.supply}, 거래대금{score.volume}, 차트{score.chart})")
                return None
            
            # 7. 포지션 계산
            position = self.position_sizer.calculate(stock.close, grade)
            
            # 8. 시그널 생성
            signal = Signal(
                stock_code=stock.code,
                stock_name=stock.name,
                market=stock.market,
                sector=stock.sector,
                signal_date=target_date,
                signal_time=datetime.now(),
                grade=grade,
                score=score,
                checklist=checklist,
                news_items=[{
                    "title": n.title,
                    "source": n.source,
                    "published_at": n.published_at.isoformat() if n.published_at else "",
                    "url": n.url
                } for n in news_list[:5]], # 상위 5개 뉴스 저장
                current_price=stock.close,
                entry_price=position.entry_price,
                stop_price=position.stop_price,
                target_price=position.target_price,
                r_value=position.r_value,
                position_size=position.position_size,
                quantity=position.quantity,
                r_multiplier=position.r_multiplier,
                trading_value=stock.trading_value,
                change_pct=stock.change_pct,
                status=SignalStatus.PENDING,
                created_at=datetime.now(),
            )
            
            return signal
            
        except Exception as e:
            # print(f"    분석 실패: {e}")
            return None
    
    def get_summary(self, signals: List[Signal]) -> Dict:
        """시그널 요약 정보"""
        summary = {
            "total": len(signals),
            "by_grade": {g.value: 0 for g in Grade},
            "by_market": {},
            "total_position": 0,
            "total_risk": 0,
        }
        
        for s in signals:
            summary["by_grade"][s.grade.value] += 1
            summary["by_market"][s.market] = summary["by_market"].get(s.market, 0) + 1
            summary["total_position"] += s.position_size
            summary["total_risk"] += s.r_value * s.r_multiplier
        
        return summary


async def run_screener(
    capital: float = 50_000_000,
    markets: List[str] = None,
) -> ScreenerResult:
    """
    스크리너 실행 (간편 함수)
    """
    start_time = time.time()
    
    async with SignalGenerator(capital=capital) as generator:
        signals = await generator.generate(markets=markets)
        summary = generator.get_summary(signals)
    
    processing_time = (time.time() - start_time) * 1000
    
    result = ScreenerResult(
        date=date.today(),
        total_candidates=summary["total"],
        filtered_count=len(signals),
        signals=signals,
        by_grade=summary["by_grade"],
        by_market=summary["by_market"],
        processing_time_ms=processing_time,
    )
    
    # 결과 저장
    save_result_to_json(result)
    
    return result

async def analyze_single_stock_by_code(
    code: str,
    capital: float = 50_000_000,
) -> Optional[Signal]:
    """
    단일 종목 재분석 및 결과 JSON 업데이트
    """
    async with SignalGenerator(capital=capital) as generator:
        # 1. 기본 상세 정보 조회 (StockData 구성)
        detail = await generator._collector.get_stock_detail(code)
        if not detail:
            print(f"Stock detail not found for {code}")
            return None
            
        # StockData 객체 임시 생성 (Collector의 convert 로직 일부 활용 필요하지만, 여기선 detail로 구성)
        # KRXCollector 내부에 get_stock_data 같은게 없으므로, get_stock_detail 결과로 StockData를 수동 구성해야 함.
        # 하지만 top_gainers를 안 거치므로, 기본 등락률 등의 정보가 부족할 수 있음.
        # 따라서, get_quote 등을 통해 현재가 정보를 가져와야 함.
        
        # 간편하게: get_ticker_listing -> pykrx 등 활용 또는 collector에 메서드 추가가 정석이나,
        # 여기서는 existing json에서 해당 종목 정보를 읽어와서 StockData로 복원하는게 안전함.
        
        # 1-1. 최신 JSON 로드 (이전 데이터 기반)
        import json
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        latest_path = os.path.join(base_dir, "jongga_v2_latest.json")
        
        if not os.path.exists(latest_path):
            print("Latest data file not found.")
            return None
            
        with open(latest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        target_signal_data = next((s for s in data["signals"] if s["stock_code"] == code), None)
        
        if not target_signal_data:
            print("Signal not found in latest data. Cannot re-analyze without base info.")
            return None
            
        # StockData 복원
        stock = StockData(
            code=target_signal_data.get("stock_code", code),
            name=target_signal_data.get("stock_name", ""),
            market=target_signal_data.get("market", "KOSPI"),
            sector=target_signal_data.get("sector", ""),
            close=target_signal_data.get("current_price", target_signal_data.get("entry_price", 0)),
            change_pct=target_signal_data.get("change_pct", 0),
            trading_value=target_signal_data.get("trading_value", 0),
            volume=0, 
            marcap=0  
        )
        
        # 2. 재분석 실행
        print(f"Re-analyzing {stock.name} ({stock.code})...")
        new_signal = await generator._analyze_stock(stock, date.today())
        
        if new_signal:
            print(f"✅ Re-analysis complete: {new_signal.grade.value} (Score: {new_signal.score.total})")
            
            # 3. JSON 데이터 업데이트 및 저장
            # 기존 signals 리스트에서 해당 종목 교체
            updated_signals = [
                new_signal.to_dict() if s["stock_code"] == code else s 
                for s in data["signals"]
            ]
            
            data["signals"] = updated_signals
            data["updated_at"] = datetime.now().isoformat() # 전체 업데이트 시간 갱신
            
            # 파일 저장
            # 1) Latest
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            # 2) Daily (오늘 날짜)
            date_str = date.today().strftime("%Y%m%d")
            daily_path = os.path.join(base_dir, f"jongga_v2_results_{date_str}.json")
            if os.path.exists(daily_path):
                 with open(daily_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            return new_signal
            
        else:
            print("Re-analysis failed or grade too low.")
            return None

def save_result_to_json(result: ScreenerResult):
    """결과 JSON 저장 (Daily + Latest)"""
    import json
    import shutil
    
    data = {
        "date": result.date.isoformat(),
        "total_candidates": result.total_candidates,
        "filtered_count": result.filtered_count,
        "signals": [s.to_dict() for s in result.signals],
        "by_grade": result.by_grade,
        "by_market": result.by_market,
        "processing_time_ms": result.processing_time_ms,
        "updated_at": datetime.now().isoformat()
    }
    
    # 1. 날짜별 파일 저장
    date_str = result.date.strftime("%Y%m%d")
    filename = f"jongga_v2_results_{date_str}.json"
    
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(base_dir, exist_ok=True)
    
    save_path = os.path.join(base_dir, filename)
    
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n[저장 완료] Daily: {save_path}")
    
    # 2. Latest 파일 업데이트 (덮어쓰기)
    latest_path = os.path.join(base_dir, "jongga_v2_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"[저장 완료] Latest: {latest_path}")


# 테스트용 메인
async def main():
    """테스트 실행"""
    print("=" * 60)
    print("종가베팅 시그널 생성기 v2 (Live Entity)")
    print("=" * 60)
    
    capital = 50_000_000
    print(f"\n자본금: {capital:,}원")
    print(f"R값: {capital * 0.005:,.0f}원 (0.5%)")
    
    result = await run_screener(capital=capital)
    
    print(f"\n처리 시간: {result.processing_time_ms:.0f}ms")
    print(f"생성된 시그널: {len(result.signals)}개")
    print(f"등급별: {result.by_grade}")
    
    print("\n" + "=" * 60)
    print("시그널 상세")
    print("=" * 60)
    
    for i, signal in enumerate(result.signals, 1):
        print(f"\n[{i}] {signal.stock_name} ({signal.stock_code})")
        print(f"    등급: {signal.grade.value}")
        print(f"    점수: {signal.score.total}/12 (뉴스:{signal.score.news}, 수급:{signal.score.supply}, 차트:{signal.score.chart})")
        print(f"    등락률: {signal.change_pct:+.2f}%")
        print(f"    거래대금: {signal.trading_value / 100_000_000:,.0f}억")
        print(f"    진입가: {signal.entry_price:,}원")
        print(f"    손절가: {signal.stop_price:,}원 (-3%)")
        print(f"    목표가: {signal.target_price:,}원 (+5%)")
        print(f"    수량: {signal.quantity:,}주")
        print(f"    포지션: {signal.position_size:,.0f}원")
        
        # 체크리스트 출력
        print("    [체크리스트]")
        check = signal.checklist
        print(f"     - 뉴스: {'O' if check.has_news else 'X'} {check.news_sources}")
        print(f"     - 신고가/돌파: {'O' if check.is_new_high or check.is_breakout else 'X'}")
        print(f"     - 수급: {'O' if check.supply_positive else 'X'}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
```

### engine/llm_analyzer.py (kr_market_package/engine/llm_analyzer.py)
```python
"""
LLM 기반 뉴스 분석기 (Gemini)
"""

import os
import google.generativeai as genai
from typing import List, Dict
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드 (.env)
load_dotenv()

class LLMAnalyzer:
    """Gemini를 이용한 뉴스 분석 및 점수 산출"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            print("Warning: GOOGLE_API_KEY not found. LLM analysis will be skipped.")
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            # 모델명 환경변수에서 로드 (기본값: gemini-2.0-flash-exp)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            self.model = genai.GenerativeModel(model_name)
    
    async def analyze_news_sentiment(self, stock_name: str, news_items: List[Dict]) -> Dict:
        """
        뉴스 목록을 분석하여 호재 점수(0~3)와 요약 반환
        """
        if not self.model or not news_items:
            return {"score": 0, "reason": "No LLM or No News"}
            
        # 프롬프트 구성
        news_text = ""
        for i, news in enumerate(news_items, 1):
            title = news.get("title", "")
            summary = news.get("summary", "")[:200]  # 너무 길면 자름
            news_text += f"[{i}] 제목: {title}\n내용: {summary}\n\n"
            
        prompt = f"""
            당신은 주식 투자 전문가입니다. 다음은 '{stock_name}' 종목에 대한 최신 뉴스들입니다.
            이 뉴스들을 **종합적으로 분석**하여 현재 시점에서의 호재 강도를 0~3점으로 평가하세요.
            
            [뉴스 목록]
            {news_text}
            
            [점수 기준]
            3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈, 경영권 분쟁 등)
            2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
            1점: 단순/중립적 소식
            0점: 악재 또는 별다른 호재 없음
            
            [출력 형식]
            뉴스 3개를 따로 평가하지 말고, **종목 전체에 대한 하나의 평가**를 내리세요.
            반드시 아래 포맷의 **단일 JSON 객체**로만 답하세요. (Markdown code block 없이)
            
            Format: {{"score": 2, "reason": "종합적인 요약 이유"}}
            """
        
        try:
            # 비동기 실행
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            import json
            import re
            
            text = response.text.strip()
            
            # JSON 추출 (Markdown 코드블록 제거 및 정규식)
            if "```" in text:
                text = re.sub(r"```json|```", "", text).strip()
            
            # 중괄호로 시작하고 끝나는지 확인, 아니면 정규식으로 추출
            if not (text.startswith("{") and text.endswith("}")):
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    text = match.group()
            
            try:
                result = json.loads(text)
                return result
            except json.JSONDecodeError:
                print(f"[LLM Error] JSON Decode Failed. Raw text: {text[:100]}...")
                return {"score": 0, "reason": "JSON Parsing Failed"}
            
        except Exception as e:
            print(f"[LLM Error] API Call Failed: {e}")
            return {"score": 0, "reason": f"Error: {str(e)}"}
```

### engine/config.py (kr_market_package/engine/config.py)
```python
"""
종가베팅 시그널 생성기 설정
"""

from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum


class Grade(Enum):
    """종목 등급"""
    S = "S"  # 최고 - 풀배팅
    A = "A"  # 우수 - 기본배팅
    B = "B"  # 보통 - 절반배팅
    C = "C"  # 미달 - 매매안함


@dataclass
class GradeConfig:
    """등급별 설정"""
    min_trading_value: int      # 최소 거래대금 (원)
    min_change_pct: float       # 최소 등락률 (%)
    max_change_pct: float       # 최대 등락률 (%)
    min_score: int              # 최소 점수
    r_multiplier: float         # R 배수


@dataclass
class SignalConfig:
    """시그널 생성기 설정"""
    
    # === 기본 필터 ===
    min_trading_value: int = 50_000_000_000      # 최소 거래대금: 500억
    min_change_pct: float = 5.0                   # 최소 등락률: 5%
    max_change_pct: float = 29.9                  # 최대 등락률: 29.9% (상한가 제외)
    min_price: int = 1000                         # 최소 주가: 1,000원
    max_price: int = 500000                       # 최대 주가: 50만원
    
    # === 제외 조건 ===
    exclude_etf: bool = True                      # ETF 제외
    exclude_etn: bool = True                      # ETN 제외
    exclude_spac: bool = True                     # 스팩 제외
    exclude_preferred: bool = True                # 우선주 제외
    exclude_reits: bool = True                    # 리츠 제외
    exclude_keywords: List[str] = field(default_factory=lambda: [
        "스팩", "SPAC", "ETF", "ETN", "리츠", "우B", "우C", 
        "1우", "2우", "3우", "인버스", "레버리지"
    ])
    
    # === 점수 가중치 ===
    score_weights: Dict[str, int] = field(default_factory=lambda: {
        "news": 3,           # 뉴스/재료 (필수)
        "volume": 3,         # 거래대금 (필수)
        "chart": 2,          # 차트패턴
        "candle": 1,         # 캔들형태
        "consolidation": 1,  # 기간조정
        "supply": 2,         # 수급
    })
    
    # === 등급별 기준 ===
    grade_configs: Dict[Grade, GradeConfig] = field(default_factory=lambda: {
        Grade.S: GradeConfig(
            min_trading_value=1_000_000_000_000,  # 1조
            min_change_pct=10.0,
            max_change_pct=20.0,
            min_score=10,
            r_multiplier=1.5,
        ),
        Grade.A: GradeConfig(
            min_trading_value=500_000_000_000,    # 5천억
            min_change_pct=8.0,
            max_change_pct=15.0,
            min_score=8,
            r_multiplier=1.0,
        ),
        Grade.B: GradeConfig(
            min_trading_value=100_000_000_000,    # 1천억
            min_change_pct=5.0,
            max_change_pct=12.0,
            min_score=6,
            r_multiplier=0.5,
        ),
        Grade.C: GradeConfig(
            min_trading_value=50_000_000_000,     # 500억
            min_change_pct=5.0,
            max_change_pct=29.9,
            min_score=0,
            r_multiplier=0.0,  # 매매 안함
        ),
    })
    
    # === 매매 설정 ===
    stop_loss_pct: float = 0.03       # 손절: -3%
    take_profit_pct: float = 0.05     # 익절: +5%
    gap_target_pct: float = 0.03      # 갭상승 익절: +3%
    gap_stop_pct: float = -0.02       # 갭하락 손절: -2%
    time_stop_hour: int = 10          # 시간손절: 10시
    
    # === 리스크 관리 ===
    r_ratio: float = 0.005            # R 비율: 0.5%
    max_positions: int = 2            # 최대 동시 보유
    daily_loss_limit_r: float = 2.0   # 일일 손실 한도: 2R
    weekly_loss_limit_r: float = 4.0  # 주간 손실 한도: 4R
    
    # === 뉴스 키워드 ===
    positive_keywords: List[str] = field(default_factory=lambda: [
        # 실적 관련
        "흑자전환", "실적개선", "어닝서프라이즈", "사상최대", "호실적",
        "매출증가", "영업이익", "순이익", "분기최대",
        # 계약/수주
        "수주", "계약체결", "공급계약", "납품계약", "MOU", "LOI",
        "대규모계약", "독점계약", "장기공급",
        # 신사업/기술
        "신약개발", "임상성공", "FDA승인", "CE인증", "특허취득",
        "기술이전", "라이선스", "신제품", "양산", "상용화",
        # 투자/M&A
        "지분투자", "인수합병", "자회사편입", "지분확대",
        # 정책/테마
        "정부지원", "국책사업", "수혜주", "관련주", "테마",
        # 수급
        "외국인매수", "기관매수", "프로그램매수",
    ])
    
    negative_keywords: List[str] = field(default_factory=lambda: [
        # 부정적 이슈
        "횡령", "배임", "분식", "상장폐지", "관리종목", "감사의견거절",
        "자본잠식", "부도", "파산", "워크아웃", "법정관리",
        "검찰", "수사", "구속", "기소",
        # 실적 악화
        "적자전환", "적자확대", "실적악화", "매출감소",
        # 수급 악화
        "대량매도", "공매도급증", "외국인매도",
    ])
    
    # 인스턴스 메서드로 기본값 접근 지원
    @classmethod
    def default(cls):
        return cls()
```

### frontend/src/app/dashboard/kr/vcp/page.tsx (kr_market_package/frontend/src/app/dashboard/kr/vcp/page.tsx)
```tsx
'use client';

import { useEffect, useState } from 'react';
import { krAPI, KRSignal, KRAIAnalysis } from '@/lib/api';

export default function VCPSignalsPage() {
    const [signals, setSignals] = useState<KRSignal[]>([]);
    const [aiData, setAiData] = useState<KRAIAnalysis | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<string>('');
    const [signalDate, setSignalDate] = useState<string>('');

    useEffect(() => {
        loadSignals();
    }, []);

    // Real-time price updates (every 60s)
    useEffect(() => {
        if (loading || signals.length === 0) return;

        const updatePrices = async () => {
            try {
                const tickers = signals.map(s => s.ticker);
                if (tickers.length === 0) return;

                const res = await fetch('/api/kr/realtime-prices', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tickers })
                });
                const prices = await res.json();

                if (Object.keys(prices).length > 0) {
                    setSignals(prev => prev.map(s => {
                        if (prices[s.ticker]) {
                            const current = prices[s.ticker];
                            const entry = s.entry_price || 0;
                            let ret = s.return_pct || 0;
                            if (entry > 0) {
                                ret = ((current - entry) / entry) * 100;
                            }
                            return { ...s, current_price: current, return_pct: ret };
                        }
                        return s;
                    }));
                    setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
                }
            } catch (e) {
                console.error('Price update failed:', e);
            }
        };

        const interval = setInterval(updatePrices, 60000);
        return () => clearInterval(interval);
    }, [signals.length, loading]); // Only re-run if signal count changes (initial load)

    const loadSignals = async () => {
        setLoading(true);
        try {
            const [signalsRes, aiRes] = await Promise.all([
                krAPI.getSignals(),
                krAPI.getAIAnalysis(),
            ]);
            setSignals(signalsRes.signals || []);
            setAiData(aiRes);
            // Extract signal date from generated_at
            const genAt = (signalsRes as any).generated_at;
            if (genAt) {
                const d = new Date(genAt);
                setSignalDate(d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
            }
            setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
        } catch (error) {
            console.error('Failed to load signals:', error);
        } finally {
            setLoading(false);
        }
    };

    // 수급 데이터를 억/만 단위로 포맷
    const formatFlow = (value: number | undefined) => {
        if (value === undefined || value === null) return '-';
        const absValue = Math.abs(value);
        if (absValue >= 100000000) {
            return `${(value / 100000000).toFixed(1)}억`;
        } else if (absValue >= 10000) {
            return `${(value / 10000).toFixed(0)}만`;
        }
        return value.toLocaleString();
    };

    const getAIBadge = (ticker: string, model: 'gpt' | 'gemini') => {
        if (!aiData) return null;
        const stock = aiData.signals?.find((s) => s.ticker === ticker);
        if (!stock) return null;

        const rec = model === 'gpt' ? stock.gpt_recommendation : stock.gemini_recommendation;
        if (!rec) return <span className="text-gray-500 text-[10px]">-</span>;

        const action = rec.action?.toUpperCase();
        let bgClass = 'bg-yellow-500/20 text-yellow-400';
        let icon = '■';
        let label = '관망';

        if (action === 'BUY') {
            bgClass = 'bg-green-500/20 text-green-400';
            icon = '▲';
            label = '매수';
        } else if (action === 'SELL') {
            bgClass = 'bg-red-500/20 text-red-400';
            icon = '▼';
            label = '매도';
        }

        return (
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${bgClass} border border-current/30`} title={rec.reason}>
                {icon} {label}
            </span>
        );
    };

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-blue-500/20 bg-blue-500/5 text-xs text-blue-400 font-medium mb-4">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping"></span>
                    VCP Pattern Scanner
                </div>
                <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
                    VCP <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">Signals</span>
                </h2>
                <p className="text-gray-400 text-lg">Volatility Contraction Pattern + 기관/외국인 수급</p>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                        <span className="w-1 h-5 bg-blue-500 rounded-full"></span>
                        Live VCP Signals
                    </h3>
                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-full">
                        {signals.length}
                    </span>
                </div>

                <button
                    onClick={loadSignals}
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl transition-all flex items-center gap-2 disabled:opacity-50"
                >
                    <i className={`fas fa-sync-alt ${loading ? 'animate-spin' : ''}`}></i>
                    Refresh
                </button>
            </div>

            {/* Signals Table */}
            <div className="rounded-2xl bg-[#1c1c1e] border border-white/10 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead className="bg-black/20">
                            <tr className="text-[10px] text-gray-500 border-b border-white/5 uppercase tracking-wider">
                                <th className="px-4 py-3 font-semibold">Stock</th>
                                <th className="px-4 py-3 font-semibold">Date</th>
                                <th className="px-4 py-3 font-semibold text-right">외국인 5D</th>
                                <th className="px-4 py-3 font-semibold text-right">기관 5D</th>
                                <th className="px-4 py-3 font-semibold text-center">Score</th>
                                <th className="px-4 py-3 font-semibold text-center">Cont.</th>
                                <th className="px-4 py-3 font-semibold text-right">Entry</th>
                                <th className="px-4 py-3 font-semibold text-right">Current</th>
                                <th className="px-4 py-3 font-semibold text-right">Return</th>
                                <th className="px-4 py-3 font-semibold text-center">GPT</th>
                                <th className="px-4 py-3 font-semibold text-center">Gemini</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5 text-sm">
                            {loading ? (
                                <tr>
                                    <td colSpan={11} className="p-8 text-center text-gray-500">
                                        <i className="fas fa-spinner fa-spin text-2xl text-blue-500/50 mb-3"></i>
                                        <p className="text-xs">Loading signals...</p>
                                    </td>
                                </tr>
                            ) : signals.length === 0 ? (
                                <tr>
                                    <td colSpan={11} className="p-8 text-center text-gray-500">
                                        <i className="fas fa-inbox text-2xl opacity-30 mb-3"></i>
                                        <p className="text-xs">오늘 시그널이 없습니다</p>
                                    </td>
                                </tr>
                            ) : (
                                signals.map((signal, idx) => (
                                    <tr
                                        key={`${signal.ticker}-${idx}`}
                                        onClick={() => setSelectedTicker(signal.ticker)}
                                        className={`hover:bg-white/5 transition-colors cursor-pointer ${selectedTicker === signal.ticker ? 'bg-white/10' : ''
                                            }`}
                                        style={{ animationDelay: `${idx * 0.05}s` }}
                                    >
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                                {/* Stock Icon */}
                                                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-white/10 flex items-center justify-center text-white font-bold text-sm">
                                                    {signal.name?.charAt(0) || signal.ticker?.charAt(0) || '?'}
                                                </div>
                                                <div className="flex flex-col">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-white font-bold">{signal.name || signal.ticker}</span>
                                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${signal.market === 'KOSPI' ? 'bg-blue-500/20 text-blue-400' : 'bg-pink-500/20 text-pink-400'}`}>
                                                            {signal.market}
                                                        </span>
                                                    </div>
                                                    <span className="text-[10px] text-gray-500 font-mono">{signal.ticker}</span>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-gray-400 text-xs">{signal.signal_date || signalDate || '-'}</td>
                                        <td className={`px-4 py-3 text-right font-mono text-xs ${signal.foreign_5d > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            <div className="flex items-center justify-end gap-1">
                                                {signal.foreign_5d > 0 ? <i className="fas fa-arrow-up text-[8px]"></i> : signal.foreign_5d < 0 ? <i className="fas fa-arrow-down text-[8px]"></i> : null}
                                                {formatFlow(signal.foreign_5d)}
                                            </div>
                                        </td>
                                        <td className={`px-4 py-3 text-right font-mono text-xs ${signal.inst_5d > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            <div className="flex items-center justify-end gap-1">
                                                {signal.inst_5d > 0 ? <i className="fas fa-arrow-up text-[8px]"></i> : signal.inst_5d < 0 ? <i className="fas fa-arrow-down text-[8px]"></i> : null}
                                                {formatFlow(signal.inst_5d)}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                                {signal.score ? Math.round(signal.score) : '-'}
                                            </span>
                                        </td>
                                        <td className={`px-4 py-3 text-center font-mono text-xs ${signal.contraction_ratio && signal.contraction_ratio <= 0.6 ? 'text-emerald-400' : 'text-purple-400'
                                            }`}>
                                            {signal.contraction_ratio?.toFixed(2) ?? '-'}
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-xs text-gray-400">
                                            ₩{signal.entry_price?.toLocaleString() ?? '-'}
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-xs text-white">
                                            ₩{signal.current_price?.toLocaleString() ?? '-'}
                                        </td>
                                        <td className={`px-4 py-3 text-right font-mono text-xs font-bold ${signal.return_pct >= 0 ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                            {signal.return_pct !== undefined ? `${signal.return_pct >= 0 ? '+' : ''}${signal.return_pct.toFixed(1)}%` : '-'}
                                        </td>
                                        <td className="px-4 py-3 text-center">{getAIBadge(signal.ticker, 'gpt')}</td>
                                        <td className="px-4 py-3 text-center">{getAIBadge(signal.ticker, 'gemini')}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Last Updated */}
            <div className="text-center text-xs text-gray-500">
                Last updated: {lastUpdated || '-'}
            </div>
        </div>
    );
}
```

