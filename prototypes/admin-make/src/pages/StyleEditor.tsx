import React, { useEffect, useRef, useState } from "react";
import {
  PageContainer,
  ProCard,
  ProForm,
  ProFormText,
  ProFormTextArea,
  ProFormSelect,
  ProFormInstance,
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
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { history, useParams } from "@umijs/max";
import { useStore } from "../data/store";
import { Style, categoryNames } from "../data/domain";
import { go, required, useAction, useUnsaved, useReturnPath } from "../ui";
export default function StyleEditor() {
  const p = useStore(),
    { id } = useParams(),
    record = p.data.styles.find((s) => s.id === id),
    form = useRef<ProFormInstance | undefined>(undefined),
    action = useAction(),
    { modal, message } = App.useApp(),
    [savedId, setSavedId] = useState(record?.id),
    [pictures, setPictures] = useState(record?.pictures || []),
    [uploading, setUploading] = useState(false),
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
  return (
    <PageContainer
      title={savedId ? "维护共用款式" : "新建款式"}
      onBack={() => history.push(back)}
      extra={
        savedId ? (
          <Button onClick={() => go("/catalog/issue/new?styleId=" + savedId)}>
            建立该款发行约定
          </Button>
        ) : undefined
      }
    >
      <div className="page-stack form-page">
        {action.feedback}
        <div className="two-columns">
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
                setPreview(all);
              }}
              onFinish={() => save()}
              submitter={{
                searchConfig: { submitText: "保存共用资料" },
                resetButtonProps: false,
                submitButtonProps: { disabled: action.unknown || uploading },
              }}
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
                  listType="picture-card"
                  multiple
                  maxCount={20}
                  fileList={pictures.map((url, n) => ({
                    uid: String(n),
                    name: "商品图片" + (n + 1),
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
                    setUploading(true);
                    const reader = new FileReader();
                    reader.onload = () => {
                      setPictures((prev) =>
                        [...prev, String(reader.result)].slice(0, 20),
                      );
                      unsaved.setDirty(true);
                      setUploading(false);
                      options.onSuccess?.({});
                    };
                    reader.onerror = () => {
                      setUploading(false);
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
                  {pictures.length < 20 && <PlusOutlined />}
                </Upload>
                <Typography.Paragraph type="secondary">
                  图片仅在浏览器暂存，保存后关联本原型共用资料。
                </Typography.Paragraph>
              </Col>
            </ProForm>
          </ProCard>
          <ProCard
            size="small"
            headerBordered
            variant="outlined"
            title="商品资料预览"
            className="preview-box"
          >
            <Typography.Text type="secondary">
              商品资料预览 ·{" "}
              {!savedId || unsaved.isDirty ? "未保存" : "已保存内容"}
            </Typography.Text>
            {pictures[0] && (
              <Image
                src={pictures[0]}
                style={{ marginTop: 16, width: "100%" }}
              />
            )}
            <Typography.Title level={3}>
              {preview.name || "商品名称"}
            </Typography.Title>
            <p>{preview.description}</p>
            <p>{preview.material}</p>
            <p>{preview.care}</p>
            <Typography.Text type="secondary">
              不公开内部持有人、核对依据或操作历史。
            </Typography.Text>
          </ProCard>
        </div>
        {savedId && (
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
    </PageContainer>
  );
}
