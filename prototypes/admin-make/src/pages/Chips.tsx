import React, { useEffect, useState } from "react";
import {
  PageContainer,
  ProTable,
  ModalForm,
  ProFormText,
} from "@ant-design/pro-components";
import { Button, Tag, Space } from "antd";
import { useStore } from "../data/store";
import { Chip, chipStates, timeText } from "../data/domain";
import {
  required,
  go,
  useAction,
  useDataTable,
  tableRequest,
  ErrorState,
} from "../ui";
export default function Chips() {
  const p = useStore(),
    d = p.data,
    table = useDataTable(),
    a = useAction(),
    [create, setCreate] = useState(false),
    [lastUid, setLastUid] = useState("");
  useEffect(() => {
    if (lastUid) {
      const c = d.chips.find((c) => c.uid === lastUid);
      if (c) {
        setLastUid("");
        go("/chips/" + c.id);
      }
    }
  }, [lastUid, d.revision]);
  return (
    <PageContainer
      title="芯片管理"
      subTitle="登记、首次关联、配置与当前服务状态"
    >
      <div className="page-stack">
        {a.feedback}
        {p.readError ? (
          <ErrorState />
        ) : (
          <ProTable<Chip>
            {...table}
            rowKey="id"
            headerTitle="芯片档案"
            request={(v) =>
              tableRequest(
                [...d.chips].sort(
                  (a, b) =>
                    b.createdAt.localeCompare(a.createdAt) || b.id - a.id,
                ),
                v,
                (c) => c.uid + " " + c.batch,
                (c, x) =>
                  (!x.state || c.state === x.state) &&
                  (!x.source || c.source === x.source) &&
                  (!x.configured ||
                    (x.configured === "yes") === !!c.configuredAt),
              )
            }
            toolBarRender={() => [
              <Button
                data-demo-only
                key="webhook"
                onClick={() => {
                  const uid =
                    "04CC" +
                    Date.now().toString(16).slice(-10).padStart(10, "0");
                  a.run(
                    "register",
                    { uid, source: "nfc_cool", batch: "WEBHOOK-DEMO" },
                    "已登记合成Webhook样例，未请求真实服务",
                  );
                }}
              >
                〔演示〕Webhook登记
              </Button>,
              <Button
                key="new"
                type="primary"
                onClick={() => {
                  a.clear();
                  setCreate(true);
                }}
              >
                手工登记芯片
              </Button>,
            ]}
            columns={[
              { title: "关键词", dataIndex: "keyword", hideInTable: true },
              {
                title: "芯片UID",
                dataIndex: "uid",
                search: false,
                render: (_, c) => (
                  <Button type="link" onClick={() => go("/chips/" + c.id)}>
                    {c.uid}
                  </Button>
                ),
              },
              { title: "批次", dataIndex: "batch", search: false },
              {
                title: "首次来源",
                dataIndex: "source",
                valueEnum: {
                  manual: "手工",
                  nfc_cool: "NFC.cool",
                  unknown: "未记录",
                },
              },
              {
                title: "服务状态",
                dataIndex: "state",
                valueEnum: chipStates,
                render: (_, c) => (
                  <Space>
                    <Tag
                      color={
                        c.state === "bound"
                          ? "blue"
                          : c.state === "lost"
                            ? "orange"
                            : "default"
                      }
                    >
                      {chipStates[c.state]}
                    </Tag>
                    {c.candidateFor && <Tag>候选准备</Tag>}
                  </Space>
                ),
              },
              {
                title: "配置状态",
                dataIndex: "configured",
                valueEnum: { yes: "已核验", no: "待核验" },
                render: (_, c) => (c.configuredAt ? "演示核验就绪" : "待配置"),
              },
              {
                title: "关联物品",
                search: false,
                render: (_, c) => {
                  const i = d.items.find((i) => i.id === c.itemId);
                  return i ? (
                    <Button type="link" onClick={() => go("/items/" + i.id)}>
                      {i.uid}
                    </Button>
                  ) : c.candidateFor ? (
                    "候选未生效"
                  ) : (
                    "未关联"
                  );
                },
              },
              {
                title: "登记时间",
                search: false,
                render: (_, c) => timeText(c.createdAt),
              },
            ]}
          />
        )}
      </div>
      <ModalForm
        title="手工登记芯片"
        open={create}
        onOpenChange={setCreate}
        modalProps={{ destroyOnHidden: true }}
        onFinish={async (v) => {
          const ok = a.run("register", v);
          if (ok) {
            setCreate(false);
            setLastUid(
              v.uid
                .replace(/[^0-9a-f]/gi, "")
                .toUpperCase()
                .match(/../g)
                ?.join(":") || "",
            );
          }
          return ok;
        }}
        submitter={{
          searchConfig: { submitText: "登记并查看" },
          submitButtonProps: { disabled: a.unknown },
        }}
      >
        <ProFormText
          name="uid"
          label="芯片UID"
          rules={required}
          placeholder="04:AA:BB:CC:DD:EE:01"
        />
        <ProFormText
          name="batch"
          label="批次（选填）"
          fieldProps={{ maxLength: 64 }}
        />
        {a.feedback}
      </ModalForm>
    </PageContainer>
  );
}
