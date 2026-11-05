import React from "react";
import { Result, Button } from "antd";
import { history } from "@umijs/max";
export default function NotFound() {
  return (
    <Result
      status="404"
      title="页面不存在"
      extra={
        <Button onClick={() => history.push("/overview")}>返回工作台</Button>
      }
    />
  );
}
