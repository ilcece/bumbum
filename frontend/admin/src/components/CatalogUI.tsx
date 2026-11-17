import ReadFailure from "./ReadFailure";
import React, { useEffect, useRef, useState } from "react";
import {
  App,
  Alert,
  Button,
  Empty,
  Form,
  FormInstance,
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
import { list, read, Row } from "../catalog";
import { isDestructiveAction, isOrdinaryAction } from "../api/catalogActions";
import { useCatalogAction, useCatalogCommand } from "../hooks/useCatalogAction";
import type { ActionPayloadMap, ActionResult, CatalogAction, CatalogQuery, CatalogResource, DetailResource, FormValues } from "../types/catalog";
import { sessionIsExpired } from "../api";

const isDetailResource = (resource: CatalogResource): resource is DetailResource =>
  ["styles", "issues", "items", "chips", "physical-items"].includes(resource);
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
          compact ? "product-image-frame product-thumb placeholder-thumb" : "gallery-empty"
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
        className="product-image-frame product-thumb"
        src={urls[0]}
        alt="商品款图"
        width={56}
      />
    );
  const current = Math.min(active, urls.length - 1);
  return (
    <div className="product-gallery">
      <Image.PreviewGroup items={urls}>
        <Image
          src={urls[current]}
          alt={`商品图片 ${current + 1}`}
          className="product-image-frame gallery-main"
        />
      </Image.PreviewGroup>
      <div className="gallery-thumbnails" aria-label="商品图片切换">
        {urls.map((url, n) => (
          <button
            key={n}
            type="button"
            className={current === n ? "product-image-frame selected" : "product-image-frame"}
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
  optionLabel,
  emptyState,
}: {
  id?: string;
  resource: CatalogResource;
  params?: CatalogQuery;
  value?: number | string;
  onChange?: (v: number | string) => void;
  placeholder?: string;
  optionLabel?: (row: Row) => string;
  emptyState?: React.ReactNode;
}) {
  const [options, setOptions] = useState<Row[]>([]),
    [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [refresh, setRefresh] = useState(0),
    [total, setTotal] = useState(0),
    [error, setError] = useState(""),
    [listResult, setListResult] = useState<{ key: string; total?: number; error?: string }>(),
    seq = useRef(0);
  const [selectedOption, setSelectedOption] = useState<Row>();
  useEffect(() => {
    let live = true;
    setSelectedOption(undefined);
    if (value && isDetailResource(resource))
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
  const requestKey = JSON.stringify([resource, key, page, q, refresh]);
  const result = listResult?.key === requestKey ? listResult : undefined;
  const hasEmptyState = emptyState !== undefined;
  // 搜索和切换关联条件时只显示当前查询的候选。翻页期间保留已经加载的前页。
  const candidates = page === 1 && (!result || result.error) ? [] : options;
  const visibleOptions = selectedOption && !candidates.some((r) => r.id === selectedOption.id)
    ? [selectedOption, ...candidates] : candidates;
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
          setListResult({ key: requestKey, total: p.total });
          setError("");
        }
      })
      .catch((e) => {
        if (n === seq.current) setListResult({ key: requestKey, error: e.message });
      });
    return () => { ++seq.current; };
  }, [requestKey]);
  return (
    <>
      <Select
        id={id}
        showSearch={{
          filterOption: false,
          searchValue: q,
          onSearch: (keyword) => {
            setQ(keyword);
            setPage(1);
          },
        }}
        loading={!result}
        disabled={hasEmptyState && !q && (result?.total === 0 || !!result?.error)}
        notFoundContent={!result ? <Spin size="small" /> : result.error ? "读取失败" :
          q && hasEmptyState ? <Space wrap>
            <Typography.Text type="secondary">没有符合搜索词的记录</Typography.Text>
            <Button size="small" onMouseDown={(event) => event.preventDefault()}
              onClick={() => { setQ(""); setPage(1); }}>清除搜索</Button>
          </Space> : q ? "没有符合搜索词的记录" : undefined}
        value={value}
        onChange={onChange}
        onOpenChange={(open) => {
          if (open) {
            if (!hasEmptyState) setQ("");
            setPage(1);
            setRefresh((n) => n + 1);
          }
        }}
        options={visibleOptions.map((r) => ({
          value: r.id,
          label:
            optionLabel?.(r) ||
            (r.physical_uid && `${r.physical_uid} · ${r.spec || "规格不适用"}`) ||
            r.chip_uid ||
            r.item_uid ||
            (resource === "styles"
              ? `${r.code} · ${r.name}`
              : resource === "issues"
                ? `${r.name} · ${r.mode === "period" && !r.sealed_at ? "限时待核定" : r.total ? `总量${r.total}个身份` : "非限定"}`
                : `${r.nickname || "账户"}${r.phone ? " · " + r.phone : ""} · UID ${r.public_uid || r.id}`),
        }))}
        onPopupScroll={(e) => {
          const el = e.currentTarget;
          if (
            el.scrollTop + el.clientHeight >= el.scrollHeight - 8 &&
            !!result && !result.error && options.length < total
          )
            setPage((p) => p + 1);
        }}
        placeholder={placeholder || "搜索并选择真实记录"}
        style={{ minWidth: 200, width: "100%" }}
      />
      {error && <Typography.Text type="danger">{error}</Typography.Text>}
      {result?.error && <ReadFailure title={hasEmptyState ? "库存读取失败" : "候选读取失败"}
        error={result.error} retry={() => setRefresh((n) => n + 1)} />}
      {hasEmptyState && !q && result?.total === 0 && emptyState}
    </>
  );
}
export { useCatalogRecord as useRecord } from "../hooks/useCatalogRecord";
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
    <ReadFailure error={error} retry={retry} />
  ) : loading ? (
    <Spin description="正在读取真实数据">
      <div style={{ height: 100 }} />
    </Spin>
  ) : (
    <>{children}</>
  );
}
export function ActionForm<A extends CatalogAction>({
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
  formInstance,
}: {
  title: string;
  action: A;
  initial?: object;
  children: React.ReactNode;
  onDone: (r: ActionResult) => void;
  onClose: () => void;
  submitText?: string;
  cancelText?: string;
  width?: number;
  readOnly?: boolean;
  page?: boolean;
  execute?: (payload: ActionPayloadMap[A], token: string) => Promise<ActionResult>;
  onReceipt?: (r: ActionResult) => boolean;
  footerNote?: React.ReactNode;
  className?: string;
  beforeSubmit?: (values: FormValues) => Promise<boolean>;
  onDirtyChange?: (dirty: boolean) => void;
  submitDisabled?: boolean;
  formInstance?: FormInstance<FormValues>;
}) {
  const [dirty, setDirty] = useState(false);
  const form = useRef<ProFormInstance<FormValues> | undefined>(undefined);
  const { modal } = App.useApp();
  const { error, busy, uncertain, retryReady, success, submit, checkReceipt, retry } = useCatalogAction({
    action, execute, beforeSubmit, onDone, onReceipt,
    onSaved: () => { setDirty(false); onDirtyChange?.(false); },
    onIncompleteReceipt: () => setDirty(true),
  });
  const ordinary = isOrdinaryAction(action);
  const destructive = isDestructiveAction(action);
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
        focusable: { autoFocusButton: "cancel" },
        onOk: continueLeaving,
      });
      return;
    }
    let saving = false;
    const prompt = modal.confirm({
      title: "有未保存修改",
      content: "可以继续编辑、放弃本次输入，或保存后离开。",
      okText: "保存后继续",
      cancelText: "继续编辑",
      focusable: { autoFocusButton: "cancel" },
      okButtonProps: { disabled: submitDisabled },
      footer: (_, { CancelBtn, OkBtn }) => (
        <Space wrap>
          <CancelBtn />
          <Button danger onClick={() => {
            if (saving) return;
            prompt.destroy();
            continueLeaving();
          }}>放弃并离开</Button>
          <OkBtn />
        </Space>
      ),
      onOk: async () => {
        saving = true;
        prompt.update({ cancelButtonProps: { disabled: true }, keyboard: false });
        const values = await (formInstance ?? form.current)?.validateFields().catch(() => undefined);
        // 校验失败或服务报错时，关闭离开提示，留在原表单查看错误。
        if (values && await submit(values)) continueLeaving();
      },
    });
  };
  const close = () => leave(onClose);
  useEffect(() => {
    const unload = (e: BeforeUnloadEvent) => {
      if (!success.current && !sessionIsExpired() && (dirty || busy || uncertain)) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    const unblock = history.block((tx) => {
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
  const FormContainer = page ? ProForm<FormValues> : ModalForm<FormValues>;
  return (
    <FormContainer
      open={page ? undefined : true}
      title={page ? undefined : title}
      width={width}
      formRef={form}
      form={formInstance}
      className={className}
      initialValues={initial as FormValues}
      scrollToFirstError={{ focus: true, block: "nearest" }}
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
                danger: destructive,
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
                return page ? (
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
            onClick={() => void checkReceipt()}
          >
            核对已提交回执
          </Button>
          {retryReady && (
            <Button
              loading={busy}
              disabled={busy}
              onClick={() => void retry()}
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

export function InlineCommand<A extends CatalogAction>({
  action,
  payload,
  label,
  onDone,
  danger = false,
  checked,
}: {
  action: A;
  payload: ActionPayloadMap[A];
  label: string;
  onDone: () => void;
  danger?: boolean;
  checked?: boolean;
}) {
  const { busy, error, uncertain, retryReady, send, checkReceipt } = useCatalogCommand({ action, payload, onDone });
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
          onClick={() => void checkReceipt()}
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
    /^\/(?:items|physical-items|orders|chips|overview(?:\/activity)?|system|catalog(?:\/(?:style|issue))?)(\/[1-9][0-9]*)?(\?[^#]*)?$/.test(
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
