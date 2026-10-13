# 版本核对与锁定

2026-10-13（北京时间）实施时核对 npm 官方 registry 元数据与 lockfile；镜像经 Docker 官方仓库实际拉取并校验 digest。没有使用 latest。锁文件含每个包的integrity，构建 `npm ci`；离线cache同样按integrity校验，不关闭TLS/校验和。所有基础镜像为多平台manifest digest，当前实例实际验证linux/amd64；ARM部署需匹配架构重新测试。

| 组件 | 锁定版本 | 验证 |
|---|---|---|
| Node | 24.19.0-bookworm-slim | 运行/镜像构建通过 |
| Express | 5.3.0 | 登录/API/浏览器通过 |
| mysql2 | 3.24.5 | MySQL8.0事务与严格TLS主机名校验 |
| Zod | 4.6.7 | 严格字段白名单与校验 |
| TypeScript | 7.0.2 | 编译通过 |
| tsx | 4.23.15 | 集成测试执行 |
| Playwright | 1.64.0 | 使用系统Chromium执行 |
| MySQL（仅隔离开发） | 8.0.45 | 真数据库测试 |
| Caddy | 2.11.2-alpine | 配置验证、容器代理 |

镜像完整锁定值：

- Node：`sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df`
- Caddy：`sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d`
- MySQL：`sha256:4af1f8815716546f5b12410f7621f37f93db8dd11a184706ef59111930b8c2ff`
- Dockerfile frontend：`sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e`

核对方式：`npm view 包名@版本 version`、`npm ls --depth=0`、`npm audit`、`docker image inspect 镜像 --format '{{json .RepoDigests}}'`。lockfile为实际安装结果。当前npm audit（全量及生产依赖）均0已知漏洞，此结果仅代表检测时数据库，不保证以后没有漏洞。

来源：<https://registry.npmjs.org/>、<https://hub.docker.com/_/node>、<https://hub.docker.com/_/mysql>、<https://hub.docker.com/_/caddy>、<https://github.com/sidorares/node-mysql2>（驱动源码核对 `ssl.verifyIdentity` / `rejectUnauthorized`）、<https://docs.docker.com/reference/compose-file/services/#env_file>。

以后升级需要同时核对兼容性、更新精确版本和lockfile/镜像digest，在隔离数据库重跑测试。不要只改tag或期望checksum。
