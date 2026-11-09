import TestBatches from "../components/TestBatches";
import { PageContainer } from "@ant-design/pro-components";
import { Descriptions, Tabs, Typography } from "antd";
import { RuntimeChecks } from "../RuntimeChecks";
import { Copy } from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import { useLocation, history } from "@umijs/max";
import { statusNames, time } from "../catalog";
export default function System() {
  return (
    <PageContainer title={false}>
      <Tabs
        className="section-tabs"
        size="small"
        activeKey={
          new URLSearchParams(useLocation().search).get("tab") || "audit"
        }
        onChange={(tab) => history.replace("/system?tab=" + tab)}
        items={[
          { key: "settings", label: "设置", children: <TestBatches /> },
          {
            key: "audit",
            label: "操作审计",
            children: (
              <ServerTable
                resource="audit"
                columns={[
                  { title: "时间", search: false, render: (_, r) => time(r.created_at) },
                  { title: "操作人", dataIndex: "username", search: false },
                  { title: "操作", dataIndex: "operation", search: false },
                  { title: "对象或结果关键词", dataIndex: "keyword", hideInTable: true },
                  { title: "操作筛选", dataIndex: "action", hideInTable: true, valueType: "select", valueEnum: {
                    "catalog.installAssembly": { text: "确认安装" }, "catalog.sale": { text: "确认售出" },
                    "catalog.loseItem": { text: "登记挂失" }, "catalog.prepare": { text: "准备换新或转售" },
                    "catalog.complete": { text: "交付确认" }, "catalog.undoInstall": { text: "纠正安装" },
                    "catalog.issueClaimCode": { text: "首次发放认领码" }, "catalog.reissueClaimCode": { text: "核对后补发认领码" },
                  } },
                  { title: "操作人账号", dataIndex: "operator", hideInTable: true },
                  { title: "起日（北京时间）", dataIndex: "date_from", hideInTable: true, valueType: "date" },
                  { title: "末日（北京时间）", dataIndex: "date_to", hideInTable: true, valueType: "date" },
                  {
                    title: "对象",
                    search: false,
                    render: (_, r) => <Copy value={r.object_code} onClick={r.object_exists ? () => history.push(`/items/${r.target_id}?from=${encodeURIComponent(location.pathname + location.search)}`) : undefined} />,
                  },
                  {
                    title: "结果与依据",
                    search: false,
                    render: (_, r) => (
                      <details>
                        <summary>{r.summary || "历史记录，摘要未保存"}</summary>
                        <Descriptions column={1} size="small">
                          <Descriptions.Item label="结果">{r.outcome || "历史结果未单独记录"}</Descriptions.Item>
                          {r.detail?.evidence && <Descriptions.Item label="核对依据">{r.detail.evidence}</Descriptions.Item>}
                          {r.detail?.work_id && <Descriptions.Item label="办理记录">{r.detail.work_id}</Descriptions.Item>}
                          {r.detail?.candidate && <Descriptions.Item label="待交付组合">{auditSummary(r.detail.candidate)}</Descriptions.Item>}
                          {r.detail?.before && <Descriptions.Item label="操作前">{auditSummary(r.detail.before)}</Descriptions.Item>}
                          {r.detail?.after && <Descriptions.Item label="操作后">{auditSummary(r.detail.after)}</Descriptions.Item>}
                        </Descriptions>
                      </details>
                    ),
                  },
                ]}
              />
            ),
          },
          { key: "runtime", label: "系统与环境", children: <RuntimeChecks /> },
          {
            key: "users",
            label: "账户与持有",
            children: (
              <ServerTable
                resource="users"
                columns={[
                  { title: "关键词", dataIndex: "keyword", hideInTable: true },
                  { title: "账户ID", dataIndex: "id", search: false },
                  { title: "昵称", dataIndex: "nickname", search: false },
                  {
                    title: "联系方式（脱敏）",
                    dataIndex: "phone",
                    search: false,
                  },
                  {
                    title: "当前持有物品",
                    dataIndex: "held_items",
                    search: false,
                  },
                ]}
              />
            ),
          },
        ]}
      />
    </PageContainer>
  );
}

function auditSummary(value: Record<string, any>) {
  const parts = [
    statusNames[value.status], value.generation && `第 ${value.generation} 代`,
    value.physical_uid && `实体 ${value.physical_uid}`, value.chip_uid && `芯片 ${value.chip_uid}`,
    value.user_id && `持有人 U${value.user_id}`, value.lost_at && "已挂失",
    value.sold != null && (value.sold ? "已售出" : "未售出"),
    value.first_sold_at && `首次成交 ${time(value.first_sold_at)}`,
    value.quota_review ? "换新额度待核对" : value.quota_year && value.quota_used != null && `${value.quota_year} 年换新已用 ${value.quota_used} 次`,
  ];
  return <Typography.Text>{parts.filter(Boolean).join(" · ") || "档案已记录"}</Typography.Text>;
}
