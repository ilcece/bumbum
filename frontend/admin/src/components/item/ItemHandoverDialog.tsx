import { ProCard } from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Steps,
  Typography,
} from "antd";
import { edition, statusNames, time, wholeStatus } from "../../catalog";
import type { HandoverRecord, ItemRecord } from "../../types/catalog";
import { ActionForm, Copy, State, required } from "../CatalogUI";
import UserIdentity from "../UserIdentity";

export default function ItemHandoverDialog({
  item,
  work: initialWork,
  onClose,
  onDone,
  onConfigure,
}: {
  item: ItemRecord;
  work: HandoverRecord;
  onClose: () => void;
  onDone: () => void;
  onConfigure: (id: number) => void;
}) {
  const work =
    item.handovers.find((x) => x.id === initialWork.id) || initialWork;
  const old = item.wholes.find((e) => e.id === work.source_id),
    target = item.wholes.find((e) => e.id === work.target_id);
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
          <Typography.Paragraph>
            实体编号：<Copy value={old?.physical_uid} />
          </Typography.Paragraph>
          <Copy value={old?.chip_uid} />
          <p>
            原持有人：{work.owner_name || "账户"}{" "}
            <UserIdentity uid={work.owner_public_uid} />
          </p>
          <State value={old ? wholeStatus(old) : "待核对"} />
          {old?.loss_evidence && <p>曾挂失：{old.loss_evidence}</p>}
        </ProCard>
        <ProCard title="新物品（实物＋芯片）" variant="outlined">
          <Typography.Paragraph>
            第{work.generation}代 · {work.spec}
          </Typography.Paragraph>
          <Typography.Paragraph>
            实体编号：<Copy value={work.physical_uid} />
          </Typography.Paragraph>
          <Copy value={work.chip_uid} />
          <p>
            接收账户：{work.recipient_name || "账户"}{" "}
            <UserIdentity uid={work.recipient_public_uid} />
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
