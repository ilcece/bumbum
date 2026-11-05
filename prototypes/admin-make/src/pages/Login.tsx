import React, { useEffect } from "react";
import { App, Alert, Button, Card, Space, Typography } from "antd";
import { history, useModel } from "@umijs/max";
export default function Login() {
  const { setInitialState } = useModel("@@initialState");
  useEffect(() => {
    sessionStorage.removeItem("bumbum-pro-demo-auth");
    setInitialState((s: any) => ({ ...s, currentUser: undefined }));
  }, []);
  return (
    <div className="login-frame">
      <Card className="login-card">
        <Space>
          <span className="brand-mark">BB</span>
          <Typography.Title level={2} style={{ margin: 0 }}>
            BUMBUM
          </Typography.Title>
        </Space>
        <Typography.Title level={4}>数字物品管理</Typography.Title>
        <Typography.Paragraph type="secondary">
          款式与发行、物品档案、芯片关联和核心数据。
        </Typography.Paragraph>
        <Alert
          type="info"
          showIcon
          title="交互原型 · 全部使用合成样例"
          description="不连接真实账号、短信、芯片或订单，请勿输入真实个人资料。"
        />
        <Button
          type="primary"
          block
          size="large"
          style={{ marginTop: 24 }}
          onClick={async () => {
            sessionStorage.setItem("bumbum-pro-demo-auth", "yes");
            await setInitialState((s: any) => ({
              ...s,
              currentUser: { name: "演示管理员" },
            }));
            history.push("/overview");
          }}
        >
          使用演示身份进入
        </Button>
      </Card>
    </div>
  );
}
