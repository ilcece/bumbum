import { PageContainer } from "@ant-design/pro-components";
import { Tabs } from "antd";
import { RuntimeChecks } from "../RuntimeChecks";
import { Copy } from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import { time } from "../catalog";
export default function System() {
  return (
    <PageContainer title={false}>
      <Tabs
        items={[
          {
            key: "audit",
            label: "操作日志",
            children: (
              <ServerTable
                resource="audit"
                columns={[
                  { title: "关键词", dataIndex: "keyword", hideInTable: true },
                  { title: "操作", dataIndex: "action", search: false },
                  { title: "操作者", dataIndex: "username", search: false },
                  {
                    title: "对象",
                    search: false,
                    render: (_, r) => <Copy value={r.target_id} />,
                  },
                  {
                    title: "时间",
                    search: false,
                    render: (_, r) => time(r.created_at),
                  },
                  {
                    title: "必要记录",
                    search: false,
                    render: (_, r) => (
                      <details>
                        <summary>查看记录</summary>
                        <pre style={{ whiteSpace: "pre-wrap" }}>
                          {JSON.stringify(r.detail, null, 2)}
                        </pre>
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
