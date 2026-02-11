import pandas as pd
from dataclasses import dataclass
from typing import Optional

@dataclass
class VCPResult:
    """VCP 패턴 감지 결과"""
    ticker: str
    name: str
    vcp_score: float
    contraction_ratio: float
    is_vcp: bool
    date: str
    entry_price: float
    pattern_desc: str = ""

def detect_vcp_pattern(df: pd.DataFrame, ticker: str, name: str) -> VCPResult:
    """
    VCP 패턴 감지 (ATR & Range Contraction & Near High)
    
    Args:
        df: OHLCV 데이터프레임 (columns: ['open', 'high', 'low', 'close', 'volume', 'date'])
        ticker: 종목 코드
        name: 종목명
        
    Returns:
        VCPResult 객체
    """
    try:
        if len(df) < 60: 
            return VCPResult(ticker, name, 0, 1.0, False, str(df.iloc[-1]['date']) if not df.empty else "", 0, "Not enough data")

        # 1. Price Near Recent High (Constraint)
        high_60d = df['high'].tail(60).max()
        current_close = df.iloc[-1]['close']
        
        if current_close < high_60d * 0.85:
                return VCPResult(ticker, name, 0, 1.0, False, str(df.iloc[-1]['date']), 0, "Price too low vs 60d High")

        # 2. ATR (Volatility) Check
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        atr_20 = df['tr'].tail(20).mean()
        atr_5 = df['tr'].tail(5).mean()
        
        vol_contracting = atr_5 < atr_20
        
        # 3. Range Contraction Ratio
        daily_range = df['high'] - df['low']
        avg_range_20 = daily_range.tail(20).mean()
        recent_range_5 = daily_range.tail(5).mean()
        
        # Avoid division by zero
        contraction_ratio = recent_range_5 / avg_range_20 if avg_range_20 > 0.0001 else 1.0
        
        # 4. Volume Contraction
        volume = df['volume']
        recent_vol = volume.tail(5).mean()
        avg_vol = volume.tail(20).mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
        
        # 5. MA Alignment
        ma5 = df['close'].tail(5).mean()
        ma20 = df['close'].tail(20).mean()
        
        score = 0
        
        # A. Volatility Score
        if contraction_ratio < 0.5: score += 40
        elif contraction_ratio < 0.6: score += 30
        elif contraction_ratio < 0.7: score += 15
        
        # B. Volume Score
        if vol_ratio < 0.5: score += 30
        elif vol_ratio < 0.7: score += 20
        elif vol_ratio < 0.9: score += 10
        
        # C. MA Score
        if current_close > ma5 > ma20: score += 30
        elif current_close > ma20: score += 15
        
        is_vcp = (contraction_ratio <= 0.7) and vol_contracting and (score >= 50)
        
        entry_price = high_60d
        
        desc = []
        if not vol_contracting: desc.append("ATR Expansion")
        if contraction_ratio > 0.7: desc.append(f"Range Ratio {contraction_ratio:.2f} > 0.7")
        if score < 50: desc.append(f"Low Score {score}")
        
        pattern_desc = ", ".join(desc) if not is_vcp else "VCP Confirmed"

        return VCPResult(
            ticker=ticker,
            name=name,
            vcp_score=float(score),
            contraction_ratio=round(contraction_ratio, 2),
            is_vcp=is_vcp,
            date=df.iloc[-1]['date'].strftime('%Y-%m-%d'),
            entry_price=entry_price,
            pattern_desc=pattern_desc
        )

    except Exception as e:
        return VCPResult(ticker, name, 0, 1.0, False, "", 0, f"Error: {e}")
