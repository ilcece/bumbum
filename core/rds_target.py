"""杭州生产与测试的明确目标，防止脚本串库；不保存账号密码。"""

RDS_HOST = "rm-cn-ofv50a5zs00014.rwlb.rds.aliyuncs.com"
SLOTS = {
    "test": {"database": "bumbum_hz_test", "user": "bumbum_hz_test", "port": 15001},
    "production": {"database": "bumbum_hz_production", "user": "bumbum_hz_production", "port": 15000},
}


def validate_target(config, *, initialization=False):
    """同时匹配地域端点、环境、库和专用身份；初始化账号与应用分开。"""
    slot = config.get("HANGZHOU_SLOT")
    if slot not in SLOTS:
        raise ValueError("HANGZHOU_SLOT必须明确为test或production。")
    target = SLOTS[slot]
    expected_user = target["user"] + ("_init" if initialization else "")
    expected = {
        "APP_ENV": "production", "DB_HOST": RDS_HOST, "DB_PORT": 3306,
        "DB_NAME": target["database"], "DB_USER": expected_user,
        "DB_SSL_MODE": "VERIFY_IDENTITY",
    }
    if any(config.get(name) != value for name, value in expected.items()):
        raise ValueError("杭州环境、端点、库、身份或TLS配置不匹配；未连接或修改其他目标。")
    return target
