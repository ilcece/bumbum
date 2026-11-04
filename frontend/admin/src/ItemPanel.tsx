import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Result,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { PageHeading } from "./MakeSurfaces";
import { InventorySearch } from "./InventorySearch";
import { PlusOutlined } from "@ant-design/icons";
import {
  Link,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { ApiError, ITEM_FILTERS, listItems, safeRecordId } from "./api";
import type { ItemQuery, ItemSummary } from "./api";
import { sourcePoint } from "./adminNavigation";
import { ITEM_PROJECTS, ITEM_STATUSES, validateItem } from "./itemFields";
import { CreateItem } from "./CreateItem";
import { ItemDetailPage } from "./ItemDetailPage";
const MATCHES: Record<string, string> = {
  item_uid: "物品编号",
  sku_code: "款式编号",
  name: "物品名称",
  chip_uid: "关联芯片UID",
};
const failureText = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.message : fallback;

function queryFrom(search: URLSearchParams): ItemQuery {
  const integer = (name: string, fallback: number) =>
    /^[1-9][0-9]*$/.test(search.get(name) || "")
      ? Number(search.get(name))
      : fallback;
  const query: ItemQuery = {
    page: integer("page", 1),
    page_size: integer("page_size", 20),
  };
  for (const key of ITEM_FILTERS)
    if (search.has(key)) query[key] = search.get(key)!;
  return query;
}
function queryString(query: ItemQuery) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    if (value !== "" && value !== undefined && value !== null)
      search.set(key, String(value));
  return search;
}
function submittedQuery(
  values: Record<string, unknown>,
  pageSize: number,
): ItemQuery {
  const query: ItemQuery = { page: 1, page_size: pageSize };
  for (const key of ITEM_FILTERS)
    if (
      !/_(from|to)$/.test(key) &&
      typeof values[key] === "string" &&
      values[key]
    )
      query[key] = values[key] as string;
  for (const name of ["created", "updated"] as const) {
    const range = values[`${name}_range`];
    if (Array.isArray(range) && range.length === 2) {
      if (range[0]) query[`${name}_from`] = String(range[0]);
      if (range[1]) query[`${name}_to`] = String(range[1]);
    }
  }
  return query;
}
function ItemListPage({ onSessionExpired }: { onSessionExpired: () => void }) {
  const location = useLocation(),
    navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const recordOpen = location.pathname !== "/items";
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
    items: ItemSummary[];
    total: number;
    page: number;
  }>({ items: [], total: 0, page: 1 });
  const [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const initialValues = useMemo(() => {
    const initial: Record<string, unknown> = {
      ...Object.fromEntries(ITEM_FILTERS.map((key) => [key, undefined])),
      ...query,
    };
    for (const name of ["created", "updated", "provisioned"])
      initial[`${name}_range`] =
        query[`${name}_from` as keyof ItemQuery] ||
        query[`${name}_to` as keyof ItemQuery]
          ? [
              query[`${name}_from` as keyof ItemQuery]
                ? dayjs(String(query[`${name}_from` as keyof ItemQuery]))
                : null,
              query[`${name}_to` as keyof ItemQuery]
                ? dayjs(String(query[`${name}_to` as keyof ItemQuery]))
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
    listItems(query)
      .then((result) => {
        if (
          !Array.isArray(result.items) ||
          !Number.isSafeInteger(result.total) ||
          result.total < 0
        )
          throw new Error("列表返回异常");
        result.items.forEach((row) => validateItem(row, row.id));
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
  const columns: ColumnsType<ItemSummary> = [
    {
      title: "物品编号",
      dataIndex: "item_uid",
      width: 210,
      fixed: "left",
      render: (_, row) => (
        <div>
          <Typography.Text className="make-id" copyable>
            {row.item_uid}
          </Typography.Text>
          {!!row.keyword_matches?.length && (
            <div className="make-secondary">
              命中：
              {row.keyword_matches.map((key) => MATCHES[key] || key).join("、")}
            </div>
          )}
        </div>
      ),
    },
    {
      title: "项目",
      dataIndex: "project",
      width: 90,
      render: (v) => (
        <Tag color={v === "fashion" ? "blue" : "gold"}>
          {ITEM_PROJECTS[v as keyof typeof ITEM_PROJECTS]}
        </Tag>
      ),
    },
    {
      title: "名称／资料摘要",
      key: "summary",
      width: 240,
      render: (_, row) => (
        <div>
          <div className="make-summary">
            {String(row.profile?.name || "未填写名称")}
          </div>
          <div className="make-secondary make-summary">
            {String(row.profile?.material || "未填写材质")} · 图片{" "}
            {Array.isArray(row.profile?.image_urls)
              ? row.profile.image_urls.length
              : 0}{" "}
            张
          </div>
        </div>
      ),
    },
    {
      title: "款式编号",
      dataIndex: "sku_code",
      width: 180,
      render: (v) =>
        v ? <Typography.Text code>{v}</Typography.Text> : "未填写",
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (v) => (
        <Badge
          color={
            v === "active" ? "green" : v === "disabled" ? "orange" : "#cbd5e1"
          }
          text={ITEM_STATUSES[v as keyof typeof ITEM_STATUSES]}
        />
      ),
    },
    {
      title: "关联芯片／配置",
      key: "chip",
      width: 230,
      render: (_, row) =>
        row.linked_chip ? (
          <div>
            <Link
              to={`/chips/${row.linked_chip.id}`}
              state={{ returnTo: sourcePoint(location) }}
            >
              {row.linked_chip.chip_uid}
            </Link>
            <div className="make-secondary">
              <Tag>
                {
                  {
                    pending: "待绑定",
                    bound: "已绑定",
                    disabled: "停用",
                    lost: "丢失",
                  }[row.linked_chip.chip_status]
                }
              </Tag>
              {row.linked_chip.provisioned_at
                ? "实卡配置已核验"
                : row.linked_chip.keys_generated
                  ? "已生密钥 · 待核验"
                  : "未生密钥"}
            </div>
          </div>
        ) : (
          "未关联"
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
            navigate(`/items/${row.id}`, {
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
        title="物品管理"
        subtitle="查询身份、关联与配置，维护日常资料。"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => setCreateOpen(true)}
          >
            创建物品
          </Button>
        }
      />
      {!recordOpen ? (
        <InventorySearch
          key={queryString(query).toString()}
          kind="items"
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
            <span>物品列表</span>
            <Tag color="blue">共 {data.total} 条</Tag>
          </Space>
        }
        extra={
          <Button onClick={() => setRevision((v) => v + 1)} loading={loading}>
            刷新列表
          </Button>
        }
      >
        <Table<ItemSummary>
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
        <CreateItem
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

export function ItemPanel({
  onSessionExpired,
}: {
  onSessionExpired: () => void;
}) {
  return (
    <>
      <ItemListPage onSessionExpired={onSessionExpired} />
      <Routes>
        <Route index element={null} />
        <Route
          path=":id"
          element={<ItemDetailPage onSessionExpired={onSessionExpired} />}
        />
        <Route
          path=":id/edit"
          element={<ItemDetailPage edit onSessionExpired={onSessionExpired} />}
        />
        <Route
          path="*"
          element={
            <Result
              status="404"
              title="物品页面不存在"
              extra={<Link to="/items">返回物品列表</Link>}
            />
          }
        />
      </Routes>
    </>
  );
}
