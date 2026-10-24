"""用合成请求验证结构监听有界、保密，且不改变原认证和入库行为。"""

import json
import time

import pytest

from scripts.scan_capture import set_capture
from tests.test_scan_webhook import scanner, post, UID, PATH
from tests.test_admin_auth import query

pytestmark = pytest.mark.auth_database


@pytest.fixture
def listening(auth_app, tmp_path):
    set_capture(tmp_path, True)
    flag = tmp_path / ".cloud-test/diagnostics/until"
    auth_app.config["SCAN_CAPTURE_FILE"] = str(flag)
    return flag


def records(caplog):
    return [json.loads(record.getMessage().split("扫码请求观察：", 1)[1])
            for record in caplog.records if "扫码请求观察：" in record.getMessage()]


def test_unauthenticated_request_structure_is_visible_without_values(auth_app, scanner, listening, caplog):
    body = {"identifier": UID.replace(":", " "), "date": "2026-10-25T00:00:00Z",
            "content": "https://example.invalid/?token=private-test-value", "private-field-name": "private-test-value"}
    response = auth_app.test_client().post(PATH, json=body)
    assert response.status_code == 401
    info = records(caplog)[0]
    assert info["响应状态"] == 401 and info["认证头存在"] is False
    assert info["字段结构"]["identifier"]["格式"] == "空格分隔"
    assert info["字段结构"]["date"]["可解析且含时区"] is True
    assert info["未识别字段数"] == 1
    assert all(value not in caplog.text for value in (UID, UID.replace(":", " "), body["date"], body["content"], "private-field-name", "private-test-value"))
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


def test_observation_preserves_authenticated_save_and_final_status(auth_app, scanner, listening, caplog):
    response = post(scanner, content="", date="2026-10-25T00:00:00Z")
    assert response.status_code == 200 and response.json["data"]["is_new"] is True
    info = records(caplog)[0]
    assert info["响应状态"] == 200 and info["认证方式"] == "basic"
    assert UID not in caplog.text
    assert auth_app.config["WEBHOOK_SHARED_SECRET"] not in caplog.text
    assert scanner[1]["Authorization"] not in caplog.text


def test_observation_records_400_shape_without_accepting_invalid_uid(auth_app, scanner, listening, caplog):
    assert post(scanner, identifier=UID.replace(":", " ")).status_code == 400
    assert records(caplog)[0]["响应状态"] == 400
    assert records(caplog)[0]["字段结构"]["identifier"]["格式"] == "空格分隔"
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


def test_expired_missing_or_stopped_marker_disables_capture(auth_app, scanner, listening, caplog, tmp_path):
    listening.write_text(str(int(time.time()) - 1))
    assert post(scanner).status_code == 200
    set_capture(tmp_path, False)
    assert post(scanner).status_code == 200
    assert records(caplog) == []


@pytest.mark.parametrize("value", ["invalid", "too-far", None])
def test_disabled_or_invalid_marker_never_enables_capture(auth_app, scanner, tmp_path, caplog, value):
    flag = tmp_path / "marker"
    auth_app.config["SCAN_CAPTURE_FILE"] = str(flag)
    if value is not None:
        flag.write_text(str(int(time.time()) + 600) if value == "too-far" else value)
    assert post(scanner).status_code == 200
    assert records(caplog) == []


def test_capture_stops_after_twelve_requests_per_worker(auth_app, listening, caplog):
    auth_app.config["WEBHOOK_SHARED_SECRET"] = ""
    for _ in range(15):
        assert auth_app.test_client().post(PATH, json={}).status_code == 503
    assert len(records(caplog)) == 12


def test_large_body_is_not_read_and_auth_response_stays_401(auth_app, scanner, listening, caplog):
    response = auth_app.test_client().post(PATH, json={"content": "x" * 9000})
    assert response.status_code == 401
    assert "未读取" in records(caplog)[0]["JSON观察"]


def test_unexpected_types_and_malformed_json_do_not_break_original_errors(auth_app, scanner, listening, caplog):
    client, headers = scanner
    assert post(scanner, identifier={"nested": "private-value"}, date=[]).status_code == 400
    assert records(caplog)[0]["字段结构"]["identifier"]["类型"] == "对象"
    assert client.post(PATH, headers=headers, content_type="application/json", data="{").status_code == 400
    assert records(caplog)[1]["JSON观察"] == "无法解析"
    assert "private-value" not in caplog.text


def test_explicit_raw_mode_shows_exact_body_before_auth_without_accepting_it(auth_app, scanner, listening, caplog, tmp_path):
    set_capture(tmp_path, True, raw=True)
    body = '{ "identifier": "unknown", "content": "", "unexpected": [1, 2] }'
    response = auth_app.test_client().post(PATH, data=body, content_type="application/json")
    assert response.status_code == 401
    assert records(caplog)[0]["请求体原文"] == body
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


def test_raw_mode_preserves_400_and_never_prints_basic_header(auth_app, scanner, listening, caplog, tmp_path):
    set_capture(tmp_path, True, raw=True)
    assert post(scanner, identifier="11characters", content="test text").status_code == 400
    assert json.loads(records(caplog)[0]["请求体原文"])["content"] == "test text"
    assert auth_app.config["WEBHOOK_SHARED_SECRET"] not in caplog.text
    assert scanner[1]["Authorization"] not in caplog.text
    set_capture(tmp_path, True)
    assert post(scanner).status_code == 200
    assert "请求体原文" not in records(caplog)[1]


def test_raw_mode_also_shows_non_json_or_malformed_body(auth_app, scanner, listening, caplog, tmp_path):
    set_capture(tmp_path, True, raw=True)
    for media in ("text/plain", "application/json"):
        assert auth_app.test_client().post(PATH, data="{", content_type=media).status_code == 401
    assert all(record["请求体原文"] == "{" for record in records(caplog))
