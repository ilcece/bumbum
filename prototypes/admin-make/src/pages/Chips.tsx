import React, { useEffect, useState } from "react";
import {
  PageContainer,
  ProTable,
  ModalForm,
  ProFormText,
  ProFormSwitch,
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
import RecordDrawer from "../components/RecordDrawer";
import { CopyValue, StatusTag } from "../components/RecordPresentation";
import { KeyConfigDialog } from "../components/ChipActions";
export default function Chips() {
  const p = useStore(),
    d = p.data,
    table = useDataTable(),
    a = useAction(),
    [create, setCreate] = useState(false),
    [lastUid, setLastUid] = useState(""),
    [target, setTarget] = useState<{ kind: "items" | "chips"; id: number }>(),
    [keyId, setKeyId] = useState<number>();
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
      header={{ title: false, breadcrumb: {} }}
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
                (c) => c.uid + " " + c.batch + " " + d.items.find(i => i.id === c.itemId)?.uid,
                (c, x) =>
                  (!x.state || c.state === x.state) &&
                  (!x.source || c.source === x.source) &&
                  (!x.isValidation || (x.isValidation === "yes") === !!c.isValidation) &&
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
              { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { placeholder: "搜索芯片 UID、批次或物品编号" } },
              {
                title: "芯片UID",
                dataIndex: "uid",
                search: false,
                render: (_, c) => (
                  <div><CopyValue value={c.uid} onClick={() => setTarget({kind: "chips", id: c.id})} />{c.isValidation && <div style={{marginTop: 4}}><StatusTag value="生产验证对象" /></div>}</div>
                ),
              },
              { title: "批次", dataIndex: "batch", search: false, render: (_, c) => <CopyValue value={c.batch} /> },
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
                    <StatusTag value={chipStates[c.state]} />
                    {c.candidateFor && <StatusTag value="候选准备" />}
                  </Space>
                ),
              },
              {
                title: "配置状态",
                dataIndex: "configured",
                valueEnum: { yes: "已核验", no: "待核验" },
                render: (_, c) => <StatusTag value={c.configuredAt ? "演示核验就绪" : "待配置"} />,
              },
              { title: "数据性质", dataIndex: "isValidation", hideInTable: true, valueEnum: { yes: "仅生产验证对象", no: "仅非验证对象" } },
              {
                title: "关联物品",
                search: false,
                render: (_, c) => {
                  const i = d.items.find((i) => i.id === c.itemId);
                  return i ? (
                    <CopyValue value={i.uid} onClick={() => setTarget({kind: "items", id: i.id})} />
                  ) : c.candidateFor ? (
                    <StatusTag value="候选未生效" />
                  ) : (
                    <StatusTag value="未关联" />
                  );
                },
              },
              { title: "操作", valueType: "option", fixed: "right", render: (_, c) => <Space><a onClick={() => setTarget({kind: "chips", id: c.id})}>查看</a><Button type="link" disabled={(!c.itemId && !c.candidateFor) || ["retired", "lost", "disabled"].includes(c.state)} onClick={() => setKeyId(c.id)}>密钥与配置</Button></Space> },
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
        <ProFormSwitch name="isValidation" label="生产验证对象" fieldProps={{ "aria-label": "生产验证对象" }} extra="开启后可直接删除验证对象，不受绑定、配置或服务状态限制。" />
        {a.feedback}
      </ModalForm>
      <RecordDrawer target={target} onClose={() => setTarget(undefined)} />
      {keyId != null && <KeyConfigDialog chipId={keyId} onClose={() => setKeyId(undefined)} />}
    </PageContainer>
  );
}
