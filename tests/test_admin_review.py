"""原型审查整改的业务回归：自由编号、事实时间和候选资格。"""
from datetime import timedelta
import pytest
from tests.test_admin_catalog import catalog, action, ok, owner
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in

pytestmark=pytest.mark.auth_database


def test_free_identifier_keeps_global_uniqueness_and_basic_limits(auth_app,catalog):
    s,_,issue,_,_=catalog
    created=ok(action(s,'item',{'issue_id':issue,'item_uid':' 自定义-款式a/第二件 ','edition_number':2}))
    assert query(auth_app,'SELECT item_uid FROM item WHERE id=%s',(created['id'],))[0]['item_uid']=='自定义-款式a/第二件'
    assert action(s,'item',{'issue_id':issue,'item_uid':'自定义-款式a/第二件','edition_number':3}).status_code==409
    for uid in ('',' '*5,'x'*33):
        assert action(s,'item',{'issue_id':issue,'item_uid':uid,'edition_number':3}).status_code==400
    assert s[0].get(f'/api/admin/catalog/issues/{issue}').json['data']['suggested_edition_number']==3


def test_sales_use_evidenced_time_and_never_rewrite_first_fact(auth_app,catalog):
    s,_,_,i,_=catalog
    at=(auth_app.test_clock[0]-timedelta(days=3)).isoformat()+'Z'
    p={'item_id':i,'confirmed':True,'evidence':'核对外部真实成交时刻','first_sold_at':at}
    ok(action(s,'sale',p))
    first=query(auth_app,'SELECT first_sold_at FROM digital_item WHERE item_id=%s',(i,))[0]['first_sold_at']
    assert first==auth_app.test_clock[0]-timedelta(days=3)
    assert action(s,'sale',{**p,'first_sold_at':auth_app.test_clock[0].isoformat()+'Z'}).status_code==409
    ok(action(s,'sale',{'item_id':i,'confirmed':False,'evidence':'仅撤销售出标记'}))
    ok(action(s,'sale',{'item_id':i,'confirmed':True,'evidence':'重新确认原有成交'}))
    assert query(auth_app,'SELECT first_sold_at FROM digital_item WHERE item_id=%s',(i,))[0]['first_sold_at']==first
    audit=query(auth_app,"SELECT created_at,detail FROM admin_audit WHERE action='catalog.sale' ORDER BY id LIMIT 1")[0]
    assert audit['created_at']>first


@pytest.mark.parametrize('offset',[timedelta(seconds=1),timedelta(days=1)])
def test_future_sales_roll_back_without_changing_facts(auth_app,catalog,offset):
    s,_,_,i,_=catalog
    result=action(s,'sale',{'item_id':i,'confirmed':True,'evidence':'不可伪造未来成交','first_sold_at':(auth_app.test_clock[0]+offset).isoformat()+'Z'})
    assert result.status_code==400
    assert not query(auth_app,'SELECT sold,first_sold_at FROM digital_item WHERE item_id=%s',(i,))[0]['sold']


def test_eligible_candidates_and_optional_spec_keep_protection(auth_app,catalog):
    s,style,issue,i,chips=catalog
    uid=owner(auth_app,i,91)
    other=owner(auth_app,None,92)
    rows=s[0].get('/api/admin/catalog/users',query_string={'exclude_id':uid}).json['data']['items']
    assert uid not in {x['id'] for x in rows} and other in {x['id'] for x in rows}
    jewelry=query(auth_app,"SELECT id FROM project WHERE code='jewelry'")[0]['id']
    query(auth_app,'UPDATE chip SET project_id=%s WHERE id=%s',(jewelry,chips[1]))
    candidates=s[0].get('/api/admin/catalog/chips?available=true&compatible_project=fashion').json['data']['items']
    assert chips[0] in {x['id'] for x in candidates} and chips[1] not in {x['id'] for x in candidates}
    ok(action(s,'bind',{'item_id':i,'chip_id':chips[0]}))
    assert query(auth_app,'SELECT spec FROM whole_item WHERE item_id=%s',(i,))[0]['spec']==''
    assert i not in {x['id'] for x in s[0].get('/api/admin/catalog/items?bindable=true').json['data']['items']}
    assert action(s,'bind',{'item_id':i,'chip_id':chips[1]}).status_code==409
    st=s[0].get(f'/api/admin/catalog/styles/{style}').json['data']
    assert st['item_count']==1 and st['active_item_count']==0
