import { useRef, useState } from "react";
import { PageContainer, ProColumns } from "@ant-design/pro-components";
import {
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
import { Row, edition, read, statusNames } from "../catalog";
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
function CreateFields() {
  const [issue, setIssue] = useState<Row>();
  return (
    <>
      <Form.Item name="issue_id" label="发行约定" rules={required}>
        <RemoteSelect
          resource="issues"
          params={{ status: "confirmed" }}
          onChange={(id) => void read("issues", id).then(setIssue)}
        />
      </Form.Item>
      <Form.Item name="item_uid" label="系统物品编号" rules={required}>
        <Input
          maxLength={32}
          placeholder={
            issue?.project === "jewelry"
              ? "JEW-2026-000001"
              : "FASH-2026-000001"
          }
        />
      </Form.Item>
      {!(issue?.mode === "period" && !issue?.sealed_at) && (
        <Form.Item name="edition_number" label="本件正式序号" rules={required}>
          <InputNumber min={1} precision={0} max={issue?.total || undefined} />
        </Form.Item>
      )}
      <Form.Item
        name="is_validation"
        label="生产验证对象"
        valuePropName="checked"
      >
        <Switch aria-label="物品生产验证对象" />
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
      valueEnum: { yes: "已认领", no: "未认领" },
      render: (_, r) =>
        r.owner_id ? (
          <div>
            {r.owner_name}
            <div className="cell-secondary">
              <Copy value={r.owner_id} />
            </div>
          </div>
        ) : (
          <State value="未认领" />
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
              onClick={() => history.push("/chips/" + r.chip_id)}
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
          <Form.Item name="confirmed" label="售出确认" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="evidence" label="外部核对依据" rules={required}>
            <Input.TextArea maxLength={1000} />
          </Form.Item>
        </ActionForm>
      )}
      {create && (
        <ActionForm
          title="新建数字物品身份"
          action="item"
          initial={{ is_validation: false }}
          onClose={() => setCreate(false)}
          onDone={(r) => {
            setCreated(r.id);
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
