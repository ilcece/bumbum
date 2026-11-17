import { ProCard } from "@ant-design/pro-components";
import { Button, List, Typography } from "antd";
import { history, useModel } from "@umijs/max";
import { testBatch } from "../../testDataMode";

export const orderPreparationPath = "/overview/order-preparation";
export type OrderPreparationAction = "createPhysicalItem" | "assembleOrderItem" | "orderSale" | "issueClaimCode" | "toggleItem";

export type OrderPreparationDraft = {
  id: string;
  route: "new" | "stock";
  channel?: string;
  external_order_no?: string;
  physical_item_id?: number;
  item_id?: number;
  item_uid?: string;
  physical_uid?: string;
  sold?: boolean;
  completed?: boolean;
  values?: Record<string, unknown>;
  pending?: {
    action: OrderPreparationAction;
    requestId: string;
    payload: Record<string, unknown>;
  };
};

export function useOrderPreparationDraftKey() {
  const { initialState } = useModel("@@initialState");
  const scope = initialState?.session?.draft_scope;
  return scope && /^[a-f0-9]{64}$/.test(scope)
    ? `bumbum-order-preparation-v1:${scope}:${testBatch() ?? "business"}`
    : undefined;
}

export function readOrderPreparationDrafts(
  key: string,
): OrderPreparationDraft[] {
  try {
    const data = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(data)
      ? data.filter(
          (entry) =>
            entry &&
            typeof entry.id === "string" &&
            ["new", "stock"].includes(entry.route),
        )
      : [];
  } catch {
    return [];
  }
}

export function OrderPreparationQueue() {
  const key = useOrderPreparationDraftKey();
  const entries = key
    ? readOrderPreparationDrafts(key).filter((entry) => !entry.completed)
    : [];
  if (!entries.length) return null;
  return (
    <ProCard title="此浏览器的旧版未办记录" headerBordered>
      <Typography.Text type="secondary">
        已保存的旧待办可继续。新订单请使用上方订单列表。
      </Typography.Text>
      {entries.length > 0 && (
        <List
          dataSource={entries}
          renderItem={(entry) => (
            <List.Item
              actions={[
                <Button
                  key="resume"
                  onClick={() =>
                    history.push(`${orderPreparationPath}?draft=${entry.id}`)
                  }
                >
                  继续办理
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  entry.external_order_no
                    ? `${entry.channel || "待填渠道"} · ${entry.external_order_no}`
                    : "待填写成交来源"
                }
                description={[
                  entry.item_uid || entry.physical_uid,
                  entry.pending
                    ? "有操作结果待核对"
                    : entry.sold
                      ? "待确认交付"
                      : entry.item_id
                        ? "继续核对物品进度"
                        : entry.physical_item_id
                          ? "已登记实体 · 待装配"
                          : entry.route === "stock"
                            ? "选用已有库存"
                            : "登记新实物",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              />
            </List.Item>
          )}
        />
      )}
    </ProCard>
  );
}
