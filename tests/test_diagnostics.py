"""用合成秘密检查错误编号、允许日志字段及日志故障隔离。"""

import io
import json
import logging
import re

import pymysql
import pytest

from app import create_app
from core import diagnostics, db


@pytest.fixture
def captured(monkeypatch):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    monkeypatch.setattr(diagnostics.LOGGER, "handlers", [handler])
    return stream


@pytest.mark.parametrize("kind,status", [(RuntimeError, 500), (pymysql.OperationalError, 503)])
def test_fault_id_and_allowlist_never_include_payload(captured, kind, status):
    app = create_app({"TESTING": True})
    @app.post('/test/fault/<value>')
    def fault(value):
        private_local = "synthetic-local-secret"
        raise kind("synthetic-exception-secret", private_local)
    response = app.test_client().post('/test/fault/synthetic-path-secret?password=synthetic-query-secret',
        json={"password": "synthetic-body-secret"}, headers={"Authorization": "Basic synthetic-header-secret"})
    assert response.status_code == status
    assert re.fullmatch('[0-9a-f]{24}', response.json['error_id'])
    rows = captured.getvalue().splitlines()
    assert len(rows) == 1
    record = json.loads(rows[0])
    assert set(record) == {'event','error_id','time','method','route','exception_type','locations'}
    assert record['error_id'] == response.json['error_id']
    assert record['route'] == '/test/fault/<value>' and record['method'] == 'POST'
    assert record['exception_type'] == kind.__name__ and record['time'].endswith('Z')
    assert record['locations'][-1]['file'] == 'tests/test_diagnostics.py'
    assert isinstance(record['locations'][-1]['line'], int)
    assert 'synthetic-' not in captured.getvalue() + response.get_data(as_text=True)


def test_ready_database_exception_has_matching_id(captured, monkeypatch):
    app = create_app({"TESTING": True, "DB_USER": "", "DB_PASSWORD": ""})
    response = app.test_client().get('/api/ready')
    assert response.status_code == 503
    assert json.loads(captured.getvalue())['error_id'] == response.json['error_id']


def test_normal_failures_are_not_program_faults(captured):
    app = create_app({"TESTING": True})
    client = app.test_client()
    for path in ['/missing', '/api/health?x=1']:
        response = client.get(path)
        assert response.status_code in (400,404) and 'error_id' not in response.json
    assert captured.getvalue() == ''


def test_one_id_per_request_and_distinct_requests(captured):
    app = create_app({"TESTING": True})
    @app.get('/test/id')
    def same():
        first = diagnostics.record_failure(ValueError('synthetic-secret'))
        assert first == diagnostics.record_failure(ValueError('synthetic-secret'))
        return {'first': first}
    client = app.test_client()
    assert client.get('/test/id').json != client.get('/test/id').json
    assert len(captured.getvalue().splitlines()) == 2


def test_log_failure_does_not_change_response(monkeypatch):
    app = create_app({"TESTING": True})
    @app.get('/test/failure')
    def fault():
        raise RuntimeError('synthetic-secret')
    def broken(*args, **kwargs):
        raise OSError('synthetic-log-secret')
    monkeypatch.setattr(diagnostics.LOGGER, 'error', broken)
    response = app.test_client().get('/test/failure')
    assert response.status_code == 500 and re.fullmatch('[0-9a-f]{24}', response.json['error_id'])
    assert 'synthetic-' not in response.get_data(as_text=True)


@pytest.mark.auth_database
def test_log_failure_preserves_business_rollback(auth_app, drafts, garment, monkeypatch):
    from core import admin_items
    from tests.test_admin_auth import query
    def fail_audit(*args, **kwargs):
        raise pymysql.OperationalError('synthetic-sql-secret')
    def fail_logging(*args, **kwargs):
        raise OSError('synthetic-log-secret')
    monkeypatch.setattr(admin_items, 'record_item_change', fail_audit)
    monkeypatch.setattr(diagnostics.LOGGER, 'error', fail_logging)
    response = save(drafts, garment)
    assert response.status_code == 503 and response.json['error_id']
    assert query(auth_app, 'SELECT COUNT(*) AS n FROM fashion_item_profile')[0]['n'] == 0
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit WHERE action='item.profile.save'")[0]['n'] == 0


# 复用既有专属临时数据库夹具，不连接本地业务配置。
from tests.test_admin_items import drafts
from tests.test_fashion_profile import garment, save
