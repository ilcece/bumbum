"""杭州测试短信使用阿里云官方 SDK 发码。"""

import json
import re


ALIYUN_SMS_SETTINGS = (
    'SMS_ALIYUN_ACCESS_KEY_ID',
    'SMS_ALIYUN_ACCESS_KEY_SECRET',
    'SMS_ALIYUN_SIGN_NAME',
    'SMS_ALIYUN_TEMPLATE_CODE',
    'SMS_ALIYUN_TEST_PHONE',
)
MAINLAND_PHONE = r'1[3-9][0-9]{9}'


def valid_settings(config):
    values = [config.get(name) for name in ALIYUN_SMS_SETTINGS]
    if not all(isinstance(value, str) and value.strip() == value and value
               and not any(char in value for char in '\r\n\0') for value in values):
        return False
    return bool(re.fullmatch(r'SMS_[0-9]+', config['SMS_ALIYUN_TEMPLATE_CODE'])
                and re.fullmatch(MAINLAND_PHONE, config['SMS_ALIYUN_TEST_PHONE']))


def send_aliyun_sms(config, phone, code):
    # 只在杭州测试路径加载 SDK，沿用其它环境的 HTTPS 网关。
    from alibabacloud_dysmsapi20170525.client import Client
    from alibabacloud_dysmsapi20170525.models import SendSmsRequest
    from alibabacloud_tea_openapi.utils_models import Config
    from darabonba.policy.retry import RetryOptions
    from darabonba.runtime import RuntimeOptions

    client = Client(Config(
        access_key_id=config['SMS_ALIYUN_ACCESS_KEY_ID'],
        access_key_secret=config['SMS_ALIYUN_ACCESS_KEY_SECRET'],
        endpoint='dysmsapi.aliyuncs.com',
        protocol='HTTPS',
        retry_options=RetryOptions(retryable=False),
    ))
    request = SendSmsRequest(
        phone_numbers=phone,
        sign_name=config['SMS_ALIYUN_SIGN_NAME'],
        template_code=config['SMS_ALIYUN_TEMPLATE_CODE'],
        template_param=json.dumps({'code': code}),
    )
    response = client.send_sms_with_options(request, RuntimeOptions(connect_timeout=2000, read_timeout=5000))
    return getattr(response.body, 'code', None) == 'OK'
