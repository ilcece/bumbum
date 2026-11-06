import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  InputNumber,
  Space,
  Table,
  Typography,
  Tag,
} from "antd";
import { history } from "@umijs/max";
import { list, Row } from "../catalog";
import { request } from "../api";
import { ActionForm } from "./CatalogUI";
export default function TestBatches() {
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [writable, setWritable] = useState(false),
    [revision, setRevision] = useState(0),
    [preview, setPreview] = useState<Row>();
  useEffect(() => {
    let live = true;
    list("test-batches", { page_size: 100 })
      .then((r) => {
        if (live) {
          setRows(r.items);
          setWritable(!!(r as any).writable);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [revision]);
  return (
    <Card title="测试数据">
      <Space orientation="vertical" style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          title="测试批次与生产验证开关分开保存"
          description="灌入通过受控测试命令执行；可查看、剔除或整批清理。合成数据不能作为真实卡、认领或交付证据。"
        />
        {error && <Alert type="error" title={error} />}
        <Button onClick={() => setRevision((x) => x + 1)}>刷新批次</Button>
        <Table<Row>
          rowKey="id"
          dataSource={rows}
          columns={[
            { title: "批次", dataIndex: "name" },
            { title: "编号", dataIndex: "code" },
            {
              title: "状态",
              render: (_, r) => (
                <Tag color={r.status === "active" ? "orange" : "default"}>
                  {r.status === "active" ? "可验收" : "已清理"}
                </Tag>
              ),
            },
            {
              title: "操作",
              render: (_, r) => (
                <Space wrap>
                  <Button
                    onClick={() =>
                      history.push(
                        `/items?data_scope=test&test_batch_id=${r.id}`,
                      )
                    }
                  >
                    查看本批物品
                  </Button>
                  <Button
                    onClick={() =>
                      history.push(
                        `/overview?data_scope=test&test_batch_id=${r.id}`,
                      )
                    }
                  >
                    查看本批统计
                  </Button>
                  <Button
                    danger
                    disabled={!writable || r.status !== "active"}
                    onClick={async () => {
                      try {
                        setPreview(
                          await request(
                            `/admin/catalog/test-batches/${r.id}/preview`,
                          ),
                        );
                        setError("");
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    清理本批数据
                  </Button>
                </Space>
              ),
            },
            {
              title: "场景说明",
              render: (_, r) => (
                <details>
                  <summary>查看样本与预期值</summary>
                  <Typography.Paragraph>
                    {r.manifest?.warning}
                  </Typography.Paragraph>
                  <Typography.Paragraph>
                    初始数字身份：{r.manifest?.expected_initial?.items}
                    ；生命周期触碰：
                    {r.manifest?.expected_initial?.lifecycle_taps}；售出后触碰：
                    {r.manifest?.expected_initial?.sold_taps}
                    。人工操作后统计会变化。
                  </Typography.Paragraph>
                  <ul>
                    {r.manifest?.items?.map((x: any) => (
                      <li key={x.item_id}>
                        <Button
                          type="link"
                          onClick={() => history.push(`/items/${x.item_id}`)}
                        >
                          {x.uid}
                        </Button>
                        {x.scenario}
                      </li>
                    ))}
                  </ul>
                </details>
              ),
            },
          ]}
        />
        {!writable && (
          <Typography.Text type="secondary">
            当前环境不允许测试数据写操作。
          </Typography.Text>
        )}
        {preview && (
          <ActionForm
            title="确认整批清理"
            action="clearTestBatch"
            initial={{ batch_id: preview.id, confirmed: false }}
            onClose={() => setPreview(undefined)}
            onDone={() => {
              setPreview(undefined);
              setRevision((x) => x + 1);
            }}
            submitText="确认清理本批数据"
          >
            <Alert
              type={preview.conflicts.length ? "error" : "warning"}
              title={
                preview.conflicts.length
                  ? "存在批次外关联，禁止清理"
                  : "将删除本批物品、芯片、合成账户和专用图片；审计保留。"
              }
              description={Object.entries(preview.counts)
                .map(
                  ([k, v]) =>
                    `${({ style: "款式", issue: "发行", item: "物品", chip: "芯片", user: "合成账户", scan: "导入触碰" } as any)[k]} ${v}`,
                )
                .join("，")}
            />
            <details>
              <summary>查看清理对象ID与冲突</summary>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  maxHeight: 240,
                  overflow: "auto",
                }}
              >
                {JSON.stringify(
                  preview.conflicts.length
                    ? preview.conflicts
                    : preview.objects,
                  null,
                  2,
                )}
              </pre>
            </details>
            <Form.Item name="batch_id" hidden>
              <InputNumber />
            </Form.Item>
            <Typography.Paragraph>
              结果未知时先核对回执，不重复发起新请求。
            </Typography.Paragraph>
            <Form.Item
              name="confirmed"
              valuePropName="checked"
              rules={[
                {
                  validator: (_, v) =>
                    v ? Promise.resolve() : Promise.reject("请先确认清理范围"),
                },
              ]}
            >
              <Checkbox>我已核对清单，确认删除此批数据</Checkbox>
            </Form.Item>
          </ActionForm>
        )}
      </Space>
    </Card>
  );
}
