import { Alert, Button, Modal, Spin, Typography } from "antd";
import { time } from "../catalog";

export default function ClaimCodeDialog({ code, expiresAt, error, loading, receipt, onClose }: {
  code?: string;
  expiresAt?: string;
  error?: string;
  loading?: boolean;
  receipt?: string;
  onClose: () => void;
}) {
  return <Modal open title="交付认领码" onCancel={onClose}
    footer={<Button onClick={onClose}>关闭</Button>}>
    {loading ? <Spin description="正在读取认领码" /> : error ? (
      <Alert type="error" showIcon title="无法查看认领码" description={error} />
    ) : code ? (
      <>
        <div data-private="true"><Typography.Paragraph copyable>{code}</Typography.Paragraph></div>
        <Typography.Paragraph>有效期至 {time(expiresAt)}（北京时间）。请通过交付渠道交给接收人。</Typography.Paragraph>
      </>
    ) : <Alert type="info" showIcon title="已核对发放记录" description={receipt} />}
  </Modal>;
}
