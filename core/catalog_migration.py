"""数字档案006升级：停止管理写入、先备份，未知或部分结构拒绝猜测修复。"""
from pathlib import Path

TABLES={'product_style':{'id','project_id','code','name','specs','image_urls'},'style_image':{'asset_id','style_id','content','created_by','source_sha256'},'product_issue':{'id','style_id','mode','confirmed_at','sealed_at','ever_used'},'digital_item':{'item_id','issue_id','edition_number','sold','first_sold_at','is_validation','quota_year','quota_used','quota_review'},'whole_item':{'id','item_id','chip_id','generation','current_item_id','lost_at','loss_evidence'},'item_handover':{'id','item_id','source_id','target_id','chip_id','pending_item_id','pending_chip_id','owner_id','recipient_id'},'chip_validation':{'chip_id','is_validation'},'admin_operation':{'request_id','admin_id','action','payload_hash','result'}}

class CatalogMigrationError(Exception):
    """只输出阶段信息，不含连接秘密。"""


def catalog_schema(cursor):
    cursor.execute('SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')
    columns={}
    for table,column in cursor.fetchall():columns.setdefault(table,set()).add(column)
    present=set(TABLES)&set(columns)
    if not present:return 'missing'
    if present!=set(TABLES) or any(not required<=columns[name] for name,required in TABLES.items()):return 'unknown'
    cursor.execute("SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND COLUMN_NAME='chip_status'")
    if cursor.fetchone()!=("enum('pending','bound','disabled','lost','retired')",):return 'unknown'
    cursor.execute("SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND NON_UNIQUE=0 AND INDEX_NAME IN ('uk_whole_current','uk_whole_chip','uk_whole_generation','uk_digital_edition','uk_work_pending_item','uk_work_pending_chip') GROUP BY INDEX_NAME")
    if {r[0] for r in cursor.fetchall()}!={'uk_whole_current','uk_whole_chip','uk_whole_generation','uk_digital_edition','uk_work_pending_item','uk_work_pending_chip'}:return 'unknown'
    return 'ready'


def migrate(connection,backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.digital-catalog',5)")
        if cursor.fetchone()[0]!=1:raise CatalogMigrationError('另一个数字档案升级正在进行。')
        try:
            state=catalog_schema(cursor)
            if state=='ready':return False
            if state!='missing':raise CatalogMigrationError('存在部分或未知006结构，保留数据与备份，请让AI核对；没有删表重建。')
            cursor.execute('SELECT VERSION()')
            if not cursor.fetchone()[0].startswith('8.0.'):raise CatalogMigrationError('仅在MySQL 8.0验证此升级，未修改数据库。')
            connection.commit();backup()
            sql=(Path(__file__).resolve().parents[1]/'db/migrations/006_digital_catalog.sql').read_text()
            sql='\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
            for statement in sql.split(';'):
                if statement.strip():cursor.execute(statement)
            connection.commit()
            if catalog_schema(cursor)!='ready':raise CatalogMigrationError('006升级后识别失败，保留备份，不自动回滚DDL或覆盖后来数据。')
            return True
        finally:cursor.execute("SELECT RELEASE_LOCK('bumbum.digital-catalog')")
