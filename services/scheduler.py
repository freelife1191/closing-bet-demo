
import time
import schedule
import threading
import logging
import fcntl
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

# Global lock file reference to prevent GC
_scheduler_lock_file = None




def run_jongga_v2_analysis(test_mode=False):
    """장 마감 후 AI 종가베팅 분석 (16:30 - Last)"""
    now = datetime.now()
    if test_mode or now.weekday() < 5:  # 평일만 or 테스트
        logger.info(">>> [Scheduler] AI 종가베팅 분석 시작 (16:30 - After Closing Analysis)")
        try:
            # 1. 당일(장중) 데이터 수집 (Pre-close) -> 제거 (16:05 정기 분석에서 수행됨)
            # 16:30 시점에 실행되므로 이미 create_daily_prices()가 완료된 상태라 가정
            # logger.info("[Scheduler] 장중 주가 데이터 업데이트...")
            # create_daily_prices()
            
            # 2. 분석 실행
            create_jongga_v2_latest()
            logger.info("<<< [Scheduler] AI 종가베팅 분석 완료 (16:30)")
            
            # 3. 알림 발송 (Messenger 사용)
            send_jongga_notification()
            
            logger.info("<<< [Scheduler] AI 종가베팅 분석 완료")
            
        except Exception as e:
            logger.error(f"[Scheduler] AI 종가베팅 분석 실패: {e}")



def run_daily_closing_analysis(test_mode=False):
    """장 마감 후 전체 데이터 수집 및 분석 (16:05 - First)"""
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
            
            # [2026-02-11 Modified] Chain Execution: Run Jongga V2 immediately after Closing Analysis
            logger.info(">>> [Scheduler] Chaining: 데이터 수집 완료 후 AI 종가베팅 분석 즉시 시작")
            run_jongga_v2_analysis(test_mode=test_mode)
            
            logger.info("<<< [Scheduler] 장 마감 정기 분석 및 종가베팅 완료")
        except Exception as e:
            logger.error(f"[Scheduler] 장 마감 정기 분석 실패: {e}")

def run_market_gate_sync():
    """주기적 매크로 지표 및 스마트머니 데이터 업데이트 (30분)"""
    # [2026-02-08] 주말 실행 방지
    if datetime.now().weekday() >= 5:
        logger.debug("[Scheduler] 주말이므로 Market Gate 동기화 건너뜀")
        return

    logger.debug(">>> [Scheduler] Market Gate 및 전체 데이터 동기화 시작")
    try:
        # 1. 기초 데이터 업데이트 (주가 & 수급)
        # Market Gate와 Smart Money Tracking 페이지의 데이터 일관성을 위해 필수
        logger.debug("[Scheduler] 실시간 주가/수급 데이터 갱신 중...")
        
        # force=True로 최근 데이터(특히 당일) 강제 갱신 유도
        # (주의: 너무 빈번하면 API 제한 걸릴 수 있으나, 30분 주기는 적절함)
        # [Optimization] lookback_days=2 (오늘+어제)만 갱신하여 5~7일치 중복 수집 방지
        # 이미 수집된 날짜(어제 이전)는 건너뛰고 싶지만, 장중에는 오늘 데이터가 계속 변하므로 force 필요
        # 단, 과거 데이터까지 force할 필요는 없으므로 2일로 제한
        # [2026-02-08 Fix] 서버 재기동 시 VCP 분석처럼 보이는 전체 종목 갱신 방지
        # Market Gate는 지수/섹터만 필요하므로 개별 종목 갱신은 불필요 (장 마감 때만 수행)
        # create_daily_prices(force=True, lookback_days=2) 
        # create_institutional_trend(force=True, lookback_days=2)
        
        # 2. VCP 시그널 분석 (Smart Money 업데이트 시 제외 요청)
        # 사용자 요청: VCP 시그널, 종가 베팅 데이터는 업데이트 되면 안됨
        # logger.info("[Scheduler] 실시간 VCP 시그널 스캔...")
        # create_signals_log(run_ai=False) 

        # 3. Market Gate 분석
        from engine.market_gate import MarketGate
        mg = MarketGate()
        result = mg.analyze()
        mg.save_analysis(result)
        
        logger.debug("<<< [Scheduler] Market Gate 및 전체 데이터 동기화 완료")
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
    """스케줄러 시작 (백그라운드 스레드) - Singleton 보장"""
    # 1. Lock File Check FIRST (항상 먼저 실행 - 모든 워커에서 중복 로그 방지)
    global _scheduler_lock_file
    lock_file_path = os.path.join(os.path.dirname(__file__), 'scheduler.lock')
    try:
        # Create or open the lock file
        _scheduler_lock_file = open(lock_file_path, 'w')
        # Try to acquire a non-blocking exclusive lock
        fcntl.lockf(_scheduler_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # If successful, we are the scheduler instance
        logger.info("Scheduler lock acquired. Starting scheduler service...")
    except IOError:
        # Lock acquisition failed, meaning another worker is running the scheduler
        # Silent return - no log needed to avoid duplicates
        return

    # 2. Config Check (잠금 획득한 워커에서만 실행)
    if not app_config.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in configuration. Skipping start.")
        return

    # 2. Schedule Jobs
    # 매크로 지표 업데이트 (Configured Interval)
    interval = app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES
    schedule.every(interval).minutes.do(run_market_gate_sync).tag('market_gate')
    logger.info(f"Scheduled Market Gate sync every {interval} minutes")
    
    # 스케줄 시간 설정 (환경변수로 커스터마이징 가능)
    # [2026-02-11 Modified] 장 마감(16:00) 정각에 시작하여 순차적으로 실행
    closing_time = os.getenv('CLOSING_SCHEDULE_TIME', '16:00') # 장 마감 직후 실행 (16:00)
    # jongga_time = os.getenv('JONGGA_SCHEDULE_TIME', '16:30')   # 가장 늦게 실행 (16:30)
    
    # 매일 AI 종가베팅 (장 마감 후)
    # schedule.every().day.at(jongga_time).do(run_jongga_v2_analysis)
    # logger.info(f"Scheduled Jongga V2 Analysis at {jongga_time} (Runs Last)")

    # 매일 장 마감 전체 분석 (이후 Jongga V2 자동 실행됨)
    schedule.every().day.at(closing_time).do(run_daily_closing_analysis)
    logger.info(f"Scheduled Daily Closing Analysis at {closing_time} (Chains Jongga V2)")
    
    # 앱 시작 시 1회 즉시 실행 (데이터 확인용 - 비동기로 실행하여 부팅 지연 방지)
    # threading.Thread(target=run_market_gate_sync, daemon=True).start()

    # 3. Start Loop
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
