import React, { useEffect, useRef, useState } from "react";
import {
  PageContainer,
  ProTable,
  ModalForm,
  ProFormSelect,
  ProFormText,
  ProFormDigit,
  ProFormInstance,
} from "@ant-design/pro-components";
import { Alert, Button, Space, Tag } from "antd";
import { history } from "@umijs/max";
import { useStore } from "../data/store";
import { Item, itemStates, edition, issueText, userName } from "../data/domain";
import {
  go,
  required,
  saveQuery,
  queryState,
  useDataTable,
  tableRequest,
  useAction,
  ErrorState,
} from "../ui";
import SaleEditor from "../components/SaleEditor";
import RecordDrawer from "../components/RecordDrawer";
import { CopyValue, EditionValue, StatusTag, StyleCell } from "../components/RecordPresentation";
export default function Items() {
  const p = useStore(),
    d = p.data,
    q = queryState(),
    table = useDataTable(),
    action = useAction(),
    [create, setCreate] = useState(q.create === "1"),
    [issueId, setIssueId] = useState<string | undefined>(q.issueId),
    [selected, setSelected] = useState<React.Key[]>([]),
    [sale, setSale] = useState(false),
    [lastUid, setLastUid] = useState(""),
    [target, setTarget] = useState<{ kind: "items" | "chips"; id: number }>();
  const form = useRef<ProFormInstance | undefined>(undefined),
    issue = d.issues.find((i) => i.id === issueId),
    style = d.styles.find((s) => s.id === issue?.styleId);
  useEffect(() => {
    if (q.create) {
      const { create: _create, issueId: _issue, ...filters } = q;
      saveQuery(filters);
    }
  }, []);
  const suggest = (id?: string) => {
    const s = d.issues.find((i) => i.id === id),
      style = d.styles.find((x) => x.id === s?.styleId),
      prefix = style?.category === "jewelry" ? "JEW" : "FASH",
      used = new Set(
        d.items.filter((i) => i.issueId === id).map((i) => i.number),
      );
    let number = 1;
    while (used.has(number)) number++;
    let n =
      Math.max(
        0,
        ...d.items
          .filter((i) => i.uid.startsWith(prefix))
          .map((i) => Number(i.uid.slice(-6))),
      ) + 1;
    return {
      uid: `${prefix}-2026-${String(n).padStart(6, "0")}`,
      number: s?.mode === "timed" && !s.sealedAt ? undefined : number,
    };
  };
  useEffect(() => {
    if (lastUid) {
      const i = d.items.find((x) => x.uid === lastUid);
      if (i) {
        setLastUid("");
        go("/items/" + i.id);
      }
    }
  }, [lastUid, d.revision]);
  return (
    <PageContainer header={{ title: false, breadcrumb: {} }}>
      {p.readError ? (
        <ErrorState />
      ) : (
        <ProTable<Item>
          {...table}
          rowKey="id"
          headerTitle="数字物品档案"
          rowSelection={{ selectedRowKeys: selected, onChange: setSelected }}
          request={(v) =>
            tableRequest(
              d.items,
              v,
              (i) =>
                i.uid + " " + d.styles.find((s) => s.id === i.styleId)?.name + " " + d.chips.find(c => c.id === i.entities.find(e => !e.to)?.chipId)?.uid,
              (i, x) =>
                (!x.status || i.status === x.status) &&
                (!x.sold || String(i.sold) === x.sold) &&
                (!x.owner || (x.owner === "yes") === !!i.ownerId),
            )
          }
          toolBarRender={() => [
            <Button
              key="sale"
              disabled={!selected.length}
              onClick={() => setSale(true)}
            >
              批量售出确认{selected.length ? "（" + selected.length + "）" : ""}
            </Button>,
            <Button
              key="new"
              type="primary"
              onClick={() => {
                form.current?.resetFields();
                setIssueId(undefined);
                setCreate(true);
                action.clear();
              }}
            >
              登记数字物品
            </Button>,
          ]}
          columns={[
            { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { placeholder: "搜索物品编号、款式名称或芯片 UID" } },
            {
              title: "系统物品编号",
              dataIndex: "uid",
              search: false,
              render: (_, i) => (
                <CopyValue value={i.uid} onClick={() => setTarget({kind: "items", id: i.id})} />
              ),
            },
            {
              title: "商品款式",
              search: false,
              render: (_, i) => <StyleCell style={d.styles.find((s) => s.id === i.styleId)} />,
            },
            {
              title: "发行编号",
              search: false,
              render: (_, i) =>
                <EditionValue value={edition(
                  i,
                  d.issues.find((s) => s.id === i.issueId),
                )} />,
            },
            { title: "物品状态", dataIndex: "status", valueEnum: itemStates, render: (_, i) => <StatusTag value={itemStates[i.status]} /> },
            {
              title: "售出确认",
              dataIndex: "sold",
              valueEnum: { true: "已确认售出", false: "未确认售出" },
              render: (_, i) => (
                <Tag color={i.sold ? "blue" : "default"}>
                  {i.sold ? "已确认售出" : "未确认售出"}
                </Tag>
              ),
            },
            {
              title: "当前持有人",
              dataIndex: "owner",
              valueEnum: { yes: "已认领", no: "未认领" },
              render: (_, i) => i.ownerId ? <div>{userName(i.ownerId)}<div className="cell-secondary"><CopyValue value={i.ownerId} /></div></div> : <StatusTag value="未认领" />,
            },
            {
              title: "当前芯片",
              search: false,
              render: (_, i) => {
                const e = i.entities.find((e) => !e.to),
                  c = d.chips.find((c) => c.id === e?.chipId);
                return c ? (
                  <div><CopyValue value={c.uid} onClick={() => setTarget({kind: "chips", id: c.id})} /><div style={{marginTop: 6}}><StatusTag value={c.configuredAt ? "演示核验就绪" : "待配置"} /></div></div>
                ) : (
                  <StatusTag value="未关联" />
                );
              },
            },
            { title: "操作", valueType: "option", fixed: "right", render: (_, i) => <a onClick={() => setTarget({ kind: "items", id: i.id })}>查看</a> },
          ]}
        />
      )}
      <ModalForm
        title="登记数字物品"
        formRef={form}
        open={create}
        onOpenChange={setCreate}
        modalProps={{ destroyOnHidden: true }}
        initialValues={issueId ? { issueId, ...suggest(issueId) } : {}}
        onValuesChange={(change: any) => {
          if (change.issueId) {
            setIssueId(change.issueId);
            form.current?.setFieldsValue(suggest(change.issueId));
          }
        }}
        onFinish={async (v) => {
          const ok = action.run(
            "item",
            {
              ...v,
              number:
                issue?.mode === "timed" && !issue.sealedAt ? null : v.number,
            },
            "物品草稿已登记，可继续绑定芯片",
          );
          if (ok) {
            setCreate(false);
            setLastUid(v.uid);
          }
          return ok;
        }}
        submitter={{
          searchConfig: { submitText: "登记并查看物品" },
          submitButtonProps: { disabled: action.unknown },
        }}
      >
        <ProFormSelect
          name="issueId"
          label="关联发行约定"
          rules={[{ required: true }]}
          options={d.issues
            .filter((i) => i.status === "confirmed")
            .map((i) => ({
              value: i.id,
              label: i.name + " · " + issueText(i),
            }))}
        />
        <Alert
          type="info"
          title={
            style
              ? style.name + " · 类别从款式引用"
              : "先选择已确认发行，自动取得款式和类别"
          }
          style={{ marginBottom: 16 }}
        />
        <ProFormText name="uid" label="系统物品编号" rules={required} />
        <ProFormDigit
          name="number"
          label="本件正式序号"
          disabled={issue?.mode === "timed" && !issue.sealedAt}
          min={1}
          fieldProps={{ precision: 0 }}
          rules={
            issue?.mode === "timed" && !issue.sealedAt
              ? []
              : [{ required: true }]
          }
          extra={
            issue?.mode === "timed" && !issue.sealedAt
              ? "先准备稳定身份，正式编号在封版时确定"
              : "本次发行内唯一，不能超固定/封版总量。"
          }
        />
        {action.feedback}
      </ModalForm>
      <SaleEditor
        ids={selected.map(Number)}
        open={sale}
        onOpenChange={setSale}
      />
      <RecordDrawer target={target} onClose={() => setTarget(undefined)} />
    </PageContainer>
  );
}
