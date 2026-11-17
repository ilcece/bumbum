"""款式图片上传与资格核对后的共用图片读取。"""

from datetime import timedelta
import hashlib
import re

from flask import Response, current_app, g, jsonify, request
import pymysql

from core.admin_auth import lock_admin_session
from core.admin_queries import check_parameters, consistent_read, invalid
from core.catalog.audit import audit
from core.catalog.common import decoded, fail, locked, now, row
from core.db import get_database
from core.test_batches import lock_batch, source


def style_image(style_id, asset_id):
    from core.admin_media import encode_image, UploadFormDataParser
    from core.media_assets import MAX_FILE

    check_parameters(set())
    if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
        invalid("图片编号须为随机32位十六进制。")
    if request.method == "GET":
        with consistent_read() as cursor:
            image = row(
                cursor,
                "SELECT content FROM style_image WHERE style_id=%s AND asset_id=%s",
                (style_id, asset_id),
            )
            if not image:
                fail("图片不存在。", 404, "not_found")
        response = Response(image["content"], mimetype="image/webp")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    # 小规模共用图片随数据库一起备份；规模增大时迁回文件存储，不能公开数据URL。
    if current_app.config.get("MEDIA_ENABLED") is not True:
        fail("图片上传未启用。", 503, "service_unavailable")
    request.max_content_length = 9 * 1024**2
    request.max_form_parts = 1
    request.max_form_memory_size = 64 * 1024
    request.form_data_parser_class = UploadFormDataParser
    if set(request.files) != {"file"} or len(request.files.getlist("file")) != 1 or request.form:
        invalid("仅接受一个图片文件。")
    raw = request.files["file"].stream.read(MAX_FILE + 1)
    if not raw or len(raw) > MAX_FILE:
        invalid("单张图片最多8MiB。")
    digest = hashlib.sha256(raw).hexdigest()
    encoded, _ = encode_image(raw)
    connection = get_database()
    with connection.cursor() as guard:
        guard.execute("SELECT GET_LOCK(CONCAT(DATABASE(),':media-admission'),0)")
        if guard.fetchone()[0] != 1:
            fail("另一张图片正在处理，请稍后明确重试。", 409, "media_busy")
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            locked(cursor, "product_style", style_id)
            lock_batch(cursor, source(cursor, "style", style_id))
            found = row(
                cursor,
                "SELECT asset_id,style_id,source_sha256,expires_at FROM style_image WHERE asset_id=%s FOR UPDATE",
                (asset_id,),
            )
            if found:
                if found["expires_at"] and found["expires_at"] <= now():
                    fail("暂存已过期，请放弃本次上传后重新选择。")
                if found["style_id"] != style_id or found["source_sha256"] != digest:
                    fail("图片请求编号已被其他上传使用。")
            else:
                cursor.execute(
                    "DELETE FROM style_image WHERE style_id=%s AND expires_at<%s", (style_id, now())
                )
                count = row(
                    cursor, "SELECT COUNT(*) AS n FROM style_image WHERE style_id=%s", (style_id,)
                )["n"]
                if count >= 100:
                    fail("本款已上传图片达到100张，请先核对资料。")
                cap = current_app.config.get("MEDIA_MAX_TOTAL_BYTES")
                size = row(
                    cursor, "SELECT COALESCE(SUM(OCTET_LENGTH(content)),0) AS n FROM style_image"
                )["n"]
                file_size = row(
                    cursor,
                    "SELECT COALESCE(SUM(GREATEST(byte_size,reserved_bytes)),0) AS n FROM media_asset",
                )["n"]
                if type(cap) is not int or int(size) + int(file_size) + len(encoded) > cap:
                    fail("图片容量不足，未接收新图片。", 409, "media_quota_exceeded")
                cursor.execute(
                    "INSERT INTO style_image(asset_id,style_id,created_by,source_sha256,content,expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        asset_id,
                        style_id,
                        g.admin_session["admin_id"],
                        digest,
                        encoded,
                        now() + timedelta(hours=24),
                    ),
                )
                audit(cursor, "image.upload", style_id, {"asset_id": asset_id})
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        with connection.cursor() as guard:
            guard.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(),':media-admission'))")
    return jsonify(
        status="ok", data={"url": f"/api/admin/catalog/styles/{style_id}/images/{asset_id}"}
    )


def shared_image(cursor, item_id, asset_id):
    found = row(
        cursor,
        "SELECT s.image_urls,a.content FROM digital_item d JOIN product_issue r ON r.id=d.issue_id JOIN product_style s ON s.id=r.style_id JOIN style_image a ON a.style_id=s.id WHERE d.item_id=%s AND a.asset_id=%s",
        (item_id, asset_id),
    )
    if not found or not any(
        url.endswith("/images/" + asset_id) for url in decoded(found["image_urls"])
    ):
        fail("该图片不属于当前物品的已保存共用资料。", 404, "not_found")
    return {"content": found["content"]}


def style_image_status(style_id, asset_id):
    check_parameters(set())
    with consistent_read() as cursor:
        found = row(
            cursor,
            "SELECT asset_id FROM style_image WHERE style_id=%s AND asset_id=%s",
            (style_id, asset_id),
        )
        if not found:
            fail("尚无已提交上传记录。", 404, "not_found")
    return jsonify(
        status="ok", data={"url": f"/api/admin/catalog/styles/{style_id}/images/{asset_id}"}
    )
