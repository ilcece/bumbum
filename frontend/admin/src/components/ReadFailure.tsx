import { Alert, Button } from "antd";

export default function ReadFailure({ title = "读取失败", error, retry }: {
  title?: string;
  error: string;
  retry: () => void;
}) {
  return <Alert type="error" showIcon title={title} description={error}
    action={<Button onClick={retry}>重试读取</Button>} />;
}
