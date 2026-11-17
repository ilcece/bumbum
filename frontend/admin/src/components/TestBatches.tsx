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
  Switch,
} from "antd";
import { testBatch, setTestBatch } from "../testDataMode";
import { list } from "../catalog";
import type { TestBatchPreview, TestBatchRecord } from "../types/catalog";
import { request } from "../api";
import { ActionForm } from "./CatalogUI";
const cleanupLabels: Record<string, string> = {
  order: "订单", style: "款式", issue: "发行", physical: "实体物品",
  item: "数字物品", chip: "芯片", user: "合成账户", scan: "导入触碰",
};
const cleanupReceiptKey = (id: number) => `bumbum-test-batch-cleaned:${id}`;

export default function TestBatches() {
  const [rows, setRows] = useState<TestBatchRecord[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [selectionMissing, setSelectionMissing] = useState(false),
    [writable, setWritable] = useState(false),
    [revision, setRevision] = useState(0),
    [preview, setPreview] = useState<TestBatchPreview>();
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    list("test-batches", { page_size: 100 })
      .then((r) => {
        if (live) {
          // 清理回执跨数据范围切换保留，直到批次列表确认已清理。
          const currentRows = r.items.map((row) => {
            const key = cleanupReceiptKey(row.id);
            if (row.status === "deleted") sessionStorage.removeItem(key);
            if (row.status === "active" && sessionStorage.getItem(key) === "1")
              return { ...row, status: "deleted" as const };
            return row;
          });
          setRows(currentRows);
          setWritable(!!r.writable);
          setSelectionMissing(
            !!testBatch() &&
              r.total <= r.items.length &&
              !currentRows.some(
                (row) => row.id === testBatch() && row.status === "active",
              ),
          );
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [revision]);
  const active = rows.find((r) => r.status === "active");
  return (
    <Card title="测试数据">
      <Space orientation="vertical" style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          title="测试数据仅用于验收"
          description="仅影响当前浏览器标签页，各页面统一显示验收数据；关闭后恢复业务数据，不改变其他标签页或管理员的选择。不会删除数据或改变生产验证标记。合成样本不能证明实卡、认领或真实交付。"
        />
        {error && <Alert type="error" title={error} />}
        {!loading && !error && writable && !active && (
          <Alert
            type="info"
            showIcon
            title="尚无可用的验收数据"
            description="请先准备一套独立验收数据，再刷新并开启。这个开关只切换显示范围，不会自动生成数据，也不会恢复已清理的数据。"
          />
        )}
        {!loading && !error && selectionMissing && (
          <Alert
            type="warning"
            showIcon
            title="当前标签页仍开启着已失效的验收批次"
            description="原批次已不存在或已清理。请关闭下方测试数据开关，返回业务数据；旧选择不会自动切换到其他批次。"
          />
        )}
        <Space>
          <Typography.Text strong>开启测试数据</Typography.Text>
          <Switch
            aria-label="开启测试数据"
            checked={!!testBatch()}
            disabled={
              !testBatch() && (loading || !!error || !writable || !active)
            }
            onChange={(enabled) =>
              setTestBatch(enabled ? active?.id : undefined)
            }
          />
          <Button loading={loading} onClick={() => setRevision((x) => x + 1)}>
            刷新数据
          </Button>
        </Space>
        <Table<TestBatchRecord>
          rowKey="id"
          loading={loading}
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
                    danger
                    disabled={
                      loading || !!error || !writable || r.status !== "active"
                    }
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
                    {r.manifest?.items?.map((x) => (
                      <li key={x.item_id}>
                        <Typography.Text>{x.uid} · </Typography.Text>
                        {x.scenario}
                      </li>
                    ))}
                  </ul>
                  {!!r.manifest?.photos?.length && (
                    <details>
                      <summary>图片来源与许可</summary>
                      <ul>
                        {r.manifest.photos.map((photo) => (
                          <li key={photo.sha256}>
                            <a
                              href={photo.page}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {photo.style_name}
                            </a>
                            {` · ${photo.artist} · ${photo.license}`}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </details>
              ),
            },
          ]}
        />
        {!loading && !error && !writable && (
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
            onDone={(result) => {
              if (result.id === preview.id && result.status === "deleted") {
                sessionStorage.setItem(cleanupReceiptKey(result.id), "1");
                setRows((current) => current.map((row) =>
                  row.id === result.id ? { ...row, status: "deleted" as const } : row));
              }
              setPreview(undefined);
              if (testBatch() === preview.id) {
                setTestBatch();
                return;
              }
              setRevision((x) => x + 1);
            }}
            submitText="确认清理本批数据"
            submitDisabled={preview.conflicts.length > 0}
          >
            <Alert
              type={preview.conflicts.length ? "error" : "warning"}
              showIcon
              title={
                preview.conflicts.length
                  ? "存在批次外关联，禁止清理"
                  : "将删除清单中的本批数据及专用图片，保留审计。"
              }
              description={<>
                <div>批次 {rows.find((row) => row.id === preview.id)?.code ?? preview.id}</div>
                {Object.entries(preview.counts).map(([kind, count]) =>
                  `${cleanupLabels[kind] ?? kind} ${count}`).join("，")}
              </>}
            />
            <details>
              <summary>查看清理明细与关联冲突</summary>
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
