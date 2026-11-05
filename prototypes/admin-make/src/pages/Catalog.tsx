import React, { useState } from "react";
import {
  PageContainer,
  ProTable,
  ProColumns,
} from "@ant-design/pro-components";
import { Button, Tabs, Tag, Space } from "antd";
import { history } from "@umijs/max";
import { useStore } from "../data/store";
import {
  Style,
  Issue,
  categoryNames,
  issueText,
  modeNames,
} from "../data/domain";
import { go, queryState, useDataTable, tableRequest, ErrorState } from "../ui";
export default function Catalog() {
  const p = useStore(),
    table = useDataTable(),
    [tab, setTab] = useState(queryState().tab || "styles");
  const d = p.data;
  const styleColumns: ProColumns<Style>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true },
    { title: "款式编号", dataIndex: "code", search: false },
    { title: "名称", dataIndex: "name", search: false },
    { title: "物品类别", dataIndex: "category", valueEnum: categoryNames },
    {
      title: "关联发行",
      search: false,
      render: (_, s) => d.issues.filter((i) => i.styleId === s.id).length,
    },
    {
      title: "引用物品",
      search: false,
      render: (_, s) => d.items.filter((i) => i.styleId === s.id).length,
    },
    {
      title: "操作",
      valueType: "option",
      render: (_, s) => [
        <a key="edit" onClick={() => go("/catalog/style/" + s.id)}>
          维护资料
        </a>,
        <a key="issue" onClick={() => go("/catalog/issue/new?styleId=" + s.id)}>
          建立发行约定
        </a>,
      ],
    },
  ];
  const issueColumns: ProColumns<Issue>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true },
    { title: "发行约定", dataIndex: "name", search: false },
    {
      title: "款式",
      search: false,
      render: (_, i) => d.styles.find((s) => s.id === i.styleId)?.name,
    },
    { title: "发行方式", dataIndex: "mode", valueEnum: modeNames },
    { title: "发行总量", search: false, render: (_, i) => issueText(i) },
    {
      title: "确认状态",
      dataIndex: "status",
      valueEnum: { draft: "草案", confirmed: "已确认" },
    },
    {
      title: "引用物品",
      search: false,
      render: (_, i) => d.items.filter((x) => x.issueId === i.id).length,
    },
    {
      title: "操作",
      valueType: "option",
      render: (_, i) => (
        <a onClick={() => go("/catalog/issue/" + i.id)}>
          {i.status === "draft" ? "维护并确认" : "查看约定"}
        </a>
      ),
    },
  ];
  return (
    <PageContainer
      title="款式与发行"
      subTitle="先维护共用商品，再确认数字发行承诺"
    >
      <Tabs
        activeKey={tab}
        onChange={(t) => {
          setTab(t);
          history.replace("/catalog?tab=" + t);
        }}
        items={[
          { key: "styles", label: "款式资料" },
          { key: "issues", label: "发行约定" },
        ]}
      />
      {p.readError ? (
        <ErrorState />
      ) : tab === "styles" ? (
        <ProTable<Style>
          key="styles"
          {...table}
          rowKey="id"
          columns={styleColumns}
          request={(v) =>
            tableRequest(
              d.styles,
              v,
              (s) => s.code + " " + s.name,
              (r, x) => !x.category || r.category === x.category,
            )
          }
          headerTitle="共用款式资料"
          toolBarRender={() => [
            <Button
              key="new"
              type="primary"
              onClick={() => go("/catalog/style/new")}
            >
              新建款式
            </Button>,
          ]}
        />
      ) : (
        <ProTable<Issue>
          key="issues"
          {...table}
          rowKey="id"
          columns={issueColumns}
          request={(v) =>
            tableRequest(
              d.issues,
              v,
              (i) =>
                i.name +
                " " +
                i.series +
                " " +
                d.styles.find((s) => s.id === i.styleId)?.code,
              (r, x) =>
                (!x.mode || r.mode === x.mode) &&
                (!x.status || r.status === x.status),
            )
          }
          headerTitle="发行承诺与核定结果"
          toolBarRender={() => [
            <Button
              key="new"
              type="primary"
              onClick={() => go("/catalog/issue/new")}
            >
              新建发行约定
            </Button>,
          ]}
        />
      )}
    </PageContainer>
  );
}
