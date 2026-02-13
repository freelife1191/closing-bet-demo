from datetime import datetime, date

class MarketSchedule:
    """시장 휴장일 관리 (2026년 기준)"""
    
    # 2026년 공휴일 및 대체공휴일 리스트 (YYYY-MM-DD)
    HOLIDAYS_2026 = {
        '2026-01-01', # 신정
        '2026-02-16', '2026-02-17', '2026-02-18', # 설날 연휴
        '2026-03-01', # 삼일절
        '2026-03-02', # 삼일절 대체공휴일
        '2026-05-05', # 어린이날
        '2026-05-24', # 부처님오신날
        '2026-05-25', # 부처님오신날 대체공휴일
        '2026-06-03', # 전국동시지방선거
        '2026-06-06', # 현충일
        '2026-08-15', # 광복절
        '2026-09-24', '2026-09-25', '2026-09-26', # 추석 연휴
        '2026-10-03', # 개천절
        '2026-10-09', # 한글날
        '2026-12-25', # 성탄절
    }

    @staticmethod
    def is_market_open(target_date: date = None) -> bool:
        """
        해당 날짜가 시장이 열리는 날인지 확인
        True: 개장일 (평일 & 비공휴일)
        False: 휴장일 (주말 or 공휴일)
        """
        if target_date is None:
            target_date = datetime.now().date()
        
        # 1. 주말 체크 (토: 5, 일: 6)
        if target_date.weekday() >= 5:
            return False
            
        # 2. 공휴일 체크
        date_str = target_date.strftime('%Y-%m-%d')
        if date_str in MarketSchedule.HOLIDAYS_2026:
            return False
            
        return True

    @staticmethod
    def is_holiday(target_date: date = None) -> bool:
        """휴장일 여부 반환 (is_market_open의 반대)"""
        return not MarketSchedule.is_market_open(target_date)
