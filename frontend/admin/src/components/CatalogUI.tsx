import React, { useEffect, useRef, useState } from "react";
import {
  App,
  Alert,
  Button,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
} from "antd";
import { ModalForm, ProFormInstance } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { command, list, read, Row, unknown } from "../catalog";
import { ApiError, readSession, sessionIsExpired } from "../api";
export function Copy({
  value,
  onClick,
}: {
  value?: string | number | null;
  onClick?: () => void;
}) {
  return value === null || value === undefined || value === "" ? (
    <Typography.Text type="secondary">未记录</Typography.Text>
  ) : (
    <Space size={4}>
      {onClick ? (
        <Button type="link" onClick={onClick}>
          {value}
        </Button>
      ) : (
        <span>{value}</span>
      )}
      <Typography.Text copyable={{ text: String(value) }} />
    </Space>
  );
}
export function State({ value }: { value: string }) {
  return (
    <Tag
      color={
        /挂失/.test(value)
          ? "red"
          : /启用|正常|已确认|已完成|核验就绪|已售出/.test(value)
            ? "green"
            : /待|停用|验证/.test(value)
              ? "orange"
              : "default"
      }
    >
      {value}
    </Tag>
  );
}
export function Gallery({
  urls = [],
  compact = false,
}: {
  urls?: string[];
  compact?: boolean;
}) {
  return urls.length ? (
    <Image.PreviewGroup>
      {urls.map((url, n) => (
        <Image
          key={url}
          src={url}
          alt={`商品参考图${n + 1}`}
          width={compact ? 56 : 160}
          height={compact ? 56 : 160}
          style={{ objectFit: "contain", marginRight: 8 }}
        />
      ))}
    </Image.PreviewGroup>
  ) : (
    <div style={{ width: compact ? 56 : undefined }}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={compact ? "暂无款图" : "暂无图片"}
      />
    </div>
  );
}
export function Product({ row }: { row: Row }) {
  return (
    <Space>
      <Gallery compact urls={row.image_urls?.slice(0, 1) || []} />
      <div>
        <strong>{row.name || "款式待核对"}</strong>
        <div className="cell-secondary">
          {row.material || "材质未填写"} · 图片 {row.image_urls?.length || 0} 张
        </div>
      </div>
    </Space>
  );
}
export function RemoteSelect({
  id,
  resource,
  params = {},
  value,
  onChange,
  placeholder,
}: {
  id?: string;
  resource: string;
  params?: Record<string, any>;
  value?: number;
  onChange?: (v: number) => void;
  placeholder?: string;
}) {
  const [options, setOptions] = useState<Row[]>([]),
    [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [total, setTotal] = useState(0),
    [error, setError] = useState(""),
    seq = useRef(0);
  const key = JSON.stringify(params);
  useEffect(() => {
    const n = ++seq.current;
    list(resource, {
      data_scope: "all",
      ...params,
      page,
      page_size: 20,
      keyword: q,
    })
      .then((p) => {
        if (n === seq.current) {
          setOptions((prev) =>
            page === 1
              ? p.items
              : [
                  ...prev,
                  ...p.items.filter((x) => !prev.some((y) => y.id === x.id)),
                ],
          );
          setTotal(p.total);
          setError("");
        }
      })
      .catch((e) => {
        if (n === seq.current) setError(e.message);
      });
  }, [resource, key, page, q]);
  return (
    <>
      <Select
        id={id}
        showSearch
        filterOption={false}
        value={value}
        onChange={onChange}
        onSearch={(v) => {
          setQ(v);
          setPage(1);
        }}
        options={options.map((r) => ({
          value: r.id,
          label:
            r.chip_uid ||
            r.item_uid ||
            `${r.name || r.nickname || "账户"}${r.code ? " · " + r.code : ""}${r.phone ? " · " + r.phone : ""} · ID ${r.id}`,
        }))}
        onPopupScroll={(e) => {
          const el = e.currentTarget;
          if (
            el.scrollTop + el.clientHeight >= el.scrollHeight - 8 &&
            options.length < total
          )
            setPage((p) => p + 1);
        }}
        placeholder={placeholder || "搜索并选择真实记录"}
        style={{ minWidth: 200, width: "100%" }}
      />
      {error && <Typography.Text type="danger">{error}</Typography.Text>}
    </>
  );
}
export function useRecord(resource: string, id?: number) {
  const [record, setRecord] = useState<Row>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [rev, setRev] = useState(0),
    seq = useRef(0);
  useEffect(() => {
    const n = ++seq.current;
    setRecord(undefined);
    setError("");
    if (id === undefined) return;
    if (!Number.isSafeInteger(id) || id < 1 || id > 2147483647) {
      setError("记录编号无效或超出页面可处理范围。");
      return;
    }
    setLoading(true);
    read(resource, id)
      .then((v) => {
        if (n === seq.current) setRecord(v);
      })
      .catch((e) => {
        if (n === seq.current) setError(e.message);
      })
      .finally(() => {
        if (n === seq.current) setLoading(false);
      });
  }, [resource, id, rev]);
  return { record, error, loading, reload: () => setRev((n) => n + 1) };
}
export function Load({
  error,
  loading,
  retry,
  children,
}: {
  error: string;
  loading: boolean;
  retry: () => void;
  children: React.ReactNode;
}) {
  return error ? (
    <Alert
      type="error"
      title={error}
      action={<Button onClick={retry}>重试读取</Button>}
    />
  ) : loading ? (
    <Spin description="正在读取真实数据">
      <div style={{ height: 100 }} />
    </Spin>
  ) : (
    <>{children}</>
  );
}
export function ActionForm({
  title,
  action,
  initial = {},
  children,
  onDone,
  onClose,
  submitText = "保存",
  cancelText = "取消",
  width = 680,
  readOnly = false,
}: {
  title: string;
  action: string;
  initial?: Record<string, any>;
  children: React.ReactNode;
  onDone: (r: Row) => void;
  onClose: () => void;
  submitText?: string;
  cancelText?: string;
  width?: number;
  readOnly?: boolean;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [uncertain, setUncertain] = useState(false),
    [retryReady, setRetryReady] = useState(false),
    [dirty, setDirty] = useState(false),
    success = useRef(false),
    token = useRef(crypto.randomUUID()),
    submitted = useRef<Record<string, any> | undefined>(undefined),
    form = useRef<ProFormInstance | undefined>(undefined);
  const { modal } = App.useApp();
  const submit = async (v: Record<string, any>) => {
    setBusy(true);
    setError("");
    try {
      submitted.current ??= pickPayload(action, v);
      const r = await command(action, submitted.current, token.current);
      success.current = true;
      setDirty(false);
      onDone(r);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求未完成");
      if (e instanceof ApiError && e.code === "csrf_failed") {
        try {
          await readSession();
          setError("会话口令已更新，请明确重试；未自动重发。");
        } catch {
          setError("登录状态无法更新，请重新登录。");
        }
      }
      if (unknown(e)) setUncertain(true);
      else {
        token.current = crypto.randomUUID();
        submitted.current = undefined;
      }
      return false;
    } finally {
      setBusy(false);
    }
  };
  const close = () => {
    if (busy) return;
    if (dirty || uncertain)
      modal.confirm({
        title: "有未保存修改或待核对结果",
        content: "关闭将清除输入；已提交的操作不会被撤销。",
        okText: "放弃并关闭",
        cancelText: "继续编辑",
        onOk: onClose,
      });
    else onClose();
  };
  useEffect(() => {
    const unload = (e: BeforeUnloadEvent) => {
      if (!sessionIsExpired() && (dirty || busy || uncertain)) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    const unblock = history.block((tx: any) => {
      if (
        sessionIsExpired() ||
        success.current ||
        (!dirty && !busy && !uncertain)
      ) {
        unblock();
        tx.retry();
        return;
      }
      if (busy) return;
      modal.confirm({
        title: "有未保存修改",
        okText: "保存后继续",
        cancelText: "继续编辑",
        content: (
          <Button
            danger
            onClick={() => {
              setDirty(false);
              unblock();
              onClose();
              tx.retry();
            }}
          >
            放弃并继续
          </Button>
        ),
        onOk: async () => {
          if (await form.current?.validateFields().then(submit)) {
            unblock();
            tx.retry();
          }
        },
      });
    });
    return () => {
      unblock();
      window.removeEventListener("beforeunload", unload);
    };
  }, [dirty, busy, uncertain]);
  return (
    <ModalForm
      open
      title={title}
      width={width}
      formRef={form}
      initialValues={initial}
      onValuesChange={() => setDirty(true)}
      onFinish={submit}
      modalProps={{
        onCancel: close,
        maskClosable: false,
        keyboard: !busy,
        closable: !busy,
        destroyOnHidden: true,
      }}
      disabled={busy || uncertain}
      submitter={
        readOnly
          ? false
          : {
              searchConfig: { submitText },
              submitButtonProps: { disabled: uncertain, loading: busy },
              resetButtonProps: { style: { display: "none" } },
              render: (_, dom) => (
                <Space>
                  <Button disabled={busy} onClick={close}>
                    {cancelText}
                  </Button>
                  {dom}
                </Space>
              ),
            }
      }
    >
      {children}
      {error && (
        <Alert
          style={{ marginTop: 16 }}
          showIcon
          type="error"
          title={uncertain ? "保存结果未知，请先核对" : error}
          description={uncertain ? error : undefined}
        />
      )}
      {uncertain && (
        <Space style={{ marginTop: 12 }}>
          <Button
            disabled={busy}
            onClick={async () => {
              try {
                const r = await command(
                  "receipt",
                  { request_id: token.current },
                  crypto.randomUUID(),
                );
                success.current = true;
                onDone(r);
              } catch (e) {
                if (e instanceof ApiError && e.status === 404) {
                  setRetryReady(true);
                  setError("服务端尚无已提交回执，可以明确重试原请求。");
                } else setError(e instanceof Error ? e.message : "核对失败");
              }
            }}
          >
            核对已提交回执
          </Button>
          {retryReady && (
            <Button
              loading={busy}
              disabled={busy}
              onClick={() => void submit(submitted.current!)}
            >
              明确重试原请求
            </Button>
          )}
        </Space>
      )}
    </ModalForm>
  );
}
export const required = [{ required: true, message: "请填写此项" }];
export function Evidence() {
  return (
    <Form.Item name="evidence" label="核对依据" rules={required}>
      <Input.TextArea rows={3} maxLength={1000} />
    </Form.Item>
  );
}

const fields: Record<string, string[]> = {
  legacyProfile: ["item_id", "profile"],
  style: [
    "id",
    "project",
    "code",
    "name",
    "description",
    "material",
    "care_instructions",
    "specs",
    "image_urls",
    "shared_confirmed",
    "test_batch_id",
  ],
  issue: [
    "id",
    "style_id",
    "name",
    "series",
    "mode",
    "total",
    "starts_at",
    "ends_at",
    "counting_rule",
    "description",
    "rights",
  ],
  confirmIssue: ["issue_id"],
  deleteIssue: ["issue_id"],
  seal: ["issue_id", "total", "evidence"],
  clearTestBatch: ["batch_id", "confirmed"],
  item: [
    "issue_id",
    "item_uid",
    "edition_number",
    "is_validation",
    "test_batch_id",
  ],
  bind: ["item_id", "chip_id", "spec"],
  sale: ["item_id", "confirmed", "evidence"],
  toggleItem: ["item_id", "status"],
  loseItem: ["item_id", "whole_id", "evidence"],
  linkIssue: ["item_id", "issue_id", "edition_number", "evidence"],
  prepare: ["item_id", "kind", "chip_id", "spec", "evidence", "recipient_id"],
  complete: ["work_id", "evidence", "checked"],
  validationItem: ["item_id", "enabled"],
  deleteItem: ["item_id"],
  validationChip: ["chip_id", "enabled"],
  deleteChip: ["chip_id"],
  register: [
    "chip_uid",
    "project",
    "batch_no",
    "is_validation",
    "test_batch_id",
  ],
  chipBatch: ["chip_id", "batch_no"],
  chipState: ["chip_id", "state", "evidence"],
};
function pickPayload(action: string, value: Record<string, any>) {
  if (action === "legacyProfile") {
    value = {
      ...value,
      profile: {
        ...value.profile,
        image_urls: [],
      },
    };
  }
  return Object.fromEntries(
    (fields[action] || [])
      .filter((k) => value[k] !== undefined)
      .map((k) => [k, value[k]]),
  );
}
export function InlineCommand({
  action,
  payload,
  label,
  onDone,
  danger = false,
  checked,
}: {
  action: string;
  payload: Record<string, any>;
  label: string;
  onDone: () => void;
  danger?: boolean;
  checked?: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [uncertain, setUncertain] = useState(false),
    [retryReady, setRetryReady] = useState(false),
    token = useRef(crypto.randomUUID()),
    done = useRef(false);
  const send = async () => {
    done.current = false;
    setBusy(true);
    try {
      await command(action, payload, token.current);
      done.current = true;
      setUncertain(false);
      setError("");
      token.current = crypto.randomUUID();
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作未完成");
      if (unknown(e)) setUncertain(true);
      else token.current = crypto.randomUUID();
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (!busy && !uncertain) return;
    const unblock = history.block((tx: any) => {
      if (sessionIsExpired() || done.current) {
        unblock();
        tx.retry();
      }
    });
    return unblock;
  }, [busy, uncertain]);
  return (
    <Space wrap>
      {checked === undefined ? (
        <Button
          danger={danger}
          loading={busy}
          disabled={uncertain}
          onClick={() => void send()}
        >
          {label}
        </Button>
      ) : (
        <Switch
          aria-label={label}
          checked={checked}
          loading={busy}
          disabled={uncertain}
          onChange={() => void send()}
        />
      )}
      {error && (
        <Typography.Text type="danger">
          {uncertain ? "结果未知，先核对回执。" : error}
        </Typography.Text>
      )}
      {uncertain && (
        <Button
          onClick={async () => {
            try {
              await command(
                "receipt",
                { request_id: token.current },
                crypto.randomUUID(),
              );
              done.current = true;
              setUncertain(false);
              onDone();
            } catch (e) {
              if (e instanceof ApiError && e.status === 404)
                setRetryReady(true);
              else setError(e instanceof Error ? e.message : "核对失败");
            }
          }}
        >
          核对结果
        </Button>
      )}
      {retryReady && (
        <Button onClick={() => void send()} loading={busy}>
          明确重试原请求
        </Button>
      )}
    </Space>
  );
}

export function returnPath(fallback: string) {
  const value = new URLSearchParams(window.location.search).get("from");
  return value && /^\/(items|chips)(\/[1-9][0-9]*)?(\?[^#]*)?$/.test(value)
    ? value
    : fallback;
}
