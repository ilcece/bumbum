import { useState, useEffect } from "react";
import { Alert, Button, Space, Upload } from "antd";
import { ApiError, request, uploadStyleImage } from "../api";
export default function StyleImages({
  styleId,
  value = [],
  onChange,
  onStatusChange,
}: {
  styleId?: number;
  value?: string[];
  onChange?: (v: string[]) => void;
  onStatusChange?: (busy: boolean) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [pending, setPending] = useState<{ id: string; file: File }>(),
    [checked, setChecked] = useState(false);
  useEffect(() => {
    onStatusChange?.(busy || !!pending);
  }, [busy, pending]);
  const upload = async (
    file: File,
    id = crypto.randomUUID().replaceAll("-", ""),
  ) => {
    onChange?.([...value]);
    setBusy(true);
    setError("");
    setPending({ id, file });
    try {
      const r = await uploadStyleImage(styleId!, id, file);
      onChange?.([...value, r.url]);
      setPending(undefined);
      setChecked(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传结果未知");
      if (
        e instanceof ApiError &&
        ((e.status >= 400 && e.status < 500) ||
          (e.code === "service_unavailable" &&
            e.message.startsWith("图片上传未启用")))
      )
        setPending(undefined);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Upload
        listType="picture-card"
        accept="image/jpeg,image/png,image/webp"
        disabled={!styleId || busy || !!pending}
        fileList={value.map((url) => ({
          uid: url,
          name: "已上传款图",
          status: "done",
          url,
        }))}
        beforeUpload={(file) => {
          if (value.length >= 20 || file.size > 8 * 1024 ** 2) {
            setError("最多20张，单张8MiB。");
            return Upload.LIST_IGNORE;
          }
          void upload(file);
          return Upload.LIST_IGNORE;
        }}
        onRemove={(file) => {
          onChange?.(value.filter((url) => url !== file.uid));
          return true;
        }}
      >
        {value.length < 20 && (
          <Button disabled={!styleId || busy || !!pending}>
            {busy ? "上传中" : "上传图片"}
          </Button>
        )}
      </Upload>
      {!styleId && <Alert type="info" title="先保存款式，再维护参考图片。" />}
      {error && <Alert type="error" title={error} />}{" "}
      {pending && !busy && (
        <Space>
          <Button
            onClick={() => {
              setPending(undefined);
              setChecked(false);
              setError("");
            }}
          >
            放弃本次上传
          </Button>
          <Button
            onClick={async () => {
              try {
                const r = await request<{ url: string }>(
                  `/admin/catalog/styles/${styleId}/images/${pending.id}/status`,
                );
                onChange?.([...value, r.url]);
                setPending(undefined);
                setError("");
              } catch (e) {
                if (e instanceof ApiError && e.status === 404) {
                  setChecked(true);
                  setError("尚无已提交记录，可明确重试同一上传。");
                } else setError(e instanceof Error ? e.message : "核对失败");
              }
            }}
          >
            核对上传结果
          </Button>
          {checked && (
            <Button onClick={() => void upload(pending.file, pending.id)}>
              明确重试原上传
            </Button>
          )}
        </Space>
      )}
    </>
  );
}
