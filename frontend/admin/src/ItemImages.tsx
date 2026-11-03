import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Image, Space, Typography, Upload } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import type { RcFile } from "antd/es/upload/interface";
import { ApiError, readImageStatus, readSession, uploadItemImage } from "./api";
import type { ImageFile } from "./itemFields";

type Props = { id?: string; itemId: number; value?: ImageFile[]; onChange?: (files: ImageFile[]) => void; disabled?: boolean; onSessionExpired: () => void };
export function ItemImages({ id, itemId, value = [], onChange, disabled, onSessionExpired }: Props) {
  const { message } = App.useApp();
  const files = useRef(value); files.current = value;
  const emit = useRef(onChange); emit.current = onChange;
  const alive = useRef(true), occupied = useRef(false);
  const requests = useRef(new Map<string, AbortController>());
  const [preview, setPreview] = useState<number | null>(null), [checking, setChecking] = useState<string | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; requests.current.forEach(request => request.abort()); requests.current.clear(); }; }, []);
  function write(next: ImageFile[]) { if (alive.current) { files.current = next; emit.current?.(next); } }
  function patch(uid: string, change: Partial<ImageFile>) { write(files.current.map(file => file.uid === uid ? { ...file, ...change } : file)); }
  async function perform(file: RcFile) {
    if (requests.current.size) return;
    const controller = new AbortController(), uploadId = crypto.randomUUID().replace(/-/g, "");
    requests.current.set(file.uid, controller); occupied.current = true;
    patch(file.uid, { status: "uploading", uploadId, uncertain: false, error: undefined });
    try {
      const result = await uploadItemImage(itemId, uploadId, file, controller.signal);
      if (!alive.current || controller.signal.aborted) return;
      if (!result.preview_url || result.expired || !["pending", "attached"].includes(result.state)) throw new Error("上传尚未完成");
      patch(file.uid, { status: "done", response: result, reference: result.url, url: result.preview_url, uncertain: false });
    } catch (failure) {
      if (!alive.current || controller.signal.aborted) return;
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return; }
      let error = failure instanceof ApiError ? failure.message : "上传请求未完成。";
      const uncertain = !(failure instanceof ApiError && failure.status >= 400 && failure.status < 500 && failure.code !== "unexpected_response");
      if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try { await readSession(); error = "登录状态已更新，请明确重试本张上传；未自动重发。"; }
        catch (refreshFailure) { if (alive.current && refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired(); else error = "登录状态更新失败，请稍后重试；未自动上传。"; }
      }
      if (!controller.signal.aborted) patch(file.uid, { status: "error", uncertain, error });
    } finally { requests.current.delete(file.uid); occupied.current = requests.current.size > 0; }
  }
  async function verify(file: ImageFile) {
    if (!file.uploadId || checking || requests.current.size) return;
    setChecking(file.uid);
    try {
      const result = await readImageStatus(itemId, file.uploadId);
      if (!alive.current || !files.current.some(current => current.uid === file.uid)) return;
      if (!result.expired && ["pending", "attached"].includes(result.state) && result.preview_url) {
        patch(file.uid, { status: "done", response: result, reference: result.url, url: result.preview_url, uncertain: false, error: undefined });
      } else if (result.state === "uploading" && !result.expired) {
        patch(file.uid, { error: "服务器仍在处理，请稍后再核对；未重新上传。", uncertain: true });
      } else patch(file.uid, { error: "本次暂存已失效，可移除或明确重新上传。", uncertain: false, status: "error" });
    } catch (failure) {
      if (!alive.current) return;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else if (failure instanceof ApiError && failure.status === 404) patch(file.uid, { uncertain: false, status: "error", error: "尚未找到本次上传，原请求仍可能处理中。可移除此项或明确重新上传；不会自动关联。" });
      else patch(file.uid, { uncertain: true, error: failure instanceof ApiError ? failure.message : "核对失败，上传结果仍未确认。" });
    } finally { if (alive.current) setChecking(null); }
  }
  const previews = value.filter(file => file.status === "done" && file.url);
  const blocked = value.some(file => file.status === "uploading" || file.uncertain);
  const props: UploadProps = {
    id, accept: "image/jpeg,image/png,image/webp", listType: "picture", maxCount: 20, multiple: false,
    disabled, fileList: value, openFileDialogOnClick: !blocked,
    beforeUpload: file => {
      if (disabled || occupied.current || files.current.some(current => current.uncertain) || files.current.length >= 20) { void message.warning("请先处理当前上传；最多20张图片。"); return Upload.LIST_IGNORE; }
      if (!file.size || file.size > 8 * 1024**2 || !(file.type ? ["image/jpeg", "image/png", "image/webp"].includes(file.type) : /\.(?:jpe?g|png|webp)$/i.test(file.name))) {
        void message.error("请选择不超过8MiB的静态JPEG、PNG或WebP；实际格式由服务端校验。"); return Upload.LIST_IGNORE;
      }
      occupied.current = true;
      return true;
    },
    customRequest: options => { void perform(options.file as RcFile); },
    onChange: info => {
      // 官方组件负责列表交互；业务回执与未知状态不被迟到的组件事件抹掉。
      const next = info.fileList.map(file => ({ ...file, ...files.current.find(current => current.uid === file.uid), ...(file.status === "removed" ? { status: "removed" as const } : {}) }));
      write(next);
    },
    onRemove: file => {
      requests.current.get(file.uid)?.abort(); requests.current.delete(file.uid); occupied.current = requests.current.size > 0;
      write(files.current.filter(current => current.uid !== file.uid));
      return true;
    },
    onPreview: file => { const index = previews.findIndex(current => current.uid === file.uid); if (index >= 0) setPreview(index); },
    showUploadList: { showDownloadIcon: false },
  };
  return <Space direction="vertical" style={{ width: "100%" }}>
    <Image.PreviewGroup items={previews.map(file => ({ src: file.url!, crossOrigin: undefined }))} preview={{ visible: preview !== null, current: preview || 0, onVisibleChange: visible => { if (!visible) setPreview(null); } }}>
      <Upload {...props}>{value.length < 20 && <Button type="text" aria-label="选择图片上传" disabled={disabled || blocked} icon={<PlusOutlined aria-hidden />}>上传图片</Button>}</Upload>
    </Image.PreviewGroup>
    <Typography.Text type="secondary">最多20张、单张8MiB；JPEG/PNG最多1600万像素，WebP最多800万像素。上传成功仅暂存，保存资料后才关联；取消编辑不改变已保存图片。</Typography.Text>
    {value.filter(file => file.status === "error").map(file => <Alert key={file.uid} showIcon type="warning" message={file.uncertain ? "上传结果尚未确认" : "图片尚未上传成功"}
      description={typeof file.error === "string" ? file.error : "请处理失败项或移除后再保存。"} action={<Space>
        {file.uncertain ? <Button disabled={disabled} loading={checking === file.uid} onClick={() => void verify(file)}>核对上传结果</Button>
          : file.originFileObj && <Button disabled={disabled || blocked || !!checking} onClick={() => void perform(file.originFileObj!)}>重试上传</Button>}
      </Space>} />)}
  </Space>;
}
