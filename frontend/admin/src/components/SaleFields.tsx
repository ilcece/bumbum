import { Alert, DatePicker, Form, Input, Radio, Typography } from "antd";
import { inputDate, inputISO } from "../businessTime";
import { time } from "../catalog";
import { required } from "./CatalogUI";
export default function SaleFields({
  firstSoldAt,
}: {
  firstSoldAt?: string | null;
}) {
  const confirmed = Form.useWatch("confirmed");
  return (
    <>
      <Alert
        type="info"
        showIcon
        title="售出与认领分别记录"
        description="按有依据的外部成交结果确认，不录订单、金额或物流。已有首次成交时间不改写，撤销标记不删除历史或改变持有人。"
      />
      {firstSoldAt && (
        <Typography.Paragraph>
          首次售出时间（只读）：{time(firstSoldAt)}（北京时间）
        </Typography.Paragraph>
      )}
      <Form.Item name="confirmed" label="处理方式">
        <Radio.Group
          options={[
            { value: true, label: "确认已售出" },
            { value: false, label: "撤销售出确认" },
          ]}
        />
      </Form.Item>
      {confirmed && !firstSoldAt && (
        <Form.Item
          name="first_sold_at"
          label="首次售出时间（北京时间）"
          initialValue={inputISO(inputDate())}
          rules={required}
          getValueProps={(value) => ({
            value: typeof value === "string" ? inputDate(value) : value,
          })}
          normalize={(value) => (value ? inputISO(value) : undefined)}
          extra="填写有依据的实际成交时间，不能晚于当前；已有首次时间的物品仍保留原值。"
        >
          <DatePicker showTime />
        </Form.Item>
      )}
      <Form.Item name="evidence" label="销售确认或更正依据" rules={required}>
        <Input.TextArea maxLength={1000} />
      </Form.Item>
    </>
  );
}
