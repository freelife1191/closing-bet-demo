#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""현재 뉴스 검색 DOM과 오래된 빈 캐시에서의 복구 회귀."""
import asyncio
from collections import OrderedDict
from types import SimpleNamespace

from engine.collectors.news import EnhancedNewsCollector
from engine.collectors.news_scrape_helpers import fetch_naver_search_news


def test_naver_current_cards_extract_title_source_and_deduplicate(monkeypatch):
    html = '''<div><div data-sds-comp="Profile"><span class="sds-comps-profile-info-title-text"><a><span class="sds-comps-text">언론A</span><span>새 창 열림</span></a></span></div><div><div><a data-heatmap-target=".tit" href="https://example.com/1"><span class="sds-comps-text-type-headline1">삼성<mark>전자</mark> 실적 발표</span><span>새 창 열림</span></a><a data-heatmap-target=".body">본문 중복</a></div></div></div>
    <div><div data-sds-comp="Profile"><span class="sds-comps-profile-info-title-text"><a><span class="sds-comps-text">언론B</span></a></span></div><div><a data-heatmap-target=".tit" href="https://example.com/2"><span class="sds-comps-text-type-headline1">두 번째 기사</span></a></div></div>'''
    monkeypatch.setattr('requests.get', lambda *a, **k: SimpleNamespace(ok=True, text=html))
    seen = set()
    kwargs = dict(stock_name='삼성전자', limit=2, seen_titles=seen, headers={}, get_weight_fn=lambda *a: 0.8)
    items = fetch_naver_search_news(**kwargs)
    assert [(x.title, x.source, x.url) for x in items] == [('삼성전자 실적 발표', '언론A', 'https://example.com/1'), ('두 번째 기사', '언론B', 'https://example.com/2')]
    assert fetch_naver_search_news(**kwargs) == []


def test_naver_legacy_markup_still_supported(monkeypatch):
    monkeypatch.setattr('requests.get', lambda *a, **k: SimpleNamespace(ok=True, text='<div class="news_wrap"><a class="news_tit" title="기존 기사" href="https://example.com/old"></a><a class="info press">언론사 선정기존언론</a></div>'))
    items = fetch_naver_search_news(stock_name='종목', limit=1, seen_titles=set(), headers={}, get_weight_fn=lambda *a: 0.8)
    assert [(x.title, x.source) for x in items] == [('기존 기사', '기존언론')]


def test_old_empty_cache_is_not_a_successful_news_lookup(monkeypatch):
    collector = EnhancedNewsCollector()
    monkeypatch.setattr(EnhancedNewsCollector, '_news_cache', OrderedDict())
    monkeypatch.setattr('engine.collectors.news._load_json_payload_from_sqlite', lambda **k: (True, {'rows': []}))
    assert collector._load_cached_news_items(code='005930', limit=3, stock_name='삼성전자', cache_slot='old') is None


def test_empty_result_is_retried_without_writing_snapshot(monkeypatch):
    collector = EnhancedNewsCollector()
    monkeypatch.setattr(collector, '_load_cached_news_items', lambda **k: None)
    writes = []
    monkeypatch.setattr(collector, '_save_cached_news_items', lambda **k: writes.append(k))
    monkeypatch.setattr('engine.collectors.news.collect_stock_news_impl', lambda **k: [])
    assert asyncio.run(collector.get_stock_news('005930', 3, '삼성전자')) == []
    assert writes == []


def test_collectors_only_advertise_supported_response_compression():
    from engine.collectors.base import BaseCollector
    assert BaseCollector._build_default_headers()['Accept-Encoding'] == 'gzip, deflate'
