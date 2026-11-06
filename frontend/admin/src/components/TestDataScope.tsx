import { useEffect, useState } from "react";
import { Alert, Select, Space, Tag } from "antd";
import { list, Row } from "../catalog";
export function TestSource({ record }: { record?: Row }) {
  return record?.test_batch_id ? (
    <Alert
      type="warning"
      showIcon
      title={`测试数据 · 批次 ${record.test_batch_id}`}
      description="本批包含合成配置、持有、交付及触碰样本，不代表真实认领或实卡验证；可按批次剔除或清理。"
    />
  ) : null;
}
export function BatchSelect({
  value,
  onChange,
}: {
  value?: number;
  onChange?: (v?: number) => void;
}) {
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    list("test-batches", { page_size: 100 })
      .then((r) => {
        if (live) setRows(r.items.filter((x) => x.status === "active"));
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, []);
  return (
    <>
      <Select
        aria-label="测试批次"
        placeholder="选择测试批次"
        style={{ minWidth: 200 }}
        allowClear
        value={value}
        onChange={onChange}
        options={rows.map((r) => ({
          value: r.id,
          label: `${r.name} · ${r.id}`,
        }))}
      />
      {error && <Alert type="error" title={error} />}
    </>
  );
}
export function DataScope({
  scope,
  batch,
  onChange,
}: {
  scope: string;
  batch?: number;
  onChange: (scope: string, batch?: number) => void;
}) {
  return (
    <Space wrap>
      <Select
        aria-label="数据范围"
        value={scope}
        options={[
          { value: "business", label: "业务数据" },
          { value: "test", label: "测试数据" },
          { value: "all", label: "全部数据" },
        ]}
        onChange={(v) => onChange(v, v === "business" ? undefined : batch)}
      />
      {scope !== "business" && (
        <BatchSelect value={batch} onChange={(v) => onChange(scope, v)} />
      )}
    </Space>
  );
}
export function TestTag({ id }: { id?: number }) {
  return id ? <Tag color="orange">测试数据 · {id}</Tag> : null;
}
