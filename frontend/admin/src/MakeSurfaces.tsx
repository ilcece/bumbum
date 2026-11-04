import type { ReactNode } from "react";
import { Card, Drawer, Modal, Space, Typography } from "antd";
// 页面骨架和尺寸取自上传的 Make；不承载请求、权限或模拟业务逻辑。
export function PageHeading({
  title,
  subtitle,
  extra,
}: {
  title: string;
  subtitle?: string;
  extra?: ReactNode;
}) {
  return (
    <Card size="small" styles={{ body: { padding: "18px 24px" } }}>
      <div className="make-page-heading">
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {title}
          </Typography.Title>
          {subtitle && (
            <Typography.Text type="secondary">{subtitle}</Typography.Text>
          )}
        </div>
        {extra}
      </div>
    </Card>
  );
}
export function RecordSurface({
  edit,
  title,
  subtitle,
  onClose,
  extra,
  footer,
  children,
}: {
  edit?: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  extra?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const heading = (
    <Space wrap>
      <Typography.Title level={4} style={{ margin: 0 }}>
        {title}
      </Typography.Title>
      {subtitle && <Typography.Text code>{subtitle}</Typography.Text>}
    </Space>
  );
  return edit ? (
    <Modal
      open
      className="make-record"
      title={heading}
      width={960}
      style={{ top: 24 }}
      mask={{ closable: false }}
      onCancel={onClose}
      footer={footer}
    >
      {extra && <div style={{ marginBottom: 16 }}>{extra}</div>}
      {children}
    </Modal>
  ) : (
    <Drawer
      open
      className="make-record"
      title={heading}
      size={680}
      mask={{ closable: false }}
      onClose={onClose}
      extra={extra}
    >
      {children}
    </Drawer>
  );
}
