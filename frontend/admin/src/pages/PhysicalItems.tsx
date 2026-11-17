import { useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import { history, useLocation, useParams } from "@umijs/max";
import { Button, Descriptions } from "antd";
import { Copy, Load, RemoteSelect, State, returnPath, useRecord } from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import { assemblyPath, orderPath, time } from "../catalog";
import RegisterPhysical from "../components/RegisterPhysical";

const labels: Record<string, string> = { installed: "已装配", available: "可用", replaced: "已替换", prepared: "售后准备中" };

export default function PhysicalItems() {
  const id = Number(useParams().id);
  return id ? <PhysicalDetail id={id} /> : <PhysicalList />;
}

function PhysicalList() {
  const [create, setCreate] = useState(false);
  const location = useLocation();
  const from = location.pathname + location.search;
  return <PageContainer title={false}>
    <ServerTable resource="physical-items" columns={[
      { title: "实体编号或规格", dataIndex: "keyword", hideInTable: true },
      { title: "款式", dataIndex: "style_id", hideInTable: true, formItemRender: () => <RemoteSelect resource="styles" /> },
      { title: "实体编号", search: false,
        render: (_, r) => <Copy value={r.physical_uid} onClick={() => history.push("/physical-items/" + r.id + "?from=" + encodeURIComponent(from))} /> },
      { title: "款式", dataIndex: "style_name", search: false },
      { title: "实际规格", dataIndex: "spec", search: false },
      { title: "状态", search: false, render: (_, r) => <State value={r.order_id ? "订单已占用" : labels[r.assembly_status || ""]} /> },
    ]} extra={[<Button key="new" type="primary" onClick={() => setCreate(true)}>登记实物</Button>]} />
    {create && <RegisterPhysical onClose={() => setCreate(false)}
      onDone={(r) => history.push("/physical-items/" + r.id + "?from=" + encodeURIComponent(from))} />}
  </PageContainer>;
}

function PhysicalDetail({ id }: { id: number }) {
  const r = useRecord("physical-items", id);
  const location = useLocation();
  const from = location.pathname + location.search;
  return <PageContainer title={r.record?.physical_uid || "实体物品"} onBack={() => history.push(returnPath("/physical-items"))}
    extra={r.record && (r.record.order_id ?
        <Button type="primary" onClick={() => history.push(orderPath(r.record!.order_id!, r.record!.order_unit_id ?? undefined, from))}>打开订单件</Button> :
        r.record.item_id ? <Button type="primary" onClick={() => history.push("/items/" + r.record!.item_id + "?from=" + encodeURIComponent(from))}>打开数字物品</Button> :
          r.record.assembly_status === "available" && <Button type="primary" onClick={() => history.push(assemblyPath(from, { physical_item_id: id }))}>新建数字物品</Button>)}>
    <Load error={r.error} loading={r.loading} retry={r.reload}>
      {r.record && <ProCard title="实体资料">
        <Descriptions size="small" bordered column={2}>
          <Descriptions.Item label="实体编号"><Copy value={r.record.physical_uid} /></Descriptions.Item>
          <Descriptions.Item label="款式"><Button type="link" onClick={() => history.push("/catalog/style/" + r.record!.style_id + "?from=" + encodeURIComponent(from))}>{r.record.style_name}</Button></Descriptions.Item>
          <Descriptions.Item label="实际规格">{r.record.spec || "规格不适用"}</Descriptions.Item>
          <Descriptions.Item label="批次">{r.record.batch_no || "未填写"}</Descriptions.Item>
          <Descriptions.Item label="供应商序列号">{r.record.supplier_serial || "未填写"}</Descriptions.Item>
          <Descriptions.Item label="登记时间">{time(r.record.created_at)}</Descriptions.Item>
        </Descriptions>
      </ProCard>}
    </Load>
  </PageContainer>;
}
