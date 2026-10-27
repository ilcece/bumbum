#!/usr/bin/env bash
# 香港Ubuntu云测试专用；只操作本项目，不清空服务、不删除数据库卷。
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
if [[ ! -f .env.cloud-test ]]; then
    echo '请先按云测试手册准备配置；没有修改本机.env。' >&2
    exit 1
fi
# 明确只用当前机器和独立配置文件，避免终端里旧的同名变量覆盖云测试配置。
docker_local=(env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH
    -u DB_USER -u DB_PASSWORD -u CLOUD_DB_ROOT_PASSWORD -u STORAGE_ENCRYPTION_KEY
    -u IP_HASH_KEY -u WEBHOOK_ADMIN_USERNAME -u WEBHOOK_SHARED_SECRET
    -u MASTER_KEY_FASHION -u MASTER_KEY_JEWELRY -u SDM_META_KEY_V1 -u SDM_META_KEY_VERSION -u TAP_VERIFY_PER_MINUTE
    docker --host=unix:///var/run/docker.sock)
compose=("${docker_local[@]}" compose --env-file .env.cloud-test -f deploy/cloud_test/compose.yaml)
# 同名项目若来自另一个目录，先停下核对，不接管其服务。
task_containers="$("${docker_local[@]}" ps -aq --filter label=com.docker.compose.project=bumbum-cloud-test)"
while IFS= read -r task_container; do
    [[ -z "$task_container" ]] && continue
    task_files="$("${docker_local[@]}" inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$task_container")"
    if [[ "$task_files" != "$task_root/deploy/cloud_test/compose.yaml" ]]; then
        echo '发现来自其他目录的同名云测试项目，未接管；请先让AI核对配置和数据归属。' >&2
        exit 1
    fi
done <<< "$task_containers"
case "${1:-status}" in
    start)
        python3 scripts/setup_cloud_test.py --prepare-build-ca
        "${compose[@]}" up -d --build --wait --wait-timeout 120
        echo '后端与测试库已就绪；还需按手册配置网页和HTTPS。'
        ;;
    stop)
        "${compose[@]}" stop
        echo '本项目后端和数据库已停止，配置与数据保留；Nginx及其他项目不受影响。'
        ;;
    status) "${compose[@]}" ps ;;
    logs) "${compose[@]}" logs --tail=80 backend ;;
    upgrade-source)
        # 先构建成功再暂停服务；备份或升级失败时不继续启动，保留原数据供排查。
        python3 scripts/setup_cloud_test.py --prepare-build-ca
        "${compose[@]}" build backend
        "${compose[@]}" up -d --wait --wait-timeout 120 db
        "${compose[@]}" stop backend
        bash "$task_root/scripts/cloud_test.sh" backup
        "${compose[@]}" run --rm --no-deps -T backend python -m core.registration_migration --apply-after-backup
        "${compose[@]}" up -d --no-build --wait --wait-timeout 120 backend
        echo '来源升级及后端启动完成；请执行publish-page更新网页，再核对原账号和芯片。'
        ;;
    upgrade-tap)
        # 先构建成功再暂停服务；备份或升级失败时不继续启动，保留原数据供排查。
        python3 scripts/setup_cloud_test.py --prepare-build-ca
        "${compose[@]}" build backend
        "${compose[@]}" up -d --wait --wait-timeout 120 db
        "${compose[@]}" stop backend
        bash "$task_root/scripts/cloud_test.sh" backup
        "${compose[@]}" run --rm --no-deps -T backend python -m core.tap_migration --apply-after-backup
        "${compose[@]}" up -d --no-build --wait --wait-timeout 120 backend
        echo '触碰日志升级及后端启动完成；原公开路由保持关闭，后续另行部署用户入口。'
        ;;
    upgrade-view)
        # 先构建成功再暂停服务；备份或升级失败时不继续启动，保留原数据供排查。
        python3 scripts/setup_cloud_test.py --prepare-build-ca
        "${compose[@]}" build backend
        "${compose[@]}" up -d --wait --wait-timeout 120 db
        "${compose[@]}" stop backend
        bash "$task_root/scripts/cloud_test.sh" backup
        "${compose[@]}" run --rm --no-deps -T backend python -m core.tap_migration --apply-after-backup
        "${compose[@]}" run --rm --no-deps -T backend python -m core.view_migration --apply-after-backup
        "${compose[@]}" up -d --no-build --wait --wait-timeout 120 backend
        echo '触碰日志和持续查看资格升级完成；用户页面发布及Nginx仍需按手册执行，未自动公开管理入口。'
        ;;
    admin)
        shift
        "${compose[@]}" exec backend python -m flask --app app:create_app admin "$@"
        ;;
    publish-page)
        install -d -m 0755 /var/www/bumbum-cloud-test
        "${compose[@]}" cp backend:/app/frontend-dist/. /var/www/bumbum-cloud-test/
        chmod -R a+rX /var/www/bumbum-cloud-test
        echo '本项目测试网页已更新；没有修改其他网站目录。'
        ;;
    publish-user-page)
        install -d -m 0755 /var/www/bumbum-user-test
        "${compose[@]}" cp backend:/app/frontend-user-dist/. /var/www/bumbum-user-test/
        chmod -R a+rX /var/www/bumbum-user-test
        echo '手机用户静态页已发布到独立目录；没有修改管理页或Nginx，HTTPS及公开入口另按手册配置。'
        ;;
    export-qr)
        task_qr="${2:-}"
        if [[ ! "$task_qr" =~ ^/tmp/bumbum-authenticator-[A-Za-z0-9_-]+/authenticator\.html$ ]] || [[ -e .cloud-test/authenticator.html ]]; then
            echo '请提供本次设置终端显示的完整临时路径；已有导出文件时先按手册清理。' >&2
            exit 1
        fi
        umask 077
        # /tmp是容器内存盘，docker cp可能看不到；从运行中的容器读取，直接写入受限文件。
        task_export="$(mktemp .cloud-test/authenticator-XXXXXXXX.tmp)"
        trap 'rm -f -- "$task_export"' EXIT
        if ! "${compose[@]}" exec -T backend cat -- "$task_qr" >"$task_export" || [[ ! -s "$task_export" ]]; then
            echo '导出未完成：临时页面不可读取。请确认原设置终端仍在等待，并使用本次完整路径；设置已结束时重新创建并使用新路径。' >&2
            exit 1
        fi
        # 原子创建且不覆盖已有文件；文件内容不经过终端，也不进入日志。
        if ! ln -- "$task_export" .cloud-test/authenticator.html; then
            echo '已有导出文件，未覆盖；请先按手册清理旧副本。' >&2
            exit 1
        fi
        echo '二维码已安全导出到.cloud-test/authenticator.html；只下载到自己的电脑，完成后删除两边副本。'
        ;;
    backup)
        umask 077
        mkdir -p .cloud-test/backups
        task_backup="$(mktemp .cloud-test/backups/database-XXXXXXXX.sql)"
        if "${compose[@]}" exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --user="$MYSQL_USER" --single-transaction --no-tablespaces --skip-lock-tables --databases "$MYSQL_DATABASE"' >"$task_backup" && tail -c 512 "$task_backup" | grep -q -- '-- Dump completed on'; then
            echo "完整测试库备份已保存：$task_backup；包含账号秘密，请勿分享。"
        else
            rm -f -- "$task_backup"
            echo '备份未完成；已移除本次不完整文件，原库和旧备份保留。' >&2
            exit 1
        fi
        ;;
    *) echo '可用操作：start、stop、status、logs、upgrade-source、upgrade-tap、upgrade-view、admin、publish-page、publish-user-page、export-qr、backup。' >&2; exit 1 ;;
esac
