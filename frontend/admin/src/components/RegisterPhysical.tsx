import { useState } from "react";
import { Alert, Button, Form, Input, InputNumber, Select } from "antd";
import { ActionForm, RemoteSelect, required, useRecord } from "./CatalogUI";
import StyleEditor from "./StyleEditor";
import type { ActionResult, OrderUnit } from "../types/catalog";

export function PhysicalFields({
  nested = false,
  fixedSpec,
}: {
  nested?: boolean;
  fixedSpec?: string;
}) {
  const field = (name: string) => (nested ? ["physical", name] : name);
  const style = useRecord("styles", Form.useWatch(field("style_id"))).record;
  return (
    <>
      <Form.Item name={field("physical_uid")} label="实体编号" rules={required}>
        <Input maxLength={64} />
      </Form.Item>
      {fixedSpec ? (
        <Form.Item name={field("spec")} hidden>
          <Input />
        </Form.Item>
      ) : (
        <Form.Item
          name={field("spec")}
          label="实际规格"
          rules={style?.specs?.length ? required : []}
        >
          {style?.specs?.length ? (
            <Select
              options={style.specs.map((spec: string) => ({
                label: spec,
                value: spec,
              }))}
            />
          ) : (
            <Input maxLength={256} placeholder="填写实物尺码、颜色等信息" />
          )}
        </Form.Item>
      )}
      <Form.Item name={field("batch_no")} label="实物批次">
        <Input maxLength={64} />
      </Form.Item>
      <Form.Item name={field("supplier_serial")} label="供应商序列号">
        <Input maxLength={128} />
      </Form.Item>
    </>
  );
}

export default function RegisterPhysical({
  orderUnit,
  onClose,
  onDone,
}: {
  orderUnit?: OrderUnit;
  onClose: () => void;
  onDone: (r: ActionResult) => void;
}) {
  const [creatingStyle, setCreatingStyle] = useState(false);
  const [form] = Form.useForm();
  const unitId = orderUnit?.id;
  return (
    <>
      <ActionForm
        title="登记实体物品"
        submitText={unitId ? "登记并用于本件" : "登记实物"}
        formInstance={form}
        action={unitId ? "orderPhysical" : "createPhysicalItem"}
        initial={
          unitId
            ? {
                order_unit_id: unitId,
                physical: {
                  style_id: orderUnit.expected_style_id,
                  spec: orderUnit.expected_spec,
                },
              }
            : {}
        }
        onDone={onDone}
        onClose={onClose}
      >
        {orderUnit ? (
          <>
            <Alert
              type="info"
              title={
                orderUnit.expected_style_name +
                " · " +
                (orderUnit.expected_spec || "无指定规格")
              }
            />
            <Form.Item name="order_unit_id" hidden>
              <InputNumber />
            </Form.Item>
            <Form.Item name={["physical", "style_id"]} hidden>
              <InputNumber />
            </Form.Item>
          </>
        ) : (
          <>
            <Form.Item
              name="style_id"
              label="款式"
              rules={required}
              extra={
                <Button type="link" onClick={() => setCreatingStyle(true)}>
                  补建款式
                </Button>
              }
            >
              <RemoteSelect
                resource="styles"
                onChange={() => form.setFieldValue("spec", undefined)}
              />
            </Form.Item>
          </>
        )}
        <PhysicalFields
          nested={!!unitId}
          fixedSpec={orderUnit?.expected_spec ?? undefined}
        />
      </ActionForm>
      {creatingStyle && (
        <StyleEditor
          page={false}
          compact
          returnTo="保存后返回实物登记并选中新款式。"
          onClose={() => setCreatingStyle(false)}
          onDone={(r) => {
            form.setFieldsValue({ style_id: r.id, spec: undefined });
            setCreatingStyle(false);
          }}
        />
      )}
    </>
  );
}
