import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Tag } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { ApiError, checkBackend, checkDatabase } from "./api";

type State = "checking" | "ok" | "failed";
export function RuntimeChecks() {
  const [states, setStates] = useState<State[]>(["checking", "checking"]);
  const [messages, setMessages] = useState(["", ""]);
  const revision = useRef(0);
  async function refresh() {
    const current = ++revision.current;
    setStates(["checking", "checking"]);
    setMessages(["", ""]);
    await Promise.allSettled(
      [checkBackend, checkDatabase].map((check, index) =>
        check().then(
          () => {
            if (current === revision.current)
              setStates((values) =>
                values.map((value, i) => (i === index ? "ok" : value)),
              );
          },
          (error: unknown) => {
            if (current !== revision.current) return;
            setStates((values) =>
              values.map((value, i) => (i === index ? "failed" : value)),
            );
            setMessages((values) =>
              values.map((value, i) =>
                i === index
                  ? error instanceof ApiError
                    ? error.message
                    : "暂时无法连接服务。"
                  : value,
              ),
            );
          },
        ),
      ),
    );
  }
  useEffect(() => {
    void refresh();
    return () => {
      revision.current++;
    };
  }, []);
  return (
    <Space
      orientation="vertical"
      size="middle"
      style={{ width: "100%" }}
      aria-label="运行检查结果"
    >
      <Row gutter={16}>
        {["后端程序", "数据库"].map((title, index) => (
          <Col span={12} key={title}>
            <Card title={title}>
              <Tag
                color={
                  states[index] === "ok"
                    ? "success"
                    : states[index] === "failed"
                      ? "error"
                      : "processing"
                }
              >
                {states[index] === "ok"
                  ? "检查通过"
                  : states[index] === "failed"
                    ? "检查失败"
                    : "检查中…"}
              </Tag>
              {messages[index] && (
                <Alert type="error" title={messages[index]} />
              )}
              <p>本项只代表当前运行检查结果。</p>
            </Card>
          </Col>
        ))}
      </Row>
      <Button
        icon={<ReloadOutlined />}
        loading={states.includes("checking")}
        onClick={() => void refresh()}
      >
        重新检查
      </Button>
    </Space>
  );
}
