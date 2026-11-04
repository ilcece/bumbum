import { useEffect, useRef, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  Row,
  Select,
  Space,
} from "antd";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
// 复用 Make 的常用/高级筛选布局，条件继续提交给原有服务端接口。
export function InventorySearch({
  kind,
  initialValues,
  onFinish,
  onReset,
  busy,
}: {
  kind: "items" | "chips";
  initialValues: Record<string, unknown>;
  onFinish: (values: Record<string, unknown>) => void;
  onReset: () => void;
  busy: boolean;
}) {
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const [form] = Form.useForm();
  const [expanded, setExpanded] = useState(false);
  const select = (
    name: string,
    label: string,
    options: Record<string, string>,
  ) => (
    <Col key={name} xs={24} sm={12} lg={6}>
      <Form.Item name={name} label={label}>
        <Select
          allowClear
          placeholder="全部"
          options={Object.entries(options).map(([value, label]) => ({
            value,
            label,
          }))}
        />
      </Form.Item>
    </Col>
  );
  return (
    <Card size="small" styles={{ body: { padding: "16px 20px" } }}>
      <Form
        className="make-query"
        form={form}
        initialValues={initialValues}
        layout="vertical"
        onFinish={() => {
          // 收起的高级字段仍属于已提交查询；官方Form默认只回传已挂载字段。
          if (alive.current) onFinish(form.getFieldsValue(true));
        }}
        onKeyDown={(event) => {
          // 日期框回车先交给Picker确认选择，阻止浏览器同时提交整张查询表单。
          if (
            event.key === "Enter" &&
            (event.target as HTMLElement).closest(".ant-picker")
          )
            event.preventDefault();
        }}
        disabled={busy}
      >
        <Row gutter={[12, 12]} align="bottom">
          <Col xs={24} lg={8}>
            <Form.Item name="keyword" label="关键词">
              <Input
                allowClear
                maxLength={128}
                placeholder={
                  kind === "items"
                    ? "物品编号、款式、名称或关联芯片UID"
                    : "UID、关联物品编号或名称"
                }
              />
            </Form.Item>
          </Col>
          {select("project", "项目", {
            fashion: "服装",
            jewelry: "饰品",
            ...(kind === "chips" ? { unassigned: "未分配" } : {}),
          })}
          {select(
            "status",
            "状态",
            kind === "items"
              ? {
                  draft: "草稿",
                  active: "启用",
                  disabled: "停用",
                  archived: "归档",
                }
              : {
                  pending: "待绑定",
                  bound: "已绑定",
                  disabled: "停用",
                  lost: "丢失",
                },
          )}
          <Col xs={24} lg={4}>
            <Space wrap>
              <Button
                type="primary"
                htmlType="submit"
                icon={<SearchOutlined aria-hidden />}
              >
                查询
              </Button>
              <Button
                onClick={() => {
                  form.resetFields();
                  onReset();
                }}
                icon={<ReloadOutlined aria-hidden />}
              >
                重置
              </Button>
              <Button type="link" onClick={() => setExpanded((v) => !v)}>
                {expanded ? "收起" : "展开"}
              </Button>
            </Space>
          </Col>
        </Row>
        {expanded && (
          <Row
            gutter={[12, 12]}
            style={{
              marginTop: 16,
              paddingTop: 16,
              borderTop: "1px solid #f1f5f9",
            }}
          >
            {kind === "items" ? (
              select("has_chip", "关联芯片", {
                true: "已关联",
                false: "未关联",
              })
            ) : (
              <>
                <Col xs={24} lg={6}>
                  <Form.Item name="batch_no" label="批次">
                    <Input maxLength={64} />
                  </Form.Item>
                </Col>
                {select("registration_source", "首次登记来源", {
                  manual: "网页手工",
                  nfc_cool: "手机扫描",
                  unknown: "历史未知",
                })}
                {select("has_item", "关联物品", {
                  true: "已关联",
                  false: "未关联",
                })}
                {select("keys_generated", "密钥生成", {
                  true: "已生成",
                  false: "未生成",
                })}
                {select("provisioned", "配置核验", {
                  true: "已核验",
                  false: "未核验",
                })}
              </>
            )}
            {(kind === "items"
              ? ["created", "updated"]
              : ["created", "updated", "provisioned"]
            ).map((key, index) => (
              <Col xs={24} lg={12} key={key}>
                <Form.Item
                  name={`${key}_range`}
                  label={
                    [
                      kind === "items"
                        ? "创建日期（北京时间）"
                        : "登记日期（北京时间）",
                      "更新日期（北京时间）",
                      "核验日期（北京时间）",
                    ][index]
                  }
                >
                  <DatePicker.RangePicker allowEmpty={[true, true]} />
                </Form.Item>
              </Col>
            ))}
          </Row>
        )}
      </Form>
    </Card>
  );
}
