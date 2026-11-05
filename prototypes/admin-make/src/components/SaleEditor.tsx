import React from "react";
import {
  ModalForm,
  ProFormRadio,
  ProFormDateTimePicker,
  ProFormTextArea,
} from "@ant-design/pro-components";
import { Alert, Typography } from "antd";
import { useAction, required, dateISO, localDate } from "../ui";
export default function SaleEditor({
  ids,
  open,
  onOpenChange,
}: {
  ids: number[];
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const a = useAction();
  return (
    <ModalForm
      title="售出确认"
      open={open}
      onOpenChange={(v) => {
        a.clear();
        onOpenChange(v);
      }}
      initialValues={{
        confirmed: true,
        at: localDate(new Date().toISOString()),
      }}
      modalProps={{ destroyOnHidden: true }}
      submitter={{
        searchConfig: { submitText: "保存售出确认" },
        submitButtonProps: { disabled: a.unknown },
      }}
      onFinish={async (v) => {
        const ok = a.run("sale", {
          ids,
          confirmed: v.confirmed,
          at: dateISO(v.at),
          evidence: v.evidence,
        });
        if (ok) onOpenChange(false);
        return ok;
      }}
    >
      <Alert
        type="info"
        title={`本次${ids.length}件数字身份，售出与认领分别记录`}
        description="根据电商平台有效成交结果确认，不录订单、金额或物流。已有首次售出时间保留，换新/转售不会重置。"
      />
      <ProFormRadio.Group
        name="confirmed"
        label="处理方式"
        options={[
          { value: true, label: "确认已售出" },
          { value: false, label: "撤销售出确认" },
        ]}
      />
      <ProFormDateTimePicker
        name="at"
        label="首次售出时间（北京时间）"
        rules={[{ required: true }]}
      />
      <ProFormTextArea
        name="evidence"
        label="销售确认或更正依据"
        rules={required}
      />
      <Typography.Paragraph type="secondary">
        撤销只更正销售归类，保留首次记录和审计，不删除身份/触碰，不自动改变所有权。
      </Typography.Paragraph>
      {a.feedback}
    </ModalForm>
  );
}
