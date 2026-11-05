import React from "react";
import {
  PageContainer,
  ProCard,
  ProDescriptions,
  ProTable,
} from "@ant-design/pro-components";
import { Alert, Tabs, Tag } from "antd";
import { useStore } from "../data/store";
import { timeText } from "../data/domain";
import { ErrorState } from "../ui";
const actions: Record<string, string> = {
  style: "维护款式",
  issue: "维护发行草稿",
  confirmIssue: "确认发行",
  deleteIssue: "删除未引用发行",
  seal: "封版发行数量",
  item: "登记物品",
  assignIssue: "补齐原发行",
  register: "登记芯片",
  batch: "维护批次",
  bind: "首次绑定",
  keys: "演示密钥准备",
  configure: "演示配置核验",
  toggleItem: "启停物品",
  sale: "售出确认/更正",
  demoClaim: "演示首次认领",
  chipState: "芯片状态变更",
  prepare: "准备新绑定",
  complete: "确认接续",
  touch: "演示有效触碰",
};
export default function System() {
  const p = useStore();
  return (
    <PageContainer title="系统管理" subTitle="查看操作记录和原型连接状态">
      {p.readError ? (
        <ErrorState />
      ) : (
        <Tabs
          items={[
            {
              key: "audit",
              label: "操作审计",
              children: (
                <ProTable
                  rowKey="id"
                  headerTitle="本地演示操作记录"
                  search={false}
                  options={{ reload: true, density: true }}
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  dataSource={p.data.audits}
                  columns={[
                    { title: "发生时间", render: (_, r) => timeText(r.at) },
                    {
                      title: "操作",
                      render: (_, r) => actions[r.action] || r.action,
                    },
                    { title: "对象", dataIndex: "target" },
                    { title: "依据 / 范围", dataIndex: "detail" },
                  ]}
                />
              ),
            },
            {
              key: "diagnostics",
              label: "连接与范围",
              children: (
                <ProCard
                  size="small"
                  headerBordered
                  variant="outlined"
                  title="原型诊断"
                >
                  <Alert
                    type="info"
                    title="独立交互原型，全部为合成数据"
                    description="未连接正式后台、身份服务、真实芯片或电商平台。页面成功仅代表原型状态变更。"
                  />
                  <ProDescriptions
                    size="small"
                    bordered
                    column={1}
                    columns={[
                      {
                        title: "页面工程",
                        render: () =>
                          "官方 Ant Design Pro 工程结构 + Umi Max 路由与运行时",
                      },
                      { title: "正式业务API", render: () => <Tag>未连接</Tag> },
                      {
                        title: "真实配卡与验证",
                        render: () => <Tag>未执行</Tag>,
                      },
                      {
                        title: "当前数据",
                        render: () =>
                          p.data.importNote ||
                          "新版样例数据；仅保存在当前浏览器会话",
                      },
                      {
                        title: "保存状态",
                        render: () =>
                          p.storageError ||
                          "当前会话可保存；重置只影响新版演示数据",
                      },
                    ]}
                  />
                </ProCard>
              ),
            },
          ]}
        />
      )}
    </PageContainer>
  );
}
