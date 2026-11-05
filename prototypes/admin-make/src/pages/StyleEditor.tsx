import React, { useEffect, useRef, useState } from "react";
import {
  PageContainer,
  ProCard,
  ProForm,
  ProFormText,
  ProFormTextArea,
  ProFormSelect,
  ProFormInstance,
  FooterToolbar,
} from "@ant-design/pro-components";
import {
  App,
  Alert,
  Button,
  Image,
  Space,
  Upload,
  Typography,
  Col,
  Modal,
  Tag,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { history, useParams } from "@umijs/max";
import { useStore } from "../data/store";
import { Style, categoryNames } from "../data/domain";
import { go, required, useAction, useUnsaved, useReturnPath } from "../ui";
import { CopyValue, ProductPreview } from "../components/RecordPresentation";
export default function StyleEditor({ styleId, modalMode = false, onClose }: { styleId?: string; modalMode?: boolean; onClose?: () => void }) {
  const params = useParams();
  const p = useStore(),
    id = styleId || params.id,
    record = p.data.styles.find((s) => s.id === id),
    form = useRef<ProFormInstance | undefined>(undefined),
    action = useAction(),
    { modal, message } = App.useApp(),
    [savedId, setSavedId] = useState(record?.id),
    [pictures, setPictures] = useState(record?.pictures || []),
    [uploading, setUploading] = useState(0),
    [saving, setSaving] = useState(false),
    [preview, setPreview] = useState(
      record || { name: "商品名称", description: "", material: "", care: "" },
    ),
    back = useReturnPath("/catalog");
  const save = async (confirm = true) => {
    let values: any;
    try {
      values = await form.current?.validateFields();
    } catch {
      return false;
    }
    if (uploading) return false;
    const value: Style = {
      ...values,
      id: savedId || crypto.randomUUID(),
      specs: String(values.specsText || "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      pictures,
    };
    const used = p.data.items.filter((i) => i.styleId === value.id);
    if (confirm && used.length) {
      return new Promise<boolean>((resolve) =>
        modal.confirm({
          title: "确认同步共用商品资料？",
          content: `影响${used.length}件引用物品，其中${used.filter((i) => i.status === "active").length}件已启用。只改共用内容，不改变发行承诺、身份、实体或持有人。`,
          okText: "确认同步保存",
          onOk: () => {
            const ok = action.run("style", value);
            if (ok) {
              unsaved.setDirty(false);
              setSavedId(value.id);
              if (id === "new")
                history.replace(
                  "/catalog/style/" + value.id,
                  history.location.state,
                );
            }
            resolve(ok);
          },
          onCancel: () => resolve(false),
        }),
      );
    }
    const ok = action.run("style", value);
    if (ok) {
      unsaved.setDirty(false);
      setSavedId(value.id);
      if (id === "new")
        history.replace("/catalog/style/" + value.id, history.location.state);
    }
    return ok;
  };
  const unsaved = useUnsaved(() => save());
  const close = () => {
    if (uploading || saving) return;
    const leave = () => { unsaved.setDirty(false); if (modalMode) onClose?.(); else history.push(back); };
    if (!modalMode || !unsaved.isDirty) { if (modalMode) leave(); else history.push(back); return; }
    const popup = modal.confirm({
      title: "尚有未保存的修改", content: "已保存资料会保留，选择如何离开。",
      footer: () => <Space><Button onClick={() => popup.destroy()}>继续编辑</Button><Button onClick={() => { popup.destroy(); leave(); }}>放弃并继续</Button><Button type="primary" onClick={async () => { if (await save()) { popup.destroy(); leave(); } }}>保存后继续</Button></Space>,
    });
  };
  const footer = <div className="editor-footer"><Typography.Text type="secondary">{savedId ? `共用资料 · 引用 ${p.data.items.filter(i => i.styleId === savedId).length} 件物品` : "先建立款式资料，再维护发行约定"}</Typography.Text><Space><Button disabled={!!uploading || saving} onClick={close}>取消</Button><Button type="primary" loading={saving} disabled={action.unknown || !!uploading} onClick={async () => { setSaving(true); try { if (await save()) { if (modalMode) onClose?.(); } } finally { setSaving(false); } }}>保存共用资料</Button></Space></div>;
  useEffect(() => {
    const next = p.getData().styles.find((x) => x.id === id);
    setSavedId(next?.id);
    form.current?.resetFields();
    setPictures(next?.pictures || []);
    setPreview(
      next || { name: "商品名称", description: "", material: "", care: "" },
    );
    form.current?.setFieldsValue(
      next
        ? { ...next, specsText: next.specs.join("\n") }
        : { category: "fashion" },
    );
    unsaved.setDirty(false);
  }, [id]);
  const content = (
      <div className="page-stack form-page">
        {action.feedback}
        <div className="style-editor-grid">
          <ProCard
            size="small"
            headerBordered
            variant="outlined"
            title="共用商品资料"
          >
            <ProForm
              grid
              colProps={{ span: 24 }}
              rowProps={{ gutter: 16 }}
              formRef={form}
              initialValues={
                record
                  ? { ...record, specsText: record.specs.join("\n") }
                  : { category: "fashion" }
              }
              onValuesChange={(_, all) => {
                unsaved.setDirty(true);
                setPreview({...all, specs: String(all.specsText || "").split("\n").map(s => s.trim()).filter(Boolean)});
              }}
              onFinish={() => save()}
              submitter={false}
            >
              <ProFormText
                name="code"
                label="款式编号"
                colProps={{ xs: 24, md: 12 }}
                rules={required}
              />
              <ProFormSelect
                name="category"
                label="物品类别"
                colProps={{ xs: 24, md: 12 }}
                disabled={
                  !!savedId &&
                  (p.data.items.some((i) => i.styleId === savedId) ||
                    p.data.issues.some((i) => i.styleId === savedId))
                }
                options={Object.entries(categoryNames).map(
                  ([value, label]) => ({ value, label }),
                )}
                rules={[{ required: true }]}
              />

              <ProFormText name="name" label="款式名称" rules={required} />
              <ProFormTextArea name="description" label="商品介绍" />

              <ProFormText
                name="material"
                label="材质"
                colProps={{ xs: 24, md: 12 }}
              />
              <ProFormText
                name="care"
                label="养护或寓意"
                colProps={{ xs: 24, md: 12 }}
              />

              <ProFormTextArea
                name="specsText"
                label="适用规格（每行一项）"
                fieldProps={{ rows: 3 }}
                extra="按实际商品填写尺寸/颜色等。共用规格调整不改变历史实体实际规格。"
              />
              <Col span={24}>
                <Typography.Paragraph>参考图片</Typography.Paragraph>
                <Upload
                  accept="image/png,image/jpeg,image/webp"
                  listType="picture"
                  multiple
                  maxCount={20}
                  fileList={pictures.map((url, n) => ({
                    uid: String(n),
                    name: `第 ${n + 1} 张 · 商品图片${n + 1}${n === 0 ? " · 列表首图" : ""}`,
                    status: "done",
                    url,
                  }))}
                  beforeUpload={(file) => {
                    if (
                      !["image/png", "image/jpeg", "image/webp"].includes(
                        file.type,
                      ) ||
                      file.size > 8 * 1024 * 1024
                    ) {
                      message.warning("请选择8MiB以内的JPEG/PNG/WebP图片");
                      return Upload.LIST_IGNORE;
                    }
                    return true;
                  }}
                  customRequest={(options) => {
                    setUploading(n => n + 1);
                    const reader = new FileReader();
                    reader.onload = () => {
                      setPictures((prev) =>
                        [...prev, String(reader.result)].slice(0, 20),
                      );
                      unsaved.setDirty(true);
                      setUploading(n => n - 1);
                      options.onSuccess?.({});
                    };
                    reader.onerror = () => {
                      setUploading(n => n - 1);
                      message.error("图片读取失败，请重新选择；原有图片保留");
                      options.onError?.(new Error("读取失败"));
                    };
                    reader.readAsDataURL(options.file as File);
                  }}
                  onRemove={(file) => {
                    setPictures((prev) =>
                      prev.filter((_, n) => String(n) !== file.uid),
                    );
                    unsaved.setDirty(true);
                  }}
                  onPreview={(file) =>
                    modal.info({
                      title: "图片预览",
                      content: <Image src={file.url} />,
                    })
                  }
                >
                  {pictures.length < 20 && <Button icon={<PlusOutlined />}>上传商品图片</Button>}
                </Upload>
                <Typography.Paragraph type="secondary">
                  <Tag color={unsaved.isDirty ? "gold" : "green"}>{unsaved.isDirty ? "有未保存修改" : "已保存内容"}</Tag>最多20张，单张不超过8MiB。图片仅在本原型浏览器暂存。
                </Typography.Paragraph>
              </Col>
            </ProForm>
          </ProCard>
          <div className="style-editor-preview">
            <ProductPreview style={preview} pictures={pictures} dirty={!savedId || unsaved.isDirty} />
            <Typography.Text type="secondary">
              不公开内部持有人、核对依据或操作历史。
            </Typography.Text>
          </div>
        </div>
        {savedId && !modalMode && (
          <Alert
            type="success"
            title="款式已保存，可建立发行约定"
            action={
              <Button
                onClick={() => go("/catalog/issue/new?styleId=" + savedId)}
              >
                继续建立发行约定
              </Button>
            }
          />
        )}
      </div>
  );
  return modalMode ? <Modal title={<Space>编辑共用款式 <CopyValue value={record?.code} /></Space>} open width={1120} className="editor-modal" onCancel={close} maskClosable={false} footer={footer} destroyOnHidden>{content}</Modal> : <PageContainer title={savedId ? "维护共用款式" : "新建款式"} onBack={() => history.push(back)}>{content}<FooterToolbar>{footer}</FooterToolbar></PageContainer>;
}
