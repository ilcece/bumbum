import ReadFailure from "../components/ReadFailure";
import ClaimCodeDialog from "../components/ClaimCodeDialog";
import React, { useEffect, useState } from "react";
import { ProCard } from "@ant-design/pro-components";
import {
  Descriptions,
  Alert,
  Button,
  Collapse,
  Space,
  Spin,
  Table,
  Typography,
  Tooltip,
} from "antd";
import { history, useLocation, useParams } from "@umijs/max";
import { activityPath, fromPath, itemWorkflow, orderPath } from "../catalog";
import AuditDetails from "../components/AuditDetails";
import {
  edition,
  statistics,
  statusNames,
  time,
  wholeStatus,
  validationHelp,
  read,
} from "../catalog";
import {
  DetailContainer,
  InlineCommand,
  Copy,
  Gallery,
  Load,
  State,
  useRecord,
  returnPath,
} from "../components/CatalogUI";
import KeyConfiguration from "../components/KeyConfiguration";
import ItemH5Preview from "../components/ItemH5Preview";
import ItemActivity from "../components/ItemActivity";

import UserIdentity, { PhoneReveal } from "../components/UserIdentity";
import type { ItemAction } from "../components/item/ItemActionDialog";
import ItemActionDialog from "../components/item/ItemActionDialog";
import ItemHandoverDialog from "../components/item/ItemHandoverDialog";
import ItemAssemblyCard from "../components/item/ItemAssemblyCard";
import ItemDeliveryCard from "../components/item/ItemDeliveryCard";
import type {
  ActionResult,
  HandoverRecord,
  OwnershipRecord,
  CatalogStatistics,
} from "../types/catalog";

function HolderPhone({
  itemId,
  holder,
}: {
  itemId: number;
  holder?: OwnershipRecord;
}) {
  if (!holder) return <>手机号未记录</>;
  return (
    <Space wrap>
      <UserIdentity uid={holder.public_uid} />
      <PhoneReveal
        masked={holder.masked_phone}
        path={`/admin/catalog/items/${itemId}/owners/${holder.id}/phone`}
      />
    </Space>
  );
}

export default function ItemDetail({
  id,
  embedded = false,
  onDeleted,
}: {
  id?: number;
  embedded?: boolean;
  onDeleted?: () => void;
}) {
  const params = useParams();
  const location = useLocation();
  const query = new URLSearchParams(location.search);
  const installChip = Number(query.get("installChip"));
  const ident = id || Number(params.id);
  const currentPath = location.pathname + location.search;
  const from = embedded
    ? fromPath("/items/" + ident, currentPath)
    : currentPath;
  const { record: r, error, loading, reload } = useRecord("items", ident),
    [action, setAction] = useState<ItemAction | undefined>(
      installChip || query.get("install") === "1" ? "bind" : undefined,
    ),
    [work, setWork] = useState<HandoverRecord>(),
    [preview, setPreview] = useState(false),
    [claimResult, setClaimResult] = useState<ActionResult>(),
    [keyChip, setKeyChip] = useState<number>(),
    [stats, setStats] = useState<CatalogStatistics>(),
    [statsError, setStatsError] = useState(""),
    [statsRevision, setStatsRevision] = useState(0),
    [scope, setScope] = useState("sold"),
    [range, setRange] = useState("all");
  useEffect(() => {
    let active = true;
    setStats(undefined);
    setStatsError("");
    statistics({ item_id: ident, scope, range })
      .then((x) => {
        if (active) {
          setStats(x);
          setStatsError("");
        }
      })
      .catch((e) => {
        if (active) setStatsError(e.message);
      });
    return () => {
      active = false;
    };
  }, [ident, scope, range, r, statsRevision]);
  const done = (result?: ActionResult) => {
    const deleted = action === "deleteItem";
    if (
      result &&
      (action === "issueClaimCode" || action === "reissueClaimCode")
    )
      setClaimResult(result);
    setAction(undefined);
    setWork(undefined);
    if (action?.startsWith("prepare")) {
      void read("items", r!.id).then((fresh) =>
        setWork(fresh.handovers.find((x) => !x.completed_at)),
      );
    }
    if (deleted) {
      onDeleted?.();
      if (!embedded) history.push("/items");
    } else if (action === "bind" && r?.order && orderTarget) {
      history.push(orderTarget);
    } else reload();
  };
  const e = r?.wholes?.find((x) => !x.ended_at),
    pending = r?.handovers?.find((x) => !x.completed_at);
  const owner = r?.owners?.find((holder) => holder.is_active);
  const canonicalOrder = r?.order ? orderPath(r.order.order_id, r.order.id) : undefined;
  const originalPage = returnPath("");
  const orderTarget =
    canonicalOrder &&
    (originalPage.startsWith(canonicalOrder + "&")
      ? originalPage
      : canonicalOrder);
  const configurable =
    !!e && !(e.lost_at || e.loss_evidence) && r?.chip_status === "bound";
  const canConfigure =
    configurable && !r?.provisioned_at && r?.status !== "archived";
  const canEnable =
    configurable &&
    !!r?.provisioned_at &&
    !!r?.issue_id &&
    r?.status !== "archived" &&
    r?.status !== "active";
  const canInstall =
    !e && !!r?.issue_id && r?.status !== "archived" && !orderTarget;
  const orderNext = orderTarget && !r?.order?.delivered_at && !canConfigure ? orderTarget : undefined;
  const lost = !!(e?.lost_at || e?.loss_evidence);
  const canCancelLoss = lost && !pending && r?.chip_status === "lost";
  const container = (content: React.ReactNode) => (
    <DetailContainer
      embedded={embedded}
      title={
        <Space wrap id="item-detail-heading" tabIndex={-1}>
          {r?.style?.name || "数字物品"}
          <Copy value={r?.item_uid} />
        </Space>
      }
      subTitle={
        r && (
          <Space wrap>
            <State value={itemWorkflow(r)} />
            {r.spec || "规格待核对"} · {r.sold ? "已售出" : "未售出"}
            {r.owner_id && <UserIdentity uid={r.owner_public_uid} />}
          </Space>
        )
      }
      onBack={() => history.push(returnPath("/items"))}
      extra={
        r && (
          <Space wrap>
            <Button onClick={() => setPreview(true)}>预览手机页</Button>
            {r.status === "active" && (
              <Button danger onClick={() => setAction("toggleItem")}>
                停用物品
              </Button>
            )}
            {canConfigure ? (
              <Button type="primary" onClick={() => setKeyChip(e!.chip_id)}>
                配置并核验芯片
              </Button>
            ) : orderNext ? (
              <Button type="primary" onClick={() => history.push(orderNext)}>
                打开对应订单件
              </Button>
            ) : canEnable ? (
              <Button type="primary" onClick={() => setAction("toggleItem")}>
                启用物品
              </Button>
            ) : canInstall ? (
              <Button type="primary" onClick={() => setAction("bind")}>
                安装芯片
              </Button>
            ) : null}
            {e && r.status !== "archived" && (
              <>
                {lost ? (
                  <Tooltip
                    title={
                      pending
                        ? "有未完成的换新或转售，暂不能取消挂失"
                        : !canCancelLoss
                          ? "配套芯片状态需要核对"
                          : undefined
                    }
                  >
                    <span>
                      <Button
                        disabled={!canCancelLoss}
                        onClick={() => setAction("cancelLoss")}
                      >
                        取消挂失
                      </Button>
                    </span>
                  </Tooltip>
                ) : (
                  <Button
                    danger
                    disabled={!["bound", "disabled"].includes(r.chip_status || "")}
                    onClick={() => setAction("loseItem")}
                  >
                    挂失物品
                  </Button>
                )}
                {pending ? (
                  <Button onClick={() => setWork(pending)}>
                    继续办理{pending.kind === "resale" ? "转售" : "换新"}
                  </Button>
                ) : (
                  <>
                    <Button
                      disabled={
                        !r.owner_id ||
                        !r.rights?.some((right) => right.kind === "renewal") ||
                        !!r.quota_review ||
                        (r.quota_used ?? 0) >= 1
                      }
                      onClick={() => setAction("prepareRenewal")}
                    >
                      办理换新
                    </Button>
                    <Button
                      disabled={
                        !r.owner_phone_verified ||
                        !r.rights?.some((right) => right.kind === "resale")
                      }
                      onClick={() => setAction("prepareResale")}
                    >
                      办理转售
                    </Button>
                  </>
                )}
              </>
            )}
            {!orderTarget && r.status !== "archived" && (
              <Button onClick={() => setAction("sale")}>维护售出事实</Button>
            )}
            {!!r.is_validation && (
              <InlineCommand
                danger
                label="直接删除物品"
                action="deleteItem"
                payload={{ item_id: r.id }}
                onDone={() => {
                  onDeleted?.();
                  if (!embedded) history.push("/items");
                }}
              />
            )}
          </Space>
        )
      }
    >
      {content}
    </DetailContainer>
  );
  return container(
    <Load error={error} loading={loading} retry={reload}>
      {r && (
        <div className="page-stack">
          <ProCard
            size="small"
            variant="outlined"
            title="身份与发行"
            headerBordered
            extra={<State value={statusNames[r.status]} />}
          >
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="系统物品编号">
                <Copy value={r.item_uid} />
              </Descriptions.Item>
              <Descriptions.Item label="本件正式序号">
                {edition(r)}
              </Descriptions.Item>
              <Descriptions.Item label="发行约定">
                {r.issue_name || (
                  <Button onClick={() => setAction("linkIssue")}>
                    核对并补齐发行
                  </Button>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="类别">
                {r.project === "fashion" ? "服装" : "饰品"}
              </Descriptions.Item>
              <Descriptions.Item
                label={
                  <Tooltip title={validationHelp}>
                    <span tabIndex={0}>生产验证对象 ⓘ</span>
                  </Tooltip>
                }
              >
                <InlineCommand
                  action="validationItem"
                  payload={{ item_id: r.id, enabled: !r.is_validation }}
                  label="物品生产验证对象"
                  checked={!!r.is_validation}
                  onDone={reload}
                />
              </Descriptions.Item>
            </Descriptions>
          </ProCard>
          <ProCard
            size="small"
            variant="outlined"
            title="共用商品资料"
            headerBordered
            extra={
              r.style && (
                <Button
                  onClick={() =>
                    history.push(
                      `/catalog?tab=styles&keyword=${encodeURIComponent(r.style!.code)}`,
                    )
                  }
                >
                  维护共用款式
                </Button>
              )
            }
          >
            {!r.issue_id && r.project === "fashion" && (
              <Button onClick={() => setAction("legacyProfile")}>
                维护历史单件资料
              </Button>
            )}
            <div className="product-profile">
              <Gallery urls={r.style?.image_urls || []} />
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="商品名称">
                  {r.style?.name || r.legacy_profile?.name || "待补齐"}
                </Descriptions.Item>
                <Descriptions.Item label="介绍">
                  {r.style?.description ||
                    r.legacy_profile?.description ||
                    "未填写"}
                </Descriptions.Item>
                <Descriptions.Item label="材质">
                  {r.style?.material || r.legacy_profile?.material || "未填写"}
                </Descriptions.Item>
                <Descriptions.Item label="养护或寓意">
                  {r.style?.care_instructions ||
                    r.legacy_profile?.care_instructions ||
                    r.legacy_profile?.meaning ||
                    "未填写"}
                </Descriptions.Item>
                <Descriptions.Item label="适用规格">
                  {r.style?.specs?.join("、") || "未填写"}
                </Descriptions.Item>
              </Descriptions>
            </div>
            {!r.issue_id && (
              <Alert
                type="warning"
                title="旧档案未关联发行；原资料保留，核对原承诺后补齐。"
              />
            )}
          </ProCard>
          <ItemAssemblyCard
            item={r}
            whole={e}
            pending={pending}
            canConfigure={canConfigure}
            from={currentPath}
            onAction={setAction}
            onConfigure={setKeyChip}
          />
          <ItemDeliveryCard
            item={r}
            whole={e}
            orderTarget={orderTarget}
            orderNext={orderNext}
            onAction={setAction}
          />
          <ProCard title="持有人与权益" headerBordered>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="适用数字权益">
                {r.rights
                  ?.map(
                    (right) =>
                      `${right.kind === "renewal" ? "换新" : "转售"}（${right.rule_version}）`,
                  )
                  .join("、") || "暂无已确认权益"}
              </Descriptions.Item>
              <Descriptions.Item label="当前持有人">
                {r.owner_id ? (
                  <HolderPhone key={owner?.id} itemId={r.id} holder={owner} />
                ) : (
                  <State value="暂无持有人" />
                )}
              </Descriptions.Item>
              <Descriptions.Item label="年度共享换新额度">
                {r.quota_year
                  ? `${r.quota_year}年，已核定使用${r.quota_used}次`
                  : "年度事实待核对"}
              </Descriptions.Item>
              <Descriptions.Item label="计次状态">
                <State value={r.quota_review ? "待核对计次" : "暂无待核对"} />
              </Descriptions.Item>
            </Descriptions>
            <Collapse
              items={[
                {
                  key: "works",
                  label: `物品办理记录（${r.handovers?.length || 0}）`,
                  children: (
                    <Table
                      rowKey="id"
                      size="small"
                      dataSource={r.handovers}
                      pagination={{ pageSize: 5 }}
                      columns={[
                        {
                          title: "业务",
                          render: (_, x) => (
                            <State value={statusNames[x.kind]} />
                          ),
                        },
                        {
                          title: "新物品",
                          render: (_, x) => `第${x.generation}代 · ${x.spec}`,
                        },
                        {
                          title: "状态",
                          render: (_, x) => (
                            <State
                              value={x.completed_at ? "已完成" : "待生效"}
                            />
                          ),
                        },
                        {
                          title: "操作",
                          render: (_, x) => (
                            <Button type="link" onClick={() => setWork(x)}>
                              查看
                            </Button>
                          ),
                        },
                      ]}
                    />
                  ),
                },
              ]}
            />
          </ProCard>
          <ProCard
            size="small"
            variant="outlined"
            title="历程与动态"
            headerBordered
          >
            <Table
              rowKey="id"
              dataSource={r.wholes}
              pagination={{ pageSize: 5 }}
              scroll={{ x: 700 }}
              columns={[
                { title: "代次", render: (_, x) => `第${x.generation}代` },
                { title: "实际规格", dataIndex: "spec" },
                {
                  title: "配套芯片",
                  render: (_, x) => <Copy value={x.chip_uid} />,
                },
                {
                  title: "状态",
                  render: (_, x) => <State value={wholeStatus(x)} />,
                },
                {
                  title: "挂失事实",
                  render: (_, x) =>
                    x.lost_at || x.loss_evidence ? (
                      <Space orientation="vertical">
                        <State value="曾挂失" />
                        {time(x.lost_at)}
                        <span>{x.loss_evidence}</span>
                      </Space>
                    ) : (
                      "—"
                    ),
                },
                { title: "关联时间", render: (_, x) => time(x.started_at) },
              ]}
            />
            <Collapse
              items={[
                {
                  key: "owners",
                  label: "持有人历史",
                  children: (
                    <Table
                      rowKey="id"
                      dataSource={r.owners}
                      columns={[
                        {
                          title: "脱敏手机号",
                          render: (_, x) => (
                            <HolderPhone key={x.id} itemId={r.id} holder={x} />
                          ),
                        },
                        { title: "开始", render: (_, x) => time(x.bound_at) },
                        { title: "结束", render: (_, x) => time(x.unbound_at) },
                      ]}
                    />
                  ),
                },
              ]}
            />
          </ProCard>
          <ProCard
            size="small"
            variant="outlined"
            title="物品触碰统计"
            headerBordered
            extra={
              <Space>
                <Button
                  onClick={() => setScope(scope === "sold" ? "all" : "sold")}
                >
                  {scope === "sold" ? "售出后的有效触碰" : "生命周期有效触碰"}
                </Button>
                {["7d", "30d", "all"].map((v) => (
                  <Button
                    key={v}
                    type={range === v ? "primary" : "default"}
                    onClick={() => setRange(v)}
                  >
                    {v === "all" ? "全部时间" : v === "7d" ? "近7天" : "近30天"}
                  </Button>
                ))}
              </Space>
            }
          >
            {statsError ? (
              <ReadFailure
                title="触碰统计读取失败"
                error={statsError}
                retry={() => setStatsRevision((value) => value + 1)}
              />
            ) : stats ? (
              <>
                <Button
                  type="link"
                  onClick={() =>
                    history.push(
                      activityPath(from, {
                        event: "tap",
                        item_id: r.id,
                        scope,
                        range,
                        as_of: stats.as_of,
                      }),
                    )
                  }
                >
                  查看 {stats.total} 次有效触碰明细
                </Button>
                <Typography.Paragraph type="secondary">
                  按稳定数字身份汇总历代物品；配置核验、失败及旧读数不计次。北京时间。
                </Typography.Paragraph>
                <Table
                  rowKey="chip_id"
                  dataSource={stats.by_chip}
                  columns={[
                    {
                      title: "配套芯片",
                      render: (_, x) => <Copy value={x.chip_uid} />,
                    },
                    {
                      title: "有效触碰",
                      dataIndex: "total",
                      render: (_, x) => (
                        <Button
                          type="link"
                          onClick={() =>
                            history.push(
                              activityPath(from, {
                                event: "tap",
                                item_id: r.id,
                                chip_id: x.chip_id,
                                scope,
                                range,
                                as_of: stats.as_of,
                              }),
                            )
                          }
                        >
                          {x.total}
                        </Button>
                      ),
                    },
                  ]}
                />
              </>
            ) : (
              <Spin description="正在读取触碰统计">
                <div style={{ height: 72 }} />
              </Spin>
            )}
          </ProCard>
          <ProCard
            title="用户动态"
            headerBordered
            extra={
              <Button
                onClick={() =>
                  history.push(activityPath(from, { item_id: r.id }))
                }
              >
                查看全部动态
              </Button>
            }
          >
            <ItemActivity key={r.id} itemId={r.id} revision={r} />
          </ProCard>
          <ProCard
            title="业务操作记录"
            headerBordered
            extra={
              <Button
                onClick={() =>
                  history.push(
                    fromPath(`/system?tab=audit&item_id=${r.id}`, from),
                  )
                }
              >
                查看全部
              </Button>
            }
          >
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={r.audit || []}
              columns={[
                { title: "时间", render: (_, event) => time(event.created_at) },
                { title: "操作人", dataIndex: "username" },
                { title: "操作", dataIndex: "operation" },
                {
                  title: "结果摘要",
                  render: (_, event) => (
                    <Typography.Paragraph
                      className="audit-row-summary"
                      ellipsis
                    >
                      {(event.summary !== event.operation && event.summary) ||
                        event.outcome ||
                        "未记录"}
                    </Typography.Paragraph>
                  ),
                },
                {
                  title: "详情",
                  width: 88,
                  render: (_, event) => <AuditDetails event={event} />,
                },
              ]}
            />
          </ProCard>
        </div>
      )}
      {r && action && (
        <ItemActionDialog
          item={r}
          whole={e}
          owner={owner}
          action={action}
          installChip={installChip}
          onClose={() => setAction(undefined)}
          onDone={done}
        />
      )}
      {r && work && (
        <ItemHandoverDialog
          item={r}
          work={work}
          onClose={() => setWork(undefined)}
          onDone={() => {
            setWork(undefined);
            reload();
          }}
          onConfigure={setKeyChip}
        />
      )}
      {keyChip && (
        <KeyConfiguration
          id={keyChip}
          onClose={() => setKeyChip(undefined)}
          onUpdated={() => {
            reload();
          }}
        />
      )}
      {preview && r && (
        <ItemH5Preview id={r.id} onClose={() => setPreview(false)} />
      )}
      {claimResult && (
        <ClaimCodeDialog
          code={claimResult.claim_code}
          expiresAt={claimResult.expires_at}
          receipt="可在「订单与交付」查看有效码。旧码无法查看时，请核对交付后补发。"
          onClose={() => setClaimResult(undefined)}
        />
      )}
    </Load>,
  );
}
