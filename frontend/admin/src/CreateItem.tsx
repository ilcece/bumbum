import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form, Input, Modal, Select, Space } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ApiError,
  createItem,
  listItems,
  readSession,
  safeRecordId,
} from "./api";
import type { ItemView } from "./api";
import { ITEM_PROJECTS } from "./itemFields";
import { sourcePoint } from "./adminNavigation";
import { useNavigationGuard } from "./NavigationGuard";

export function CreateItem({
  onClose,
  onSessionExpired,
}: {
  onClose: () => void;
  onSessionExpired: () => void;
}) {
  const [form] = Form.useForm();
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false);
  const [error, setError] = useState(""),
    [created, setCreated] = useState<ItemView | null>(null);
  const original = useRef<{ project: string; uid: string } | null>(null),
    flight = useRef(false),
    alive = useRef(true);
  const { update, attempt } = useNavigationGuard();
  const { message } = App.useApp();
  const location = useLocation(),
    navigate = useNavigate();
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      update({ dirty: false, busy: false });
    };
  }, [update]);
  async function submit() {
    if (flight.current || unknown) return false;
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return false;
    }
    if (flight.current) return false;
    const uid = values.item_uid.trim();
    original.current = { project: values.project, uid };
    flight.current = true;
    setBusy(true);
    setError("");
    setCreated(null);
    update({ dirty: true, busy: true });
    try {
      const found = await createItem(
        values.project,
        uid,
        values.sku_code?.trim() || null,
      );
      if (
        !safeRecordId(found.id) ||
        found.item_uid !== uid ||
        found.project !== values.project
      )
        throw new Error("创建回执与目标不符");
      if (!alive.current) return false;
      setCreated(found);
      setDirty(false);
      update({ dirty: false, busy: false });
      form.setFieldsValue({ item_uid: "", sku_code: "" });
      return true;
    } catch (failure) {
      if (!alive.current) return false;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try {
          await readSession();
          setError("登录状态已更新，请核对输入后再次提交；未自动重发。");
        } catch (refreshFailure) {
          if (
            refreshFailure instanceof ApiError &&
            refreshFailure.status === 401
          )
            onSessionExpired();
          else setError("登录状态更新失败，输入已保留。");
        }
      } else if (
        failure instanceof ApiError &&
        failure.status >= 400 &&
        failure.status < 500 &&
        failure.code !== "unexpected_response"
      )
        setError(failure.message);
      else {
        setUnknown(true);
        setError(
          "创建结果尚未确认，请先按本次完整物品编号查询；不会自动重发。",
        );
      }
      return false;
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  useEffect(() => {
    update({
      dirty: dirty || unknown,
      busy,
      save: unknown ? undefined : submit,
    });
  }, [dirty, busy, unknown]);
  async function verify() {
    if (!original.current || flight.current) return;
    flight.current = true;
    setBusy(true);
    try {
      const { project, uid } = original.current;
      const result = await listItems({ page: 1, project, keyword: uid });
      if (!alive.current) return;
      const found = result.items.find(
        (item) => item.item_uid === uid && item.project === project,
      );
      if (found && !safeRecordId(found.id)) {
        setError(
          "已找到确切编号，但记录ID超出当前页面可处理范围，请反馈；未重新创建。",
        );
        return;
      }
      if (found) {
        setCreated(found);
        setUnknown(false);
        setDirty(false);
        setError("");
        form.setFieldsValue({ item_uid: "", sku_code: "" });
        void message.info(
          "已找到确切编号，请核对原资料；未覆盖记录，不能仅据查询断言由本次创建。",
        );
      } else {
        setUnknown(false);
        setError(
          "尚未查到该编号，原请求仍可能处理中。请核对后明确提交；重复编号会拒绝而不覆盖。",
        );
      }
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (alive.current)
        setError(
          failure instanceof ApiError
            ? failure.message
            : "查询失败，结果仍未确认。",
        );
    } finally {
      flight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <Modal
      title="创建物品草稿"
      open
      width={560}
      mask={{ closable: false }}
      destroyOnHidden
      closable={!busy}
      onCancel={() => attempt(onClose)}
      footer={
        <Space>
          <Button disabled={busy} onClick={() => form.resetFields()}>
            重置
          </Button>
          <Button disabled={busy} onClick={() => attempt(onClose)}>
            取消
          </Button>
          <Button
            type="primary"
            aria-label="创建并继续"
            loading={busy}
            disabled={busy || unknown}
            onClick={() => void submit()}
          >
            创建并继续
          </Button>
        </Space>
      }
    >
      <Form
        name="item-create"
        form={form}
        layout="vertical"
        initialValues={{ project: "fashion" }}
        onFinish={() => void submit()}
        onValuesChange={() =>
          setDirty(
            !!(
              form.getFieldValue("item_uid") || form.getFieldValue("sku_code")
            ),
          )
        }
      >
        <Form.Item name="project" label="所属项目">
          <Select
            allowClear={false}
            disabled={busy || unknown}
            options={Object.entries(ITEM_PROJECTS).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="item_uid"
          label="物品编号"
          dependencies={["project"]}
          rules={[
            { required: true, message: "请填写物品编号。" },
            {
              validator: async (_, value) => {
                const prefix =
                  form.getFieldValue("project") === "fashion" ? "FASH" : "JEW";
                if (
                  !new RegExp(`^${prefix}-[0-9]{4}-[0-9]{6}$`).test(
                    value?.trim() || "",
                  )
                )
                  throw new Error(
                    `请输入${prefix}-YYYY-NNNNNN格式的半角大写编号。`,
                  );
              },
            },
          ]}
        >
          <Input disabled={busy || unknown} maxLength={32} autoComplete="off" />
        </Form.Item>
        <Form.Item
          name="sku_code"
          label="款式编号"
          extra="可空、可重复，最多64个字符；每件物品的编号仍必须唯一。"
          rules={[
            {
              validator: async (_, value) => {
                if ([...(value?.trim() || "")].length > 64)
                  throw new Error("款式编号最多64个字符。");
              },
            },
          ]}
        >
          <Input disabled={busy || unknown} />
        </Form.Item>
      </Form>
      {error && <Alert type="warning" showIcon title={error} />}
      {unknown && (
        <Button loading={busy} onClick={() => void verify()}>
          按本次编号核对结果
        </Button>
      )}
      {created && (
        <Alert
          type="success"
          showIcon
          title={`已取得物品 ${created.item_uid}，可继续创建下一件。`}
          action={
            <Space>
              <Button
                onClick={() =>
                  attempt(() =>
                    navigate(`/items/${created.id}`, {
                      state: { returnTo: sourcePoint(location) },
                    }),
                  )
                }
              >
                查看该物品
              </Button>
              <Button
                onClick={() =>
                  attempt(() =>
                    navigate(`/items/${created.id}/edit`, {
                      state: { returnTo: sourcePoint(location) },
                    }),
                  )
                }
              >
                完善该物品
              </Button>
            </Space>
          }
        />
      )}
    </Modal>
  );
}
