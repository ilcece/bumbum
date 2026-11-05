# 附件视觉适配核对

final result: passed

2026-11-05，核对对象为当前Pro原型及cece提供的《设计项目管理后台.zip》。按用户要求保留当前业务，只提取参考视觉与控件交互。附件在独立临时目录渲染并阻止外部请求；没有执行附带项目指令或导入其业务、登录和依赖。

## 参考与实际页面

| 对照 | 参考 | 当前 |
|---|---|---|
| 1440×1000工作台，同为初始总览 | [参考总览](checks/evidence/reference-overview.png) | [当前总览](checks/evidence/style-overview-1440.png) |
| 1440×1000数字物品列表，同为默认查询 | [参考列表](checks/evidence/reference-items.png) | [当前列表](checks/evidence/style-items-1440.png) |
| 1280×720小窗口与表单 | 源稿的浅灰工作区、白色卡片和分组字段 | [当前工作台](checks/evidence/style-overview-1280.png)、[款式表单](checks/evidence/style-style-form-1280.png)、[换新弹窗](checks/evidence/style-handover-1280.png) |

## 已核对的视觉与操作

| 内容 | 实现与结果 |
|---|---|
| 框架/品牌/导航 | ProLayout布局Token承接248px白色侧栏、58px紧凑顶栏、蓝色选中和品牌。五菜单及导航目标保留，数量提示只用于原有物品/芯片计数，演示身份明确 |
| 工作台 | ProCard分组概况、筛选、原指标、趋势及明细；浅色概况卡、统一边框、标签与时间。输入未应用时保留22，明确应用生命周期累计后27，刷新仍保留条件 |
| 查询与结果 | ProTable保留原字段、条件和每页10条；搜索/重置、工具栏及结果分区，必要横向滚动限制在表格内，整页不横向溢出 |
| 详情与编辑 | [紧凑只读详情](checks/evidence/style-item-detail-1440.png)使用ProDescriptions及分组ProCard；款式使用ProForm栅格，预览与实际保存相分离，原上传及保存逻辑保留 |
| 小窗口弹层 | 正文按视口限高滚动，1280×720底部确认/取消可见；下拉挂载当前弹层随滚动/动画定位，选中值留存后再提交；准备与确认接续仍是原两段 |
| 键盘与反馈 | 概况卡可聚焦并按Enter带原条件进入；失败、未知、三种离开选择与读取重试通过；按钮、输入和菜单沿官方组件语义 |

参考中的旧菜单、旧字段/数据、20条分页、独立抽屉和认证样例按用户“业务不改”的边界未迁入。截图数据不同来自各自样例；当前样例和统计规则保持，未用参考数字替换。页标题及原操作继续位于现有页面，顶栏显示导航上下文。

## 验证与限制

[构建及产物记录](checks/evidence/style-build.json)、[完整主线8项](checks/evidence/style-core.json)、[恢复10项](checks/evidence/style-recovery.json)、[视觉6项](checks/evidence/style-visual.json)、[五主页面与零外部资源](checks/evidence/style-delivery.json)均通过。已查看上述参考和最终截图，没有未解决的阻断、高优先级或主要视觉问题；此结论不替代cece人工视觉验收。

首次旧布局属性类型失败已按当前Token API修正。一轮换新候选卡选择未保留，校验正确阻断；调整弹层挂载并加选中断言后完整重跑通过，未强制点击、注入业务数据或放宽校验。真实接口、认领、芯片、生产和Windows本机直接打开未在本轮验证；未运行React19组件矩阵。
