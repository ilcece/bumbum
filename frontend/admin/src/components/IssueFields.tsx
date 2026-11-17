import { ProForm } from "@ant-design/pro-components";
import {
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row as GridRow,
  Select,
} from "antd";
import { inputDate, inputISO } from "../businessTime";
import { statusNames } from "../catalog";
import { RemoteSelect, required } from "./CatalogUI";

export default function IssueFields() {
  const mode = Form.useWatch("mode");
  return (
    <>
      <Form.Item name="id" hidden>
        <InputNumber />
      </Form.Item>
      <Form.Item name="name" label="发行名称" rules={required}>
        <Input autoFocus placeholder="请输入" maxLength={128} />
      </Form.Item>
      <Form.Item name="style_id" label="关联款式" rules={required}>
        <RemoteSelect resource="styles" placeholder="请选择" />
      </Form.Item>
      <ProForm.Group>
        <Form.Item
          name="series"
          label="系列归类（选填）"
          style={{ width: 328 }}
        >
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item
          name="mode"
          label="发行方式"
          rules={required}
          style={{ width: 328 }}
        >
          <Select
            options={["fixed", "period", "unlimited"].map((v) => ({
              value: v,
              label: statusNames[v],
            }))}
          />
        </Form.Item>
      </ProForm.Group>
      {mode === "fixed" && (
        <Form.Item name="total" label="固定发行总量" rules={required}>
          <InputNumber min={1} precision={0} style={{ width: "100%" }} />
        </Form.Item>
      )}
      {mode === "period" && (
        <>
          <GridRow gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item
                name="starts_at"
                label="销售开始（北京时间）"
                getValueProps={(v) => ({
                  value: typeof v === "string" ? inputDate(v) : v,
                })}
                normalize={(v) => (v ? inputISO(v) : undefined)}
                rules={required}
              >
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="ends_at"
                label="销售结束（北京时间）"
                getValueProps={(v) => ({
                  value: typeof v === "string" ? inputDate(v) : v,
                })}
                normalize={(v) => (v ? inputISO(v) : undefined)}
                rules={required}
              >
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </GridRow>
          <Form.Item
            name="counting_rule"
            label="有效数量核定规则"
            rules={required}
          >
            <Input.TextArea
              placeholder="明确取消、退款及跨期处理；预估量不作上限。"
              rows={3}
            />
          </Form.Item>
        </>
      )}
      <Form.Item
        name="description"
        label="发行说明与规格承诺"
        rules={required}
        extra="说明限量、规格/颜色限制及允许的例外；确认后普通维护不可追改。"
      >
        <Input.TextArea rows={3} maxLength={4000} />
      </Form.Item>
    </>
  );
}
