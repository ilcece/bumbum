import {
  Alert,
  Checkbox,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
} from "antd";
import { edition, validationHelp } from "../../catalog";
import type {
  ActionResult,
  ItemRecord,
  OwnershipRecord,
} from "../../types/catalog";
import { ActionForm, Evidence, RemoteSelect, required } from "../CatalogUI";
import AssemblyFields from "../AssemblyFields";
import SaleFields from "../SaleFields";

export type ItemAction =
  | "legacyProfile"
  | "loseItem"
  | "cancelLoss"
  | "prepareRenewal"
  | "prepareResale"
  | "bind"
  | "undoInstall"
  | "issueClaimCode"
  | "reissueClaimCode"
  | "sale"
  | "linkIssue"
  | "validationItem"
  | "deleteItem"
  | "toggleItem";

type Props = {
  item: ItemRecord;
  whole?: NonNullable<ItemRecord["wholes"]>[number];
  owner?: OwnershipRecord;
  action: ItemAction;
  installChip: number;
  onClose: () => void;
  onDone: (result?: ActionResult) => void;
};

export default function ItemActionDialog({
  item: r,
  whole: e,
  owner,
  action,
  installChip,
  onClose,
  onDone,
}: Props) {
  return (
    <ActionForm
      key={action}
      title={
        {
          legacyProfile: "维护物品",
          loseItem: "挂失物品",
          cancelLoss: "取消挂失",
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
          toggleItem: r.status === "active" ? "停用物品档案" : "启用物品档案",
        }[action] || "维护物品"
      }
      action={
        action === "prepareRenewal" || action === "prepareResale"
          ? "prepare"
          : action === "bind"
            ? "installAssembly"
            : action
      }
      initial={{
        item_id: r.id,
        chip_id: action === "bind" && installChip ? installChip : undefined,
        physical_item_id:
          action === "bind" ? r.order?.physical_item_id : undefined,
        whole_id: e?.id,
        lost_at: e?.lost_at ?? null,
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
      onClose={onClose}
      onDone={onDone}
      submitText={
        action === "loseItem"
          ? "确认挂失整套物品"
          : action === "cancelLoss"
            ? "确认取消挂失"
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
      {(action === "loseItem" || action === "cancelLoss") && (
        <>
          <Form.Item name="whole_id" hidden>
            <InputNumber />
          </Form.Item>
          {action === "cancelLoss" && (
            <Form.Item name="lost_at" hidden>
              <Input />
            </Form.Item>
          )}
          <Alert
            type="warning"
            title={`${r.item_uid} · 第${e?.generation}代 · ${e?.spec || "规格不适用"} · ${e?.chip_uid}`}
            description={
              action === "loseItem"
                ? "挂失后配套芯片停止普通触碰服务。"
                : "核对实物已经找回。取消挂失后，现有找回入口立即失效，操作记录保留。"
            }
          />
          {action === "cancelLoss" &&
            (r.chip_state_before_loss ? (
              <p>
                {r.chip_state_before_loss === "disabled"
                  ? "芯片在挂失前已停用，取消后仍保持停用。"
                  : "芯片恢复到挂失前的已关联状态。"}
              </p>
            ) : (
              <Form.Item
                name="chip_state"
                label="取消后芯片服务"
                rules={required}
              >
                <Select
                  placeholder="旧挂失未记录原芯片状态，请选择"
                  options={[
                    { value: "disabled", label: "保持芯片停用" },
                    {
                      value: "bound",
                      label: "已核对芯片，恢复服务",
                      disabled: !r.provisioned_at,
                    },
                  ]}
                />
              </Form.Item>
            ))}
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
                {r.owner_id
                  ? owner?.masked_phone || "手机号未记录"
                  : "暂无持有人"}
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
          <AssemblyFields
            styleId={r.style_id}
            project={r.project}
            orderUnit={action === "bind" ? r.order : undefined}
          />
          {action === "prepareResale" && (
            <>
              <Form.Item
                name="recipient_id"
                label="已核对接收账户"
                rules={required}
              >
                <RemoteSelect
                  resource="users"
                  params={{ exclude_id: r.owner_id, verified: true }}
                />
              </Form.Item>
              <Form.Item
                name="seller_confirmation"
                label="原持有人确认依据"
                rules={required}
              >
                <Input maxLength={1000} />
              </Form.Item>
              <Form.Item
                name="recipient_confirmation"
                label="接收人确认依据"
                rules={required}
              >
                <Input maxLength={1000} />
              </Form.Item>
              <Form.Item
                name="identity_review_required"
                valuePropName="checked"
              >
                <Checkbox>有持有争议或身份无法对应，须实名核验</Checkbox>
              </Form.Item>
              <Form.Item
                name="identity_verification_reference"
                label="实名核验结果引用"
                extra="需要实名核验时填写核验通过的凭证引用。"
              >
                <Input maxLength={128} />
              </Form.Item>
            </>
          )}
          {action.startsWith("prepare") && <Evidence />}
        </>
      )}
      {action === "sale" && <SaleFields firstSoldAt={r.first_sold_at} />}
      {action === "undoInstall" && (
        <>
          <Form.Item name="whole_id" hidden>
            <InputNumber />
          </Form.Item>
          <Alert
            type="warning"
            title={`核对实体 ${e?.physical_uid} 和芯片 ${e?.chip_uid}，拆离后再确认。`}
          />
          <Evidence />
          <Form.Item
            name="confirmed"
            valuePropName="checked"
            rules={[
              {
                validator: (_, value) =>
                  value === true
                    ? Promise.resolve()
                    : Promise.reject("请确认已拆离"),
              },
            ]}
          >
            <Checkbox>已拆离所选芯片</Checkbox>
          </Form.Item>
        </>
      )}
      {(action === "issueClaimCode" || action === "reissueClaimCode") && (
        <>
          <Alert
            type="info"
            title="请通过既有交付渠道把认领码交给接收人。认领码有效期为 30 天，补发时旧码失效。"
          />
          <Form.Item
            name="delivery_reference"
            label="首次交付核对依据"
            rules={required}
          >
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item
            name="confirmed"
            valuePropName="checked"
            rules={[
              {
                validator: (_, value) =>
                  value === true
                    ? Promise.resolve()
                    : Promise.reject("请确认已核对首次交付"),
              },
            ]}
          >
            <Checkbox>已核对实际交付与接收对象</Checkbox>
          </Form.Item>
        </>
      )}
      {action === "linkIssue" && (
        <>
          <Form.Item name="issue_id" label="同类别已确认发行" rules={required}>
            <RemoteSelect
              resource="issues"
              params={{ status: "confirmed", project: r.project }}
            />
          </Form.Item>
          <Form.Item name="edition_number" label="正式序号（限时核定前留空）">
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
  );
}
