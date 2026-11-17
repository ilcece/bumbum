---
doc_type: archive
status: archived
date: 2026-11-09
reason: 集中索引已归档的方案、手册和复盘
---

# 历史归档

这里查原提案、历史验收和复盘。判断现行规则从 [产品导航](../../PRD.md) 开始；执行部署、恢复或日常操作从 [操作手册](../OP_GUIDE.md) 开始。

<a id="admin-history"></a>

## 旧后台提案与原型

| 原主题 | 历史原文 |
|---|---|
| Make 管理后台重构 | [原稿](admin-make-rebuild-2026-11-05.md) |
| A：维护与查询 | [原稿及 S01–S30](admin-management-update-2026-11-05.md) |
| A：改版技术 | [原稿](admin-management-implementation-2026-11-05.md) |
| 通用销售与交付 | [原稿及旧原型证据](initial-sale-delivery-2026-11-05.md) |
| B：验证识别与清理 | [原稿](production-validation-cleanup-2026-11-05.md) |
| C：建档与绑定纠错 | [原稿](chip-correction-2026-11-05.md) |
| D：挂失、换新与转售 | [原稿](replacement-resale-2026-11-05.md) |

旧 FigJam、Make 和整月经营原型作为历史设计材料，实际版本和验收记录按 [变更历史](../../CHANGELOG.md) 查阅。

2026年11月17日把已实现规则纳入现行规范，整理前的批准方案原文保留如下。归档日期是本次文档收口日期，不是原方案批准或人工验收日期。

| 整理前方案快照 | 当前承接位置 |
|---|---|
| [后台重构主方案](admin-make-rebuild-2026-11-17.md) | [数字档案](../product/digital-catalog.md)；[未决政策](../proposals/admin-make-rebuild.md)单独保留 |
| [业务字段表](admin-rebuild-fields-2026-11-17.md) | [现行业务字段](../product/admin-fields.md) |
| [用户H5方案](digital-item-h5-mvp-2026-11-17.md) | [用户H5规范](../product/user-h5.md) |
| [装配与H5增量技术方案](digital-item-assembly-h5-technical-2026-11-17.md) | [技术附录第19节](../IMPLEMENTATION_DETAILS.md#19-数字档案装配与-h5-实现约束)及现行API |
| [Umi工程迁移说明](admin-rebuild-implementation-2026-11-17.md) | [前端协作](../FRONTEND_COLLABORATION.md)及[技术附录第19节](../IMPLEMENTATION_DETAILS.md#19-数字档案装配与-h5-实现约束) |
| [原Vite后台接入约束](admin-vite-integration-2026-11-17.md) | [前端协作](../FRONTEND_COLLABORATION.md)；原技术附录第10节保留当前入口 |

旧 `docs/proposals/digital-item-h5-mvp.md` 已归档。需要核对该原路径时，可查看[整理前的固定历史版本](https://github.com/ilcece/bumbum/blob/0721c0e6b91a1937250272a3f03cbf1e4ffa9f4c/docs/proposals/digital-item-h5-mvp.md)；当前产品规则使用上表的[用户H5规范](../product/user-h5.md)，不以旧版本覆盖现行决定。


## 已结束的产品探索

- [旧祈愿 H5 PRD](nfc-prayer-h5.md)，包含每日一签等早期设计。
- [旧饰品成长候选](legacy-growth-candidate.md)，包含成长、任务和奖励的早期提案。
- 当前手串问题与待验证方向从 [手串探索](../BRACELET_NFC_EXPLORATION.md) 查阅。

<a id="ops-history"></a>

## 历史运维与协作

- [香港云测试手册](cloud-test-deployment.md)，记录原云测试环境、手机页部署及恢复过程。
- [项目优先级与过度工程化复盘](project-priority-review.md)，保存早期协作选择和纠正依据。
