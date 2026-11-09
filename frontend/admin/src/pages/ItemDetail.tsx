import React, { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import {
  Descriptions,
  Alert,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Steps,
  Switch,
  Table,
  Tabs,
  Typography,
  Tooltip,
} from "antd";
import { history, useLocation, useParams } from "@umijs/max";
import {
  Row,
  edition,
  statistics,
  statusNames,
  time,
  wholeStatus,
  read,
  validationHelp,
} from "../catalog";
import {
  ActionForm,
  DetailContainer,
  InlineCommand,
  Copy,
  Evidence,
  Gallery,
  Load,
  RemoteSelect,
  State,
  required,
  useRecord,
  returnPath,
} from "../components/CatalogUI";
import SaleFields from "../components/SaleFields";
import KeyConfiguration from "../components/KeyConfiguration";
import AssemblyFields from "../components/AssemblyFields";
import ItemH5Preview from "../components/ItemH5Preview";
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
  const installChip = Number(new URLSearchParams(useLocation().search).get("installChip"));
  const ident = id || Number(params.id),
    { record: r, error, loading, reload } = useRecord("items", ident),
    [action, setAction] = useState<string | undefined>(installChip ? "bind" : undefined),
    [work, setWork] = useState<Row>(),
    [preview, setPreview] = useState(false),
    [claimResult, setClaimResult] = useState<Row>(),
    [keyChip, setKeyChip] = useState<number>(),
    [stats, setStats] = useState<Row>(),
    [statsError, setStatsError] = useState(""),
    [scope, setScope] = useState("sold"),
    [range, setRange] = useState("all");
  useEffect(() => {
    let active = true;
    setStats(undefined);
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
  }, [ident, scope, range, r]);
  const done = (result?: Row) => {
    const deleted = action === "deleteItem";
    if (result && (action === "issueClaimCode" || action === "reissueClaimCode")) setClaimResult(result);
    setAction(undefined);
    setWork(undefined);
    if (action?.startsWith("prepare")) {
      void read("items", r!.id).then((fresh) =>
        setWork(fresh.handovers.find((x: Row) => !x.completed_at)),
      );
    }
    if (deleted) {
      onDeleted?.();
      if (!embedded) history.push("/items");
    } else reload();
  };
  const e = r?.wholes?.find((x: Row) => !x.ended_at),
    pending = r?.handovers?.find((x: Row) => !x.completed_at);
  const container = (content: React.ReactNode) => (
    <DetailContainer
      embedded={embedded}
      title={<Copy value={r?.item_uid} />}
      subTitle={`${r?.style?.name || "款式待核对"} · ${r ? edition(r) : ""}`}
      onBack={() => history.push(returnPath("/items"))}
      extra={
        r && (
          <Space>
            {!embedded && (
              <Button onClick={() => history.push(returnPath("/items"))}>
                返回来源
              </Button>
            )}
            <Button onClick={() => setPreview(true)}>预览手机页</Button>
            <Button onClick={() => setAction("sale")}>维护售出确认</Button>
            <Button
              danger={r.status === "active"}
              type={r.status === "active" ? "default" : "primary"}
              disabled={!r.issue_id || r.status === "archived"}
              onClick={() => setAction("toggleItem")}
            >
              {r.status === "active" ? "停用物品" : "启用物品"}
            </Button>
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
            title="数字身份与发行"
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
              </Descriptions.Item>
              <Descriptions.Item label="售出状态">
                <State value={r.sold ? "已售出" : "未确认售出"} />
                <Button type="link" onClick={() => setAction("sale")}>
                  维护售出事实
                </Button>
              </Descriptions.Item>
              <Descriptions.Item label="首次售出时间">
                {time(r.first_sold_at)}
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
                      `/catalog?tab=styles&keyword=${encodeURIComponent(r.style.code)}`,
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
          <ProCard
            size="small"
            variant="outlined"
            title="当前物品（实物＋芯片）"
            headerBordered
            extra={
              e ? (
                <Space wrap>
                  <Button
                    danger
                    disabled={
                      !!(e.lost_at || e.loss_evidence) ||
                      r.status === "archived"
                    }
                    onClick={() => setAction("loseItem")}
                  >
                    挂失物品
                  </Button>
                  {pending ? (
                    <Button type="primary" onClick={() => setWork(pending)}>
                      继续办理{pending.kind === "resale" ? "转售" : "换新"}
                    </Button>
                  ) : (
                    <>
                      <Button
                        disabled={!r.owner_id || !r.rights?.some((right: Row) => right.kind === "renewal") || r.quota_review || r.quota_used >= 1}
                        type="primary"
                        onClick={() => setAction("prepareRenewal")}
                      >
                        办理换新
                      </Button>
                      <Button
                        disabled={!r.owner_phone_verified || !r.rights?.some((right: Row) => right.kind === "resale")}
                        onClick={() => setAction("prepareResale")}
                      >
                        办理转售
                      </Button>
                    </>
                  )}
                </Space>
              ) : (
                <Button
                  disabled={!r.issue_id}
                  type="primary"
                  onClick={() => setAction("bind")}
                >
                  安装芯片
                </Button>
              )
            }
          >
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
                    {e.physical_uid ? <Copy value={e.physical_uid} /> : "历史编号待核对"}
                  </Descriptions.Item>
                  <Descriptions.Item label="实物规格">
                    {e.spec}
                  </Descriptions.Item>
                  <Descriptions.Item label="配套芯片">
                    <Copy
                      value={e.chip_uid}
                      onClick={() =>
                        history.push(
                          `/chips/${e.chip_id}?from=${encodeURIComponent(location.pathname + location.search)}`,
                        )
                      }
                    />
                  </Descriptions.Item>
                  <Descriptions.Item label="芯片服务状态">
                    <State value={statusNames[r.chip_status] || "关联待核对"} />
                  </Descriptions.Item>
                  <Descriptions.Item label="配置状态">
                    <State value={r.provisioned_at ? r.status === "active" ? "核验通过 · 已启用" : "核验通过 · 待启用" : "已安装 · 待核验"} />
                    {r.status === "draft" && e.physical_item_id && !r.provisioned_at && !r.keys_generated && !r.sold && !r.owner_id && <Button type="link" onClick={() => setAction("undoInstall")}>纠正安装</Button>}
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
                    description="配套芯片已停止服务；挂失属于这一代，新代不会继承。解除挂失政策待定。"
                  />
                )}
                <ProCard title="当前物品的芯片配置" size="small" headerBordered>
                  <State value={r.provisioned_at ? "核验就绪" : "待配置"} />
                  <Button
                    disabled={
                      !!(e.lost_at || e.loss_evidence) ||
                      r.chip_status !== "bound"
                    }
                    onClick={() => setKeyChip(e.chip_id)}
                  >
                    查看密钥与配置
                  </Button>
                </ProCard>
              </>
            ) : (
              <Alert type="info" title="尚未准备当前整套物品" />
            )}
          </ProCard>
          <ProCard title="持有人与权益" headerBordered>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="适用数字权益">
                {r.rights?.map((right: Row) => `${right.kind === "renewal" ? "换新" : "转售"}（${right.rule_version}）`).join("、") || "暂无已确认权益"}
              </Descriptions.Item>
              <Descriptions.Item label="当前持有人">
                {r.owner_id ? (
                  <Copy value={r.owner_id} />
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
            {!r.owner_id && (
              <Space wrap>
                <Typography.Text type="secondary">{r.claim_code_status ? `认领码有效期至 ${time(r.claim_code_status.expires_at)}` : "首次交付后可发放认领码"}</Typography.Text>
                <Button disabled={!r.physical_item_id || r.status !== "active" || !r.provisioned_at || !!e?.lost_at || !!e?.loss_evidence || r.chip_status !== "bound"} onClick={() => setAction(r.claim_code_status ? "reissueClaimCode" : "issueClaimCode")}>
                  {r.claim_code_status ? "核对交付后补发" : "发放认领码"}
                </Button>
              </Space>
            )}
            <Collapse
              items={[
                {
                  key: "works",
                  label: `物品办理记录（${r.handovers?.length || 0}）`,
                  children: (
                    <Table<Row>
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
            title="物品历程（实物＋芯片）"
            headerBordered
          >
            <Table<Row>
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
                    <Table<Row>
                      rowKey="id"
                      dataSource={r.owners}
                      columns={[
                        { title: "账户ID", dataIndex: "user_id" },
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
              <Alert type="error" title={statsError} />
            ) : stats ? (
              <>
                <Typography.Title level={3}>{stats.total}次</Typography.Title>
                <Typography.Paragraph type="secondary">
                  按稳定数字身份汇总历代物品；配置核验、失败及旧读数不计次。北京时间。
                </Typography.Paragraph>
                <Table<Row>
                  rowKey="chip_id"
                  dataSource={stats.by_chip}
                  columns={[
                    {
                      title: "配套芯片",
                      render: (_, x) => <Copy value={x.chip_uid} />,
                    },
                    { title: "有效触碰", dataIndex: "total" },
                  ]}
                />
              </>
            ) : null}
          </ProCard>
          <ProCard title="业务操作记录" headerBordered extra={<Button onClick={() => history.push(`/system?tab=audit&item_id=${r.id}`)}>查看全部</Button>}>
            <Table<Row> rowKey="id" size="small" pagination={false} dataSource={r.audit || []} columns={[
              { title: "时间", render: (_, event) => time(event.created_at) },
              { title: "操作人", dataIndex: "username" },
              { title: "结果", render: (_, event) => event.detail?.summary || "历史记录" },
            ]} />
          </ProCard>
        </div>
      )}
      {r && action && (
        <ActionForm
          key={action}
          title={
            {
              loseItem: "挂失物品",
              prepareRenewal: "准备替换物品",
              prepareResale: "准备转售的新整套物品",
              bind: "安装芯片",
              undoInstall: "纠正未配置的安装",
              issueClaimCode: "发放交付认领码",
              reissueClaimCode: "核对交付后补发认领码",
              sale: "维护售出事实",
              linkIssue: "核对并补齐发行",
              validationItem: "维护生产验证标记",
              deleteItem: "直接删除生产验证物品",
              toggleItem:
                r.status === "active" ? "停用物品档案" : "启用物品档案",
            }[action] || "维护物品"
          }
          action={action.startsWith("prepare") ? "prepare" : action === "bind" ? "installAssembly" : action}
          initial={{
            item_id: r.id,
            chip_id: action === "bind" && installChip ? installChip : undefined,
            whole_id: e?.id,
            status: r.status === "active" ? "disabled" : "active",
            confirmed: action === "sale" ? !r.sold : undefined,
            enabled: !r.is_validation,
            profile: r.legacy_profile || {
              name: "",
              description: "",
              material: "",
              care_instructions: "",
            },
            kind:
              action === "prepareResale"
                ? "resale"
                : e?.lost_at || e?.loss_evidence
                  ? "loss"
                  : "periodic",
          }}
          onClose={() => setAction(undefined)}
          onDone={done}
          submitText={
            action === "loseItem"
              ? "确认挂失整套物品"
              : action === "deleteItem"
                ? "直接删除"
                : action === "sale"
                  ? "保存售出确认"
                  : action.startsWith("prepare")
                    ? "保存新物品准备"
                    : action === "bind"
                      ? "确认安装"
                      : action === "toggleItem"
                        ? r.status === "active"
                          ? "确认停用物品"
                          : "确认启用物品"
                        : "保存"
          }
        >
          {action === "legacyProfile" && (
            <>
              <Form.Item
                name={["profile", "name"]}
                label="商品名称"
                rules={required}
              >
                <Input maxLength={128} />
              </Form.Item>
              <Form.Item name={["profile", "description"]} label="介绍">
                <Input.TextArea maxLength={4000} />
              </Form.Item>
              <Form.Item name={["profile", "material"]} label="材质">
                <Input maxLength={256} />
              </Form.Item>
              <Form.Item name={["profile", "care_instructions"]} label="养护">
                <Input.TextArea maxLength={2000} />
              </Form.Item>
            </>
          )}
          <Form.Item name="item_id" hidden>
            <InputNumber />
          </Form.Item>
          {action === "loseItem" && (
            <>
              <Form.Item name="whole_id" hidden>
                <InputNumber />
              </Form.Item>
              <Alert
                type="warning"
                title={`${r.item_uid} · 第${e?.generation}代 · ${e?.spec || "规格不适用"} · ${e?.chip_uid}`}
                description="整套物品挂失并同步停用配套芯片；保留身份、持有人和历史。"
              />
              <Evidence />
            </>
          )}
          {(action === "bind" || action.startsWith("prepare")) && (
            <>
              <Alert
                type="info"
                showIcon
                title={
                  action === "bind"
                    ? "准备首套实物＋芯片"
                    : "准备一整套替换物品，尚未生效"
                }
                description={`${r.item_uid} · ${edition(r)} · ${e ? `第${e.generation}代 · ${e.physical_uid || "实体编号待核对"} · ${e.chip_uid}` : "尚无当前物品"}。${action === "bind" ? "请按实物与芯片标签核对。" : "确认实际交付后新整套才生效。换新按北京时间确认生效日计次。"}`}
              />
              {action.startsWith("prepare") && (
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="业务类型">
                    {action === "prepareResale"
                      ? "后台转售"
                      : e?.lost_at || e?.loss_evidence
                        ? "挂失换新"
                        : "定期换新"}
                  </Descriptions.Item>
                  <Descriptions.Item label="当前持有人">
                    {r.owner_name || "暂无持有人"}{" "}
                    {r.owner_id && <Copy value={r.owner_id} />}
                  </Descriptions.Item>
                  <Descriptions.Item label="年度核对">
                    {r.quota_year || "待核对"}年 · 已核定使用
                    {r.quota_used ?? "待核对"}次 ·{" "}
                    {r.quota_review ? "有待核事项" : "无待核事项"}
                  </Descriptions.Item>
                </Descriptions>
              )}
              <Form.Item name="kind" hidden>
                <Input />
              </Form.Item>
              <AssemblyFields styleId={r.style_id} project={r.project} />
              {action === "prepareResale" && (
                <>
                  <Form.Item name="recipient_id" label="已核对接收账户" rules={required}>
                    <RemoteSelect resource="users" params={{ exclude_id: r.owner_id, verified: true }} />
                  </Form.Item>
                  <Form.Item name="seller_confirmation" label="原持有人确认依据" rules={required}><Input maxLength={1000} /></Form.Item>
                  <Form.Item name="recipient_confirmation" label="接收人确认依据" rules={required}><Input maxLength={1000} /></Form.Item>
                  <Form.Item name="identity_review_required" valuePropName="checked"><Checkbox>有持有争议或身份无法对应，须实名核验</Checkbox></Form.Item>
                  <Form.Item name="identity_verification_reference" label="实名核验结果引用" extra="需要实名核验时填写核验通过的凭证引用。"><Input maxLength={128} /></Form.Item>
                </>
              )}
              {action.startsWith("prepare") && <Evidence />}
            </>
          )}
          {action === "sale" && <SaleFields firstSoldAt={r.first_sold_at} />}
          {action === "undoInstall" && <>
            <Form.Item name="whole_id" hidden><InputNumber /></Form.Item>
            <Alert type="warning" title={`核对实体 ${e?.physical_uid} 和芯片 ${e?.chip_uid}，拆离后再确认。`} />
            <Evidence />
            <Form.Item name="confirmed" valuePropName="checked" rules={[{ validator: (_, value) => value === true ? Promise.resolve() : Promise.reject("请确认已拆离") }]}><Checkbox>已拆离所选芯片</Checkbox></Form.Item>
          </>}
          {(action === "issueClaimCode" || action === "reissueClaimCode") && <>
            <Alert type="info" title="请通过既有交付渠道把认领码交给接收人。认领码有效期为 30 天，补发时旧码失效。" />
            <Form.Item name="delivery_reference" label="首次交付核对依据" rules={required}><Input maxLength={128} /></Form.Item>
            <Form.Item name="confirmed" valuePropName="checked" rules={[{ validator: (_, value) => value === true ? Promise.resolve() : Promise.reject("请确认已核对首次交付") }]}><Checkbox>已核对实际交付与接收对象</Checkbox></Form.Item>
          </>}
          {action === "linkIssue" && (
            <>
              <Form.Item
                name="issue_id"
                label="同类别已确认发行"
                rules={required}
              >
                <RemoteSelect
                  resource="issues"
                  params={{ status: "confirmed", project: r.project }}
                />
              </Form.Item>
              <Form.Item
                name="edition_number"
                label="正式序号（限时核定前留空）"
              >
                <InputNumber min={1} precision={0} />
              </Form.Item>
              <Evidence />
            </>
          )}
          {action === "validationItem" && (
            <Form.Item
              name="enabled"
              label="生产验证标记"
              extra={validationHelp}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          )}
          {action === "deleteItem" && (
            <Alert
              type="warning"
              title="仅删除当前物品及其触碰、办理和关联；另一侧芯片及操作审计保留。"
            />
          )}
          {action === "toggleItem" && (
            <>
              <Form.Item name="status" hidden>
                <Input />
              </Form.Item>
              <Alert
                type="info"
                title="启用须具备发行、整套物品和真实配置核验；停用会永久撤销现有查看资格。"
              />
            </>
          )}
        </ActionForm>
      )}
      {r && work && (
        <Handover
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
      {preview && r && <ItemH5Preview id={r.id} onClose={() => setPreview(false)} />}
      {claimResult && <Modal open title="交付认领码" onCancel={() => setClaimResult(undefined)} footer={<Button onClick={() => setClaimResult(undefined)}>完成</Button>}>
        {claimResult.claim_code ? <><Typography.Paragraph copyable>{claimResult.claim_code}</Typography.Paragraph><p>有效期至 {time(claimResult.expires_at)}。关闭前请复制并交给接收人。</p></> : <Alert type="info" title="已核对发放记录" description="认领原码只显示一次。需要新的认领码时，请核对交付后补发。" />}
      </Modal>}
    </Load>,
  );
}
function Handover({
  item,
  work: initialWork,
  onClose,
  onDone,
  onConfigure,
}: {
  item: Row;
  work: Row;
  onClose: () => void;
  onDone: () => void;
  onConfigure: (id: number) => void;
}) {
  const work =
    item.handovers.find((x: Row) => x.id === initialWork.id) || initialWork;
  const old = item.wholes.find((e: Row) => e.id === work.source_id),
    target = item.wholes.find((e: Row) => e.id === work.target_id);
  return (
    <ActionForm
      title={`${statusNames[work.kind]} · 整套物品办理`}
      cancelText="关闭，保留办理记录"
      action="complete"
      readOnly={!!work.completed_at}
      width={900}
      initial={{ work_id: work.id }}
      onDone={onDone}
      onClose={onClose}
      submitText="确认交付并生效"
      submitDisabled={!work.completed_at && !work.provisioned_at}
    >
      <Form.Item name="work_id" hidden>
        <InputNumber />
      </Form.Item>
      <Steps
        size="small"
        current={work.completed_at ? 2 : 1}
        items={[{ title: "准备替换物品" }, { title: "确认交付与生效" }]}
      />
      <Typography.Paragraph>
        沿用数字身份 <Copy value={item.item_uid} /> · {edition(item)}
      </Typography.Paragraph>
      <ProCard gutter={16}>
        <ProCard title="原物品（实物＋芯片）" variant="outlined">
          <Typography.Paragraph>
            第{old?.generation || "待核对"}代 · {old?.spec}
          </Typography.Paragraph>
          <Copy value={old?.chip_uid} />
          <p>
            原持有人：{work.owner_name || "账户"} <Copy value={work.owner_id} />
          </p>
          <State value={old ? wholeStatus(old) : "待核对"} />
          {old?.loss_evidence && <p>曾挂失：{old.loss_evidence}</p>}
        </ProCard>
        <ProCard title="新物品（实物＋芯片）" variant="outlined">
          <Typography.Paragraph>
            第{work.generation}代 · {work.spec}
          </Typography.Paragraph>
          <Copy value={work.chip_uid} />
          <p>
            接收账户：{work.recipient_name || "账户"}{" "}
            <Copy value={work.recipient_id} />
          </p>
          <State
            value={
              work.completed_at
                ? target
                  ? wholeStatus(target)
                  : "已完成"
                : "待生效"
            }
          />
        </ProCard>
      </ProCard>
      <p>
        准备时间：{time(work.created_at)} · 准备依据：{work.prepare_evidence}
      </p>
      {work.completed_at ? (
        <>
          <Alert
            type="success"
            title="整套新物品已生效，数字身份及发行编号沿用"
            description={`完成于${time(work.completed_at)}。旧物品退出授权，历史挂失记录保留。`}
          />
          <Button onClick={onClose}>关闭，保留办理记录</Button>
        </>
      ) : (
        <>
          <Alert
            type="info"
            title="准备完成，尚未替换当前物品"
            description="只有核对实际交付并明确生效，才切换新旧整套物品及必要持有人关系。"
          />
          <ProCard title="新物品的芯片配置" variant="outlined">
            <State value={work.provisioned_at ? "核验就绪" : "待配置核验"} />
            {!work.provisioned_at && (
              <Typography.Paragraph>
                请先完成候选芯片的真实配置核验，再确认交付生效。
              </Typography.Paragraph>
            )}
            <Button onClick={() => onConfigure(work.chip_id)}>
              查看密钥与配置
            </Button>
          </ProCard>
          <Form.Item name="evidence" label="实际交付核对依据" rules={required}>
            <Input.TextArea maxLength={1000} rows={3} />
          </Form.Item>
          <Form.Item
            name="checked"
            valuePropName="checked"
            rules={[
              {
                validator: (_, v) =>
                  v ? Promise.resolve() : Promise.reject("请确认整套实际交付"),
              },
            ]}
          >
            <Checkbox>已核对整套新物品的实际交付、配套芯片和接收账户</Checkbox>
          </Form.Item>
        </>
      )}
    </ActionForm>
  );
}
