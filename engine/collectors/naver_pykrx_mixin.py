#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector pykrx enrichment mixin
"""

import logging
from datetime import datetime, timedelta
from typing import Dict


logger = logging.getLogger(__name__)


class NaverPykrxMixin:
    """pykrx 기반 투자자/펀더멘탈 보강 로직."""

    async def _get_investor_trend(self, code: str, result: Dict) -> None:
        """pykrx를 통해 투자자 동향 수집"""
        try:
            from pykrx import stock

            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            if not df.empty:
                df = df.tail(5)

                foreign_col = "외국인합계" if "외국인합계" in df.columns else "외국인"
                inst_col = "기관합계" if "기관합계" in df.columns else "기관"
                retail_col = "개인" if "개인" in df.columns else None

                if foreign_col in df.columns:
                    result["investorTrend"]["foreign"] = int(df[foreign_col].sum())
                if inst_col in df.columns:
                    result["investorTrend"]["institution"] = int(df[inst_col].sum())
                if retail_col and retail_col in df.columns:
                    result["investorTrend"]["individual"] = int(df[retail_col].sum())
        except Exception as e:
            logger.debug(f"투자자 동향 pykrx 조회 실패: {e}")

    async def _get_fundamental_data(self, code: str, result: Dict) -> None:
        """pykrx를 통해 펀더멘탈 데이터 수집"""
        try:
            from pykrx import stock

            today = datetime.now().strftime("%Y%m%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            for target_date in [today, yesterday]:
                try:
                    df = stock.get_market_fundamental_by_ticker(target_date)
                    if not df.empty and code in df.index:
                        row = df.loc[code]
                        if "PER" in row:
                            result["indicators"]["per"] = (
                                float(row["PER"])
                                if result["indicators"]["per"] == 0
                                else result["indicators"]["per"]
                            )
                        if "PBR" in row:
                            result["indicators"]["pbr"] = (
                                float(row["PBR"])
                                if result["indicators"]["pbr"] == 0
                                else result["indicators"]["pbr"]
                            )
                        if "EPS" in row:
                            result["indicators"]["eps"] = float(row["EPS"])
                        if "BPS" in row:
                            result["indicators"]["bps"] = float(row["BPS"])
                        if "DIV" in row:
                            result["indicators"]["dividendYield"] = float(row["DIV"])
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"펀더멘탈 pykrx 조회 실패: {e}")


__all__ = ["NaverPykrxMixin"]
