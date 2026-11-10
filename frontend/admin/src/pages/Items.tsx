import UserIdentity from "../components/UserIdentity";
import { useEffect, useRef, useState } from "react";
import { PageContainer, ProColumns } from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Space,
  Switch,
  Select,
  Typography,
} from "antd";
import { history } from "@umijs/max";
import { Row, edition, read, statusNames, validationHelp } from "../catalog";
import {
  ActionForm,
  Copy,
  Product,
  RemoteSelect,
  State,
  required,
} from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import ItemDetail from "./ItemDetail";
import SaleFields from "../components/SaleFields";
function CreateFields() {
  const form = Form.useFormInstance();
  const id = Form.useWatch("issue_id", form);
  const [issue, setIssue] = useState<Row>();
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setIssue(undefined);
    setError("");
    form.setFieldValue("edition_number", undefined);
    if (id)
      read("issues", id)
        .then((r) => {
          if (!live) return;
          setIssue(r);
          if (!form.getFieldValue("item_uid"))
            form.setFieldValue("item_uid", r.suggested_item_uid);
          if (!(r.mode === "period" && !r.sealed_at))
            form.setFieldValue("edition_number", r.suggested_edition_number);
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [id]);
  const pending = issue?.mode === "period" && !issue?.sealed_at;
  return (
    <>
      <Form.Item name="issue_id" label="关联发行约定" rules={required}>
        <RemoteSelect resource="issues" params={{ status: "confirmed" }} />
      </Form.Item>
      {error && <Alert type="error" title={error} />}
      {issue && (
        <Alert
          type="info"
          title={`${issue.style_name} · ${statusNames[issue.project] || (issue.project === "fashion" ? "服装" : "饰品")} · 类别从款式引用`}
          description={
            issue.mode === "period" && !issue.sealed_at
              ? "限时数量待核定，不以预估量作上限。"
              : issue.total
                ? `本发行最多${issue.total}个数字身份。`
                : "非限定发行，正式序号仍须发行内唯一。"
          }
        />
      )}
      <Form.Item
        name="item_uid"
        label="系统物品编号"
        rules={required}
        extra="建议使用易识别的唯一编号，例如FASH-2026-000001；格式不限，最多32字符，去首尾空白后全局唯一。"
      >
        <Input maxLength={32} placeholder="请输入或采用建议编号" />
      </Form.Item>
      <Form.Item
        name="is_validation"
        label="生产验证对象"
        valuePropName="checked"
        extra={validationHelp}
      >
        <Switch aria-label="物品生产验证对象" />
      </Form.Item>
      <Form.Item
        name="edition_number"
        label="本件正式序号"
        rules={pending ? [] : required}
        extra={
          pending
            ? "封版前正式编号待核定；先准备稳定身份，封版时确定。"
            : "本次发行内唯一，不能超过已确认总量；建议值不预占编号。"
        }
      >
        <InputNumber
          prefix="#"
          min={1}
          precision={0}
          disabled={!issue || pending}
          max={issue?.total || undefined}
          style={{ width: "100%" }}
        />
      </Form.Item>
    </>
  );
}
export default function Items() {
  const [selected, setSelected] = useState<React.Key[]>([]),
    [sale, setSale] = useState(false);
  const [id, setId] = useState<number>(),
    [create, setCreate] = useState(
      new URLSearchParams(location.search).get("create") === "1",
    ),
    [rev, setRev] = useState(0),
    [created, setCreated] = useState<number>();
  const columns: ProColumns<Row>[] = [
    {
      title: "关键词",
      dataIndex: "keyword",
      hideInTable: true,
      fieldProps: { placeholder: "物品编号、款式名称或芯片编号" },
    },
    {
      title: "系统物品编号",
      dataIndex: "item_uid",
      search: false,
      render: (_, r) => (
        <div>
          <Copy value={r.item_uid} onClick={() => setId(r.id)} />
          {!!r.is_validation && (
            <div>
              <State value="生产验证对象" />
            </div>
          )}
        </div>
      ),
    },
    {
      title: "商品款式",
      search: false,
      render: (_, r) => (
        <div>
          <Product row={r} />
          <div className="cell-secondary">
            {r.generation
              ? `第${r.generation}代物品 · ${r.spec}`
              : "物品待准备 · 实物＋芯片尚未准备"}
          </div>
        </div>
      ),
    },
    { title: "正式序号", search: false, render: (_, r) => edition(r) },
    {
      title: "档案状态",
      dataIndex: "status",
      valueEnum: {
        draft: "草稿",
        active: "启用",
        disabled: "停用",
        archived: "归档",
      },
      render: (_, r) => <State value={statusNames[r.status]} />,
    },
    {
      title: "当前物品状态",
      dataIndex: "whole_status",
      valueEnum: { normal: "正常", lost: "已挂失", missing: "待准备" },
      render: (_, r) => (
        <State
          value={
            !r.whole_id
              ? "待准备"
              : r.lost_at || r.loss_evidence
                ? "已挂失"
                : "正常"
          }
        />
      ),
    },
    {
      title: "数据性质",
      dataIndex: "is_validation",
      hideInTable: true,
      valueEnum: { true: "生产验证", false: "正常业务" },
      render: (_, r) =>
        r.is_validation ? <State value="生产验证对象" /> : "—",
    },
    {
      title: "售出确认",
      dataIndex: "sold",
      valueEnum: { true: "已确认售出", false: "未确认售出" },
      render: (_, r) => <State value={r.sold ? "已确认售出" : "未确认售出"} />,
    },
    {
      title: "当前持有人",
      dataIndex: "owner",
      valueEnum: { yes: "已有持有人", no: "暂无持有人" },
      render: (_, r) =>
        r.owner_id ? (
          <div>
            {r.owner_name}
            <div className="cell-secondary">
              <UserIdentity uid={r.owner_public_uid} />
            </div>
          </div>
        ) : (
          <State value="暂无持有人" />
        ),
    },
    {
      title: "当前芯片",
      search: false,
      render: (_, r) =>
        r.chip_uid ? (
          <div>
            <Copy
              value={r.chip_uid}
              onClick={() =>
                history.push(
                  `/chips/${r.chip_id}?from=${encodeURIComponent(location.pathname + location.search)}`,
                )
              }
            />
            <div>
              <State value={r.provisioned_at ? "核验就绪" : "待配置"} />
            </div>
          </div>
        ) : (
          <State value="未关联" />
        ),
    },
    {
      title: "操作",
      valueType: "option",
      fixed: "right",
      render: (_, r) => [
        <Button type="link" key="view" onClick={() => setId(r.id)}>
          查看
        </Button>,
      ],
    },
  ];
  return (
    <PageContainer title={false}>
      {created && (
        <Button onClick={() => setId(created)}>打开刚创建的确切物品</Button>
      )}
      <ServerTable
        resource="items"
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys),
        }}
        columns={columns}
        refresh={rev}
        extra={[
          <Button
            key="sale"
            disabled={!selected.length}
            onClick={() => setSale(true)}
          >
            批量售出确认{selected.length ? `（${selected.length}）` : ""}
          </Button>,
          <Button type="primary" key="create" onClick={() => setCreate(true)}>
            登记数字物品
          </Button>,
        ]}
      />
      <Drawer
        open={!!id}
        width={900}
        title="数字物品详情"
        onClose={() => {
          setId(undefined);
          setRev((n) => n + 1);
        }}
        extra={
          <Button
            onClick={() =>
              history.push(
                `/items/${id}?from=${encodeURIComponent(location.pathname + location.search)}`,
              )
            }
          >
            打开完整详情
          </Button>
        }
        destroyOnHidden
      >
        {id && (
          <ItemDetail
            id={id}
            embedded
            onDeleted={() => {
              setId(undefined);
              setRev((n) => n + 1);
            }}
          />
        )}
      </Drawer>
      {sale && (
        <ActionForm
          title="批量售出确认"
          submitText="保存售出确认"
          action="saleBatch"
          initial={{ item_ids: selected, confirmed: true }}
          onClose={() => setSale(false)}
          onDone={() => {
            setSale(false);
            setSelected([]);
            setRev((n) => n + 1);
          }}
        >
          <Form.Item name="item_ids" hidden>
            <Select mode="multiple" />
          </Form.Item>
          <Typography.Paragraph>
            将维护已选择的{selected.length}
            件物品的售出事实，不改变持有人或历史。
          </Typography.Paragraph>
          <SaleFields />
        </ActionForm>
      )}
      {create && (
        <ActionForm
          title="登记数字物品"
          submitText="登记并查看物品"
          width={800}
          action="item"
          initial={{
            is_validation: false,
            issue_id:
              Number(new URLSearchParams(location.search).get("issue_id")) ||
              undefined,
          }}
          onClose={() => setCreate(false)}
          onDone={(r) => {
            setCreated(undefined);
            setId(r.id);
            setCreate(false);
            setRev((n) => n + 1);
          }}
        >
          <CreateFields />
        </ActionForm>
      )}
    </PageContainer>
  );
}
