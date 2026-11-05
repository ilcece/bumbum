import React, { useState } from "react";
import { Button, Empty, Image, Space, Tag, Typography } from "antd";
import { PageContainer } from "@ant-design/pro-components";
import type { Style } from "../data/domain";

// 编号的链接与复制各自独立，复制时不触发导航。
export function CopyValue({ value, onClick }: { value?: string | null; onClick?: () => void }) {
  if (!value) return <Typography.Text type="secondary">未记录</Typography.Text>;
  return <span className="copy-value">
    {onClick ? <Button type="link" onClick={onClick}>{value}</Button> : <span>{value}</span>}
    <Typography.Text copyable={{ text: value, tooltips: ["复制 " + value, "已复制"] }} />
  </span>;
}

const colors: Record<string, string> = {
  草稿: "default", 草案: "default", 启用: "green", 停用: "orange", 归档: "default",
  待绑定: "blue", 已绑定: "green", 临时停用: "orange", 已挂失: "red", 已退役: "default",
  待配置: "gold", "待准备/核验": "gold", 演示核验就绪: "cyan", 已确认: "green",
  已确认售出: "blue", 未确认售出: "default", 已认领: "green", 未认领: "default",
  已完成: "green", 待确认接续: "gold", 候选准备: "purple", 候选未生效: "purple",
  未关联: "default", 待封版: "gold", 待核对计次: "gold", 暂无待核对: "default",
  旧版记录待核对: "orange", 当前关联: "green", 当前持有人: "green",
  未准备: "gold", 已准备演示标记: "blue", 未连接: "default", 未执行: "default",
  待核对: "gold", 未分配: "default", 已保存内容: "green", 未保存预览: "gold",
  全局共享: "red", 单卡独立: "cyan",
  正式编号待封版: "gold", 未关联发行: "gold",
};
export function StatusTag({ value }: { value: string }) {
  return <Tag color={colors[value] || "default"} className="status-tag">{value}</Tag>;
}
export function EditionValue({ value }: { value: string }) {
  return value.startsWith("#") ? <CopyValue value={value} /> : <StatusTag value={value} />;
}
export function HolderValue({ id, name }: { id: string | null; name: string }) {
  return id ? <Space direction="vertical" size={0}><span>{name}</span><CopyValue value={id} /></Space> : <StatusTag value="未认领" />;
}

export function ProductGallery({ pictures = [], compact = false }: { pictures?: string[]; compact?: boolean }) {
  const [active, setActive] = useState(0);
  if (!pictures.length) return <div className={compact ? "product-thumb placeholder-thumb" : "gallery-empty"}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={compact ? "暂无款图" : "暂无商品图片"} /></div>;
  if (compact) return <Image className="product-thumb" src={pictures[0]} alt="商品款图" width={56} height={56} />;
  const current = Math.min(active, pictures.length - 1);
  return <div className="product-gallery">
    <Image.PreviewGroup items={pictures}>
      <Image src={pictures[current]} alt={`商品图片 ${current + 1}`} className="gallery-main" />
    </Image.PreviewGroup>
    <div className="gallery-thumbnails" aria-label="商品图片切换">
      {pictures.map((url, n) => <button key={n} type="button" className={current === n ? "selected" : ""} aria-label={`查看商品图片 ${n + 1}`} aria-pressed={current === n} onClick={() => setActive(n)}><img src={url} alt={`缩略图 ${n + 1}`} /></button>)}
      <Typography.Text type="secondary">共 {pictures.length} 张</Typography.Text>
    </div>
  </div>;
}

export function StyleCell({ style, onClick }: { style?: Style; onClick?: () => void }) {
  return <div className="style-cell"><ProductGallery compact pictures={style?.pictures} /><div>
    {onClick ? <Button type="link" onClick={onClick}>{style?.name || "款式待核对"}</Button> : <Typography.Text strong>{style?.name || "款式待核对"}</Typography.Text>}
    <div className="cell-secondary">{style?.material || "材质未填写"} · 图片 {style?.pictures.length || 0} 张</div>
  </div></div>;
}

export function ProductPreview({ style, pictures, dirty }: { style: Partial<Style>; pictures: string[]; dirty: boolean }) {
  return <div className="mobile-preview"><div className="mobile-preview-header"><span>手机展示预览</span><StatusTag value={dirty ? "未保存预览" : "已保存内容"} /></div>
    <ProductGallery pictures={pictures} />
    <div className="mobile-preview-content"><Typography.Text type="secondary">{style.code || "款式编号"}</Typography.Text><Typography.Title level={4}>{style.name || "商品名称"}</Typography.Title>
      {[["商品介绍", style.description], ["材质说明", style.material], ["养护或寓意", style.care], ["适用规格", style.specs?.join("、")]].map(([label, value]) => <div className="preview-section" key={label}><div className="cell-secondary">{label}</div><div>{value || "暂未填写"}</div></div>)}
      <p className="cell-secondary">仅为内容展示示意，不代表真实核验结果。</p>
    </div>
  </div>;
}

export function DetailContainer({ embedded, children, ...props }: React.ComponentProps<typeof PageContainer> & { embedded?: boolean }) {
  return embedded ? <div className="embedded-detail"><div className="detail-heading"><Typography.Title level={4}>{props.title}</Typography.Title>{props.subTitle}</div><Space wrap className="detail-actions">{props.extra}</Space>{children}</div> : <PageContainer {...props}>{children}</PageContainer>;
}
