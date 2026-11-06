import React, { useState } from "react";
import { PageContainer, ProCard, ProColumns } from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Checkbox,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row as GridRow,
  Select,
  Space,
  Tabs,
  Typography,
} from "antd";
import { history, useLocation, useParams } from "@umijs/max";
import dayjs from "dayjs";
import { Row, read, statusNames, time } from "../catalog";
import {
  ActionForm,
  Copy,
  Evidence,
  Gallery,
  Product,
  RemoteSelect,
  State,
  required,
} from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import StyleImages from "../components/StyleImages";
function StyleFields({ record }: { record?: Row }) {
  const [imageBusy, setImageBusy] = useState(false);
  const form = Form.useFormInstance();
  const v = Form.useWatch([], form) || {};
  return (
    <GridRow gutter={24}>
      <Col span={15}>
        <Form.Item name="id" hidden>
          <InputNumber />
        </Form.Item>
        <Form.Item name="project" label="物品类别" rules={required}>
          <Select
            disabled={!!record?.issue_count}
            options={[
              { value: "fashion", label: "服装" },
              { value: "jewelry", label: "饰品" },
            ]}
          />
        </Form.Item>
        <Form.Item name="code" label="款式编号" rules={required}>
          <Input maxLength={64} disabled={!!record?.issue_count} />
        </Form.Item>
        <Form.Item name="name" label="款式名称" rules={required}>
          <Input maxLength={128} />
        </Form.Item>
        <Form.Item name="description" label="商品介绍">
          <Input.TextArea rows={3} maxLength={4000} />
        </Form.Item>
        <Form.Item name="material" label="材质">
          <Input maxLength={256} />
        </Form.Item>
        <Form.Item name="care_instructions" label="养护或寓意">
          <Input.TextArea rows={2} maxLength={2000} />
        </Form.Item>
        <Form.Item name="specs" label="适用规格">
          <Select mode="tags" tokenSeparators={["、", ","]} />
        </Form.Item>
        <Form.Item name="image_urls" label="参考图片">
          <StyleImages styleId={record?.id} onStatusChange={setImageBusy} />
        </Form.Item>
        <Form.Item
          name="image_upload_ready"
          style={{ marginBottom: 0 }}
          rules={[
            {
              validator: () =>
                imageBusy
                  ? Promise.reject("请先完成图片上传并核对结果。")
                  : Promise.resolve(),
            },
          ]}
        >
          <Input type="hidden" />
        </Form.Item>
        {!!record?.item_count && (
          <Form.Item
            name="shared_confirmed"
            valuePropName="checked"
            rules={[
              {
                validator: (_, v) =>
                  v ? Promise.resolve() : Promise.reject("请确认共用影响"),
              },
            ]}
          >
            <Checkbox>
              我确认保存将影响该款式的{record.item_count}
              件数字物品，不修改发行与物品历史。
            </Checkbox>
          </Form.Item>
        )}
      </Col>
      <Col span={9}>
        <div className="mobile-preview">
          <div className="mobile-preview-header">手机展示预览 · 未保存</div>
          <Gallery urls={v.image_urls || []} />
          <div className="mobile-preview-content">
            <Typography.Title level={4}>
              {v.name || "商品名称"}
            </Typography.Title>
            {[
              ["介绍", v.description],
              ["材质", v.material],
              ["养护或寓意", v.care_instructions],
              ["规格", v.specs?.join("、")],
            ].map(([k, x]) => (
              <div className="preview-section" key={k}>
                <div className="cell-secondary">{k}</div>
                {x || "暂未填写"}
              </div>
            ))}
          </div>
        </div>
      </Col>
    </GridRow>
  );
}
function IssueFields() {
  const mode = Form.useWatch("mode");
  return (
    <>
      <Form.Item name="id" hidden>
        <InputNumber />
      </Form.Item>
      <Form.Item name="style_id" label="关联款式" rules={required}>
        <RemoteSelect resource="styles" />
      </Form.Item>
      <Form.Item name="name" label="发行名称" rules={required}>
        <Input maxLength={128} />
      </Form.Item>
      <Form.Item name="series" label="系列归类">
        <Input maxLength={128} />
      </Form.Item>
      <Form.Item name="mode" label="发行方式" rules={required}>
        <Select
          options={["fixed", "period", "unlimited"].map((v) => ({
            value: v,
            label: statusNames[v],
          }))}
        />
      </Form.Item>
      {mode === "fixed" && (
        <Form.Item name="total" label="数字身份发行总量" rules={required}>
          <InputNumber min={1} precision={0} />
        </Form.Item>
      )}
      {mode === "period" && (
        <>
          <Form.Item
            name="starts_at"
            label="销售开始（北京时间）"
            rules={required}
          >
            <DatePicker showTime />
          </Form.Item>
          <Form.Item
            name="ends_at"
            label="销售结束（北京时间）"
            rules={required}
          >
            <DatePicker showTime />
          </Form.Item>
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
      <Form.Item name="description" label="发行说明与承诺" rules={required}>
        <Input.TextArea rows={3} maxLength={4000} />
      </Form.Item>
      <Form.Item name="rights" label="适用权益">
        <Checkbox.Group
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
    [action, setAction] = useState<{ type: string; r: Row }>();
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
          "/catalog?tab=" + (routeKind === "style" ? "styles" : "issues"),
        );
    },
    done = () => {
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
      render: (_, r) => <Product row={r} />,
    },
    {
      title: "类别",
      dataIndex: "project",
      valueEnum: { fashion: "服装", jewelry: "饰品" },
    },
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
          维护共用资料
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
      search: false,
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
      search: false,
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
          onClick={() => setEditor({ kind: "issue", record: r })}
        >
          {r.confirmed_at ? "查看约定" : "编辑草案"}
        </Button>,
        !r.confirmed_at && (
          <Button
            key="confirm"
            type="link"
            onClick={() => setAction({ type: "confirmIssue", r })}
          >
            确认约定
          </Button>
        ),
        r.confirmed_at && r.mode === "period" && !r.sealed_at && (
          <Button
            key="seal"
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
    <PageContainer title={false}>
      {routeError && <Alert type="error" title={routeError} />}
      <Tabs
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
              setEditor({ kind: tab === "styles" ? "style" : "issue" })
            }
          >
            {tab === "styles" ? "新建款式" : "新增发行约定"}
          </Button>,
        ]}
      />
      {editor && (!editor.record?.confirmed_at || editor.kind === "style") && (
        <ActionForm
          title={editor.kind === "style" ? "维护款式共用资料" : "发行约定草案"}
          action={editor.kind}
          width={editor.kind === "style" ? 1120 : 780}
          initial={
            editor.record
              ? {
                  ...editor.record,
                  starts_at: editor.record.starts_at
                    ? dayjs(editor.record.starts_at)
                    : undefined,
                  ends_at: editor.record.ends_at
                    ? dayjs(editor.record.ends_at)
                    : undefined,
                }
              : {
                  project: "fashion",
                  specs: [],
                  image_urls: [],
                  mode: "fixed",
                  rights: [],
                }
          }
          onDone={done}
          onClose={close}
        >
          {editor.kind === "style" ? (
            <StyleFields record={editor.record} />
          ) : (
            <IssueFields />
          )}
        </ActionForm>
      )}
      {editor?.record?.confirmed_at && editor.kind === "issue" && (
        <ActionForm
          title="已确认发行约定"
          readOnly
          action="confirmIssue"
          initial={{ issue_id: editor.record.id }}
          onClose={close}
          onDone={done}
          submitText="已确认"
        >
          <Typography.Paragraph>{editor.record.name}</Typography.Paragraph>
          <Typography.Paragraph>
            {editor.record.description}
          </Typography.Paragraph>
          <Typography.Paragraph>
            核定规则：{editor.record.counting_rule || "不适用"}
          </Typography.Paragraph>
          <Typography.Paragraph>
            确认时间：{time(editor.record.confirmed_at)}；最终总量：
            {editor.record.total ?? "待核定"}
          </Typography.Paragraph>
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
              <Form.Item name="total" label="最终数字身份总量" rules={required}>
                <InputNumber min={1} precision={0} />
              </Form.Item>
              <Evidence />
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
