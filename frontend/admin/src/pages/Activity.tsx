import { PageContainer } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { Copy, RemoteSelect } from "../components/CatalogUI";
import { activityLabels } from "../components/ItemActivity";
import ServerTable from "../components/ServerTable";
import UserIdentity from "../components/UserIdentity";
import { time } from "../catalog";

export default function Activity() {
  const location = useLocation();
  return (
    <PageContainer title="用户动态" onBack={() => history.push("/overview")}>
      <ServerTable resource="activity" columns={[
        { title: "物品编号", dataIndex: "item_uid", hideInTable: true },
        { title: "发行", dataIndex: "issue_id", hideInTable: true, formItemRender: () => <RemoteSelect resource="issues" /> },
        { title: "起日（北京时间）", dataIndex: "date_from", valueType: "date", hideInTable: true },
        { title: "末日（北京时间）", dataIndex: "date_to", valueType: "date", hideInTable: true },
        { title: "时间", dataIndex: "occurred_at", search: false, render: (_, row) => time(row.occurred_at) },
        { title: "动态", dataIndex: "event", valueType: "select", valueEnum: activityLabels },
        { title: "账户 UID", dataIndex: "user_uid", search: false, render: (_, row) => row.user_uid ? <UserIdentity uid={row.user_uid} /> : "匿名访客" },
        { title: "物品", search: false, render: (_, row) => <Copy value={row.item_uid} onClick={() => history.push(`/items/${row.item_id}?from=${encodeURIComponent(location.pathname + location.search)}`)} /> },
      ]} />
    </PageContainer>
  );
}
