import { PageContainer } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { RemoteSelect, returnPath } from "../components/CatalogUI";
import { ActivityActor, ActivityItem, activityLabels } from "../components/ItemActivity";
import ServerTable from "../components/ServerTable";
import { time } from "../catalog";

export default function Activity() {
  const location = useLocation();
  const scopedTaps = new URLSearchParams(location.search).has("scope");
  return (
    <PageContainer title="用户动态" onBack={() => history.push(returnPath("/overview"))}>
      <ServerTable resource="activity" columns={[
        { title: "物品编号", dataIndex: "item_uid", hideInTable: true },
        { title: "发行", dataIndex: "issue_id", hideInTable: true, search: scopedTaps ? false : undefined, formItemRender: () => <RemoteSelect resource="issues" /> },
        { title: "起日（北京时间）", dataIndex: "date_from", valueType: "date", hideInTable: true },
        { title: "末日（北京时间）", dataIndex: "date_to", valueType: "date", hideInTable: true },
        { title: "时间", dataIndex: "occurred_at", search: false, render: (_, row) => time(row.occurred_at) },
        { title: "动态", dataIndex: "event", valueType: "select", valueEnum: activityLabels, search: scopedTaps ? false : undefined },
        { title: "账户 UID", dataIndex: "user_uid", search: false, render: (_, row) => <ActivityActor row={row} /> },
        { title: "物品", search: false, render: (_, row) => <ActivityItem row={row} /> },
      ]} />
    </PageContainer>
  );
}
