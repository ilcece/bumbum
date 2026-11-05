import React, { useState } from "react";
import {
  PageContainer,
  ProCard,
  ProDescriptions,
  ProTable,
  ModalForm,
  ProFormSelect,
  ProFormDigit,
  ProFormTextArea,
} from "@ant-design/pro-components";
import { Alert, Button, Space, Tag, Statistic, Tabs, Select } from "antd";
import { history, useParams } from "@umijs/max";
import { useStore } from "../data/store";
import {
  edition,
  issueText,
  itemStates,
  chipStates,
  userName,
  users,
  timeText,
  statistics,
  kindNames,
} from "../data/domain";
import { useReturnPath, useAction, go, required, ErrorState } from "../ui";
import { BindEditor } from "../components/ChipActions";
import SaleEditor from "../components/SaleEditor";
import HandoverEditor from "../components/HandoverEditor";
export default function ItemDetail() {
  const p = useStore(),
    d = p.data,
    { id } = useParams(),
    i = d.items.find((x) => x.id === Number(id)),
    back = useReturnPath("/items"),
    a = useAction(),
    [bind, setBind] = useState(false),
    [sale, setSale] = useState(false),
    [claim, setClaim] = useState(false),
    [assign, setAssign] = useState(false),
    [assignId, setAssignId] = useState<string>(),
    [handover, setHandover] = useState(false),
    [workId, setWorkId] = useState<string>(),
    [scope, setScope] = useState<"sold" | "all">("sold"),
    [range, setRange] = useState<"7d" | "30d" | "all">("all");
  if (!i)
    return (
      <PageContainer
        title="数字物品不存在"
        onBack={() => history.push("/items")}
      />
    );
  const style = d.styles.find((s) => s.id === i.styleId),
    issue = d.issues.find((s) => s.id === i.issueId),
    entity = i.entities.find((e) => !e.to),
    chip = d.chips.find((c) => c.id === entity?.chipId),
    stats = statistics(d, { scope, range, itemId: i.id }),
    works = d.handovers.filter((w) => w.itemId === i.id),
    pending = works.find((w) => !w.completedAt && !w.legacy),
    assignIssue = d.issues.find((x) => x.id === assignId);
  const begin = (work?: string) => {
    setWorkId(work);
    setHandover(true);
  };
  return (
    <PageContainer
      title={i.uid}
      subTitle={`${style?.name || "款式待核对"} · ${edition(i, issue)}`}
      onBack={() => history.push(back)}
      extra={
        <Space>
          <Button onClick={() => history.push(back)}>返回来源</Button>
          <Button onClick={() => setSale(true)}>维护售出确认</Button>
          <Button
            type="primary"
            disabled={i.status === "archived" || a.unknown}
            onClick={() =>
              a.run(
                "toggleItem",
                { itemId: i.id },
                i.status === "active"
                  ? "物品已停用，身份与持有人保留"
                  : "物品已启用，尚未自动认领",
              )
            }
          >
            {i.status === "active" ? "停用物品" : "启用物品"}
          </Button>
        </Space>
      }
    >
      <div className="page-stack">
        {a.feedback}
        {p.readError ? (
          <ErrorState />
        ) : (
          <>
            <ProCard
              variant="outlined"
              title="数字身份与发行"
              extra={
                <Tag color={i.status === "active" ? "blue" : "default"}>
                  {itemStates[i.status]}
                </Tag>
              }
            >
              <ProDescriptions
                column={2}
                dataSource={i}
                columns={[
                  { title: "系统物品编号", dataIndex: "uid", copyable: true },
                  { title: "发行编号", render: () => edition(i, issue) },
                  {
                    title: "商品款式",
                    render: () => (
                      <Button
                        type="link"
                        onClick={() => go("/catalog/style/" + i.styleId)}
                      >
                        {style?.name}
                      </Button>
                    ),
                  },
                  {
                    title: "发行约定",
                    render: () =>
                      issue ? (
                        <Button
                          type="link"
                          onClick={() => go("/catalog/issue/" + issue.id)}
                        >
                          {issue.name + " · " + issueText(issue)}
                        </Button>
                      ) : (
                        <Button onClick={() => setAssign(true)}>
                          补齐原发行关系
                        </Button>
                      ),
                  },
                  {
                    title: "售出确认",
                    render: () => (i.sold ? "已确认售出" : "未确认售出"),
                  },
                  {
                    title: "首次售出时间",
                    render: () => timeText(i.firstSoldAt),
                  },
                  { title: "当前持有人", render: () => userName(i.ownerId) },
                  {
                    title: "首次认领时间",
                    render: () => timeText(i.firstOwnerAt),
                  },
                ]}
              />
              <Alert
                type="info"
                title="售出与认领分别维护"
                description="售出确认来自外部经营核对；未认领也可以已售出，赠品认领后也可以未售出。更正售出标记保留原时间、身份、持有人及触碰记录。"
              />
            </ProCard>
            <ProCard
              variant="outlined"
              title="当前实体与芯片"
              extra={
                !entity ? (
                  <Button type="primary" onClick={() => setBind(true)}>
                    首次绑定芯片
                  </Button>
                ) : (
                  <Button onClick={() => go("/chips/" + chip?.id)}>
                    维护当前芯片
                  </Button>
                )
              }
            >
              {entity ? (
                <ProDescriptions
                  column={2}
                  columns={[
                    { title: "实际实体规格", render: () => entity.spec },
                    {
                      title: "当前芯片",
                      render: () => (
                        <Button
                          type="link"
                          onClick={() => go("/chips/" + chip?.id)}
                        >
                          {chip?.uid}
                        </Button>
                      ),
                    },
                    {
                      title: "芯片服务状态",
                      render: () => (chip ? chipStates[chip.state] : "待核对"),
                    },
                    {
                      title: "配置状态",
                      render: () =>
                        chip?.configuredAt ? "演示核验就绪" : "待准备/核验",
                    },
                    { title: "关联时间", render: () => timeText(entity.from) },
                  ]}
                />
              ) : (
                <Alert
                  type="info"
                  title="尚无实体与芯片关联"
                  description="首次绑定后，到芯片详情准备配置，核验就绪后再启用物品。"
                />
              )}
            </ProCard>
            <ProCard
              variant="outlined"
              title="持有人与接续"
              extra={
                !i.ownerId ? (
                  <Button
                    data-demo-only
                    disabled={i.status !== "active"}
                    onClick={() => setClaim(true)}
                  >
                    〔演示〕模拟首次认领
                  </Button>
                ) : (
                  <Button type="primary" onClick={() => begin(pending?.id)}>
                    {pending ? "继续未完成接续" : "办理换新 / 转售"}
                  </Button>
                )
              }
            >
              <ProDescriptions
                column={2}
                columns={[
                  { title: "当前持有人", render: () => userName(i.ownerId) },
                  {
                    title: "已约定权益",
                    render: () =>
                      issue?.rights
                        .map((r) => (r === "resale" ? "转售" : "换新"))
                        .join("、") || "未约定",
                  },
                  {
                    title: "年度共享换新额度",
                    render: () =>
                      i.firstOwnerAt
                        ? "1次 / 年，已核定使用 " + i.used + " 次"
                        : "首次认领后起算",
                  },
                  {
                    title: "计次核对",
                    render: () =>
                      i.quotaReview ? (
                        <Tag color="orange">待核对计次</Tag>
                      ) : (
                        "暂无待核对"
                      ),
                  },
                ]}
              />
              <ProTable
                rowKey="id"
                search={false}
                options={false}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                dataSource={works}
                columns={[
                  { title: "类型", render: (_, w) => kindNames[w.kind] },
                  {
                    title: "准备时间",
                    render: (_, w) => timeText(w.createdAt),
                  },
                  {
                    title: "状态",
                    render: (_, w) =>
                      w.legacy
                        ? "旧版记录待核对"
                        : w.completedAt
                          ? "已完成"
                          : "待确认接续",
                  },
                  {
                    title: "接收账户",
                    render: (_, w) => userName(w.recipientId),
                  },
                  {
                    title: "操作",
                    render: (_, w) => (
                      <Button type="link" onClick={() => begin(w.id)}>
                        {w.completedAt || w.legacy ? "查看" : "继续接续"}
                      </Button>
                    ),
                  },
                ]}
              />
            </ProCard>
            <ProCard
              variant="outlined"
              title="物品触碰统计"
              extra={
                <Space>
                  <Select
                    aria-label="统计对象"
                    value={scope}
                    onChange={setScope}
                    options={[
                      { value: "sold", label: "售出后的有效触碰" },
                      { value: "all", label: "全生命周期有效触碰" },
                    ]}
                  />
                  <Select
                    aria-label="统计时间"
                    value={range}
                    onChange={setRange}
                    options={[
                      { value: "7d", label: "近7天" },
                      { value: "30d", label: "近30天" },
                      { value: "all", label: "全部时间" },
                    ]}
                  />
                </Space>
              }
            >
              <Space size={48} align="start">
                <Statistic
                  title={
                    scope === "sold" ? "售出后有效触碰" : "全生命周期有效触碰"
                  }
                  value={stats.total}
                  suffix="次"
                />
                <div>
                  按此稳定数字身份合并历代芯片。
                  <br />
                  北京时间；配置核验、失败和重复刷新不计次。
                </div>
              </Space>
              <ProTable
                rowKey="id"
                search={false}
                options={false}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                dataSource={d.chips.filter((c) =>
                  i.entities.some((e) => e.chipId === c.id),
                )}
                columns={[
                  {
                    title: "历代芯片",
                    render: (_, c) => (
                      <Button type="link" onClick={() => go("/chips/" + c.id)}>
                        {c.uid}
                      </Button>
                    ),
                  },
                  { title: "当前状态", render: (_, c) => chipStates[c.state] },
                  {
                    title: "所选口径有效触碰",
                    render: (_, c) =>
                      stats.events.filter((e) => e.chipId === c.id).length,
                  },
                ]}
              />
              <Space>
                <Button
                  data-demo-only
                  disabled={!chip}
                  onClick={() =>
                    a.run("touch", { chipId: chip?.id }, "已记录合成有效触碰")
                  }
                >
                  〔演示〕模拟当前卡触碰
                </Button>
                <Button
                  data-demo-only
                  disabled={!chip}
                  onClick={() =>
                    a.run("touch", { chipId: chip?.id, counter: chip?.counter })
                  }
                >
                  〔演示〕重复同一读数
                </Button>
              </Space>
            </ProCard>
            <ProCard variant="outlined" title="关系历史">
              <Tabs
                items={[
                  {
                    key: "entities",
                    label: "实体与芯片历程",
                    children: (
                      <ProTable
                        rowKey="id"
                        search={false}
                        options={false}
                        pagination={{ pageSize: 10, showSizeChanger: false }}
                        dataSource={i.entities}
                        columns={[
                          { title: "实际规格", dataIndex: "spec" },
                          {
                            title: "芯片UID",
                            render: (_, e) => (
                              <Button
                                type="link"
                                onClick={() => go("/chips/" + e.chipId)}
                              >
                                {d.chips.find((c) => c.id === e.chipId)?.uid}
                              </Button>
                            ),
                          },
                          {
                            title: "开始时间",
                            render: (_, e) => timeText(e.from),
                          },
                          {
                            title: "结束时间",
                            render: (_, e) =>
                              e.to ? timeText(e.to) : "当前关联",
                          },
                          { title: "变更原因", dataIndex: "reason" },
                        ]}
                      />
                    ),
                  },
                  {
                    key: "owners",
                    label: "持有人历程",
                    children: (
                      <ProTable
                        rowKey={(o) => o.ownerId + o.from}
                        search={false}
                        options={false}
                        pagination={{ pageSize: 10, showSizeChanger: false }}
                        dataSource={i.owners}
                        columns={[
                          {
                            title: "持有人",
                            render: (_, o) => userName(o.ownerId),
                          },
                          {
                            title: "开始时间",
                            render: (_, o) => timeText(o.from),
                          },
                          {
                            title: "结束时间",
                            render: (_, o) =>
                              o.to ? timeText(o.to) : "当前持有人",
                          },
                        ]}
                      />
                    ),
                  },
                ]}
              />
            </ProCard>
          </>
        )}
        <BindEditor itemId={i.id} open={bind} onOpenChange={setBind} />
        <SaleEditor ids={[i.id]} open={sale} onOpenChange={setSale} />
        {handover && (
          <HandoverEditor
            itemId={i.id}
            workId={workId}
            open={handover}
            onOpenChange={setHandover}
          />
        )}
        <ModalForm
          title="〔演示〕模拟首次认领"
          open={claim}
          onOpenChange={setClaim}
          modalProps={{ destroyOnHidden: true }}
          onFinish={async (v) => {
            const ok = a.run(
              "demoClaim",
              { itemId: i.id, ...v },
              "已建立演示持有关系，售出标记不变",
            );
            if (ok) setClaim(false);
            return ok;
          }}
        >
          <Alert
            type="warning"
            title="仅为合成账户演示"
            description="未实现真实首次认领、短信、账号验证或实名流程。"
          />
          <ProFormSelect
            name="ownerId"
            label="演示认领账户"
            options={users}
            rules={[{ required: true }]}
          />
          {a.feedback}
        </ModalForm>
        <ModalForm
          title="补齐原发行关系"
          open={assign}
          onOpenChange={setAssign}
          modalProps={{ destroyOnHidden: true }}
          onFinish={async (v) => {
            const ok = a.run("assignIssue", {
              itemId: i.id,
              ...v,
              number:
                assignIssue?.mode === "timed" && !assignIssue.sealedAt
                  ? null
                  : v.number,
            });
            if (ok) setAssign(false);
            return ok;
          }}
        >
          <Alert
            type="warning"
            title="只修复缺失关系，不重新发行"
            description="核对原始依据，保留已有身份、实体、芯片、持有人、触碰和历史。"
          />
          <ProFormSelect
            name="issueId"
            label="原款式的已确认发行"
            options={d.issues
              .filter(
                (s) => s.styleId === i.styleId && s.status === "confirmed",
              )
              .map((s) => ({ value: s.id, label: s.name }))}
            rules={[{ required: true }]}
            fieldProps={{ onChange: (v) => setAssignId(v as string) }}
          />
          <ProFormDigit
            name="number"
            label="原正式序号"
            min={1}
            disabled={assignIssue?.mode === "timed" && !assignIssue.sealedAt}
          />
          <ProFormTextArea
            name="evidence"
            label="原发行核对依据"
            rules={required}
          />
          {a.feedback}
        </ModalForm>
      </div>
    </PageContainer>
  );
}
