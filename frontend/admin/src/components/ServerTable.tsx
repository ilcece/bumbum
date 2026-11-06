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
}: {
  resource: string;
  columns: ProColumns<Row>[];
  extra?: React.ReactNode[];
  refresh?: number;
  filters?: Record<string, any>;
}) {
  const [error, setError] = useState("");
  const location = useLocation(),
    q = new URLSearchParams(location.search),
    ref = useRef<ActionType | undefined>(undefined);
  const saved = Object.fromEntries(
    [...q.entries()].filter(([k]) => !["tab", "from"].includes(k)),
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
        columns={columns}
        params={{ ...filters, _refresh: refresh }}
        search={{ labelWidth: "auto", defaultCollapsed: true }}
        form={{ initialValues: saved }}
        toolBarRender={() => extra || []}
        pagination={{
          pageSize: 10,
          showSizeChanger: false,
          current: Number(q.get("page") || 1),
          onChange: (page) => update({ ...saved, page }),
        }}
        scroll={{ x: 850 }}
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
