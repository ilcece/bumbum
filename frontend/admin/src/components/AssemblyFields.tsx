import React, { useEffect, useState } from "react";
import { Alert, Button, Checkbox, Form, Input, InputNumber, Typography } from "antd";
import { Row } from "../catalog";
import { ActionForm, RemoteSelect, required, useRecord } from "./CatalogUI";

export default function AssemblyFields({ styleId, project, orderUnit }: { styleId: number; project: string; orderUnit?: Row }) {
  const form = Form.useFormInstance();
  const [registering, setRegistering] = useState(false);
  const changeSelection = (value: number) => {
    form.setFieldValue("installed", false);
    return value;
  };
  return (
    <>
      {orderUnit?.physical_item_id ? <>
        <Alert type="info" title={"原订单件实物 · " + orderUnit.physical_uid + " · " + (orderUnit.spec || "无规格")} />
        <Form.Item name="physical_item_id" hidden><InputNumber /></Form.Item>
      </> : <Form.Item
        name="physical_item_id"
        label="实体编号"
        rules={required}
        getValueFromEvent={changeSelection}
        extra={<Button type="link" onClick={() => setRegistering(true)}>登记实体</Button>}
      >
        <RemoteSelect resource="physical-items" params={{ style_id: styleId, available: true }} />
      </Form.Item>}
      <Form.Item name="chip_id" label="芯片 UID" rules={required} getValueFromEvent={changeSelection}>
        <RemoteSelect resource="chips" params={{ available: true, compatible_project: project }} />
      </Form.Item>
      <InstallationConfirmation />
      {registering && (
        <ActionForm
          title="登记实体物品"
          submitText="登记并带回"
          action="createPhysicalItem"
          initial={{ style_id: styleId }}
          onClose={() => setRegistering(false)}
          onDone={(result) => {
            form.setFieldValue("physical_item_id", result.id);
            form.setFieldValue("installed", false);
            setRegistering(false);
          }}
        >
          <Form.Item name="style_id" hidden><InputNumber /></Form.Item>
          <Form.Item name="physical_uid" label="实体编号" rules={required}><Input maxLength={64} /></Form.Item>
          <Form.Item name="spec" label="实际规格" extra="有尺码、颜色等规格时必填。"><Input maxLength={256} /></Form.Item>
          <Form.Item name="batch_no" label="实物批次"><Input maxLength={64} /></Form.Item>
          <Form.Item name="supplier_serial" label="供应商序列号"><Input maxLength={128} /></Form.Item>
        </ActionForm>
      )}
    </>
  );
}

export function ChipRegistrationFields() {
  return <>
    <Form.Item name="chip_uid" label="芯片编号 UID" rules={required}>
      <Input maxLength={32} placeholder="7字节真实UID" />
    </Form.Item>
    <Form.Item name="batch_no" label="芯片批次"><Input maxLength={64} /></Form.Item>
  </>;
}

export function InstallationConfirmation() {
  const form = Form.useFormInstance();
  const physicalId = Form.useWatch("physical_item_id", form);
  const chipId = Form.useWatch("chip_id", form);
  const physical = useRecord("physical-items", physicalId).record;
  const chip = useRecord("chips", chipId).record;
  const ready = !!physical && !!chip && physical.id === physicalId && chip.id === chipId;
  useEffect(() => {
    form.setFieldValue("installed", false);
  }, [form, physicalId, chipId]);
  return <>
    {ready ? <Alert type="info" title={"安装核对 · " + physical.physical_uid + " · " + (physical.spec || "无规格") + " · " + chip.chip_uid} /> :
      <Typography.Text type="secondary">选齐实物和芯片后，核对编号再确认安装。</Typography.Text>}
    <Form.Item name="installed" valuePropName="checked" preserve={false} rules={[{
      validator: (_, value) => ready && value === true ? Promise.resolve() : Promise.reject("请核对并确认当前实物和芯片的安装"),
    }]}>
      <Checkbox disabled={!ready}>已将所选芯片安装到这件实物</Checkbox>
    </Form.Item>
  </>;
}
