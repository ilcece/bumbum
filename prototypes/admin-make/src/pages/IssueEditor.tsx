import React, { useEffect, useRef, useState } from "react";
import {
  PageContainer,
  ProCard,
  ProForm,
  ProFormText,
  ProFormTextArea,
  ProFormSelect,
  ProFormDigit,
  ProFormDateTimePicker,
  ProFormCheckbox,
  ModalForm,
  ProDescriptions,
  ProFormInstance,
} from "@ant-design/pro-components";
import { Alert, App, Button, Form, Space, Table, Typography } from "antd";
import { history, useParams } from "@umijs/max";
import { useStore } from "../data/store";
import { Issue, issueText, modeNames, timeText, edition } from "../data/domain";
import {
  go,
  required,
  useAction,
  useUnsaved,
  useReturnPath,
  queryState,
  dateISO,
} from "../ui";
import { CopyValue, StatusTag, EditionValue } from "../components/RecordPresentation";
export default function IssueEditor() {
  const p = useStore(),
    { id } = useParams(),
    record = p.data.issues.find((i) => i.id === id),
    [savedId, setSavedId] = useState(record?.id),
    form = useRef<ProFormInstance | undefined>(undefined),
    action = useAction(),
    { modal } = App.useApp(),
    [seal, setSeal] = useState(false),
    [mode, setMode] = useState(record?.mode || "fixed"),
    back = useReturnPath("/catalog?tab=issues");
  const current = p.data.issues.find((i) => i.id === savedId),
    refs = p.data.items.filter((i) => i.issueId === savedId);
  const save = async () => {
    let v: any;
    try {
      v = await form.current?.validateFields();
    } catch {
      return false;
    }
    const issue: Issue = {
      ...v,
      id: savedId || crypto.randomUUID(),
      startsAt: dateISO(v.startsAt),
      endsAt: dateISO(v.endsAt),
    };
    const ok = action.run("issue", issue);
    if (ok) {
      unsaved.setDirty(false);
      setSavedId(issue.id);
      if (id === "new")
        history.replace("/catalog/issue/" + issue.id, history.location.state);
    }
    return ok;
  };
  const unsaved = useUnsaved(save);
  useEffect(() => {
    const next = p.getData().issues.find((x) => x.id === id);
    setSavedId(next?.id);
    form.current?.resetFields();
    setMode(next?.mode || "fixed");
    form.current?.setFieldsValue(
      next || { mode: "fixed", styleId: queryState().styleId, rights: [] },
    );
    unsaved.setDirty(false);
  }, [id]);
  const confirmed = current?.status === "confirmed";
  return (
    <PageContainer
      title={confirmed ? "发行约定" : savedId ? "维护发行草案" : "新建发行约定"}
      onBack={() => history.push(back)}
      extra={
        confirmed ? (
          <Button
            type="primary"
            onClick={() => go("/items?create=1&issueId=" + savedId)}
          >
            登记该发行物品
          </Button>
        ) : undefined
      }
    >
      <div className="page-stack form-page">
        {action.feedback}
        {confirmed ? (
          <>
            <ProCard
              size="small"
              headerBordered
              variant="outlined"
              title={current.name}
              extra={<Space><StatusTag value="已确认" />{issueText(current)}</Space>}
            >
              <ProDescriptions
                size="small"
                bordered
                column={2}
                dataSource={current}
                columns={[
                  {
                    title: "关联款式",
                    render: () =>
                      p.data.styles.find((s) => s.id === current.styleId)?.name,
                  },
                  {
                    title: "发行方式",
                    dataIndex: "mode",
                    valueEnum: modeNames,
                  },
                  {
                    title: "说明与规格承诺",
                    dataIndex: "description",
                    span: 2,
                  },
                  {
                    title: "销售开始",
                    render: () => timeText(current.startsAt),
                  },
                  { title: "销售结束", render: () => timeText(current.endsAt) },
                  { title: "销量核定规则", dataIndex: "basis", span: 2 },
                  {
                    title: "确认时间",
                    render: () => timeText(current.confirmedAt),
                  },
                  {
                    title: "最终核定",
                    render: () =>
                      current.mode === "timed"
                        ? current.sealedAt
                          ? current.total + "个身份"
                          : <StatusTag value="待封版" />
                        : issueText(current),
                  },
                  { title: "核定依据", dataIndex: "sealEvidence", span: 2 },
                  {
                    title: "适用权益",
                    render: () =>
                      current.rights.length
                        ? current.rights
                            .map((x) =>
                              x === "renewal"
                                ? "付费定期/挂失换新"
                                : "后台转售",
                            )
                            .join("、")
                        : "未约定",
                  },
                ]}
              />
            </ProCard>
            {current.mode === "timed" && !current.sealedAt && (
              <ProCard
                size="small"
                headerBordered
                variant="outlined"
                title="确认最终发行结果"
              >
                <Typography.Paragraph>
                  电商平台完成核对后，在这里登记最终数量与依据；不录订单或物流。已建
                  {refs.length}个身份，正式编号待封版。
                </Typography.Paragraph>
                <Button
                  type="primary"
                  disabled={Date.parse(current.endsAt || "") > Date.now()}
                  onClick={() => setSeal(true)}
                >
                  核对并确认最终数量
                </Button>
                {Date.parse(current.endsAt || "") > Date.now() && (
                  <p className="muted">尚未到约定销售期满，不能提前封版。</p>
                )}
              </ProCard>
            )}
            <ProCard
              size="small"
              headerBordered
              title={`引用数字物品 · ${refs.length}件`}
              variant="outlined"
            >
              <Table
                rowKey="id"
                dataSource={refs}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                columns={[
                  {
                    title: "物品编号",
                    render: (_, i) => (
                      <CopyValue value={i.uid} onClick={() => go("/items/" + i.id)} />
                    ),
                  },
                  { title: "发行编号", render: (_, i) => <EditionValue value={edition(i, current)} /> },
                ]}
              />
            </ProCard>
          </>
        ) : (
          <ProCard size="small" headerBordered variant="outlined">
            <ProForm
              formRef={form}
              initialValues={
                record || {
                  mode: "fixed",
                  styleId: queryState().styleId,
                  rights: [],
                }
              }
              onValuesChange={(_, all) => {
                unsaved.setDirty(true);
                setMode(all.mode);
              }}
              onFinish={save}
              submitter={{
                searchConfig: { submitText: "保存发行草案" },
                resetButtonProps: false,
                submitButtonProps: { disabled: action.unknown },
              }}
            >
              <ProFormText name="name" label="发行名称" rules={required} />
              <ProFormSelect
                name="styleId"
                label="关联款式"
                rules={[{ required: true }]}
                options={p.data.styles.map((s) => ({
                  value: s.id,
                  label: s.code + " · " + s.name,
                }))}
              />
              <ProForm.Group>
                <ProFormText
                  name="series"
                  label="系列归类（选填）"
                  width="md"
                />
                <ProFormSelect
                  name="mode"
                  label="发行方式"
                  width="md"
                  options={Object.entries(modeNames).map(([value, label]) => ({
                    value,
                    label,
                  }))}
                />
              </ProForm.Group>
              {mode === "fixed" && (
                <ProFormDigit
                  name="total"
                  label="固定发行总量"
                  min={1}
                  fieldProps={{ precision: 0 }}
                  rules={[{ required: true }]}
                />
              )}{" "}
              {mode === "timed" && (
                <>
                  <Alert
                    type="info"
                    title="先确认数量规则，最终总量期满后核定；不录销售订单。"
                  />
                  <ProForm.Group>
                    <ProFormDateTimePicker
                      name="startsAt"
                      label="销售开始时间（北京时间）"
                      rules={[{ required: true }]}
                    />
                    <ProFormDateTimePicker
                      name="endsAt"
                      label="销售结束时间（北京时间）"
                      rules={[{ required: true }]}
                    />
                  </ProForm.Group>
                  <ProFormTextArea
                    name="basis"
                    label="有效数量核定规则"
                    rules={required}
                  />
                </>
              )}
              <ProFormTextArea
                name="description"
                label="发行说明与规格承诺"
                rules={required}
                extra="说明限量、规格/颜色限制及发行时允许的例外；确认后普通维护不可追改。"
              />
              <ProFormSelect
                name="rights"
                label="适用权益"
                mode="multiple"
                options={[
                  { value: "renewal", label: "付费定期/挂失换新" },
                  { value: "resale", label: "后台转售数字内容及约定权益" },
                ]}
              />
            </ProForm>
          </ProCard>
        )}
        {current && !confirmed && (
          <Alert
            type="info"
            title="草案已保存，确认约定后即可登记物品"
            action={
              <Button
                type="primary"
                disabled={unsaved.isDirty || action.unknown}
                onClick={() =>
                  modal.confirm({
                    title: "确认本次发行约定？",
                    content:
                      "确认后锁定款式、数量规则和权益承诺；不自动创建、启用或认领物品。",
                    okText: "确认发行约定",
                    onOk: () => {
                      action.run("confirmIssue", { issueId: savedId });
                    },
                  })
                }
              >
                确认发行约定
              </Button>
            }
          />
        )}
        {current && (
          <Button
            type="text"
            style={{ alignSelf: "flex-start" }}
            danger
            disabled={!!current.everReferenced || refs.length > 0}
            onClick={() =>
              modal.confirm({
                title: "删除从未被引用的约定？",
                content:
                  "删除事实及原约定摘要保留。当前/历史曾引用的禁止删除。",
                onOk: () => {
                  if (action.run("deleteIssue", { issueId: savedId }))
                    history.push("/catalog?tab=issues");
                },
              })
            }
          >
            删除未引用约定
          </Button>
        )}
        <ModalForm
          title="核对并确认最终数量"
          open={seal}
          onOpenChange={setSeal}
          modalProps={{ destroyOnHidden: true }}
          onFinish={async (v) => {
            if (!v.ack) return false;
            const ok = action.run(
              "seal",
              { issueId: savedId, total: v.total, evidence: v.evidence },
              "发行结果已封版，稳定身份保持",
            );
            if (ok) setSeal(false);
            return ok;
          }}
          submitter={{
            searchConfig: { submitText: "确认最终发行结果" },
            submitButtonProps: { disabled: action.unknown },
          }}
        >
          <Alert
            type="info"
            title={`当前准备${refs.length}个身份，按稳定建档顺序分配正式序号，不批量虚造剩余实体。`}
          />
          <ProFormDigit
            name="total"
            label="最终发行总量"
            min={1}
            fieldProps={{ precision: 0 }}
            rules={[{ required: true }]}
          />
          <ProFormTextArea
            name="evidence"
            label="外部核定依据"
            rules={required}
          />
          <ProFormCheckbox
            name="ack"
            rules={[
              {
                validator: (_, v) =>
                  v ? Promise.resolve() : Promise.reject("请确认影响"),
              },
            ]}
          >
            已核对有效数量及身份冲突，理解封版后不能普通改总量或重排编号
          </ProFormCheckbox>
          {action.feedback}
        </ModalForm>
      </div>
    </PageContainer>
  );
}
