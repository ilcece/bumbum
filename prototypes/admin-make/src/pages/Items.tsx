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
    [lastUid, setLastUid] = useState("");
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
    <PageContainer title="数字物品" subTitle="稳定身份、当前关联及必要历史">
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
                i.uid + " " + d.styles.find((s) => s.id === i.styleId)?.name,
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
            { title: "关键词", dataIndex: "keyword", hideInTable: true },
            {
              title: "系统物品编号",
              dataIndex: "uid",
              search: false,
              render: (_, i) => (
                <Button type="link" onClick={() => go("/items/" + i.id)}>
                  {i.uid}
                </Button>
              ),
            },
            {
              title: "商品款式",
              search: false,
              render: (_, i) => d.styles.find((s) => s.id === i.styleId)?.name,
            },
            {
              title: "发行编号",
              search: false,
              render: (_, i) =>
                edition(
                  i,
                  d.issues.find((s) => s.id === i.issueId),
                ),
            },
            { title: "物品状态", dataIndex: "status", valueEnum: itemStates },
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
              render: (_, i) => userName(i.ownerId),
            },
            {
              title: "当前芯片",
              search: false,
              render: (_, i) => {
                const e = i.entities.find((e) => !e.to),
                  c = d.chips.find((c) => c.id === e?.chipId);
                return c ? (
                  <Button type="link" onClick={() => go("/chips/" + c.id)}>
                    {c.uid}
                  </Button>
                ) : (
                  "未关联"
                );
              },
            },
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
    </PageContainer>
  );
}
