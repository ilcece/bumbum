# NTAG 424 DNA 与 nfc.cool 操作手册

日期：2026-10-23；后台基线v1.2.1。先完成第一枚，再复制流程到另外两枚，不复制密钥。既有标签不要从“新标签初始化”重做。

## 1. 已确认资产与状态

| 项目 | 会话证据 |
|---|---|
| 实物 | 用户有3枚NTAG424 DNA；已详细检查第一枚 |
| 第一枚UID | `048681CA842090`，移开重读一致 |
| App识别 | NXP NTAG424 DNA，416Bytes总存储；NDEF文件本身256Bytes |
| 原厂签名 | App显示NXP公钥验证通过；不是默认AES密钥验证 |
| 后台正确标签ID | `dbab7b32-b60e-4cde-ac81-a248240d86cb` |
| 后台准备 | nfc-prepare成功，PENDING；本地生成两份配置 |
| Key0 | 曾用nfc.cool口令模式更改且提示成功；真实AES值由App保存，最终随机换钥未确认 |
| Key1/2 | 用户报告已按服务器对应十六进制目标值设置 |
| SUN | nfc.cool显示已开启、“真实”、动态参数和读取计数 |
| 服务器最终闭环 | v1.2.1现场版本、PENDING校验、ACTIVE及后续验收尚待确认 |

档案入口码、后台UUID和芯片UID用途不同：nfc-prepare用UUID；写入网址使用服务器生成的入口码；UID用于真实身份核对；这三项都不是AES密钥。

## 2. 工具结论

- iPhone本身支持所需通信；不能把“当前App能力未核验”说成“必须买USB读卡器”。用户已有Windows11和MacBook，但本阶段不要求购买硬件。
- NFC TagInfo用于型号/UID/NDEF/原厂签名读取，不等于Key0认证或SDM初始化。
- NFC Tools能发送原始APDU，并用逗号串联一次扫描中的多条命令。单次扫描后重新发续传会丢会话；已用三段GetVersion实测连续传输成功。固定命令列表本身不能完成需随机挑战和AES计算的完整认证。
- NFC Developer App提供主密钥派生/写卡界面，但它的方案未与本项目完整核验，不拿其默认全零/demo配置当生产步骤。
- **本轮选用nfc.cool**：已观察到NTAG424专用Key0、SUN、网址及高级入口，第一枚成功生成动态SUN。具体菜单随App版本变化，文档不假定存在手填偏移入口。
- ACR1252U/ACR1552U是讨论过的PC/SC读卡器候选，无本项目实物联调证据；不用因本会话再买设备。自研iOS程序也尚未交付。

## 3. Key0–4及当前管理原则

| 槽位 | 本profile用途 | 操作原则 |
|---|---|---|
| Key0 | 写入/文件权限/SDM管理 | 当前已由App修改，使用App保存的实际钥；不再假设默认全零 |
| Key1 | SDMFileReadKey，生成MAC；本实物还要求它认证读取单独计数 | 与服务器targetKeys.1一致，十六进制输入 |
| Key2 | SDMMetaReadKey，加密PICC数据 | 与服务器targetKeys.2一致，十六进制输入 |
| Key3/4 | 本次SDM不使用 | 暂不必操作；不能推断芯片所有其他文件都不使用它们 |

口令模式输入的文本不等于同字符的AES十六进制值。每个AES128密钥为16字节、32个十六进制字符。FaceID查看是App解锁它保存的信息，不是从芯片明文导出秘密。

初始化JSON是**新目标值**，不证明芯片各槽位已应用。避免写卡记录混淆，维护一份不含钥值的“当前/目标/已写入/验证”表，模板见[交接记录](HISTORY-AND-STATUS.md)。

## 4. 新标签登记和配置生成

仅对尚未生成配置的标签执行。先按[部署手册](DEPLOYMENT.md)定义dc，后台登记真实UID、绑定已发布服装，再从标签详情地址取UUID。

```bash
dc run --rm tools check
```

确认正常后，把示例UUID替换成后台实际ID：

```bash
dc run --rm tools nfc-prepare 11111111-1111-4111-8111-111111111111
```

若提示已存在，不删除文件重试；检查是否已准备过。此命令只生成服务器文件，不写芯片、不启用ACTIVE。

主机/容器位置：

| 用途 | 主机相对项目目录 | 容器 |
|---|---|---|
| 运行钥（仅Key1/2） | secrets/nfc-runtime/标签UUID.json | /run/nfc-keys/标签UUID.json，app只读 |
| 初始化目标Key0–4及plan | secrets/nfc-personalization/标签UUID.json | /provision/标签UUID.json，仅tools |

第一枚的实际主机文件位于：

```text
/root/bumbum-sqlite-package/bumbum-main/secrets/nfc-personalization/dbab7b32-b60e-4cde-ac81-a248240d86cb.json
```

文件600、目录700、UID/GID1000。通过可信设备/SFTP私下读取，不发到聊天、Git或网页编码服务。

只显示非密钥参数的命令（现有第一枚可用，任何工作目录均可）：

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path
p = Path('/root/bumbum-sqlite-package/bumbum-main/secrets/nfc-personalization/dbab7b32-b60e-4cde-ac81-a248240d86cb.json')
d = json.loads(p.read_text())
print('标签 UID：', d['uid'])
print(json.dumps(d['plan'], ensure_ascii=False, indent=2))
PY
```

不要改成打印整个JSON；keyHex必须只在自己的可信设备查看。若准备报错，先SELECT标签UUID/UID并查文件是否存在，不直接删除配置或重置数据库。

## 5. 两种网址模式不要混用

### 服务器手工plan模板

```text
https://nfc.bumbum.cc/v/<entry_code>?p=<32字符占位>&m=<16字符占位>
```

生成器使用单条短NDEF URI、https://前缀04、含两字节NLEN。当域名为上例且入口码32字符时，原plan偏移58/93/93，文件109字节；换域名、编码、记录结构则重新核算。

### 本实物nfc.cool自动格式（当前应保留）

```text
https://nfc.bumbum.cc/v/<entry_code>?picc_data=<32字符动态密文>&cmac=<16字符动态MAC>
```

App自动配置字段位置。本实物回读为66/104/104。**不要硬填原58/93，不把偏移数字拼进网址，不在已开启SUN时盲目重写普通模板。** nfc.cool生成的格式需要后台至少v1.2.1。

全零模板不是合法验真读数；入口码固定，实际密文与MAC由芯片读取时产生。不要用UID或标签UUID替换入口码。正式域名保持稳定，改后台域名可不改用户入口，但改NFC入口域名可能需重新写卡。

## 6. 新标签的配置原则

若由App初始化，应先确认当前密钥能认证；未知时不能重置或盲猜。对当前第一枚已完成的步骤只核查，不重复应用。

- 输入Key1/Key2新值时选“十六进制”，分别来自targetKeys.1.keyHex / targetKeys.2.keyHex；不能当成当前Key0。
- 当前管理认证用App已保存的实际Key0。若要求某槽位旧钥，那与管理Key0不同，不能凭Key0成功认定所有旧钥全零。
- 使用自己域名和这枚标签入口；SUN输出加密PICC数据及MAC，UID/计数纳入加密数据，ASCII输出，MetaRead=Key2，FileRead=Key1。
- AES模式；本阶段不用LRP、TagTamper或额外加密文件数据。
- 文件02/E104公开读取、写入/组合读写/修改权限为Key0；不要永久锁定或格式化。
- Key0可在整个验真成功后换成安全随机目标值，详见第9节。

不能承诺所有nfc.cool版本用同一菜单或不覆盖已有设置；以回读的真实配置和服务器校验为准。App没有所需功能时先核实，不用不完整的裸指令替代认证。

## 7. 只读APDU与已验证的实物设置

NFC Tools高级命令，一次扫描批量发送（逗号分隔）：

```text
00:A4:04:00:07:D2:76:00:00:85:01:01:00,90:F5:00:00:01:02:00
```

第一条选择NFC应用，第二条GetFileSettings读取文件02。它不修改芯片，不读钥值，不消费服务端验真计数。第一枚实际返回：

```text
90 00
00 40 00 E0 00 01 00 C1 F1 21 42 00 00 68 00 00 68 00 00 [91 00]
```

| 部分 | 解读 |
|---|---|
| 00 | 普通数据文件 |
| 40 | SDM开启、普通通信模式 |
| 00 E0 | RW=Key0，Change=Key0，Read=E公开，Write=Key0 |
| 00 01 00 | 小端文件大小256字节 |
| C1 | UID和读取计数镜像、ASCII |
| F1 21 | 单独计数读取=Key1，MetaRead=Key2，FileRead=Key1 |
| 42 00 00 | PICCDataOffset=66 |
| 68 00 00 | MACInputOffset=104 |
| 68 00 00 | MACOffset=104；输入起点等于MAC位置，空MAC输入 |

生成器原plan是FF21（禁止单独计数读取）；实物是F121（需Key1认证读取计数）。两者都不是公开计数读取，且此差异不影响网址MAC计算。本轮不必为此改卡。

GetVersion只读连续测试：

```text
90:60:00:00:00,90:AF:00:00:00,90:AF:00:00:00
```

已实测返回91AF、91AF、9100；91AF是还有数据。分三次重新扫描不保留会话，续传可能911C；App显示“OK”可能仅表示已发送，须看芯片状态字。不要把其他型号NTAG213/215/216的写入/格式化命令用于424。

## 8. 现场闭环验收

先确认ECS已运行1.2.1，check与/health正常、对应标签启用且绑定PUBLISHED服装。

1. 退出工具，移开标签，用iPhone重新触碰，点击系统通知打开**新**动态网址。
2. PENDING时应显示“芯片动态校验通过，等待管理员启用”；后台出现成功时间/次数。
3. 在30分钟内到标签详情，填写原因并启用ACTIVE。人工“已回读URL”按钮不替代加密校验。
4. 再次触碰应显示“本次芯片验真通过”、服装和北京时间。
5. 刷新/转发已使用链接应409；新触碰通过。读取可能跳号，不要求一次只+1。
6. 停用后新触碰410；重启app后旧链接仍拒绝、新读数通过；档案/g页面无本次验真标志。
7. 测试解绑、下架和绑定变更；确认不会错误显示其他服装或转移所有者。
8. 每枚至少10次独立触碰，记录手机/iOS、网络、正确服装、失败信息和耗时；这是项目验收目标，不是厂商性能保证。

App预览或第三方扫描器可能先打开URL并消费读数，出现已使用时重新触碰。HEAD和带预取标记的请求不消费，但不能保证所有第三方都带标记。不要发真实完整动态URL求助，只发错误文字/安全日志。

## 9. Key0最终换钥及Key3/4

当前测试口令不适合长期管理；不要把它作为主密钥。先完成第8节，再备份当前可认证钥和目标钥，在App选择十六进制，将Key0改为该标签targetKeys.0.keyHex。确认App保存新值并能重新认证，再触碰验真。

只换Key0、不改Key1/2、网址、SDM/文件设置，不改变固定入口，也不改变后台校验使用的钥。App若提示联动重置SUN或其他钥，先核实；不要使用恢复出厂设置代替换钥。

Key3/4当前不是验真前提。目标JSON有它们不表示已写入。若以后保护额外文件或Vault，需要另行定义权限和写入记录，不能默认为整颗芯片完全闲置。
