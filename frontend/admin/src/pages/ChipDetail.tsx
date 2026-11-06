import { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import {
  Descriptions,
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Space,
  Switch,
  Typography,
} from "antd";
import { history, useParams } from "@umijs/max";
import { Row, statistics, statusNames, time } from "../catalog";
import {
  ActionForm,
  InlineCommand,
  Copy,
  Evidence,
  Load,
  RemoteSelect,
  State,
  required,
  useRecord,
  returnPath,
} from "../components/CatalogUI";
import KeyConfiguration from "../components/KeyConfiguration";
export default function ChipDetail({
  id,
  embedded = false,
  onDeleted,
}: {
  id?: number;
  embedded?: boolean;
  onDeleted?: () => void;
}) {
  const params = useParams();
  const ident = id || Number(params.id),
    { record: r, error, loading, reload } = useRecord("chips", ident),
    [action, setAction] = useState<string>(),
    [keys, setKeys] = useState(false),
    [stats, setStats] = useState<Row>();
  useEffect(() => {
    let active = true;
    statistics({
      chip_id: ident,
      range: "all",
      scope: "all",
    })
      .then((x) => {
        if (active) setStats(x);
      })
      .catch(() => setStats(undefined));
    return () => {
      active = false;
    };
  }, [ident, r]);
  const done = () => {
    if (action === "deleteChip") {
      onDeleted?.();
      if (!embedded) history.push("/chips");
    }
    setAction(undefined);
    reload();
  };
  const content = (
    <Load error={error} loading={loading} retry={reload}>
      {r && (
        <div className="page-stack">
          <ProCard title="芯片档案" headerBordered>
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="芯片编号">
                <Copy value={r.chip_uid} />
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <State value={statusNames[r.chip_status]} />
              </Descriptions.Item>
              <Descriptions.Item label="批次">
                <Copy value={r.batch_no} />
                <Button type="link" onClick={() => setAction("chipBatch")}>
                  维护批次
                </Button>
              </Descriptions.Item>
              <Descriptions.Item label="登记来源">
                {{
                  manual: "手工登记",
                  nfc_cool: "手机扫码",
                  unknown: "历史未知",
                }[r.registration_source as string] || "历史未知"}
              </Descriptions.Item>
              <Descriptions.Item label="生产验证对象">
                <InlineCommand
                  action="validationChip"
                  payload={{ chip_id: r.id, enabled: !r.is_validation }}
                  label="芯片生产验证对象"
                  checked={!!r.is_validation}
                  onDone={reload}
                />
                {!!r.is_validation && (
                  <InlineCommand
                    danger
                    label="直接删除芯片"
                    action="deleteChip"
                    payload={{ chip_id: r.id }}
                    onDone={() => {
                      onDeleted?.();
                      if (!embedded) history.push("/chips");
                    }}
                  />
                )}
              </Descriptions.Item>
              <Descriptions.Item label="登记时间">
                {time(r.created_at)}
              </Descriptions.Item>
            </Descriptions>
          </ProCard>
          <ProCard title="所属物品与配置" headerBordered>
            <div className="page-stack">
              {r.item_id || r.candidate_item_id ? (
                <Space orientation="vertical">
                  <Copy value={r.item_uid} />
                  <State value={r.candidate_id ? "候选未生效" : "当前关联"} />
                  <Button
                    onClick={() =>
                      history.push(
                        `/items/${r.item_id || r.candidate_item_id}?from=${encodeURIComponent("/chips/" + r.id)}`,
                      )
                    }
                  >
                    到物品办理挂失/换新/转售
                  </Button>
                </Space>
              ) : r.chip_status === "pending" ? (
                <Button type="primary" onClick={() => setAction("bind")}>
                  准备首套物品
                </Button>
              ) : (
                <State value="未关联" />
              )}
              <ProCard title="密钥与配置" size="small">
                <State
                  value={
                    r.provisioned_at
                      ? "核验就绪"
                      : r.keys_generated
                        ? "待核验"
                        : "待配置"
                  }
                />
                <Button
                  disabled={
                    !["bound", "pending"].includes(r.chip_status) ||
                    (!r.item_id && !r.candidate_id)
                  }
                  onClick={() => setKeys(true)}
                >
                  查看密钥与配置
                </Button>
              </ProCard>
            </div>
          </ProCard>
          <ProCard title="芯片技术维护" headerBordered>
            <Typography.Paragraph type="secondary">
              技术停用/恢复不改变物品身份与持有人；挂失从整套物品发起，不能通过技术恢复解除。
            </Typography.Paragraph>
            {r.chip_status === "lost" && (
              <Alert
                type="warning"
                title="关联整套物品已挂失，配套芯片随之停用。"
              />
            )}
            <Button
              disabled={
                r.candidate_id ||
                !["pending", "bound", "disabled"].includes(r.chip_status)
              }
              onClick={() => setAction("chipState")}
            >
              {r.chip_status === "disabled" ? "恢复芯片服务" : "临时停用芯片"}
            </Button>
          </ProCard>
          <ProCard title="芯片有效触碰" headerBordered>
            {stats ? (
              <Typography.Title level={3}>{stats.total}次</Typography.Title>
            ) : (
              <Typography.Text type="secondary">
                统计读取未完成，可刷新重试。
              </Typography.Text>
            )}
          </ProCard>
        </div>
      )}
      {r && action && (
        <ActionForm
          title={
            {
              validationChip: "维护生产验证标记",
              deleteChip: "直接删除生产验证芯片",
              bind: "准备物品（实物＋芯片）",
              chipBatch: "维护批次",
              chipState: "芯片技术维护",
            }[action] || "维护芯片"
          }
          action={action}
          initial={{
            chip_id: r.id,
            enabled: !r.is_validation,
            batch_no: r.batch_no,
            state: r.chip_status === "disabled" ? "restore" : "disabled",
          }}
          onDone={done}
          onClose={() => setAction(undefined)}
        >
          <Form.Item name="chip_id" hidden>
            <InputNumber />
          </Form.Item>
          {action === "chipBatch" && (
            <Form.Item name="batch_no" label="批次">
              <Input maxLength={64} />
            </Form.Item>
          )}
          {action === "validationChip" && (
            <Form.Item
              name="enabled"
              label="生产验证标记"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          )}
          {action === "deleteChip" && (
            <Alert
              type="warning"
              title="删除当前芯片及其触碰、办理和关联；物品、持有人及审计保留。"
            />
          )}
          {action === "bind" && (
            <>
              <Form.Item name="item_id" label="目标数字身份" rules={required}>
                <RemoteSelect resource="items" />
              </Form.Item>
              <Form.Item name="spec" label="物品实际规格" rules={required}>
                <Input maxLength={256} />
              </Form.Item>
            </>
          )}
          {action === "chipState" && (
            <>
              <Form.Item name="state" hidden>
                <Input />
              </Form.Item>
              <Evidence />
            </>
          )}
        </ActionForm>
      )}
      {keys && (
        <KeyConfiguration
          id={ident}
          onClose={() => setKeys(false)}
          onUpdated={reload}
        />
      )}
    </Load>
  );
  return embedded ? (
    content
  ) : (
    <PageContainer
      title={r?.chip_uid || "芯片详情"}
      onBack={() => history.push(returnPath("/chips"))}
    >
      {content}
    </PageContainer>
  );
}
