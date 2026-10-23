"""把WTForms的CSRF接口适配到现有数据库会话，不增加签名密钥。"""

import hmac
import re

from werkzeug.datastructures import MultiDict
from wtforms import Form
from wtforms.csrf.core import CSRF
from wtforms.validators import ValidationError


class DatabaseSessionCSRF(CSRF):
    def setup_form(self, form):
        self.expected = form.meta.csrf_context
        return super().setup_form(form)

    def generate_csrf_token(self, csrf_token_field):
        # 口令在登录时生成并保存；读取会话不换口令，多个标签页可共用。
        return self.expected

    def validate_csrf_token(self, form, field):
        supplied = field.data
        if not isinstance(supplied, str) or not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(self.expected, supplied):
            raise ValidationError("防冒用口令不正确。")


class SessionForm(Form):
    class Meta:
        csrf = True
        csrf_class = DatabaseSessionCSRF


def valid_csrf(expected, supplied):
    form = SessionForm(MultiDict({"csrf_token": supplied or ""}), meta={"csrf_context": expected})
    return form.validate()
