
import time
import schedule
import threading
import logging
from datetime import datetime
import sys
import os


# scripts 폴더 경로 추가 (services 상위 폴더의 scripts)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from engine.config import app_config  # Config Import

from init_data import (

    create_signals_log, # Corrected
    create_jongga_v2_latest,
    fetch_sector_indices,
    create_daily_prices,
    create_institutional_trend,
    send_jongga_notification,
    log
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)




def run_jongga_v2_analysis(test_mode=False):
    """장 마감 직전 AI 종가베팅 분석 (15:20)"""
    now = datetime.now()
    if test_mode or now.weekday() < 5:  # 평일만 or 테스트
        logger.info(">>> [Scheduler] AI 종가베팅 분석 시작 (15:20)")
        try:
            # 1. 당일(장중) 데이터 수집 (Pre-close)
            # 15:20 시점의 데이터로 업데이트하여 분석 정확도 확보
            logger.info("[Scheduler] 장중 주가 데이터 업데이트...")
            create_daily_prices()
            
            # 2. 분석 실행
            create_jongga_v2_latest()
            logger.info("<<< [Scheduler] AI 종가베팅 분석 완료")
            
            # 3. 알림 발송 (Messenger 사용)
            send_jongga_notification()
            
            logger.info("<<< [Scheduler] AI 종가베팅 분석 완료")
            
        except Exception as e:
            logger.error(f"[Scheduler] AI 종가베팅 분석 실패: {e}")



def run_daily_closing_analysis(test_mode=False):
    """장 마감 후 전체 데이터 수집 및 분석 (15:40)"""
    now = datetime.now()
    if test_mode or now.weekday() < 5: # 평일만 or 테스트
        logger.info(">>> [Scheduler] 장 마감 정기 분석 시작")
        try:
            # 1. 최신 데이터 수집
            logger.info("[Scheduler] 일별 주가 데이터 수집...")
            create_daily_prices()
            
            logger.info("[Scheduler] 기관/외인 수급 데이터 수집...")
            create_institutional_trend()
            
            # 2. 분석 실행
            logger.info("[Scheduler] VCP 시그널 분석...")
            create_signals_log(run_ai=True)
            
            # Note: Jongga V2 is now run separately at 15:20
            
            logger.info("<<< [Scheduler] 장 마감 정기 분석 완료")
        except Exception as e:
            logger.error(f"[Scheduler] 장 마감 정기 분석 실패: {e}")

def run_market_gate_sync():
    """주기적 매크로 지표 업데이트 (30분)"""
    logger.info(">>> [Scheduler] Market Gate 주기적 동기화 시작")
    try:
        from engine.market_gate import MarketGate
        mg = MarketGate()
        result = mg.analyze()
        mg.save_analysis(result)
        logger.info("<<< [Scheduler] Market Gate 주기적 동기화 완료")
    except Exception as e:
        logger.error(f"[Scheduler] Market Gate 동기화 실패: {e}")

def update_market_gate_interval(minutes: int):
    """실시간으로 Market Gate 업데이트 주기 변경"""
    try:
        # 기존 작업 제거
        schedule.clear('market_gate')
        logger.info(f"[Scheduler] 기존 Market Gate 스케줄 제거됨")
        
        # 새 작업 등록
        schedule.every(minutes).minutes.do(run_market_gate_sync).tag('market_gate')
        logger.info(f"[Scheduler] Market Gate 주기 변경 완료: {minutes}분")
        
        # 즉시 실행은 하지 않음 (주기만 변경)
    except Exception as e:
        logger.error(f"[Scheduler] 주기 변경 실패: {e}")

def start_scheduler():
    """스케줄러 시작 (백그라운드 스레드)"""
    # 매크로 지표 업데이트 (Configured Interval)
    interval = app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES
    schedule.every(interval).minutes.do(run_market_gate_sync).tag('market_gate')
    logger.info(f"Scheduled Market Gate sync every {interval} minutes")
    
    # 매일 15:20 AI 종가베팅 (장 마감 직전)
    schedule.every().day.at("15:20").do(run_jongga_v2_analysis)

    # 매일 15:40 장 마감 전체 분석
    schedule.every().day.at("15:40").do(run_daily_closing_analysis)
    
    # 앱 시작 시 1회 즉시 실행 (데이터 확인용)
    run_market_gate_sync()

    
    def run_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)

    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    logger.info("Scheduler started successfully")

def test_scheduler():
    """테스트 실행: 모든 잡을 즉시 1회 실행"""
    logger.info("========== [TEST MODE] 스케줄러 잡 테스트 시작 ==========")
    
    # 1. AI 종가베팅
    logger.info(">>> 테스트: run_jongga_v2_analysis()")
    try:
        run_jongga_v2_analysis(test_mode=True)
    except Exception as e:
        logger.error(f"FAILED: {e}")
        
    # 2. 장 마감 정기 분석
    logger.info(">>> 테스트: run_daily_closing_analysis()")
    try:
        run_daily_closing_analysis(test_mode=True)
    except Exception as e:
        logger.error(f"FAILED: {e}")
        
    logger.info("========== [TEST MODE] 테스트 종료 ==========")

if __name__ == "__main__":
    # 인자가 있으면 테스트 모드
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_scheduler()
    else:
        # 단독 실행 시 테스트 (기본)
        start_scheduler()
        while True:
            time.sleep(1)
