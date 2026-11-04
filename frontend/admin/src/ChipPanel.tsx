import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Result,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { PageHeading } from "./MakeSurfaces";
import { InventorySearch } from "./InventorySearch";
import { PlusOutlined } from "@ant-design/icons";
import { RecordSurface } from "./MakeSurfaces";
import {
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ApiError,
  CHIP_FILTERS,
  listChips,
  readChip,
  readSession,
  safeRecordId,
  saveChipBatch,
} from "./api";
import type { ChipDetail, ChipQuery, ChipView } from "./api";
import { safeReturn, sourcePoint } from "./adminNavigation";
import { useNavigationGuard } from "./NavigationGuard";
import { BindItemDialog } from "./BindItemDialog";
import { ChipKeysDialog } from "./ChipKeysDialog";
import { beijingTime } from "./itemFields";
import { CreateChip } from "./CreateChip";

export const PROJECTS = {
  fashion: "服装",
  jewelry: "饰品",
  unassigned: "未分配",
};
const STATUSES = {
  pending: "待绑定",
  bound: "已绑定",
  disabled: "停用",
  lost: "丢失",
};
const SOURCES = {
  manual: "网页手工",
  nfc_cool: "手机扫描",
  unknown: "历史未知",
};
const MATCHES: Record<string, string> = {
  chip_uid: "芯片UID",
  item_uid: "关联物品编号",
  item_name: "关联物品名称",
};
export const failureText = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.message : fallback;

type Field = {
  key: keyof ChipDetail;
  label: string;
  render: (chip: ChipDetail) => ReactNode;
};
function useChipFields(): Field[] {
  const location = useLocation();
  return [
    {
      key: "chip_uid",
      label: "芯片UID",
      render: (chip) => (
        <Typography.Text copyable>{chip.chip_uid}</Typography.Text>
      ),
    },
    {
      key: "project",
      label: "项目",
      render: (chip) => PROJECTS[chip.project || "unassigned"],
    },
    {
      key: "chip_status",
      label: "状态",
      render: (chip) => <Tag>{STATUSES[chip.chip_status]}</Tag>,
    },
    {
      key: "batch_no",
      label: "批次",
      render: (chip) => chip.batch_no || "未填写",
    },
    {
      key: "registration_source",
      label: "首次登记来源",
      render: (chip) => SOURCES[chip.registration_source],
    },
    {
      key: "item_uid",
      label: "关联物品",
      render: (chip) =>
        chip.item_id === null ? (
          "未关联"
        ) : safeRecordId(chip.item_id) ? (
          <Link
            to={`/items/${chip.item_id}`}
            state={{ returnTo: sourcePoint(location) }}
          >
            {chip.item_uid || "查看关联物品"}
          </Link>
        ) : (
          "关联编号无法处理，请反馈"
        ),
    },
    {
      key: "item_name",
      label: "关联物品名称",
      render: (chip) =>
        chip.item_name || (chip.item_id === null ? "未关联" : "未填写"),
    },
    {
      key: "keys_generated",
      label: "密钥生成",
      render: (chip) => (chip.keys_generated ? "已生成" : "未生成"),
    },
    {
      key: "provisioned_at",
      label: "配置核验时间（北京时间）",
      render: (chip) =>
        chip.provisioned_at ? beijingTime(chip.provisioned_at) : "未核验",
    },
    {
      key: "created_at",
      label: "登记时间（北京时间）",
      render: (chip) => beijingTime(chip.created_at),
    },
    {
      key: "updated_at",
      label: "更新时间（北京时间）",
      render: (chip) => beijingTime(chip.updated_at),
    },
  ];
}

function queryFrom(search: URLSearchParams): ChipQuery {
  const integer = (name: string, fallback: number) =>
    /^[1-9][0-9]*$/.test(search.get(name) || "")
      ? Number(search.get(name))
      : fallback;
  const query: ChipQuery = {
    page: integer("page", 1),
    page_size: integer("page_size", 20),
  };
  for (const key of CHIP_FILTERS)
    if (search.has(key)) query[key] = search.get(key)!;
  return query;
}
function queryString(query: ChipQuery) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    if (value !== "" && value !== undefined && value !== null)
      search.set(key, String(value));
  return search;
}
function submittedQuery(
  values: Record<string, unknown>,
  pageSize: number,
): ChipQuery {
  const query: ChipQuery = { page: 1, page_size: pageSize };
  for (const key of CHIP_FILTERS)
    if (
      !/_(from|to)$/.test(key) &&
      typeof values[key] === "string" &&
      values[key]
    )
      query[key] = values[key] as string;
  for (const name of ["created", "updated", "provisioned"] as const) {
    const range = values[`${name}_range`];
    if (Array.isArray(range) && range.length === 2) {
      if (range[0]) query[`${name}_from`] = String(range[0]);
      if (range[1]) query[`${name}_to`] = String(range[1]);
    }
  }
  return query;
}
function validateChip(value: ChipDetail, id: number) {
  if (
    value.id !== id ||
    typeof value.chip_uid !== "string" ||
    typeof value.keys_generated !== "boolean" ||
    !(value.chip_status in STATUSES) ||
    !(value.registration_source in SOURCES) ||
    !(
      value.project === null ||
      value.project === "fashion" ||
      value.project === "jewelry"
    ) ||
    !(value.batch_no === null || typeof value.batch_no === "string")
  )
    throw new Error("芯片返回资料不符合约定。");
  return value;
}

function ChipListPage({ onSessionExpired }: { onSessionExpired: () => void }) {
  const location = useLocation(),
    navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const recordOpen = location.pathname !== "/chips";
  const backgroundSearch =
    recordOpen && typeof location.state?.returnTo?.path === "string"
      ? location.state.returnTo.path.split("?")[1] || ""
      : "";
  const query = useMemo(
    () =>
      queryFrom(new URLSearchParams(recordOpen ? backgroundSearch : search)),
    [recordOpen, backgroundSearch, search],
  );
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<{
    items: ChipDetail[];
    total: number;
    page: number;
  }>({ items: [], total: 0, page: 1 });
  const [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const initialValues = useMemo(() => {
    const initial: Record<string, unknown> = {
      ...Object.fromEntries(CHIP_FILTERS.map((key) => [key, undefined])),
      ...query,
    };
    for (const name of ["created", "updated", "provisioned"])
      initial[`${name}_range`] =
        query[`${name}_from` as keyof ChipQuery] ||
        query[`${name}_to` as keyof ChipQuery]
          ? [
              query[`${name}_from` as keyof ChipQuery]
                ? dayjs(String(query[`${name}_from` as keyof ChipQuery]))
                : null,
              query[`${name}_to` as keyof ChipQuery]
                ? dayjs(String(query[`${name}_to` as keyof ChipQuery]))
                : null,
            ]
          : undefined;
    return initial;
  }, [query]);
  useEffect(() => {
    const ticket = ++sequence.current;
    let cancelled = false;
    setLoading(true);
    setError("");
    listChips(query)
      .then((result) => {
        if (
          !Array.isArray(result.items) ||
          !Number.isSafeInteger(result.total) ||
          result.total < 0
        )
          throw new Error("列表返回异常");
        result.items.forEach((row) => validateChip(row, row.id));
        if (cancelled || ticket !== sequence.current) return;
        setData(result);
        if (result.page_adjusted && !recordOpen)
          setSearch(queryString({ ...query, page: result.page }), {
            replace: true,
          });
      })
      .catch((failure) => {
        if (cancelled || ticket !== sequence.current) return;
        setData({ items: [], total: 0, page: 1 });
        if (failure instanceof ApiError && failure.status === 401)
          onSessionExpired();
        else setError(failureText(failure, "列表读取失败，请重试。"));
      })
      .finally(() => {
        if (!cancelled && ticket === sequence.current) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, revision, recordOpen, onSessionExpired]);
  useEffect(() => {
    if (
      !loading &&
      !recordOpen &&
      typeof location.state?.restoreScroll === "number"
    )
      window.scrollTo({ top: location.state.restoreScroll });
  }, [loading, recordOpen, location.key]);
  useEffect(() => {
    if (recordOpen) setCreateOpen(false);
  }, [recordOpen]);
  const columns: ColumnsType<ChipDetail> = [
    {
      title: "芯片UID",
      dataIndex: "chip_uid",
      width: 210,
      fixed: "left",
      render: (v, row) => (
        <div>
          <Typography.Text className="make-id" copyable>
            {v}
          </Typography.Text>
          {!!row.keyword_matches?.length && (
            <div className="make-secondary">
              命中：
              {row.keyword_matches.map((key) => MATCHES[key] || key).join("、")}
            </div>
          )}
          {!safeRecordId(row.id) && (
            <Typography.Text type="warning">
              记录编号超出页面可处理范围，请联系维护。
            </Typography.Text>
          )}
        </div>
      ),
    },
    {
      title: "项目／来源",
      key: "project",
      width: 140,
      render: (_, row) => (
        <div>
          <Tag
            color={
              row.project === "fashion"
                ? "blue"
                : row.project === "jewelry"
                  ? "gold"
                  : "default"
            }
          >
            {PROJECTS[row.project || "unassigned"]}
          </Tag>
          <div className="make-secondary">
            {SOURCES[row.registration_source]}
          </div>
        </div>
      ),
    },
    {
      title: "状态",
      dataIndex: "chip_status",
      width: 100,
      render: (v) => (
        <Tag
          color={v === "bound" ? "green" : v === "pending" ? "blue" : "orange"}
        >
          {STATUSES[v as keyof typeof STATUSES]}
        </Tag>
      ),
    },
    {
      title: "批次",
      dataIndex: "batch_no",
      width: 170,
      render: (v) => v || "未填写",
    },
    {
      title: "关联物品",
      key: "item",
      width: 220,
      render: (_, row) =>
        row.item_id ? (
          <div>
            <Link
              to={`/items/${row.item_id}`}
              state={{ returnTo: sourcePoint(location) }}
            >
              {row.item_uid}
            </Link>
            <div className="make-secondary">
              {row.item_name || "未填写名称"}
            </div>
          </div>
        ) : (
          "未关联"
        ),
    },
    {
      title: "密钥与配置进度",
      key: "configuration",
      width: 190,
      render: (_, row) => (
        <div>
          {row.keys_generated ? "已生成" : "未生成"}
          <div className="make-secondary">
            {row.provisioned_at ? "实卡配置已核验" : "待核验"}
          </div>
        </div>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 110,
      fixed: "right",
      render: (_, row) => (
        <Button
          type="link"
          disabled={!safeRecordId(row.id)}
          onClick={() =>
            navigate(`/chips/${row.id}`, {
              state: { returnTo: sourcePoint(location) },
            })
          }
        >
          查看详情
        </Button>
      ),
    },
  ];
  return (
    <div
      className="make-stack"
      aria-hidden={recordOpen || undefined}
      inert={recordOpen || undefined}
    >
      <PageHeading
        title="芯片管理"
        subtitle="查询身份、关联与配置，维护日常资料。"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setCreateOpen(true)}
          >
            登记芯片
          </Button>
        }
      />
      {!recordOpen ? (
        <InventorySearch
          key={queryString(query).toString()}
          kind="chips"
          initialValues={initialValues}
          busy={loading}
          onFinish={(values) => {
            const normalized = { ...values };
            for (const name of ["created", "updated", "provisioned"]) {
              const range = normalized[`${name}_range`];
              if (Array.isArray(range))
                normalized[`${name}_range`] = range.map(
                  (value) => value?.format?.("YYYY-MM-DD") || "",
                );
            }
            setSearch(
              queryString(submittedQuery(normalized, query.page_size || 20)),
            );
          }}
          onReset={() => setSearch(new URLSearchParams())}
        />
      ) : (
        <Card size="small">
          <Typography.Text type="secondary">
            原列表查询条件已保留
          </Typography.Text>
        </Card>
      )}
      {error && <Alert type="error" showIcon title={error} />}
      <Card
        size="small"
        title={
          <Space>
            <span>芯片列表</span>
            <Tag color="blue">共 {data.total} 条</Tag>
          </Space>
        }
        extra={
          <Button onClick={() => setRevision((v) => v + 1)} loading={loading}>
            刷新列表
          </Button>
        }
      >
        <Table<ChipDetail>
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={data.items}
          loading={loading}
          scroll={{ x: 1250 }}
          pagination={{
            disabled: loading,
            current: query.page,
            pageSize: query.page_size || 20,
            total: data.total,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100],
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setSearch(
                queryString({
                  ...queryFrom(new URLSearchParams(window.location.search)),
                  page,
                  page_size: pageSize,
                }),
              );
            },
          }}
          locale={{
            emptyText: error
              ? "读取失败，请重试查询。"
              : search.toString()
                ? "没有符合条件的记录，可重置查询。"
                : "尚无记录，可创建草稿。",
          }}
        />
      </Card>
      {createOpen && !recordOpen && (
        <CreateChip
          onClose={() => {
            setCreateOpen(false);
            setRevision((v) => v + 1);
          }}
          onSessionExpired={onSessionExpired}
        />
      )}
    </div>
  );
}

function ChipRecord({
  edit,
  onSessionExpired,
}: {
  edit?: boolean;
  onSessionExpired: () => void;
}) {
  const { id } = useParams();
  const navigate = useNavigate(),
    location = useLocation();
  const [chip, setChip] = useState<ChipDetail | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [outcome, setOutcome] = useState("");
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false);
  const [special, setSpecial] = useState<"bind" | "keys" | null>(null);
  const [interaction, setInteraction] = useState({ dirty: false, busy: false });
  const [form] = Form.useForm();
  const { update } = useNavigationGuard();
  const { message } = App.useApp();
  const fields = useChipFields();
  const inFlight = useRef(false),
    mounted = useRef(true);
  const originalBatch = useRef<string | null>(null),
    baseline = useRef<string | null>(null);
  const updateInteraction = useCallback(
    (value: { dirty: boolean; busy: boolean }) => setInteraction(value),
    [],
  );
  const updateFromKeys = useCallback(
    (value: ChipView) =>
      setChip((current) => (current ? { ...current, ...value } : current)),
    [],
  );
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let cancelled = false;
    setChip(null);
    setError("");
    setDirty(false);
    setBusy(false);
    setUnknown(false);
    setSpecial(null);
    if (!id || !/^[1-9][0-9]*$/.test(id) || !safeRecordId(Number(id))) {
      setError("芯片记录编号无效，未读取其他记录。");
      return;
    }
    readChip(Number(id))
      .then((value) => {
        validateChip(value, Number(id));
        if (!cancelled) {
          setChip(value);
          baseline.current = value.batch_no;
          if (edit) form.setFieldsValue({ batch_no: value.batch_no || "" });
        }
      })
      .catch((failure) => {
        if (cancelled) return;
        if (failure instanceof ApiError && failure.status === 401)
          onSessionExpired();
        else setError(failureText(failure, "芯片读取失败，请重试或返回。"));
      });
    return () => {
      cancelled = true;
    };
  }, [id, edit, revision, form, onSessionExpired]);
  useEffect(() => () => update({ dirty: false, busy: false }), [update]);
  async function save() {
    if (!chip || inFlight.current || unknown) return false;
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return false;
    }
    if (inFlight.current) return false;
    const batch = values.batch_no?.trim() || null;
    originalBatch.current = batch;
    inFlight.current = true;
    setBusy(true);
    setError("");
    update({ dirty: true, busy: true });
    try {
      const result = validateChip(await saveChipBatch(chip.id, batch), chip.id);
      if (result.batch_no !== batch) throw new Error("保存回执与提交值不符");
      if (!mounted.current) return false;
      setChip(result);
      baseline.current = result.batch_no;
      setDirty(false);
      setUnknown(false);
      update({ dirty: false, busy: false });
      void message.success(
        "批次已保存。返回列表会按原条件重新查询；若不再匹配，可调整查询。",
      );
      return true;
    } catch (failure) {
      if (!mounted.current) return false;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try {
          await readSession();
          setError("登录状态已更新，输入已保留，请再次明确提交；未自动重发。");
        } catch (refreshFailure) {
          if (
            refreshFailure instanceof ApiError &&
            refreshFailure.status === 401
          )
            onSessionExpired();
          else setError("登录状态更新失败，输入已保留，请重试。");
        }
      } else if (
        failure instanceof ApiError &&
        failure.status < 500 &&
        failure.code !== "unexpected_response"
      )
        setError(failure.message);
      else {
        setUnknown(true);
        setError("保存结果尚未确认，请先按记录ID核对；不会自动重发。");
      }
      return false;
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  useEffect(() => {
    update({
      dirty: dirty || unknown || interaction.dirty,
      busy: busy || interaction.busy,
      save: edit && !unknown ? save : undefined,
    });
  }, [dirty, busy, unknown, interaction, chip, edit]);
  async function verify() {
    if (!chip || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const found = validateChip(await readChip(chip.id), chip.id);
      if (!mounted.current) return;
      setChip(found);
      baseline.current = found.batch_no;
      setUnknown(false);
      const matches = found.batch_no === originalBatch.current;
      setDirty(!matches);
      setError(
        matches
          ? "已确认服务器当前批次与本次提交一致。"
          : "服务器当前批次与本次提交不同，输入已保留。原请求仍可能处理中，请核对后决定是否手动保存。",
      );
      if (matches) form.setFieldsValue({ batch_no: found.batch_no || "" });
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else setError(failureText(failure, "读取失败，保存结果仍未确认。"));
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function back() {
    const point = safeReturn(location.state?.returnTo);
    navigate(point?.path || "/chips", {
      state: { returnTo: point?.parent, restoreScroll: point?.scroll },
    });
  }
  function refreshAfterAction(_chip: ChipView, recovered: boolean) {
    setOutcome(recovered ? "已查询确认绑定结果。" : "绑定成功。");
    setSpecial(null);
    setInteraction({ dirty: false, busy: false });
    setRevision((value) => value + 1);
  }
  const title = edit ? "编辑芯片" : "芯片详情";
  return (
    <RecordSurface
      edit={edit}
      title={title}
      subtitle={chip?.chip_uid}
      onClose={back}
      extra={
        <Space>
          <Button onClick={back}>返回来源</Button>
          {chip && !edit && (
            <Button
              type="primary"
              onClick={() =>
                navigate(`/chips/${chip.id}/edit`, { state: location.state })
              }
            >
              编辑批次
            </Button>
          )}
        </Space>
      }
      footer={
        <Space>
          <Button onClick={back}>取消</Button>
          <Button
            disabled={busy || unknown}
            onClick={() => {
              form.setFieldsValue({ batch_no: baseline.current || "" });
              setDirty(false);
            }}
          >
            恢复已保存值
          </Button>
          <Button
            type="primary"
            aria-label="保存批次"
            loading={busy}
            disabled={busy || unknown}
            onClick={() => form.submit()}
          >
            保存批次
          </Button>
        </Space>
      }
    >
      {outcome && (
        <div role="status" style={{ marginBottom: 16 }}>
          <Alert type="success" showIcon title={outcome} />
        </div>
      )}
      {!chip ? (
        error ? (
          <Result
            status="warning"
            title="无法读取芯片"
            subTitle={error}
            extra={
              <Button onClick={() => setRevision((v) => v + 1)}>
                重试读取
              </Button>
            }
          />
        ) : (
          <Spin description="正在读取芯片">
            <div style={{ height: 160 }} />
          </Spin>
        )
      ) : (
        <div className="make-stack">
          {error && (
            <Alert
              type="warning"
              showIcon
              title={error}
              action={
                unknown && (
                  <Button loading={busy} onClick={() => void verify()}>
                    核对保存结果
                  </Button>
                )
              }
            />
          )}
          <Card size="small" title="芯片身份与配置">
            {edit ? (
              <Form
                name="chip-edit"
                form={form}
                layout="vertical"
                initialValues={{ batch_no: chip.batch_no || "" }}
                onFinish={async () => {
                  if (await save())
                    navigate(`/chips/${chip.id}`, {
                      replace: true,
                      state: location.state,
                    });
                }}
                onValuesChange={(values) =>
                  setDirty(
                    (values.batch_no?.trim() || null) !== baseline.current,
                  )
                }
              >
                {fields.map((field) =>
                  field.key === "batch_no" ? (
                    <Form.Item
                      key={field.key}
                      name="batch_no"
                      label={field.label}
                      rules={[{ max: 64, message: "批次最多64个字符。" }]}
                      extra="可以补录、修改或清空，首尾空白会去除。"
                    >
                      <Input maxLength={64} disabled={busy || unknown} />
                    </Form.Item>
                  ) : (
                    <Form.Item key={field.key} label={field.label}>
                      {field.render(chip)}
                    </Form.Item>
                  ),
                )}
              </Form>
            ) : (
              <Descriptions
                size="small"
                bordered
                column={1}
                items={fields.map((f) => ({
                  key: f.key,
                  label: f.label,
                  children: f.render(chip),
                }))}
              />
            )}
          </Card>
          {!edit && (
            <Card size="small" title="受控操作">
              <Space>
                <Button
                  disabled={
                    chip.chip_status !== "pending" ||
                    chip.item_id !== null ||
                    !safeRecordId(chip.id)
                  }
                  onClick={() => setSpecial("bind")}
                >
                  绑定物品
                </Button>
                <Button
                  disabled={
                    chip.chip_status !== "bound" ||
                    chip.item_id === null ||
                    !safeRecordId(chip.id)
                  }
                  onClick={() => setSpecial("keys")}
                >
                  密钥与配置
                </Button>
              </Space>
            </Card>
          )}
        </div>
      )}
      {chip && special === "bind" && (
        <BindItemDialog
          chip={chip}
          onClose={() => setSpecial(null)}
          onBound={refreshAfterAction}
          onSessionExpired={onSessionExpired}
          onInteraction={updateInteraction}
        />
      )}
      {chip && special === "keys" && (
        <ChipKeysDialog
          chip={chip}
          onClose={() => {
            setSpecial(null);
            setRevision((v) => v + 1);
          }}
          onUpdated={updateFromKeys}
          onSessionExpired={onSessionExpired}
          onInteraction={updateInteraction}
        />
      )}
    </RecordSurface>
  );
}

export function ChipPanel({
  onSessionExpired,
}: {
  onSessionExpired: () => void;
}) {
  return (
    <>
      <ChipListPage onSessionExpired={onSessionExpired} />
      <Routes>
        <Route index element={null} />
        <Route
          path=":id"
          element={<ChipRecord onSessionExpired={onSessionExpired} />}
        />
        <Route
          path=":id/edit"
          element={<ChipRecord edit onSessionExpired={onSessionExpired} />}
        />
        <Route
          path="*"
          element={
            <Result
              status="404"
              title="芯片页面不存在"
              extra={<Link to="/chips">返回芯片列表</Link>}
            />
          }
        />
      </Routes>
    </>
  );
}
