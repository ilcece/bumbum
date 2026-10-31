# BUMBUM 项目基线同步

目的：让新的ChatGPT和Codex会话主动读取GitHub真实状态，恢复同一项目上下文，然后继续产品与商业工作。原GitHub Ops现定位为Project Context Sync；保留本文件路径供旧链接继续使用。

这些查询由AI执行，cece不用逐条运行命令、维护脚本或搬运长报告。长期规则看 [AGENTS](../AGENTS.md)，当前任务只看 [TODO](../TODO.md)，历史证据看 [CHANGELOG](../CHANGELOG.md)。新会话先读 [本次过度工程化复盘](PROJECT_PRIORITY_AND_OVERENGINEERING_REVIEW.md)。

## 1. 使用现有连接，不再建设平台

优先用当前会话已有的GitHub连接器。确认它能按精确分支/提交读取完整文件、取得完整分支分页及PR状态；只有搜索摘要或Library快照不足以完成同步。

连接器未提供或缺少能力时，Codex优先使用已有GitHub CLI（gh）的只读API。当前环境已验证gh 2.46.0能完成本手册的查询，无须保留重复Python工具、安装依赖或建立新Token。其他ChatGPT会话的连接器和权限必须在该会话实际验证，不能从这里的成功推断。

如果现有连接器和gh都无法完成某项必要读取，说明具体缺口和已覆盖范围，再判断是否值得增加最小辅助；不为未来假设建设授权签发、审计恢复或自动化管理平台。

本流程不创建/删除远端分支，不写PR，不触发Actions，不部署。正常代码开发、提交、分支推送、PR创建和经批准的合并继续遵守AGENTS第0、3节；禁止直接向main推送，生产部署另行授权。

## 2. 开始会话时先读什么

1. 确认唯一仓库是 `ilcece/bumbum`，当前工具确实能读取它；不输出Token、密码、真实.env或完整认证环境。
2. 取得GitHub当前main的完整40位SHA；固定这个提交读取AGENTS.md、README.md、TODO.md，CHANGELOG.md只读最新相关记录，避免混用不同时间的文件；需追溯决策时再按任务关键词或具体事项查历史，不要求每次全文读取。
3. 有明确任务分支时再取它的完整HEAD，并读取对应任务文件和与main的差异；未指定时以main为基线。分支未推送或本地有未提交工作时单列本地状态，不冒充GitHub已经接收。
4. 完整分页读取远端分支名称并查询开放PR，结合当前TODO和任务发现活动分支；只对任务分支和明确活动分支读取完整SHA并计算ahead/behind。历史分支简要记录，发现未合并工作或状态疑问时再深入，不随意删除。
5. 按当前任务补读PRODUCT、PRD、TECH_SPEC、API_CONTRACT、业务PRD或技术文档。查到足够上下文就回到当前主任务，不无差别重读全部历史。
6. 结束查询时复查main及分支清单。期间变化、分页不全或权限不足时明确报告，不能用旧聊天或旧报告补齐。

还在本地工作时，AI同时检查实际目录、分支、完整HEAD和未提交文件。当前独立工作目录为 `/workspace/bumbum-github-ops`；不改原杭州目录，不重建Worktree。若发现交付记录不符，保留现场先报告，不自行reset或覆盖。

GitHub只能展示已提交并推送的状态。未合入main的本轮规则不能当作远端main已有内容，也不为了“让新会话能看到”而擅自推送或合并。

## 3. 连接器不足时的gh只读参考

下面由AI按实际目标执行。带示例名称、SHA或编号的位置需要替换，不为运行示例创建资源。每条请求都明确使用GET；不使用显示认证详情的参数，也不修改原有认证。

先确认身份、仓库和main：

```bash
gh api --method GET user --jq .login
gh api --method GET repos/ilcece/bumbum --jq '{full_name,default_branch}'
gh api --method GET repos/ilcece/bumbum/commits/main --jq .sha
```

### 第一步：发现活动工作

```bash
gh api --method GET --paginate 'repos/ilcece/bumbum/branches?per_page=100' \
  --jq '.[].name'

gh api --method GET --paginate 'repos/ilcece/bumbum/pulls?state=open&per_page=100' \
  --jq '.[] | {number,title,base:.base.ref,head:.head.ref,head_sha:.head.sha}'
```

两项列表都须完成分页；结合当前TODO、开放PR和任务确定活动分支。API附带历史分支SHA不意味着必须对它们逐一分析，也不能仅凭名称把分支认定为历史残留。

### 第二步：仅深入核对任务与活动分支

main每次都读取完整40位SHA；有任务分支时也必须读取完整SHA，并对明确活动分支做同样核对：

```bash
gh api --method GET 'repos/ilcece/bumbum/commits/指定任务分支' --jq .sha
```

分支名称中的特殊字符由AI按API要求编码。分支不存在或未推送就如实报告，不把本地HEAD填成远端结果。仅对当前任务及明确活动分支，用本轮读取的完整SHA比较：

```bash
gh api --method GET 'repos/ilcece/bumbum/compare/MAIN完整SHA...目标分支完整SHA' \
  --jq '{ahead_by,behind_by}'
```

ahead_by是目标分支尚未进入main历史的提交数，behind_by是main尚未进入目标分支历史的提交数。数量是历史关系，不直接表示业务文件遗漏；没有任务或活动分支时简要说明即可，本地未推送分支另行说明。

### 第三步：历史分支只做必要补查

对已有依据确认没有活动任务、开放PR或待处理独有工作的历史分支，仅简要记录，不逐一拉取完整SHA和比较。状态不明确或发现未合并工作时，再针对相关分支及PR深入核对；不随意删除历史分支。必要时查询PR合并状态：

```bash
gh api --method GET repos/ilcece/bumbum/pulls/25 \
  --jq '{number,state,merged,merged_at,head_sha:.head.sha,base_sha:.base.sha,merge_commit_sha}'
```

25是示例编号，先确认实际PR。closed不等于merged；不能只看PR标题、旧截图或“已关闭”就写成已合并。

按固定提交直接读取权威文件正文：

```bash
gh api --method GET -H 'Accept: application/vnd.github.raw+json' \
  'repos/ilcece/bumbum/contents/AGENTS.md?ref=MAIN完整SHA'
```

AI把MAIN完整SHA换成实际提交，按需替换文件路径。每次读AGENTS、README、TODO；CHANGELOG只取最新相关记录，追溯决策时再按关键词或具体事项查历史。任务分支的状态及相关文件使用其完整SHA，PRODUCT、PRD、TECH_SPEC、API_CONTRACT等按任务分层读取，不无差别读整个仓库。必要内容过大或接口返回不完整时说明缺口，不拿搜索片段替代。

## 4. 统一基线报告

用简短上下文摘要即可，实际版本核对与对外表达统一遵守AGENTS第1.1节。下面只是结构示例，不要求机械填满：

```text
当前任务：
版本说明：审核的是你提供的版本，分支没有更新（按实际结果填写）
结论与影响：
未覆盖范围或待决定事项：
下一步及负责人：
```

AI仍须实时核对完整提交编号、必要的分支差异及完整分页；回复默认不展示完整或缩短的哈希、核对时间、分页过程及ahead/behind。版本有更新时说明新增内容和对结论的影响，按需给出GitHub差异链接；读取不完整时明确限制。cece明确索要或实际操作需要准确版本时，再提供必要编号及参数。不为此新增证据台账或报告生成器。

主任务和下一步负责人沿用TODO。涉及实现、验收、合并或部署时区分证据；未现场复核部署时标为最后已知状态，不因main已合并就断言服务器已更新，不为摘要罗列全部历史。

无需每次重跑历史测试、重新连接生产或要求cece重复验收；只有当前任务依赖新证据时才继续核对。报告完成后直接继续已授权的产品或商业工作。

## 5. 不完整时怎样处理

| 情况 | AI怎样处理 |
|---|---|
| 当前会话没有连接器 | 使用已有gh等只读能力；没有可用替代才说明具体缺口，不要求盲目重装插件 |
| 认证、网络或仓库读取失败 | 保留安全错误摘要，说明未读取范围，不索取或输出凭据，不修改认证 |
| 分页不完整或查询期间SHA变化 | 不宣称完整；重新做必要的只读核对，不能用旧报告补足 |
| 指定分支或文件尚未推送 | 分清远端已知与本地草稿，保护工作区，不代替用户决定推送或合并 |
| 状态只在历史记录中出现 | 标明证据日期和限制，不把旧测试、旧部署当作当前现场实测 |
| 有实现但无验收/合并/部署证据 | 分栏说明，不猜测已经完成 |

基线同步不负责写操作、授权签发或审计恢复。相关自动管理工具已停止建设并清理；正常工程授权及必要业务安全机制继续保留。
