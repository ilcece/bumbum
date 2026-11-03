import { useEffect, useState } from "react";
import { Alert, Button, Card, Image, Result, Space, Spin, Typography } from "antd";
import { PageContainer, ProDescriptions } from "@ant-design/pro-components";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError, readItem, safeRecordId } from "./api";
import type { ItemView } from "./api";
import { safeReturn } from "./adminNavigation";

const PROFILE_LABELS: Record<string, string> = {
  name: "名称", description: "介绍", material: "材质", care_instructions: "养护说明",
  image_urls: "图片", size_chart: "尺码表", type: "类型", origin: "产地", meaning: "寓意",
};
export const beijingTime = (value: string | null) => value ? new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }) : "未记录";
export function ItemDetailPage({ onSessionExpired }: { onSessionExpired: () => void }) {
  const { id } = useParams();
  const location = useLocation(), navigate = useNavigate();
  const [item, setItem] = useState<ItemView | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setItem(null); setError("");
    if (!id || !/^[1-9][0-9]*$/.test(id) || !safeRecordId(Number(id))) { setError("物品记录编号无效。"); return; }
    readItem(Number(id)).then(value => {
      if (value.id !== Number(id)) throw new Error("返回的物品与目标不符。");
      if (!cancelled) setItem(value);
    }).catch(failure => {
      if (cancelled) return;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else setError(failure instanceof ApiError ? failure.message : "物品读取失败，请重试或返回。");
    });
    return () => { cancelled = true; };
  }, [id, revision, onSessionExpired]);
  function back() {
    const point = safeReturn(location.state?.returnTo);
    navigate(point?.path || "/items", { state: { returnTo: point?.parent, restoreScroll: point?.scroll } });
  }
  const fields = item ? [
    { key: "item_uid", label: "物品编号", value: item.item_uid },
    { key: "project", label: "项目", value: item.project === "fashion" ? "服装" : "饰品" },
    { key: "sku_code", label: "款式编号", value: item.sku_code || "未填写" },
    { key: "status", label: "状态", value: { draft: "草稿", active: "启用", disabled: "停用", archived: "归档" }[item.status] },
    { key: "created_at", label: "创建时间（北京时间）", value: beijingTime(item.created_at) },
    { key: "updated_at", label: "更新时间（北京时间）", value: beijingTime(item.updated_at) },
    ...Object.entries(item.profile || {}).map(([key, value]) => ({ key, label: PROFILE_LABELS[key] || key, value:
      key === "image_urls" && Array.isArray(value) ? <Image.PreviewGroup>{value.filter((url): url is string => typeof url === "string").map((url, index) => <Image key={index} width={120} src={url} alt={`物品图片${index + 1}`} />)}</Image.PreviewGroup>
        : value === null || value === "" ? "未填写" : typeof value === "object" ? <Typography.Paragraph><pre>{JSON.stringify(value, null, 2)}</pre></Typography.Paragraph> : String(value) })),
  ] : [];
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>物品详情</Typography.Title>} onBack={back} extra={<Button onClick={back}>返回来源</Button>}>
    {error ? <Result status="warning" title="无法读取物品" subTitle={error} extra={<Space><Button onClick={() => setRevision(value => value + 1)}>重试读取</Button><Button onClick={back}>返回</Button></Space>} />
      : !item ? <Spin tip="正在读取物品"><div style={{ height: 160 }} /></Spin>
      : <Space direction="vertical" size="large" style={{ width: "100%" }}><Card>
        <ProDescriptions title={item.item_uid} column={2} dataSource={item}
          columns={fields.map(field => ({ title: field.label, key: field.key, render: () => field.value }))} />
      </Card>{!item.profile && <Alert type="info" message="此物品尚未填写资料。" />}</Space>}
  </PageContainer>;
}
