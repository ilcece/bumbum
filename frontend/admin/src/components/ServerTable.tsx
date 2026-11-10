import React, { useRef, useState } from "react";
import { ProTable, ActionType, ProColumns } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { Alert } from "antd";
import { list, Row } from "../catalog";
export default function ServerTable({
  resource,
  columns,
  extra,
  refresh = 0,
  filters = {},
  rowSelection,
}: {
  resource: string;
  columns: ProColumns<Row>[];
  extra?: React.ReactNode[];
  refresh?: number;
  filters?: Record<string, any>;
  rowSelection?: React.ComponentProps<typeof ProTable<Row>>["rowSelection"];
}) {
  const [error, setError] = useState("");
  const location = useLocation(),
    q = new URLSearchParams(location.search),
    ref = useRef<ActionType | undefined>(undefined);
  const saved = Object.fromEntries(
    [...q.entries()].filter(([k]) => !["tab", "from", "create"].includes(k)),
  );
  const update = (params: Record<string, any>) => {
    const next = new URLSearchParams();
    if (q.get("tab")) next.set("tab", q.get("tab")!);
    for (const [k, v] of Object.entries(params))
      if (v !== undefined && v !== null && v !== "") next.set(k, String(v));
    history.replace({
      pathname: location.pathname,
      search: next.toString() ? "?" + next : "",
    });
  };
  return (
    <>
      {" "}
      {error && <Alert type="error" title={error} />}
      <ProTable<Row>
        actionRef={ref}
        rowKey="id"
        rowSelection={rowSelection}
        cardProps={{ size: "small", variant: "outlined" }}
        options={{ density: true, fullScreen: false, reload: true }}
        columns={columns}
        headerTitle={
          (
            {
              items: "数字物品档案",
              chips: "芯片档案",
              styles: "共用款式资料",
              issues: "发行承诺与核定结果",
              users: "账户与持有",
              audit: "操作日志",
              activity: "用户动态",
            } as Record<string, string>
          )[resource]
        }
        size="middle"
        params={{ ...filters, _refresh: refresh }}
        search={{
          layout: "vertical",
          labelWidth: "auto",
          defaultCollapsed: true,
          span: { xs: 24, sm: 12, md: 8, lg: 8, xl: 6, xxl: 6 },
        }}
        form={{ initialValues: saved, layout: "vertical" }}
        toolBarRender={() => extra || []}
        pagination={{
          pageSize: 10,
          showSizeChanger: false,
          current: Number(q.get("page") || 1),
          onChange: (page) => update({ ...saved, page }),
        }}
        scroll={{ x: "max-content" }}
        onSubmit={(p) => update({ ...p, page: 1 })}
        onReset={() => update({ page: 1 })}
        request={async (p) => {
          const { current, pageSize, _refresh, ...query } = p;
          try {
            const r = await list(resource, {
              ...saved,
              ...query,
              page: current || saved.page || 1,
              page_size: pageSize || 10,
            });
            if (r.page !== Number(current || saved.page || 1))
              update({ ...saved, ...query, page: r.page });
            setError("");
            return { data: r.items, total: r.total, success: true };
          } catch (e) {
            setError(e instanceof Error ? e.message : "查询未完成");
            return { data: [], total: 0, success: false };
          }
        }}
      />
    </>
  );
}
