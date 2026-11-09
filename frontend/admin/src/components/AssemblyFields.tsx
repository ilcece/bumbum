import React, { useState } from "react";
import { Button, Checkbox, Form, Input, InputNumber } from "antd";
import { ActionForm, RemoteSelect, required } from "./CatalogUI";

export default function AssemblyFields({ styleId, project }: { styleId: number; project: string }) {
  const form = Form.useFormInstance();
  const [registering, setRegistering] = useState(false);
  const changeSelection = (value: number) => {
    form.setFieldValue("installed", false);
    return value;
  };
  return (
    <>
      <Form.Item
        name="physical_item_id"
        label="实体编号"
        rules={required}
        getValueFromEvent={changeSelection}
        extra={<Button type="link" onClick={() => setRegistering(true)}>登记实体</Button>}
      >
        <RemoteSelect resource="physical-items" params={{ style_id: styleId, available: true }} />
      </Form.Item>
      <Form.Item name="chip_id" label="芯片 UID" rules={required} getValueFromEvent={changeSelection}>
        <RemoteSelect resource="chips" params={{ available: true, compatible_project: project }} />
      </Form.Item>
      <Form.Item name="installed" valuePropName="checked" rules={[{
        validator: (_, value) => value === true ? Promise.resolve() : Promise.reject("请核对实体编号、实际规格和芯片 UID"),
      }]}>
        <Checkbox>已核对实体编号、实际规格和芯片 UID，并将芯片安装到该实体</Checkbox>
      </Form.Item>
      {registering && (
        <ActionForm
          title="登记实体物品"
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
          <Form.Item name="batch_no" label="实体批次"><Input maxLength={64} /></Form.Item>
          <Form.Item name="supplier_serial" label="供应商序列号"><Input maxLength={128} /></Form.Item>
        </ActionForm>
      )}
    </>
  );
}
