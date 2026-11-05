import React, { useState } from "react";
import {
  PageContainer,
  ProCard,
  ProDescriptions,
  ModalForm,
  ProFormText,
  ProTable,
} from "@ant-design/pro-components";
import { Button, Space, Alert, Tag } from "antd";
import { history, useParams } from "@umijs/max";
import { useStore } from "../data/store";
import { chipStates, timeText, statistics } from "../data/domain";
import { useReturnPath, useAction, go, ErrorState } from "../ui";
import { CopyValue, StatusTag, DetailContainer } from "../components/RecordPresentation";
import {
  ProvisionPanel,
  BindEditor,
  StateEditor,
} from "../components/ChipActions";
export default function ChipDetail({ chipId, embedded = false }: { chipId?: number; embedded?: boolean }) {
  const p = useStore(),
    { id } = useParams(),
    c = p.data.chips.find((c) => c.id === (chipId ?? Number(id))),
    back = useReturnPath("/chips"),
    a = useAction(),
    [batch, setBatch] = useState(false),
    [bind, setBind] = useState(false),
    [state, setState] = useState<"disable" | "restore" | "lost" | null>(null);
  if (!c)
    return (
      <PageContainer title="芯片不存在" onBack={() => history.push("/chips")} />
    );
  const i = p.data.items.find((i) => i.id === c.itemId),
    events = p.data.touches.filter(
      (e) => e.chipId === c.id && e.valid && e.kind === "touch",
    );
  return (
    <DetailContainer
      embedded={embedded}
      title={<CopyValue value={c.uid} />}
      subTitle={<StatusTag value={chipStates[c.state]} />}
      onBack={() => history.push(back)}
      extra={!embedded && <Button onClick={() => history.push(back)}>返回来源</Button>}
    >
      <div className="page-stack">
        {a.feedback}
        {p.readError ? (
          <ErrorState />
        ) : (
          <>
            <ProCard
              size="small"
              headerBordered
              variant="outlined"
              title="芯片信息"
              extra={<Button onClick={() => setBatch(true)}>维护批次</Button>}
            >
              <ProDescriptions
                size="small"
                bordered
                style={{ marginBottom: 12 }}
                column={2}
                dataSource={c}
                columns={[
                  { title: "UID", dataIndex: "uid", copyable: true },
                  { title: "批次", render: () => <CopyValue value={c.batch} /> },
                  {
                    title: "首次登记来源",
                    render: () =>
                      c.source === "manual"
                        ? "手工"
                        : c.source === "nfc_cool"
                          ? "NFC.cool"
                          : "未记录",
                  },
                  { title: "登记时间", render: () => timeText(c.createdAt) },
                  { title: "服务状态", render: () => <StatusTag value={chipStates[c.state]} /> },
                  {
                    title: "配置状态",
                    render: () => <StatusTag value={c.configuredAt ? "演示核验就绪" : "待配置"} />,
                  },
                  {
                    title: "数字物品",
                    render: () =>
                      i ? (
                        <CopyValue value={i.uid} onClick={() => go("/items/" + i.id)} />
                      ) : (
                        <StatusTag value="未关联" />
                      ),
                  },
                  {
                    title: "关联用途",
                    render: () =>
                      c.state === "retired"
                        ? "历史芯片，已退出当前授权"
                        : c.candidateFor
                          ? "候选准备，未取得当前授权"
                          : "当前关联或待准备",
                  },
                ]}
              />
            </ProCard>
            {!i && !c.candidateFor && c.state === "pending" && (
              <ProCard
                size="small"
                headerBordered
                variant="outlined"
                title="首次关联"
              >
                <Button type="primary" onClick={() => setBind(true)}>
                  绑定数字物品
                </Button>
              </ProCard>
            )}
            {(i || c.candidateFor) && c.state !== "retired" && (
              <ProvisionPanel chipId={c.id} />
            )}
            <ProCard
              size="small"
              headerBordered
              variant="outlined"
              title="服务状态操作"
            >
              <Space wrap>
                {["bound", "pending"].includes(c.state) && !c.candidateFor && (
                  <Button danger onClick={() => setState("disable")}>
                    临时停用芯片
                  </Button>
                )}
                {c.state === "disabled" && (
                  <Button onClick={() => setState("restore")}>
                    恢复当前芯片
                  </Button>
                )}
                {i && ["bound", "disabled"].includes(c.state) && (
                  <Button danger onClick={() => setState("lost")}>
                    挂失当前芯片
                  </Button>
                )}
                {i && (
                  <Button onClick={() => go("/items/" + i.id)}>
                    到物品办理换新/转售
                  </Button>
                )}
                {c.state === "retired" && (
                  <Alert
                    type="info"
                    title="历史芯片只读，不能通过普通恢复或登记重新获得授权。"
                  />
                )}
                {c.state === "lost" && (
                  <Alert
                    type="warning"
                    title="保持挂失保护，解除条件另审；可从物品办理挂失换新。"
                  />
                )}
              </Space>
            </ProCard>
            <ProCard
              size="small"
              headerBordered
              variant="outlined"
              title={`本芯片有效触碰 · ${events.length}次`}
              extra={
                <Button
                  data-demo-only
                  onClick={() =>
                    a.run("touch", { chipId: c.id }, "已记录合成有效触碰")
                  }
                >
                  〔演示〕模拟此卡触碰
                </Button>
              }
            >
              <ProTable
                rowKey="id"
                search={false}
                scroll={{ x: "max-content" }}
                options={false}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                dataSource={events}
                columns={[
                  { title: "发生时间", render: (_, e) => timeText(e.at) },
                  {
                    title: "当时的数字物品",
                    render: (_, e) =>
                      <CopyValue value={p.data.items.find((i) => i.id === e.itemId)?.uid} />,
                  },
                  { title: "有效读数", dataIndex: "counter" },
                ]}
              />
            </ProCard>
          </>
        )}
        <ModalForm
          title="维护芯片批次"
          open={batch}
          onOpenChange={setBatch}
          initialValues={{ batch: c.batch }}
          modalProps={{ destroyOnHidden: true }}
          onFinish={async (v) => {
            const ok = a.run("batch", { chipId: c.id, batch: v.batch });
            if (ok) setBatch(false);
            return ok;
          }}
        >
          <ProFormText
            name="batch"
            label="批次"
            fieldProps={{ maxLength: 64 }}
            extra="可补录或清空，不改变UID、首次来源及登记时间。"
          />
          {a.feedback}
        </ModalForm>
        <BindEditor chipId={c.id} open={bind} onOpenChange={setBind} />
        {state && (
          <StateEditor
            chipId={c.id}
            action={state}
            open
            onOpenChange={() => setState(null)}
          />
        )}
      </div>
    </DetailContainer>
  );
}
