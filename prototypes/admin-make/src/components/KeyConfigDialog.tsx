import React, { useState } from "react";
import { Alert, App, Button, Checkbox, Form, Input, Modal, Space, Steps, Typography } from "antd";
import { ProCard, ProDescriptions } from "@ant-design/pro-components";
import { useStore } from "../data/store";
import { timeText } from "../data/domain";
import { useAction, useUnsaved } from "../ui";
import { CopyValue, StatusTag } from "./RecordPresentation";

// 这些值只用于展示交互，未使用、生成或持久保存任何真实密钥和动态读数。
const slots = ["K0", "K1", "K2", "K3", "K4"];
const template = "https://nfc.bumbum.cc/tap?picc_data=00000000000000000000000000000000&cmac=0000000000000000";
const demoLink = (id: number, count: number) => `https://example.invalid/tap?picc_data=${id.toString(16).padStart(14, "0")}${count.toString(16).padStart(6, "0")}DE0000000000&cmac=DE00000000000000`;

export default function KeyConfigDialog({ chipId, onClose }: { chipId: number; onClose: () => void }) {
  const p = useStore(), a = useAction(), { modal } = App.useApp(), c = p.data.chips.find(c => c.id === chipId)!;
  const [ack, setAck] = useState(false), [revealed, setRevealed] = useState(false), [links, setLinks] = useState(["", ""]), [management, setManagement] = useState(false), [error, setError] = useState("");
  const unsaved = useUnsaved();
  const targetItem = p.data.items.find(i => i.id === c.itemId) || p.data.items.find(i => i.id === p.data.handovers.find(w => w.id === c.candidateFor)?.itemId);
  const canOperate = !!targetItem && !["retired", "disabled", "lost"].includes(c.state);
  const clear = () => { setRevealed(false); setAck(false); setLinks(["", ""]); setManagement(false); unsaved.setDirty(false); };
  const close = () => {
    if (links.some(Boolean) && !c.configuredAt) {
      modal.confirm({ title: "放弃未提交的链接核验？", content: "关闭后清除本次展示值与输入，已保存的准备状态保留。", okText: "确认关闭", cancelText: "继续核验", onOk: () => { clear(); onClose(); } });
    } else { clear(); onClose(); }
  };
  return <Modal open title="芯片密钥、受控查看与配置核验" width={820} onCancel={close} maskClosable={false} footer={<Button onClick={close}>关闭窗口</Button>} destroyOnHidden>
    <div className="page-stack">
      <Alert type="info" showIcon title="配卡交互演示" description="本窗口恢复完整操作形式。展示值为合成示例，不可写入实卡；不连接密钥服务、不执行密码学验签。正式配卡仍由现有受控服务完成。" />
      <ProDescriptions size="small" bordered column={2} columns={[
        { title: "芯片 UID", render: () => <CopyValue value={c.uid} /> },
        { title: "关联数字物品", render: () => <CopyValue value={targetItem?.uid} /> },
        { title: "密钥状态", render: () => <StatusTag value={c.keys ? "已准备演示标记" : "未准备"} /> },
        { title: "配置状态", render: () => <StatusTag value={c.configuredAt ? "演示核验就绪" : "待配置"} /> },
      ]} />
      <Steps size="small" current={c.configuredAt ? 3 : !c.keys ? 0 : revealed ? 2 : 1} items={[{ title: "生成密钥" }, { title: "受控查看与配卡" }, { title: "双链接核验" }]} />
      {!canOperate && <Alert type="warning" title="当前状态不允许生成或确认配置" description="先核对关联与服务状态；已有结果仍可查看，不能覆盖或恢复历史授权。" />}
      <ProCard size="small" headerBordered variant="outlined" title="1. 生成并保存芯片密钥">
        <div className="page-stack"><Typography.Text type="secondary">生成不代表写卡完成。已有记录不可覆盖，换卡沿用既有接续流程。</Typography.Text><div><Button data-demo-only type="primary" disabled={!canOperate || c.keys || a.unknown} onClick={() => { setRevealed(false); a.run("keys", { chipId }, "已保存演示密钥准备标记，未生成真实密钥"); }}>{c.keys ? "已准备（不可覆盖）" : "〔演示〕准备密钥标记"}</Button></div></div>
      </ProCard>
      <ProCard size="small" headerBordered variant="outlined" title="2. 受控查看 K0–K4 与 SUN 模板">
        <div className="page-stack"><Checkbox checked={ack} disabled={!c.keys} onChange={e => { setAck(e.target.checked); if (!e.target.checked) setRevealed(false); }}>我确认本次查看：K1 为同版本全局共享秘密；关闭窗口后清除展示值。</Checkbox>
          <div><Button disabled={!c.keys || !ack} onClick={() => setRevealed(v => !v)}>{revealed ? "隐藏并清除展示值" : "受控查看 K0–K4 与 SUN 模板"}</Button></div>
          {revealed && <div className="key-values" data-private><Typography.Text>合成示例 · v1 · 未调用真实查看审计服务</Typography.Text>{slots.map((slot, n) => <div className="key-row" key={slot}><Space><strong style={{color: "#93c5fd"}}>{slot}</strong>{slot === "K1" && <StatusTag value="全局共享" />}{slot === "K2" && <StatusTag value="单卡独立" />}</Space><CopyValue value={n === 1 ? "DE110000000000000000000000000000" : `DE${n}${c.id.toString(16).padStart(29, "0")}`} /></div>)}<div className="template-value"><Typography.Text>固定 NDEF URL 模板</Typography.Text><br /><CopyValue value={template} /></div></div>}
          <Typography.Text type="secondary">按既定 NFC.cool 手册配置：SUN 加密、Meta Read Key 1、File Read Key 2；生成与查看不自动启用物品。</Typography.Text>
        </div>
      </ProCard>
      <ProCard size="small" headerBordered variant="outlined" title="3. 配卡后双链接动态读数核验" extra={!c.configuredAt && <Button data-demo-only type="link" disabled={!c.keys || !canOperate || a.unknown} onClick={() => { setRevealed(false); setLinks([demoLink(c.id, 1), demoLink(c.id, 2)]); setError(""); unsaved.setDirty(true); }}>填入两条演示链接</Button>}>
        {c.configuredAt ? <Alert type="success" showIcon title="演示配置核验已记录" description={`记录时间：${timeText(c.configuredAt)}。未验证真实卡片，不允许重复重置配置。`} /> : <div className="page-stack">
          <Typography.Text type="secondary">正式流程提交两次真实触碰结果，由服务端核对目标 UID、验签及计数递增。本原型仅接受“填入两条演示链接”生成的合成样例。</Typography.Text>
          <Form layout="vertical" className="key-inputs">{links.map((link, n) => <Form.Item key={n} label={`第 ${n + 1} 条触碰链接（演示）`} htmlFor={`tap-link-${c.id}-${n}`}><Input.TextArea data-private id={`tap-link-${c.id}-${n}`} rows={2} disabled={!c.keys || !canOperate || a.unknown} value={link} placeholder="粘贴动态触碰链接，勿在原型输入真实秘密" onChange={e => { setRevealed(false); setLinks(prev => prev.map((v, j) => n === j ? e.target.value : v)); setError(""); unsaved.setDirty(true); }} /></Form.Item>)}</Form>
          <Checkbox checked={management} disabled={!c.keys || !canOperate || a.unknown} onChange={e => { setManagement(e.target.checked); unsaved.setDirty(true); }}>我已人工核对新 K0 可以认证且文件权限符合手册（演示确认）</Checkbox>
          <div><Button type="primary" data-demo-only disabled={!canOperate || !c.keys || !links.every(Boolean) || !management || a.unknown} onClick={() => {
            setRevealed(false);
            if (links[0] !== demoLink(c.id, 1) || links[1] !== demoLink(c.id, 2)) { setError("仅接受当前芯片的两条递增演示链接；真实读数请使用正式配卡服务核验。"); return; }
            if (a.run("configure", { chipId, checked: true, checked2: management }, "演示配置核验已记录，未验证实卡")) { setLinks(["", ""]); setManagement(false); unsaved.setDirty(false); }
          }}>〔演示〕提交双链接并确认配置核验</Button></div>
          {error && <Alert type="error" showIcon title={error} />}
        </div>}
      </ProCard>
      {a.feedback}
    </div>
  </Modal>;
}
