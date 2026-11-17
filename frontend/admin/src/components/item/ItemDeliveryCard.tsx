import { ProCard } from "@ant-design/pro-components";
import { Button, Descriptions, Space, Typography } from "antd";
import { history } from "@umijs/max";
import { time } from "../../catalog";
import type { ItemRecord } from "../../types/catalog";
import { State } from "../CatalogUI";
import ClaimCodeStatus from "../ClaimCodeStatus";
import type { ItemAction } from "./ItemActionDialog";

type Props = {
  item: ItemRecord;
  whole?: NonNullable<ItemRecord["wholes"]>[number];
  orderTarget?: string;
  orderNext?: string | false;
  onAction: (action: ItemAction) => void;
};

export default function ItemDeliveryCard({
  item: r,
  whole: e,
  orderTarget,
  orderNext,
  onAction,
}: Props) {
  return (
    <ProCard
      title="订单与交付"
      headerBordered
      extra={
        orderTarget &&
        !orderNext && (
          <Button onClick={() => history.push(orderTarget)}>
            返回原订单件
          </Button>
        )
      }
    >
      <Descriptions size="small" bordered column={2}>
        <Descriptions.Item label="订单">
          {r.order
            ? r.order.channel +
              " · " +
              r.order.external_order_no +
              " · 第 " +
              r.order.position +
              " 件"
            : "无结构化订单"}
        </Descriptions.Item>
        <Descriptions.Item label="购买规格">
          {r.order?.ordered_spec || "未记录"}
        </Descriptions.Item>
        <Descriptions.Item label="分配时间">
          {time(r.order?.allocated_at)}
        </Descriptions.Item>
        <Descriptions.Item label="首次成交">
          <Space>
            <State value={r.sold ? "已售出" : "未确认售出"} />
            {time(r.first_sold_at)}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="首次交付">
          {time(r.order?.delivered_at)}
        </Descriptions.Item>
        <Descriptions.Item label="交付依据">
          {r.order?.first_delivery_reference || "未记录"}
        </Descriptions.Item>
        {r.order?.delivered_generation && (
          <Descriptions.Item label="交付实物与代次">
            第 {r.order.delivered_generation} 代 ·{" "}
            {r.order.delivered_physical_uid}
          </Descriptions.Item>
        )}
        {!r.order && r.sale_evidence && (
          <Descriptions.Item label="历史成交依据">
            {r.sale_evidence}
          </Descriptions.Item>
        )}
      </Descriptions>
      {!r.owner_id && (!r.order || r.order.delivered_at) && (
        <Space wrap>
          {r.claim_code_status ? (
            <ClaimCodeStatus
              key={r.claim_code_status.id}
              itemId={r.id}
              status={r.claim_code_status}
            />
          ) : (
            <Typography.Text type="secondary">
              首次交付后可发放认领码
            </Typography.Text>
          )}
          <Button
            disabled={
              !r.physical_item_id ||
              r.status !== "active" ||
              !r.provisioned_at ||
              !!e?.lost_at ||
              !!e?.loss_evidence ||
              r.chip_status !== "bound"
            }
            onClick={() =>
              onAction(
                r.claim_code_status ? "reissueClaimCode" : "issueClaimCode",
              )
            }
          >
            {r.claim_code_status ? "核对交付后补发" : "发放认领码"}
          </Button>
        </Space>
      )}
    </ProCard>
  );
}
