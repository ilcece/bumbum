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
import {
  FooterToolbar,
  ModalForm,
  ProForm,
  ProFormInstance,
  PageContainer,
} from "@ant-design/pro-components";
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
    <Space size={4} className="copy-value">
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
const colors: Record<string, string> = {
  有未保存修改: "gold",
  已生成: "green",
  配置已核验: "cyan",
  核验就绪: "cyan",
  草稿: "default",
  草案: "default",
  启用: "green",
  停用: "orange",
  归档: "default",
  待绑定: "blue",
  已绑定: "green",
  临时停用: "orange",
  已挂失: "red",
  已退役: "default",
  待配置: "gold",
  "待准备/核验": "gold",
  演示核验就绪: "cyan",
  已确认: "green",
  已确认售出: "blue",
  未确认售出: "default",
  已有持有人: "green",
  暂无持有人: "default",
  已完成: "green",
  待确认接续: "gold",
  候选准备: "purple",
  候选未生效: "purple",
  未关联: "default",
  待封版: "gold",
  待核对计次: "gold",
  暂无待核对: "default",
  旧版记录待核对: "orange",
  当前关联: "green",
  当前持有人: "green",
  未准备: "gold",
  已准备演示标记: "blue",
  未连接: "default",
  未执行: "default",
  待核对: "gold",
  未分配: "default",
  已保存内容: "green",
  未保存预览: "gold",
  全局共享: "red",
  单卡独立: "cyan",
  正式编号待封版: "gold",
  未关联发行: "gold",
  生产验证对象: "orange",
  正常: "green",
  已替换: "default",
  待准备: "gold",
  随物品挂失停用: "red",
  曾挂失: "red",
  待生效: "gold",
  已生效: "green",
};
export function State({ value }: { value: string }) {
  return (
    <Tag color={colors[value] || "default"} className="status-tag">
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
  const [active, setActive] = useState(0);
  if (!urls.length)
    return (
      <div
        className={
          compact ? "product-thumb placeholder-thumb" : "gallery-empty"
        }
      >
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={compact ? "暂无款图" : "暂无商品图片"}
        />
      </div>
    );
  if (compact)
    return (
      <Image
        className="product-thumb"
        src={urls[0]}
        alt="商品款图"
        width={56}
        height={56}
      />
    );
  const current = Math.min(active, urls.length - 1);
  return (
    <div className="product-gallery">
      <Image.PreviewGroup items={urls}>
        <Image
          src={urls[current]}
          alt={`商品图片 ${current + 1}`}
          className="gallery-main"
        />
      </Image.PreviewGroup>
      <div className="gallery-thumbnails" aria-label="商品图片切换">
        {urls.map((url, n) => (
          <button
            key={n}
            type="button"
            className={current === n ? "selected" : ""}
            aria-label={`查看商品图片 ${n + 1}`}
            aria-pressed={current === n}
            onClick={() => setActive(n)}
          >
            <img src={url} alt={`缩略图 ${n + 1}`} />
          </button>
        ))}
        <Typography.Text type="secondary">共 {urls.length} 张</Typography.Text>
      </div>
    </div>
  );
}

export function Product({ row, onClick }: { row: Row; onClick?: () => void }) {
  return (
    <div className="style-cell">
      <Gallery compact urls={row?.image_urls} />
      <div>
        {onClick ? (
          <Button type="link" onClick={onClick}>
            {row?.name || "款式待核对"}
          </Button>
        ) : (
          <Typography.Text strong>{row?.name || "款式待核对"}</Typography.Text>
        )}
        <div className="cell-secondary">
          {row?.material || "材质未填写"} · 图片 {row?.image_urls?.length || 0}{" "}
          张
        </div>
      </div>
    </div>
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
  const [selectedOption, setSelectedOption] = useState<Row>();
  useEffect(() => {
    let live = true;
    setSelectedOption(undefined);
    if (value && ["styles", "issues", "items", "chips", "physical-items"].includes(resource))
      read(resource, Number(value))
        .then((r) => {
          if (live) setSelectedOption(r);
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [resource, value]);
  const key = JSON.stringify(params);
  useEffect(() => {
    const n = ++seq.current;
    list(resource, {
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
        options={(selectedOption &&
        !options.some((r) => r.id === selectedOption.id)
          ? [selectedOption, ...options]
          : options
        ).map((r) => ({
          value: r.id,
          label:
            (r.physical_uid && `${r.physical_uid} · ${r.spec || "规格不适用"}`) ||
            r.chip_uid ||
            r.item_uid ||
            (resource === "styles"
              ? `${r.code} · ${r.name}`
              : resource === "issues"
                ? `${r.name} · ${r.mode === "period" && !r.sealed_at ? "限时待核定" : r.total ? `总量${r.total}个身份` : "非限定"}`
                : `${r.nickname || "账户"}${r.phone ? " · " + r.phone : ""} · ID ${r.id}`),
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
    seq = useRef(0),
    identity = useRef("");
  useEffect(() => {
    const n = ++seq.current;
    const nextIdentity = `${resource}:${id}`;
    // 同一对象后台刷新保留表单和弹窗；切换对象仍清除旧资料。
    if (identity.current !== nextIdentity) setRecord(undefined);
    identity.current = nextIdentity;
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
  const shownRecord =
    identity.current === `${resource}:${id}` ? record : undefined;
  return {
    record: shownRecord,
    error,
    loading: loading && !shownRecord,
    reload: () => setRev((n) => n + 1),
  };
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
  page = false,
  execute,
  onReceipt,
  footerNote,
  className,
  beforeSubmit,
  onDirtyChange,
  submitDisabled = false,
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
  page?: boolean;
  execute?: (payload: Record<string, any>, token: string) => Promise<Row>;
  onReceipt?: (r: Row) => boolean;
  footerNote?: React.ReactNode;
  className?: string;
  beforeSubmit?: (values: Record<string, any>) => Promise<boolean>;
  onDirtyChange?: (dirty: boolean) => void;
  submitDisabled?: boolean;
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
  const ordinary = [
    "style",
    "issue",
    "item",
    "register",
    "legacyProfile",
    "chipBatch",
  ].includes(action);
  const submit = async (v: Record<string, any>) => {
    setBusy(true);
    setError("");
    try {
      if (beforeSubmit && !(await beforeSubmit(v))) return false;
      submitted.current ??= pickPayload(action, v);
      const r = await (execute
        ? execute(submitted.current, token.current)
        : command(action, submitted.current, token.current));
      success.current = true;
      setDirty(false);
      onDirtyChange?.(false);
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
  const leave = (next: () => void) => {
    if (busy) return;
    if (!dirty && !uncertain) {
      next();
      return;
    }
    const continueLeaving = () => {
      success.current = true;
      setDirty(false);
      onDirtyChange?.(false);
      next();
    };
    if (!ordinary || uncertain) {
      modal.confirm({
        title: uncertain ? "操作结果待核对" : "离开未完成的业务确认？",
        content: "不会代为提交本次操作。已提交的结果不会因离开而撤销。",
        okText: "放弃输入并离开",
        cancelText: "返回核对",
        onOk: continueLeaving,
      });
      return;
    }
    const prompt = modal.confirm({
      title: "有未保存修改",
      okText: "保存后继续",
      cancelText: "继续编辑",
      content: (
        <Button
          danger
          onClick={() => {
            prompt.destroy();
            continueLeaving();
          }}
        >
          放弃并继续
        </Button>
      ),
      onOk: async () => {
        if (await form.current?.validateFields().then(submit))
          continueLeaving();
      },
    });
  };
  const close = () => leave(onClose);
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
      leave(() => {
        setDirty(false);
        unblock();
        onClose();
        tx.retry();
      });
    });
    return () => {
      unblock();
      window.removeEventListener("beforeunload", unload);
    };
  }, [dirty, busy, uncertain]);
  const FormContainer = (
    page ? ProForm : ModalForm
  ) as React.ComponentType<any>;
  return (
    <FormContainer
      open={page ? undefined : true}
      title={page ? undefined : title}
      width={width}
      formRef={form}
      className={className}
      initialValues={initial}
      onValuesChange={() => {
        success.current = false;
        setDirty(true);
        onDirtyChange?.(true);
      }}
      onFinish={submit}
      modalProps={{
        onCancel: close,
        maskClosable: false,
        keyboard: !busy,
        closable: !busy,
        destroyOnHidden: true,
        className: action === "style" ? "editor-modal" : undefined,
      }}
      disabled={busy || uncertain}
      submitter={
        readOnly
          ? false
          : {
              searchConfig: { submitText },
              submitButtonProps: {
                disabled: uncertain || submitDisabled,
                loading: busy,
              },
              resetButtonProps: { style: { display: "none" } },
              render: (_: unknown, dom: React.ReactNode[]) => {
                const controls = (
                  <Space>
                    <Button disabled={busy} onClick={close}>
                      {cancelText}
                    </Button>
                    {footerNote ? dom.slice(-1) : dom}
                  </Space>
                );
                const footer = footerNote ? (
                  <div className="editor-footer">
                    <Typography.Text type="secondary">
                      {footerNote}
                    </Typography.Text>
                    {controls}
                  </div>
                ) : (
                  controls
                );
                return page && footerNote ? (
                  <FooterToolbar>{footer}</FooterToolbar>
                ) : (
                  footer
                );
              },
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
                if (onReceipt && !onReceipt(r)) {
                  setUncertain(false);
                  setDirty(true);
                  token.current = crypto.randomUUID();
                  submitted.current = undefined;
                  setError(
                    "已核对款式保存记录，仍有待保存图片，请继续保存共用资料。",
                  );
                  return;
                }
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
    </FormContainer>
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
  createPhysicalItem: ["style_id", "physical_uid", "spec", "batch_no", "supplier_serial"],
  installAssembly: ["item_id", "physical_item_id", "chip_id", "installed"],
  undoInstall: ["item_id", "whole_id", "evidence", "confirmed"],
  sale: ["item_id", "confirmed", "evidence", "first_sold_at"],
  saleBatch: ["item_ids", "confirmed", "evidence", "first_sold_at"],
  toggleItem: ["item_id", "status"],
  loseItem: ["item_id", "whole_id", "evidence"],
  linkIssue: ["item_id", "issue_id", "edition_number", "evidence"],
  prepare: ["item_id", "kind", "physical_item_id", "chip_id", "installed", "evidence", "recipient_id", "seller_confirmation", "recipient_confirmation", "identity_review_required", "identity_verification_reference"],
  complete: ["work_id", "evidence", "checked"],
  issueClaimCode: ["item_id", "delivery_reference", "confirmed"],
  reissueClaimCode: ["item_id", "delivery_reference", "confirmed"],
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
  return value &&
    /^\/(?:items|chips|overview|catalog(?:\/(?:style|issue))?)(\/[1-9][0-9]*)?(\?[^#]*)?$/.test(
      value,
    )
    ? value
    : fallback;
}

export function DetailContainer({
  embedded,
  children,
  ...props
}: React.ComponentProps<typeof PageContainer> & { embedded?: boolean }) {
  return embedded ? (
    <div className="embedded-detail">
      <div className="detail-heading">
        <Typography.Title level={4}>{props.title}</Typography.Title>
        {props.subTitle}
      </div>
      <Space wrap className="detail-actions">
        {props.extra}
      </Space>
      {children}
    </div>
  ) : (
    <PageContainer {...props}>{children}</PageContainer>
  );
}
