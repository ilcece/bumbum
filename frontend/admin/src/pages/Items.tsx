import type { ItemSummary } from "../types/catalog";
import { useState } from "react";
import { PageContainer, ProColumns } from "@ant-design/pro-components";
import {
  Button,
  Drawer,
  Form,
  Select,
  Typography,
} from "antd";
import { history, useLocation } from "@umijs/max";
import { assemblyPath, itemWorkflow, itemWorkflowNames, workbenchWorkflows } from "../catalog";
import {
  ActionForm,
  Copy,
  Product,
  RemoteSelect,
  State,
} from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import ItemDetail from "./ItemDetail";
import SaleFields from "../components/SaleFields";
export default function Items() {
  const location = useLocation();
  const from = location.pathname + location.search;
  const [selected, setSelected] = useState<React.Key[]>([]),
    [sale, setSale] = useState(false),
    [id, setId] = useState<number>(),
    [rev, setRev] = useState(0);
  const columns: ProColumns<ItemSummary>[] = [
    {
      title: "关键词",
      dataIndex: "keyword",
      hideInTable: true,
      fieldProps: { placeholder: "数字编号、实体编号、芯片 UID、发行或订单号" },
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
    {
      title: "办理阶段",
      dataIndex: "workflow",
      valueEnum: Object.fromEntries(workbenchWorkflows.map((stage) => [stage, itemWorkflowNames[stage]])),
      render: (_, r) => <State value={itemWorkflow(r)} />,
    },
    {
      title: "发行", dataIndex: "issue_id", hideInTable: true,
      formItemRender: () => <RemoteSelect resource="issues" />,
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
      <ServerTable
        resource="items"
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys),
          getCheckboxProps: (record) => ({ disabled: !!record.order_unit_id }),
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
          <Button type="primary" key="create" onClick={() => history.push(assemblyPath(from))}>
            新建数字物品
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
    </PageContainer>
  );
}
