import { PageContainer } from "@ant-design/pro-components";
import ServerTable from "../components/ServerTable";
import UserIdentity from "../components/UserIdentity";

export default function Users() {
  return <PageContainer title={false}>
    <ServerTable resource="users" columns={[
      { title: "UID 或昵称", dataIndex: "keyword", hideInTable: true },
      { title: "账户 UID", search: false, render: (_, r) => <UserIdentity uid={r.public_uid} /> },
      { title: "昵称", dataIndex: "nickname", search: false },
      { title: "联系方式（脱敏）", dataIndex: "phone", search: false },
      { title: "当前持有物品", dataIndex: "held_items", search: false },
    ]} />
  </PageContainer>;
}
