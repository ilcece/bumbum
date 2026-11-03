import { Image, Space, Tag, Typography } from "antd";
import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import type { UploadFile } from "antd";
import type { FashionProfile, ItemSummary, MediaAsset } from "./api";
import { safeRecordId } from "./api";
import { sourcePoint } from "./adminNavigation";

export const ITEM_PROJECTS = { fashion: "服装", jewelry: "饰品" };
export const ITEM_STATUSES = { draft: "草稿", active: "启用", disabled: "停用", archived: "归档" };
export const beijingTime = (value: string | null) => value ? new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }) : "未记录";
export type ImageFile = UploadFile<MediaAsset> & { reference?: string; uncertain?: boolean; uploadId?: string };
export type ItemForm = { sku_code: string; name: string; description: string; material: string; care_instructions: string; image_files: ImageFile[] };
export type ItemField = { key: string; label: string; editable?: "sku_code" | "name" | "description" | "material" | "care_instructions" | "image_files"; render: (item: ItemSummary) => ReactNode };
export const profileKeys = ["name", "description", "material", "care_instructions"] as const;
export function formValues(item: ItemSummary): ItemForm {
  const profile = item.profile;
  return { sku_code: item.sku_code || "", ...Object.fromEntries(profileKeys.map(key => [key, String(profile?.[key] || "")])),
    image_files: ((profile?.image_urls || []) as string[]).map((url, index) => ({ uid: `saved-${index}`, name: `物品图片${index + 1}`, status: "done", url, reference: url })) } as ItemForm;
}
export function profileValue(values: ItemForm): FashionProfile {
  return { name: values.name?.trim() || "", description: values.description?.trim() || null, material: values.material?.trim() || null,
    care_instructions: values.care_instructions?.trim() || null, image_urls: (values.image_files || []).map(file => file.reference || file.url || "") };
}
function imageIdentity(url: string) {
  try {
    const match = new URL(url, window.location.origin).pathname.match(/^\/api\/(?:admin|tap|fashion)\/items\/([1-9][0-9]*)\/images\/([a-f0-9]{32})$/);
    return match ? `${match[1]}/${match[2]}` : url;
  } catch { return url; }
}
export function profileIdentity(profile: FashionProfile) {
  return JSON.stringify({ ...profile, image_urls: profile.image_urls.map(imageIdentity) });
}
export function changes(item: ItemSummary, values: ItemForm) {
  const base = formValues(item), profile = profileValue(values);
  const sku = values.sku_code?.trim() || null;
  const profileChanged = item.project === "fashion" && profileIdentity(profile) !== profileIdentity(profileValue(base));
  const filesChanged = (values.image_files || []).some(file => file.status !== "done" || file.uncertain);
  return { dirty: sku !== item.sku_code || profileChanged || filesChanged, profileChanged,
    body: { ...(sku !== item.sku_code ? { sku_code: sku } : {}), ...(profileChanged ? { profile } : {}) } };
}
export function validateItem(value: ItemSummary, id: number) {
  if (!value || value.id !== id || !["fashion", "jewelry"].includes(value.project) || !(value.status in ITEM_STATUSES)
    || typeof value.item_uid !== "string" || !(value.sku_code === null || typeof value.sku_code === "string")
    || !(value.profile === null || typeof value.profile === "object" && !Array.isArray(value.profile))
    || !Array.isArray(value.keyword_matches) || !value.keyword_matches.every(key => typeof key === "string")) throw new Error("物品返回资料不完整。");
  if (value.linked_chip !== null && (!value.linked_chip || typeof value.linked_chip.id !== "number" || !Number.isInteger(value.linked_chip.id) || value.linked_chip.id < 1
    || typeof value.linked_chip.chip_uid !== "string" || typeof value.linked_chip.keys_generated !== "boolean" || !["pending", "bound", "disabled", "lost"].includes(value.linked_chip.chip_status)
    || !(value.linked_chip.provisioned_at === null || typeof value.linked_chip.provisioned_at === "string" && Number.isFinite(Date.parse(value.linked_chip.provisioned_at))))) throw new Error("关联芯片返回资料不完整。");
  if (value.profile && (!Array.isArray(value.profile.image_urls) || !value.profile.image_urls.every(url => typeof url === "string")
    || typeof value.profile.name !== "string" || !["description", "material", ...(value.project === "fashion" ? ["care_instructions"] : ["meaning"])].every(key => value.profile![key] === null || typeof value.profile![key] === "string"))) throw new Error("物品资料格式异常。");
  return value;
}
export function ImagePreview({ urls }: { urls: string[] }) {
  return urls.length ? <Image.PreviewGroup><Space wrap>{urls.map((url, index) => <Image key={`${index}-${url}`} width={120} src={url} alt={`物品图片${index + 1}`} referrerPolicy="no-referrer" />)}</Space></Image.PreviewGroup> : "未填写";
}
export function useItemFields(): ItemField[] {
  const location = useLocation();
  const text = (key: string) => (item: ItemSummary) => <Typography.Text style={{ whiteSpace: "pre-wrap" }}>{String(item.profile?.[key] || "未填写")}</Typography.Text>;
  return [
    { key: "item_uid", label: "物品编号", render: item => <Typography.Text copyable>{item.item_uid}</Typography.Text> },
    { key: "project", label: "项目", render: item => ITEM_PROJECTS[item.project] },
    { key: "sku_code", label: "款式编号", editable: "sku_code", render: item => item.sku_code || "未填写" },
    { key: "status", label: "状态", render: item => <Tag>{ITEM_STATUSES[item.status]}</Tag> },
    { key: "linked_chip", label: "关联芯片", render: item => !item.linked_chip ? "未关联" : safeRecordId(item.linked_chip.id)
      ? <Link to={`/chips/${item.linked_chip.id}`} state={{ returnTo: sourcePoint(location) }}>{item.linked_chip.chip_uid}</Link> : "关联编号无法处理，请反馈" },
    { key: "chip_status", label: "关联芯片状态", render: item => item.linked_chip ? ({ pending: "待绑定", bound: "已绑定", disabled: "停用", lost: "丢失" }[item.linked_chip.chip_status] || "未知") : "未关联" },
    { key: "keys_generated", label: "密钥生成", render: item => item.linked_chip ? item.linked_chip.keys_generated ? "已生成" : "未生成" : "未关联" },
    { key: "provisioned_at", label: "配置核验时间（北京时间）", render: item => item.linked_chip ? item.linked_chip.provisioned_at ? beijingTime(item.linked_chip.provisioned_at) : "未核验" : "未关联" },
    { key: "created_at", label: "创建时间（北京时间）", render: item => beijingTime(item.created_at) },
    { key: "updated_at", label: "更新时间（北京时间）", render: item => beijingTime(item.updated_at) },
    { key: "name", label: "名称", editable: "name", render: text("name") },
    { key: "description", label: "介绍", editable: "description", render: text("description") },
    { key: "material", label: "材质", editable: "material", render: text("material") },
    { key: "care_instructions", label: "养护说明", editable: "care_instructions", render: text("care_instructions") },
    { key: "meaning", label: "寓意", render: text("meaning") },
    { key: "image_urls", label: "图片", editable: "image_files", render: item => <ImagePreview urls={(item.profile?.image_urls || []) as string[]} /> },
    { key: "size_chart", label: "尺码表", render: item => item.profile?.size_chart == null ? "未填写" : <Typography.Paragraph><pre>{JSON.stringify(item.profile.size_chart, null, 2)}</pre></Typography.Paragraph> },
  ];
}
export function applicableFields(fields: ItemField[], item: ItemSummary) {
  return fields.filter(field => item.project === "fashion" ? field.key !== "meaning" : !["care_instructions", "size_chart"].includes(field.key));
}
