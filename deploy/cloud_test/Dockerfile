# syntax=docker/dockerfile:1
# 固定构建版本，香港ECS不需要替换Ubuntu自带的Python或安装Node。
FROM node:24.19.0-bookworm-slim AS frontend
WORKDIR /src
COPY frontend/admin/package.json frontend/admin/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca,required=true NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --strict-ssl=true
COPY frontend/admin/ ./
RUN npm run build

# 用户页独立构建及导出，不覆盖管理页的入口和资源。
FROM node:24.19.0-bookworm-slim AS user_frontend
WORKDIR /user-src
COPY frontend/user/package.json frontend/user/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca,required=true NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --strict-ssl=true
COPY frontend/user/ ./
RUN npm run build

FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-deploy.txt ./
RUN --mount=type=secret,id=proxy_ca,required=true PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements-deploy.txt
COPY app.py ./
COPY core/ ./core/
COPY db/ ./db/
COPY --from=frontend /src/dist/ ./frontend-dist/
COPY --from=user_frontend /user-src/dist/ ./frontend-user-dist/
RUN chmod -R a+rX /app && groupadd --gid 10001 bumbum && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin bumbum && mkdir /app/logs && chown 10001:10001 /app/logs
USER bumbum:bumbum
# 仅监听本机；关闭当前未使用的控制socket，避免向只读主目录写文件。
CMD ["gunicorn", "--no-control-socket", "--bind", "127.0.0.1:15000", "--workers", "2", "--worker-tmp-dir", "/tmp", "--timeout", "30", "app:create_app()"]
