#!/bin/sh
# 证书成功续期后检查并重载网站入口；不重启数据库或后端。
set -eu
nginx -t
systemctl reload nginx
