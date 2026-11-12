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
import StyleEditor from "./StyleEditor";
import { CopyValue, StatusTag, StyleCell } from "../components/RecordPresentation";
export default function Catalog() {
  const p = useStore(),
    table = useDataTable(),
    [tab, setTab] = useState(queryState().tab || "styles"),
    [editId, setEditId] = useState<string>();
  const d = p.data;
  const styleColumns: ProColumns<Style>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { placeholder: "搜索款式编号或名称" } },
    { title: "款式编号", dataIndex: "code", search: false, render: (_, s) => <CopyValue value={s.code} /> },
    { title: "商品款式", dataIndex: "name", search: false, render: (_, s) => <StyleCell style={s} onClick={() => setEditId(s.id)} /> },
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
        <a key="edit" onClick={() => setEditId(s.id)}>
          维护资料
        </a>,
        <a key="issue" onClick={() => go("/catalog/issue/new?styleId=" + s.id)}>
          建立发行约定
        </a>,
      ],
    },
  ];
  const issueColumns: ProColumns<Issue>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { placeholder: "搜索发行名称、系列或款式编号" } },
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
      render: (_, i) => <StatusTag value={i.status === "confirmed" ? "已确认" : "草案"} />,
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
      header={{ title: false, breadcrumb: {} }}
    >
      <Tabs
        className="section-tabs"
        size="small"
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
      {editId && <StyleEditor key={editId} styleId={editId} modalMode onClose={() => setEditId(undefined)} />}
    </PageContainer>
  );
}
