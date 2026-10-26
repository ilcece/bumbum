"""在独立临时MySQL验证物品草稿、唯一性、权限和原子保存。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier

import pymysql
import pyotp
import pytest
from werkzeug.security import generate_password_hash

from core import admin_items
from core.db import get_database
from core.secret_storage import encrypt_totp_secret
from tests.test_admin_auth import ORIGIN, login, query

pytestmark = pytest.mark.auth_database
UID = "FASH-2026-000001"


@pytest.mark.parametrize("project,prefix", [("fashion","FASH"),("jewelry","JEW")])
@pytest.mark.parametrize("chip_status", ["bound","disabled","lost"])
def test_unbound_filter_excludes_all_occupied_states(auth_app, drafts, project, prefix, chip_status):
    client, _ = drafts
    for n in (1,2):
        query(auth_app,"INSERT INTO item(project_id,item_uid) SELECT id,%s FROM project WHERE code=%s",(f'{prefix}-2026-{n:06d}',project))
    occupied = query(auth_app,"SELECT * FROM item WHERE item_uid=%s",(f'{prefix}-2026-000002',))[0]
    query(auth_app,"INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES (%s,%s,%s,%s)",('04:00:00:00:00:00:DD',occupied['project_id'],occupied['id'],chip_status))
    assert client.get('/api/admin/items',query_string={'project':project}).json['data']['total']==2
    assert client.get('/api/admin/items?unbound_only=false').json['data']['total']==2
    data=client.get('/api/admin/items',query_string={'project':project,'unbound_only':'true'}).json['data']
    assert data['total']==1 and [row['item_uid'] for row in data['items']]==[f'{prefix}-2026-000001']
    assert client.get('/api/admin/items',query_string={'keyword':occupied['item_uid'],'unbound_only':'true'}).json['data']['total']==0


def test_unbound_filter_counts_before_pagination_and_preserves_other_filters(auth_app, drafts):
    client,_=drafts
    for n in range(1,26):
        query(auth_app,"INSERT INTO item(project_id,item_uid,sku_code,status) SELECT id,%s,%s,%s FROM project WHERE code='fashion'",(f'FASH-2026-{n:06d}','FILTER-SKU','archived' if n==1 else 'draft'))
    for n in (23,24,25):
        row=query(auth_app,'SELECT * FROM item WHERE item_uid=%s',(f'FASH-2026-{n:06d}',))[0]
        query(auth_app,"INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES (%s,%s,%s,'bound')",(f'04:00:00:00:00:00:{n:02X}',row['project_id'],row['id']))
    first=client.get('/api/admin/items?unbound_only=true&project=fashion&keyword=FILTER-SKU').json['data']
    second=client.get('/api/admin/items?unbound_only=true&page=2').json['data']
    assert first['total']==second['total']==22 and len(first['items'])==20 and len(second['items'])==2
    assert first['items'][0]['item_uid']=='FASH-2026-000022'
    assert client.get('/api/admin/items?unbound_only=true&status=draft').json['data']['total']==21
    assert client.get('/api/admin/items?unbound_only=true&status=archived').json['data']['total']==1
    assert client.get('/api/admin/items?unbound_only=true&page=3').json['data']['items']==[]
    assert client.get('/api/admin/items').json['data']['total']==25


@pytest.mark.parametrize("parameters", ['unbound_only=1','unbound_only=TRUE','unbound_only=','unbound_only=null','unbound_only=true&unbound_only=false'])
def test_unbound_filter_strict_values(drafts,parameters):
    response=drafts[0].get('/api/admin/items?'+parameters)
    assert response.status_code==400 and response.json['code']=='invalid_param'


@pytest.fixture
def drafts(auth_app, admin_account):
    # 此连接由auth_app专属临时库提供，不使用本机或香港业务库。
    for table in ("fashion_item_profile", "jewelry_item_profile", "item"):
        query(auth_app, f"DELETE FROM {table}")
    client = auth_app.test_client()
    assert login(client, auth_app, admin_account).status_code == 200
    headers = {**ORIGIN, "X-CSRF-Token": client.get("/api/admin/auth/session").json["data"]["csrf_token"]}
    return client, headers


def create(drafts, **changes):
    client, headers = drafts
    return client.post("/api/admin/items", headers=headers, json={"project": "fashion", "item_uid": UID, **changes})


@pytest.mark.parametrize("project,uid", [("fashion", UID), ("jewelry", "JEW-0000-000000")])
def test_create_real_draft_and_audit_without_profile(auth_app, drafts, admin_account, project, uid):
    response = create(drafts, project=project, item_uid=" " + uid + " ", sku_code=" 款式甲 ")
    assert response.status_code == 200
    item = response.json["data"]
    assert item["project"] == project and item["item_uid"] == uid
    assert item["status"] == "draft" and item["sku_code"] == "款式甲" and item["profile"] is None
    assert item["created_at"].endswith("Z") and item["updated_at"].endswith("Z")
    assert response.headers["Cache-Control"] == "no-store"
    for table in ("fashion_item_profile", "jewelry_item_profile"):
        assert query(auth_app, f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] == 0
    audit = query(auth_app, "SELECT * FROM admin_audit")[0]
    assert audit["action"] == "item.create" and audit["target_type"] == "item"
    assert audit["target_id"] == str(item["id"]) and audit["admin_id"] == admin_account["id"]
    assert json.loads(audit["detail"]) == {"project": project} and len(audit["ip_hash"]) == 64
    assert drafts[0].get("/api/admin/items").json["data"]["items"] == [item]


@pytest.mark.parametrize("sku", [None, "", "   ", "a" * 64])
def test_optional_sku_normalization_and_reuse(auth_app, drafts, sku):
    assert create(drafts, sku_code=sku).json["data"]["sku_code"] == (sku.strip() or None if sku is not None else None)
    assert create(drafts, item_uid="FASH-2026-000002", sku_code=sku).status_code == 200


@pytest.mark.parametrize("changes", [
    {"project": None}, {"project": "unassigned"}, {"project": []}, {"item_uid": None},
    {"item_uid": "fash-2026-000001"}, {"item_uid": "FASH-026-000001"},
    {"item_uid": "FASH-2026-00001"}, {"item_uid": "FASH-２０２６-000001"},
    {"item_uid": "FASH-2026-٠٠٠٠٠١"}, {"item_uid": "JEW-2026-000001"},
    {"item_uid": "FASH-2026-000001\nx"}, {"sku_code": "a" * 65}, {"sku_code": 42},
    {"status": "active"}, {"status": None}, {"profile": None}, {"chip_id": 1},
])
def test_invalid_create_never_writes(auth_app, drafts, changes):
    response = create(drafts, **changes)
    assert response.status_code == 400 and response.json["code"] == "invalid_param"
    assert query(auth_app, "SELECT COUNT(*) AS n FROM item")[0]["n"] == 0
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == 0


def test_duplicate_does_not_overwrite_and_unique_index_is_global(auth_app, drafts):
    assert create(drafts, sku_code="原款式").status_code == 200
    before = query(auth_app, "SELECT * FROM item")[0]
    repeat = create(drafts, sku_code="另一个款式")
    assert repeat.status_code == 409 and repeat.json["code"] == "already_exists"
    assert query(auth_app, "SELECT * FROM item")[0] == before
    assert len(query(auth_app, "SELECT * FROM admin_audit")) == 1
    with pytest.raises(pymysql.IntegrityError):
        query(auth_app, "INSERT INTO item(project_id,item_uid) SELECT id,%s FROM project WHERE code='jewelry'", (UID,))


def test_list_filters_pagination_sort_empty_and_literal_wildcards(auth_app, drafts):
    ids = []
    for n in range(23):
        ids.append(create(drafts, item_uid=f"FASH-2026-{n:06d}", sku_code="款式%_!" if n == 0 else "共同款式").json["data"]["id"])
    assert create(drafts, project="jewelry", item_uid="JEW-2026-000001").status_code == 200
    client = drafts[0]
    result = client.get("/api/admin/items").json["data"]
    assert result["total"] == 24 and len(result["items"]) == 20 and result["page_size"] == 20
    assert [r["id"] for r in result["items"]] == sorted([r["id"] for r in result["items"]], reverse=True)
    assert len(client.get("/api/admin/items?page=2").json["data"]["items"]) == 4
    empty = client.get("/api/admin/items?page=10").json["data"]
    assert empty["items"] == [] and empty["total"] == 24
    assert client.get("/api/admin/items?project=jewelry&status=draft").json["data"]["total"] == 1
    assert client.get("/api/admin/items?status=archived").json["data"]["total"] == 0
    assert client.get("/api/admin/items", query_string={"keyword": "%_!"}).json["data"]["total"] == 1
    assert client.get("/api/admin/items?keyword=共同").json["data"]["total"] == 22
    assert client.get("/api/admin/items?keyword=2026-000022").json["data"]["items"][0]["id"] == ids[-1]
    assert len(query(auth_app, "SELECT * FROM admin_audit")) == 24


@pytest.mark.parametrize("parameters", ["page=0", "page=2147483648", "page=１", "page_size=101", "page=1&page=2", "project=unassigned", "status=unknown", "extra=1", "keyword=" + "a" * 129])
def test_invalid_list_uses_error_structure(drafts, parameters):
    result = drafts[0].get("/api/admin/items?" + parameters)
    assert result.status_code == 400
    assert set(result.json) == {"status", "code", "message"} and result.json["code"] == "invalid_param"


def test_existing_profiles_are_returned_without_internal_ids(auth_app, drafts):
    item = create(drafts).json["data"]
    query(auth_app, "INSERT INTO fashion_item_profile(item_id,name,image_urls,size_chart) VALUES (%s,'已有名称','[]','{}')", (item["id"],))
    profile = drafts[0].get("/api/admin/items").json["data"]["items"][0]["profile"]
    assert profile["name"] == "已有名称" and profile["image_urls"] == [] and profile["size_chart"] == {}
    assert not {"id", "item_id", "updated_at"} & set(profile)


@pytest.mark.parametrize("point", ["audit", "commit"])
def test_failure_rolls_back_item_and_audit(auth_app, drafts, monkeypatch, point):
    execute = pymysql.cursors.DictCursor.execute
    def fail_execute(cursor, sql, args=None):
        if sql.startswith("INSERT INTO admin_audit"):
            raise pymysql.OperationalError("合成审计失败")
        return execute(cursor, sql, args)
    def fail_commit(_connection):
        raise pymysql.OperationalError("合成提交失败")
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor, "execute", fail_execute) if point == "audit" else patch.setattr(pymysql.connections.Connection, "commit", fail_commit)
        assert create(drafts).status_code == 503
    assert query(auth_app, "SELECT COUNT(*) AS n FROM item")[0]["n"] == 0
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == 0
    assert create(drafts).status_code == 200


def test_permissions_origin_csrf_and_payload_limits(auth_app, drafts):
    client, headers = drafts
    assert auth_app.test_client().get("/api/admin/items").status_code == 401
    body = {"project": "fashion", "item_uid": UID}
    for changed, status in [({"Origin": "https://unknown.example"}, 403), ({"X-CSRF-Token": ""}, 403)]:
        assert client.post("/api/admin/items", json=body, headers={**headers, **changed}).status_code == status
    assert client.post("/api/admin/items?extra=1", json=body, headers=headers).status_code == 400
    assert client.post("/api/admin/items", data="x" * 9000, content_type="application/json", headers=headers).status_code == 400
    assert client.post("/api/admin/items", data=body, headers=headers).status_code == 400
    assert client.post("/api/admin/items", json={"project": "fashion"}, headers=headers).status_code == 400
    auth_app.test_clock[0] += timedelta(hours=9)
    assert create(drafts).status_code == 401
    assert query(auth_app, "SELECT COUNT(*) AS n FROM item")[0]["n"] == 0


def test_write_rechecks_permission_inside_transaction(auth_app, drafts, monkeypatch, admin_account):
    original = admin_items.lock_admin_session
    def revoke_then_check(cursor):
        query(auth_app, "UPDATE admin_user SET status='disabled' WHERE id=%s", (admin_account["id"],))
        original(cursor)
    monkeypatch.setattr(admin_items, "lock_admin_session", revoke_then_check)
    assert create(drafts).status_code == 401
    assert query(auth_app, "SELECT COUNT(*) AS n FROM item")[0]["n"] == 0


def test_different_admins_concurrently_create_one_item(auth_app, drafts, monkeypatch):
    second = {"username": "second-item-admin", "password": "test-only-second-password", "secret": pyotp.random_base32()}
    query(auth_app, "INSERT INTO admin_user(username,password_hash) VALUES (%s,%s)", (second["username"], generate_password_hash(second["password"])))
    admin_id = query(auth_app, "SELECT id FROM admin_user WHERE username=%s", (second["username"],))[0]["id"]
    with auth_app.app_context():
        encrypted = encrypt_totp_secret(second["secret"], admin_id)
    query(auth_app, "UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s WHERE id=%s", (encrypted, admin_id))
    client = auth_app.test_client()
    assert login(client, auth_app, second).status_code == 200
    second_drafts = (client, {**ORIGIN, "X-CSRF-Token": client.get("/api/admin/auth/session").json["data"]["csrf_token"]})
    barrier, original = Barrier(2), pymysql.cursors.DictCursor.execute
    def execute(cursor, sql, args=None):
        if sql.startswith("INSERT INTO item("):
            barrier.wait(timeout=10)
        return original(cursor, sql, args)
    monkeypatch.setattr(pymysql.cursors.DictCursor, "execute", execute)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, [drafts, second_drafts]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert len(query(auth_app, "SELECT * FROM item")) == len(query(auth_app, "SELECT * FROM admin_audit")) == 1
