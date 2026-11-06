import React, { useState } from "react";
import {
  PageContainer,
  ProCard,
  ProColumns,
  ProForm,
} from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Col,
  Row as GridRow,
  Checkbox,
  DatePicker,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Tabs,
  Typography,
} from "antd";
import { history, useLocation, useParams } from "@umijs/max";
import dayjs from "dayjs";
import { Row, read, statusNames, time, edition } from "../catalog";
import {
  ActionForm,
  Copy,
  Evidence,
  Product,
  RemoteSelect,
  State,
  required,
  returnPath,
} from "../components/CatalogUI";
import { inputDate, inputISO } from "../businessTime";
import ServerTable from "../components/ServerTable";
import StyleEditor from "../components/StyleEditor";
function IssueFields() {
  const mode = Form.useWatch("mode");
  return (
    <>
      <Form.Item name="id" hidden>
        <InputNumber />
      </Form.Item>
      <Form.Item name="name" label="发行名称" rules={required}>
        <Input autoFocus placeholder="请输入" maxLength={128} />
      </Form.Item>
      <Form.Item name="style_id" label="关联款式" rules={required}>
        <RemoteSelect resource="styles" placeholder="请选择" />
      </Form.Item>
      <ProForm.Group>
        <Form.Item
          name="series"
          label="系列归类（选填）"
          style={{ width: 328 }}
        >
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item
          name="mode"
          label="发行方式"
          rules={required}
          style={{ width: 328 }}
        >
          <Select
            options={["fixed", "period", "unlimited"].map((v) => ({
              value: v,
              label: statusNames[v],
            }))}
          />
        </Form.Item>
      </ProForm.Group>
      {mode === "fixed" && (
        <Form.Item name="total" label="固定发行总量" rules={required}>
          <InputNumber min={1} precision={0} style={{ width: "100%" }} />
        </Form.Item>
      )}
      {mode === "period" && (
        <>
          <GridRow gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item
                name="starts_at"
                label="销售开始（北京时间）"
                getValueProps={(v) => ({
                  value: typeof v === "string" ? inputDate(v) : v,
                })}
                normalize={(v) => (v ? inputISO(v) : undefined)}
                rules={required}
              >
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                name="ends_at"
                label="销售结束（北京时间）"
                getValueProps={(v) => ({
                  value: typeof v === "string" ? inputDate(v) : v,
                })}
                normalize={(v) => (v ? inputISO(v) : undefined)}
                rules={required}
              >
                <DatePicker showTime style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </GridRow>
          <Form.Item
            name="counting_rule"
            label="有效数量核定规则"
            rules={required}
          >
            <Input.TextArea
              placeholder="明确取消、退款及跨期处理；预估量不作上限。"
              rows={3}
            />
          </Form.Item>
        </>
      )}
      <Form.Item
        name="description"
        label="发行说明与规格承诺"
        rules={required}
        extra="说明限量、规格/颜色限制及允许的例外；确认后普通维护不可追改。"
      >
        <Input.TextArea rows={3} maxLength={4000} />
      </Form.Item>
      <Form.Item name="rights" label="适用权益">
        <Select
          mode="multiple"
          placeholder="请选择"
          options={[
            { value: "renewal", label: "换新" },
            { value: "resale", label: "转售" },
          ]}
        />
      </Form.Item>
    </>
  );
}
export default function Catalog() {
  const location = useLocation(),
    routeId = useParams().id,
    routeKind = location.pathname.includes("/issue/") ? "issue" : "style";
  const [routeError, setRouteError] = useState("");
  const q = new URLSearchParams(location.search),
    [editor, setEditor] = useState<{ kind: string; record?: Row }>(),
    [rev, setRev] = useState(0),
    [action, setAction] = useState<{ type: string; r: Row }>(),
    [issueDirty, setIssueDirty] = useState(false);
  React.useEffect(() => {
    let live = true;
    setRouteError("");
    if (!routeId) return;
    if (routeId === "new") {
      setEditor({ kind: routeKind });
      return;
    }
    if (!/^[1-9][0-9]*$/.test(routeId)) {
      setRouteError("记录编号无效。");
      return;
    }
    read(routeKind === "style" ? "styles" : "issues", Number(routeId))
      .then((r) => {
        if (live) setEditor({ kind: routeKind, record: r });
      })
      .catch((e) => {
        if (live) setRouteError(e.message);
      });
    return () => {
      live = false;
    };
  }, [routeId, routeKind]);
  const close = () => {
      setEditor(undefined);
      if (routeId)
        history.replace(
          returnPath(
            "/catalog?tab=" + (routeKind === "style" ? "styles" : "issues"),
          ),
        );
    },
    done = (result?: Row) => {
      setIssueDirty(false);
      if (
        routeId &&
        editor &&
        result?.id &&
        ["style", "issue"].includes(editor.kind)
      ) {
        const resource = editor.kind === "style" ? "styles" : "issues";
        void read(resource, result.id).then((record) =>
          setEditor({ kind: editor.kind, record }),
        );
        history.replace(
          `/catalog/${editor.kind}/${result.id}${q.get("from") ? "?from=" + encodeURIComponent(q.get("from")!) : ""}`,
        );
        setAction(undefined);
        setRev((x) => x + 1);
        return;
      }
      close();
      setAction(undefined);
      setRev((x) => x + 1);
    };
  const tab = q.get("tab") || "styles";
  const styles: ProColumns<Row>[] = [
    {
      title: "关键词",
      dataIndex: "keyword",
      hideInTable: true,
      fieldProps: { placeholder: "款式编号或名称" },
    },
    {
      title: "款式编号",
      dataIndex: "code",
      search: false,
      render: (_, r) => <Copy value={r.code} />,
    },
    {
      title: "商品款式",
      dataIndex: "name",
      search: false,
      render: (_, r) => (
        <Product
          row={r}
          onClick={() => setEditor({ kind: "style", record: r })}
        />
      ),
    },
    {
      title: "物品类别",
      dataIndex: "project",
      valueEnum: { fashion: "服装", jewelry: "饰品" },
    },
    { title: "关联发行", dataIndex: "issue_count", search: false },
    { title: "引用物品", dataIndex: "item_count", search: false },
    {
      title: "操作",
      valueType: "option",
      render: (_, r) => [
        <Button
          type="link"
          key="edit"
          onClick={() => setEditor({ kind: "style", record: r })}
        >
          维护资料
        </Button>,
        <Button
          type="link"
          key="issue"
          onClick={() => history.push("/catalog/issue/new?style_id=" + r.id)}
        >
          建立发行约定
        </Button>,
      ],
    },
  ];
  const issues: ProColumns<Row>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true },
    { title: "发行约定", dataIndex: "name", search: false },
    { title: "关联款式", dataIndex: "style_name", search: false },
    {
      title: "发行方式",
      dataIndex: "mode",
      valueEnum: {
        fixed: "固定总量",
        period: "限时按销量定量",
        unlimited: "非限定",
      },
      render: (_, r) => <State value={statusNames[r.mode]} />,
    },
    {
      title: "总量",
      dataIndex: "total",
      search: false,
      render: (_, r) => r.total ?? (r.mode === "period" ? "待核定" : "非限定"),
    },
    {
      title: "确认状态",
      dataIndex: "status",
      valueEnum: { draft: "草案", confirmed: "已确认" },
      render: (_, r) => <State value={r.confirmed_at ? "已确认" : "草案"} />,
    },
    { title: "引用", dataIndex: "item_count", search: false },
    {
      title: "操作",
      valueType: "option",
      render: (_, r) => [
        <Button
          key="view"
          type="link"
          onClick={() =>
            history.push(
              `/catalog/issue/${r.id}?from=${encodeURIComponent(location.pathname + location.search)}`,
            )
          }
        >
          {r.confirmed_at ? "查看约定" : "编辑草案"}
        </Button>,
        !r.confirmed_at && (
          <Button
            key="confirm"
            type="link"
            onClick={() => setAction({ type: "confirmIssue", r })}
          >
            确认发行约定
          </Button>
        ),
        r.confirmed_at && r.mode === "period" && !r.sealed_at && (
          <Button
            key="seal"
            disabled={Date.parse(r.ends_at) > Date.now()}
            title={
              Date.parse(r.ends_at) > Date.now()
                ? "尚未到约定销售期满"
                : undefined
            }
            type="link"
            onClick={() => setAction({ type: "seal", r })}
          >
            核定最终量
          </Button>
        ),
        !r.ever_used && (
          <Button
            danger
            key="delete"
            type="link"
            onClick={() => setAction({ type: "deleteIssue", r })}
          >
            删除
          </Button>
        ),
      ],
    },
  ];
  return (
    <PageContainer
      title={
        routeId
          ? routeKind === "style"
            ? editor?.record
              ? "维护共用款式"
              : "新建款式"
            : editor?.record?.confirmed_at
              ? "发行约定详情"
              : editor?.record
                ? "维护发行草案"
                : "新建发行约定"
          : false
      }
      onBack={routeId ? close : undefined}
    >
      {routeError && <Alert type="error" title={routeError} />}
      {!routeId && (
        <>
          <Tabs
            className="section-tabs"
            size="small"
            activeKey={tab}
            onChange={(tab) => history.push("/catalog?tab=" + tab)}
            items={[
              { key: "styles", label: "款式资料" },
              { key: "issues", label: "发行约定" },
            ]}
          />
          <ServerTable
            key={tab}
            resource={tab}
            refresh={rev}
            columns={tab === "styles" ? styles : issues}
            extra={[
              <Button
                key="create"
                type="primary"
                onClick={() =>
                  history.push(
                    tab === "styles"
                      ? `/catalog/style/new?from=${encodeURIComponent(location.pathname + location.search)}`
                      : `/catalog/issue/new?from=${encodeURIComponent(location.pathname + location.search)}`,
                  )
                }
              >
                {tab === "styles" ? "新建款式" : "新增发行约定"}
              </Button>,
            ]}
          />
        </>
      )}
      {editor?.kind === "style" && (
        <StyleEditor
          key={String(editor.record?.id || "new")}
          record={editor.record}
          page={!!routeId}
          onClose={close}
          onDone={done}
        />
      )}
      {editor?.kind === "issue" && !editor.record?.confirmed_at && (
        <div className="page-stack form-page">
          <ProCard variant="outlined">
            <ActionForm
              key={String(editor.record?.id || "new")}
              page={!!routeId}
              title="发行约定草案"
              submitText="保存发行草案"
              onDirtyChange={setIssueDirty}
              action="issue"
              width={780}
              initial={
                editor.record
                  ? {
                      ...editor.record,
                      starts_at: editor.record.starts_at
                        ? editor.record.starts_at
                        : undefined,
                      ends_at: editor.record.ends_at
                        ? editor.record.ends_at
                        : undefined,
                    }
                  : {
                      mode: "fixed",
                      rights: [],
                      style_id: q.get("style_id")
                        ? Number(q.get("style_id"))
                        : undefined,
                    }
              }
              onDone={done}
              onClose={close}
            >
              <IssueFields />
            </ActionForm>
          </ProCard>
          {editor.record && (
            <Alert
              type="info"
              showIcon
              title="草案已保存，确认约定后即可登记物品"
              description={
                issueDirty
                  ? "存在未保存修改，请先保存草案。"
                  : "确认后锁定本次款式、数量规则及权益承诺。"
              }
              action={
                <Button
                  type="primary"
                  disabled={issueDirty}
                  onClick={() =>
                    setAction({ type: "confirmIssue", r: editor.record! })
                  }
                >
                  确认发行约定
                </Button>
              }
            />
          )}
        </div>
      )}
      {editor?.record?.confirmed_at && editor.kind === "issue" && (
        <ActionForm
          title="已确认发行约定"
          page={!!routeId}
          readOnly
          action="confirmIssue"
          initial={{ issue_id: editor.record.id }}
          onClose={close}
          onDone={done}
          submitText="已确认"
        >
          <ProCard
            title="发行承诺与核定结果"
            size="small"
            headerBordered
            variant="outlined"
          >
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="发行名称">
                {editor.record.name}
              </Descriptions.Item>
              <Descriptions.Item label="确认状态">
                <State value="已确认" />
              </Descriptions.Item>
              <Descriptions.Item label="关联款式">
                {editor.record.style_name}
              </Descriptions.Item>
              <Descriptions.Item label="物品类别">
                {editor.record.project === "fashion" ? "服装" : "饰品"}
              </Descriptions.Item>
              <Descriptions.Item label="系列归类">
                {editor.record.series || "未填写"}
              </Descriptions.Item>
              <Descriptions.Item label="发行方式">
                <State value={statusNames[editor.record.mode]} />
              </Descriptions.Item>
              <Descriptions.Item label="发行说明与承诺" span={2}>
                {editor.record.description || "未填写"}
              </Descriptions.Item>
              <Descriptions.Item label="适用权益" span={2}>
                {editor.record.rights
                  ?.map(
                    (r: string) =>
                      ({ renewal: "换新", resale: "转售" })[
                        r as "renewal" | "resale"
                      ] || r,
                  )
                  .join("、") || "未约定"}
              </Descriptions.Item>
              {editor.record.mode === "period" && (
                <>
                  <Descriptions.Item label="销售开始（北京时间）">
                    {time(editor.record.starts_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="销售结束（北京时间）">
                    {time(editor.record.ends_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="有效数量核定规则" span={2}>
                    {editor.record.counting_rule || "未填写"}
                  </Descriptions.Item>
                </>
              )}
              <Descriptions.Item label="最终总量">
                {editor.record.mode === "unlimited" ? (
                  "非限定"
                ) : editor.record.mode === "period" &&
                  !editor.record.sealed_at ? (
                  <State value="待核定" />
                ) : (
                  editor.record.total
                )}
              </Descriptions.Item>
              <Descriptions.Item label="引用物品">
                {editor.record.item_count}
              </Descriptions.Item>
              <Descriptions.Item label="确认时间">
                {time(editor.record.confirmed_at)}
              </Descriptions.Item>
              {editor.record.mode === "period" && (
                <Descriptions.Item label="最终核定时间">
                  {editor.record.sealed_at
                    ? time(editor.record.sealed_at)
                    : "尚未核定"}
                </Descriptions.Item>
              )}
            </Descriptions>
          </ProCard>
          {editor.record.mode === "period" && (
            <ProCard title="最终发行结果" size="small" headerBordered>
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="核定依据">
                  {editor.record.seal_evidence || "尚未核定"}
                </Descriptions.Item>
              </Descriptions>
              {!editor.record.sealed_at && (
                <>
                  <Typography.Paragraph>
                    已建{editor.record.item_count}
                    个身份；期满后按外部核定结果登记最终数量与依据，不录订单或物流。
                  </Typography.Paragraph>
                  <Button
                    type="primary"
                    disabled={Date.parse(editor.record.ends_at) > Date.now()}
                    onClick={() =>
                      setAction({ type: "seal", r: editor.record! })
                    }
                  >
                    核对并确认最终数量
                  </Button>
                  {Date.parse(editor.record.ends_at) > Date.now() && (
                    <p>尚未到约定销售期满，不能提前核定。</p>
                  )}
                </>
              )}
            </ProCard>
          )}
          <ProCard
            title={`引用数字物品 · ${editor.record.item_count}件`}
            size="small"
            headerBordered
          >
            <Button
              type="primary"
              onClick={() =>
                history.push(`/items?create=1&issue_id=${editor.record!.id}`)
              }
            >
              登记该发行物品
            </Button>
            <ServerTable
              resource="items"
              filters={{ issue_id: editor.record.id }}
              columns={[
                {
                  title: "系统物品编号",
                  dataIndex: "item_uid",
                  search: false,
                  render: (_, x) => (
                    <Copy
                      value={x.item_uid}
                      onClick={() =>
                        history.push(
                          `/items/${x.id}?from=${encodeURIComponent(location.pathname + location.search)}`,
                        )
                      }
                    />
                  ),
                },
                {
                  title: "正式序号",
                  search: false,
                  render: (_, x) => edition(x),
                },
                {
                  title: "状态",
                  search: false,
                  render: (_, x) => <State value={statusNames[x.status]} />,
                },
              ]}
            />
          </ProCard>
          <Button onClick={close}>关闭</Button>
        </ActionForm>
      )}
      {action && (
        <ActionForm
          title={
            action.type === "seal"
              ? "核定最终发行总量"
              : action.type === "deleteIssue"
                ? "确认删除未引用约定"
                : "确认发行约定"
          }
          action={action.type}
          submitText={
            action.type === "seal"
              ? "确认最终发行结果"
              : action.type === "deleteIssue"
                ? "确认删除约定"
                : "确认发行约定"
          }
          initial={{ issue_id: action.r.id }}
          onDone={done}
          onClose={() => setAction(undefined)}
        >
          <Form.Item name="issue_id" hidden>
            <InputNumber />
          </Form.Item>
          <Typography.Paragraph>
            {action.r.name}：{action.r.description}
          </Typography.Paragraph>
          {action.type === "seal" ? (
            <>
              <Alert
                type="warning"
                title={`已建${action.r.item_count}个身份；核定后不能普通改写总量及历史编号。`}
                description={`销售结束：${time(action.r.ends_at)}。请核对外部有效数量及已有身份冲突。`}
              />
              <Form.Item name="total" label="最终数字身份总量" rules={required}>
                <InputNumber min={1} precision={0} style={{ width: "100%" }} />
              </Form.Item>
              <Evidence />
              <Form.Item
                name="seal_checked"
                valuePropName="checked"
                rules={[
                  {
                    validator: (_, v) =>
                      v
                        ? Promise.resolve()
                        : Promise.reject("请确认最终数量与依据"),
                  },
                ]}
              >
                <Checkbox>
                  已核对最终数量、已有身份和外部依据，确认本次不可普通修改的发行结果
                </Checkbox>
              </Form.Item>
            </>
          ) : (
            <Typography.Paragraph>
              {action.type === "deleteIssue"
                ? "只允许从未引用的约定删除，审计保留。"
                : "确认后约定只读，不自动建档、启用或上架。"}
            </Typography.Paragraph>
          )}
        </ActionForm>
      )}
    </PageContainer>
  );
}
