#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 factory에서 설정 누락 안내를 검증하되 외부효과 경계는 차단한다."""
import logging

import pytest

import app as app_module


@pytest.mark.parametrize('secret', [None, '', '   '])
def test_factory_warns_when_identity_secret_missing(monkeypatch, caplog, secret):
    if secret is None:
        monkeypatch.delenv('INTERNAL_IDENTITY_SECRET', raising=False)
    else:
        monkeypatch.setenv('INTERNAL_IDENTITY_SECRET', secret)
    for name in ('_configure_logging', '_reset_startup_status_files', '_start_scheduler',
                 '_configure_app', '_configure_cors', '_register_request_context',
                 '_register_activity_logging', '_register_blueprints', '_register_core_routes',
                 '_register_global_error_handler'):
        monkeypatch.setattr(app_module, name, lambda *args: None)
    with caplog.at_level(logging.WARNING):
        app_module.create_app()
    records = [record.message for record in caplog.records if 'INTERNAL_IDENTITY_SECRET' in record.message]
    assert len(records) == 1
    assert '익명' in records[0] and '관리자' in records[0]


def test_factory_does_not_log_configured_identity_secret(monkeypatch, caplog):
    monkeypatch.setenv('INTERNAL_IDENTITY_SECRET', 'qa-secret-sentinel-not-real')
    for name in ('_configure_logging', '_reset_startup_status_files', '_start_scheduler',
                 '_configure_app', '_configure_cors', '_register_request_context',
                 '_register_activity_logging', '_register_blueprints', '_register_core_routes',
                 '_register_global_error_handler'):
        monkeypatch.setattr(app_module, name, lambda *args: None)
    with caplog.at_level(logging.WARNING):
        app_module.create_app()
    assert 'qa-secret-sentinel-not-real' not in caplog.text
    assert 'INTERNAL_IDENTITY_SECRET' not in caplog.text
