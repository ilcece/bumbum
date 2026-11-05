import React from "react";
import { Alert } from "antd";
import { ModalForm, ProDescriptions, ProFormTextArea } from "@ant-design/pro-components";
import { useStore } from "../data/store";
import { wholeName } from "../data/domain";
import { required, useAction } from "../ui";
import { CopyValue } from "./RecordPresentation";

export default function ItemLossEditor({ itemId, entityId, open, onOpenChange }: { itemId: number; entityId?: string; open: boolean; onOpenChange: (value: boolean) => void }) {
  const p = useStore(), a = useAction(), item = p.data.items.find(i => i.id === itemId), entity = item?.entities.find(e => e.id === entityId), chip = p.data.chips.find(c => c.id === entity?.chipId);
  return <ModalForm title="挂失物品" open={open} onOpenChange={onOpenChange} modalProps={{ destroyOnHidden: true }} submitter={{ searchConfig: { submitText: "确认挂失整套物品" }, submitButtonProps: { danger: true, disabled: a.unknown } }} onFinish={async values => {
    const ok = a.run("loseItem", { itemId, entityId, evidence: values.evidence }, "整套物品已挂失，配套芯片停止服务；身份和持有人保留");
    if (ok) onOpenChange(false);
    return ok;
  }}>
    <Alert showIcon type="warning" title="挂失当前整套物品：实物＋芯片" description="立即停止这代物品配套芯片的验证服务，保留数字身份、发行编号、持有人和历史，不自动扣换新次数。已有未完成定期换新会保留新物品准备，按挂失换新继续；转售准备不改变类型。" />
    <ProDescriptions size="small" column={1} columns={[
      { title: "数字身份", render: () => <CopyValue value={item?.uid} /> },
      { title: "本次挂失物品", render: () => `${wholeName(entity)} · ${entity?.spec || "待核对"}` },
      { title: "配套芯片", render: () => <CopyValue value={chip?.uid} /> },
    ]} />
    <ProFormTextArea name="evidence" label="物品挂失依据" rules={required} />
    {a.feedback}
  </ModalForm>;
}
