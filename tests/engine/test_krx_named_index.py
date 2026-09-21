#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import pytest
from types import SimpleNamespace
from engine.collectors.krx_data_mixin import KRXCollectorDataMixin


@pytest.mark.parametrize('name',[None,'티커','ticker','종목코드'])
def test_index_name_does_not_change_ticker(name):
    df=pd.DataFrame({'종가':[100000],'거래대금':[1000000000000],'등락률':[5.0],'거래량':[100000],'시가총액':[10000000000000]},index=pd.Index(['005930'],name=name))
    c=SimpleNamespace(config=SimpleNamespace(min_change_pct=0),_get_stock_name=lambda code:'삼성전자',_get_sector=lambda code:'반도체')
    out=KRXCollectorDataMixin._process_ohlcv_dataframe(c,df,'KOSPI',10)
    assert [s.code for s in out]==['005930']


def test_invalid_code_is_not_normal_empty_result():
    df=pd.DataFrame({'종가':[100000],'거래대금':[1000000000000],'등락률':[5.0]},index=[''])
    c=SimpleNamespace(config=SimpleNamespace(min_change_pct=0))
    with pytest.raises(ValueError):KRXCollectorDataMixin._process_ohlcv_dataframe(c,df,'KOSPI',10)


@pytest.mark.parametrize('code',['','000000',None,'bad'])
def test_bad_cache_snapshot_is_a_miss(code):
    from engine.collectors.krx_local_data_mixin import KRXCollectorLocalDataMixin
    row=[code,'stock','KOSPI','sector',100000,5.0,1000000000000,1000,0,0,0]
    assert KRXCollectorLocalDataMixin._deserialize_top_gainers({'rows':[row]}) is None


def test_healthy_cache_and_real_empty_snapshot_are_preserved():
    from engine.collectors.krx_local_data_mixin import KRXCollectorLocalDataMixin as C
    row=['005930','삼성전자','KOSPI','sector',100000,5.0,1000000000000,1000,0,0,0]
    assert C._deserialize_top_gainers({'rows':[row]})[0].code=='005930'
    assert C._deserialize_top_gainers({'rows':[]})==[]


def test_bad_memory_and_sqlite_cache_refetch_real_named_index(monkeypatch):
    import asyncio,sys
    from collections import OrderedDict
    from engine.collectors.krx import KRXCollector as C
    invalid={'rows':[['','bad','KOSPI','',100000,5,1000000000000,1000,0,0,0]]}
    kwargs=dict(source='pykrx',market='KOSPI',top_n=10,target_date='20260921',min_change_pct=0.0,csv_signature=None,stocks_signature=None)
    key=C._top_gainers_memory_cache_key(**kwargs)
    monkeypatch.setattr(C,'_top_gainers_cache',OrderedDict([(key,invalid)]))
    monkeypatch.setattr('engine.collectors.krx_local_data_mixin._load_json_payload_from_sqlite',lambda **k:(True,invalid))
    calls=[]
    def fetch(*a,**k):
        calls.append(1)
        return pd.DataFrame({'종가':[100000],'거래대금':[1000000000000],'등락률':[5.0]},index=pd.Index(['005930'],name='티커'))
    monkeypatch.setitem(sys.modules,'pykrx',SimpleNamespace(stock=SimpleNamespace(get_market_ohlcv_by_ticker=fetch)))
    class Collector(C):
        def __init__(self):pass
        config=SimpleNamespace(min_change_pct=0)
        def _get_stock_name(self,code):return '삼성전자'
        def _get_sector(self,code):return '반도체'
        def _save_cached_top_gainers(self,**kwargs):pass
    out=asyncio.run(Collector().get_top_gainers('KOSPI',10,'20260921'))
    assert calls==[1] and out[0].code=='005930'
