import type { ReactNode } from "react";
import { Alert } from "antd";

export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <Alert
      role={error ? "alert" : "status"}
      type={error ? "error" : "success"}
      showIcon
      title={children}
    />
  );
}
