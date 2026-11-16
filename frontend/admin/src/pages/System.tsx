import TestBatches from "../components/TestBatches";
import { PageContainer } from "@ant-design/pro-components";
import { Tabs, Typography } from "antd";
import { RuntimeChecks } from "../RuntimeChecks";
import { Copy, returnPath } from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import { useLocation, history } from "@umijs/max";
import { fromPath, time } from "../catalog";
import { request } from "../api";
import AuditDetails from "../components/AuditDetails";
import AdminPasskeys from "../components/AdminPasskeys";
import { passkeysEnabled } from "../passkeys";
export default function System() {
  const location = useLocation();
  const source = returnPath("");
  return (
    <PageContainer title={source ? "系统管理" : false} onBack={source ? () => history.push(source) : undefined}>
      <Tabs
        className="section-tabs"
        size="small"
        activeKey={
          (new URLSearchParams(location.search).get("tab") || "audit").replace(/^users$/, "audit")
        }
        onChange={(tab) => history.replace(fromPath("/system?tab=" + tab, source))}
        items={[
          { key: "settings", label: "设置", children: <TestBatches /> },
          ...(passkeysEnabled() ? [{ key: "passkeys", label: "通行密钥", children: <AdminPasskeys /> }] : []),
          {
            key: "audit",
            label: "操作审计",
            children: (
              <ServerTable
                resource="audit"
                fitWidth
                columns={[
                  { title: "时间", width: 156, search: false, render: (_, r) => time(r.created_at) },
                  { title: "操作人", width: 108, dataIndex: "username", search: false, ellipsis: true },
                  { title: "操作", width: 180, dataIndex: "operation", search: false, ellipsis: true },
                  { title: "对象或结果关键词", dataIndex: "keyword", hideInTable: true },
                  { title: "操作筛选", dataIndex: "action", hideInTable: true, valueType: "select",
                    request: () => request<{value: string; label: string}[]>("/admin/catalog/audit/actions"),
                    fieldProps: { showSearch: true, optionFilterProp: "label" } },
                  { title: "操作人账号", dataIndex: "operator", hideInTable: true },
                  { title: "起日（北京时间）", dataIndex: "date_from", hideInTable: true, valueType: "date" },
                  { title: "末日（北京时间）", dataIndex: "date_to", hideInTable: true, valueType: "date" },
                  {
                    title: "对象",
                    width: 236,
                    search: false,
                    render: (_, r) => <Copy value={r.object_code} onClick={r.object_exists ? () => history.push(`/items/${r.target_id}?from=${encodeURIComponent(location.pathname + location.search)}`) : undefined} />,
                  },
                  {
                    title: "结果摘要",
                    search: false,
                    render: (_, r) => (
                      <Typography.Paragraph className="audit-row-summary" ellipsis>
                        {(r.summary !== r.operation && r.summary) || r.outcome || "未记录"}
                      </Typography.Paragraph>
                    ),
                  },
                  { title: "详情", width: 88, search: false, render: (_, r) => <AuditDetails event={r} /> },
                ]}
              />
            ),
          },
          { key: "runtime", label: "系统与环境", children: <RuntimeChecks /> },

        ]}
      />
    </PageContainer>
  );
}
