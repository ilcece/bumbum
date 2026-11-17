import { ProCard } from "@ant-design/pro-components";
import { Alert, Button, Descriptions } from "antd";
import { history } from "@umijs/max";
import { statusNames, time, wholeStatus } from "../../catalog";
import type { HandoverRecord, ItemRecord } from "../../types/catalog";
import { Copy, State } from "../CatalogUI";
import type { ItemAction } from "./ItemActionDialog";

type Props = {
  item: ItemRecord;
  whole?: NonNullable<ItemRecord["wholes"]>[number];
  pending?: HandoverRecord;
  canConfigure: boolean;
  from: string;
  onAction: (action: ItemAction) => void;
  onConfigure: (chipId: number) => void;
};

export default function ItemAssemblyCard({
  item: r,
  whole: e,
  pending,
  canConfigure,
  from,
  onAction,
  onConfigure,
}: Props) {
  return (
    <ProCard size="small" variant="outlined" title="实物与芯片" headerBordered>
      {e ? (
        <>
          <Descriptions size="small" bordered column={2}>
            <Descriptions.Item label="物品代次">
              第{e.generation}代物品
            </Descriptions.Item>
            <Descriptions.Item label="物品状态">
              <State value={wholeStatus(e)} />
            </Descriptions.Item>
            <Descriptions.Item label="实体编号">
              {e.physical_uid ? (
                <Copy value={e.physical_uid} />
              ) : (
                "历史编号待核对"
              )}
            </Descriptions.Item>
            <Descriptions.Item label="实物规格">{e.spec}</Descriptions.Item>
            <Descriptions.Item label="配套芯片">
              <Copy
                value={e.chip_uid}
                onClick={() =>
                  history.push(
                    `/chips/${e.chip_id}?from=${encodeURIComponent(from)}`,
                  )
                }
              />
            </Descriptions.Item>
            <Descriptions.Item label="芯片服务状态">
                  <State value={statusNames[r.chip_status || ""] || "关联待核对"} />
            </Descriptions.Item>
            <Descriptions.Item label="配置状态">
              <State
                value={
                  r.provisioned_at
                    ? r.status === "active"
                      ? "核验通过 · 已启用"
                      : "核验通过 · 待启用"
                    : "已安装 · 待核验"
                }
              />
              {r.status === "draft" &&
                e.physical_item_id &&
                !r.provisioned_at &&
                !r.keys_generated &&
                !r.sold &&
                !r.owner_id && (
                  <Button type="link" onClick={() => onAction("undoInstall")}>
                    纠正安装
                  </Button>
                )}
            </Descriptions.Item>
            {(e.lost_at || e.loss_evidence) && (
              <>
                <Descriptions.Item label="挂失时间">
                  {time(e.lost_at)}
                </Descriptions.Item>
                <Descriptions.Item label="挂失依据">
                  {e.loss_evidence}
                </Descriptions.Item>
              </>
            )}
          </Descriptions>
          {(e.lost_at || e.loss_evidence) && (
            <Alert
              type="warning"
              showIcon
              title="当前整套物品已挂失"
              description={
                pending
                  ? "配套芯片已停止服务。当前有未完成的换新或转售。"
                  : r.status === "archived"
                    ? "该物品已归档，配套芯片已停止服务。"
                    : "配套芯片已停止服务。实物找回后可在顶部操作栏取消挂失。"
              }
            />
          )}
          <ProCard title="当前物品的芯片配置" size="small" headerBordered>
            <State value={r.provisioned_at ? "核验就绪" : "待配置"} />
            {!canConfigure && (
              <Button
                disabled={
                  !!(e.lost_at || e.loss_evidence) || r.chip_status !== "bound"
                }
                onClick={() => onConfigure(e.chip_id)}
              >
                查看密钥与配置
              </Button>
            )}
          </ProCard>
        </>
      ) : (
        <Alert type="info" title="尚未准备当前整套物品" />
      )}
    </ProCard>
  );
}
