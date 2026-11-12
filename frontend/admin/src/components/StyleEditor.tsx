import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Col,
  Form,
  Image,
  Input,
  InputNumber,
  Row as GridRow,
  Select,
  Space,
  Typography,
  Upload,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { ProCard } from "@ant-design/pro-components";
import { ApiError, request, uploadStyleImage } from "../api";
import { command, read, Row, unknown } from "../catalog";
import { ActionForm, Gallery, State, required } from "./CatalogUI";

type Draft = { file: File; id: string; url?: string; uncertain?: boolean };
type Drafts = Map<string, Draft>;
function Pictures({
  value = [],
  onChange,
  drafts,
}: {
  value?: string[];
  onChange?: (v: string[]) => void;
  drafts: Drafts;
}) {
  const { modal, message } = App.useApp();
  const current = useRef(value);
  current.current = value;
  return (
    <>
      <Upload
        accept="image/png,image/jpeg,image/webp"
        listType="picture"
        multiple
        maxCount={20}
        fileList={value.map((url, n) => ({
          uid: url,
          name: `第 ${n + 1} 张 · ${drafts.get(url)?.file.name || "商品图片"} · ${drafts.has(url) ? "待保存" : "已保存"}${n === 0 ? " · 列表首图" : ""}`,
          status: "done" as const,
          url,
        }))}
        beforeUpload={(file) => {
          if (
            !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
            file.size > 8 * 1024 * 1024 ||
            current.current.length >= 20
          ) {
            void message.warning("最多20张，请选择8MiB以内的JPEG/PNG/WebP图片");
            return Upload.LIST_IGNORE;
          }
          const url = URL.createObjectURL(file);
          drafts.set(url, {
            file,
            id: crypto.randomUUID().replaceAll("-", ""),
          });
          current.current = [...current.current, url];
          onChange?.(current.current);
          return Upload.LIST_IGNORE;
        }}
        onRemove={(file) => {
          current.current = current.current.filter((url) => url !== file.uid);
          onChange?.(current.current);
          return true;
        }}
        onPreview={(file) =>
          modal.info({
            title: "图片预览",
            content: <Image src={file.url} alt={file.name || "商品参考图片"} />,
          })
        }
      >
        {value.length < 20 && (
          <Button icon={<PlusOutlined />}>上传商品图片</Button>
        )}
      </Upload>
      <Typography.Paragraph type="secondary">
        <State
          value={
            value.some((url) => drafts.has(url)) ? "有未保存修改" : "已保存内容"
          }
        />
        最多20张，单张不超过8MiB。选图后预览，点击保存共用资料提交。
      </Typography.Paragraph>
    </>
  );
}
function Fields({ record, drafts }: { record?: Row; drafts: Drafts }) {
  const form = Form.useFormInstance();
  const v = Form.useWatch([], form) || {};
  useEffect(() => {
    if (record) {
      form.resetFields();
      form.setFieldsValue(record);
    }
  }, [record]);
  const dirty =
    !record ||
    form.isFieldsTouched() ||
    (v.image_urls || []).some((url: string) => drafts.has(url));
  return (
    <div className="style-editor-grid">
      <ProCard
        size="small"
        headerBordered
        variant="outlined"
        title="共用商品资料"
      >
        <GridRow gutter={16}>
          <Form.Item name="id" hidden>
            <InputNumber />
          </Form.Item>
          <Col xs={24} md={12}>
            <Form.Item
              name="code"
              label="款式编号"
              rules={required}
              extra={
                record?.issue_count
                  ? "已有发行引用，款式编号不能普通修改。"
                  : undefined
              }
            >
              <Input
                autoFocus={!record}
                placeholder="请输入"
                maxLength={64}
                disabled={!!record?.issue_count}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="project"
              label="物品类别"
              rules={required}
              extra={
                record?.issue_count
                  ? "已有发行引用，类别固定；共用资料维护不改变历史分类。"
                  : undefined
              }
            >
              <Select
                disabled={!!record?.issue_count}
                options={[
                  { value: "fashion", label: "服装" },
                  { value: "jewelry", label: "饰品" },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="name" label="款式名称" rules={required}>
              <Input placeholder="请输入" maxLength={128} />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="description" label="商品介绍">
              <Input.TextArea placeholder="请输入" rows={3} maxLength={4000} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="material" label="材质">
              <Input placeholder="请输入" maxLength={256} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="care_instructions" label="养护或寓意">
              <Input placeholder="请输入" maxLength={2000} />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item
              name="specs"
              label="适用规格（每行一项）"
              extra="按实际商品填写尺寸/颜色等。共用规格调整不改变历史实体实际规格。"
              getValueProps={(value: string[] = []) => ({
                value: value.join("\n"),
              })}
              getValueFromEvent={(event) => event.target.value.split("\n")}
            >
              <Input.TextArea placeholder="请输入" rows={3} />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="image_urls" label="参考图片">
              <Pictures drafts={drafts} />
            </Form.Item>
          </Col>
        </GridRow>
      </ProCard>
      <div className="style-editor-preview">
        <div className="mobile-preview">
          <div className="mobile-preview-header">
            <span>手机展示预览</span>
            <State value={dirty ? "未保存预览" : "已保存内容"} />
          </div>
          <Gallery urls={v.image_urls || []} />
          <div className="mobile-preview-content">
            <Typography.Text type="secondary">
              {v.code || "款式编号"}
            </Typography.Text>
            <Typography.Title level={4}>
              {v.name || "商品名称"}
            </Typography.Title>
            {[
              ["商品介绍", v.description],
              ["材质说明", v.material],
              ["养护或寓意", v.care_instructions],
              [
                "适用规格",
                v.specs
                  ?.map((s: string) => s.trim())
                  .filter(Boolean)
                  .join("、"),
              ],
            ].map(([label, value]) => (
              <div className="preview-section" key={label}>
                <div className="cell-secondary">{label}</div>
                <div>{value || "暂未填写"}</div>
              </div>
            ))}
            <p className="cell-secondary">
              仅为内容展示示意，不代表真实核验结果。
            </p>
          </div>
        </div>
        <Typography.Text type="secondary">
          不公开内部持有人、核对依据或操作历史。
        </Typography.Text>
      </div>
    </div>
  );
}
export default function StyleEditor({
  record,
  page,
  onClose,
  onDone,
}: {
  record?: Row;
  page: boolean;
  onClose: () => void;
  onDone: (r: Row) => void;
}) {
  const { modal } = App.useApp();
  const drafts = useRef<Drafts>(new Map()).current;
  const [savedId, setSavedId] = useState(record?.id);
  const [partial, setPartial] = useState(false);
  useEffect(
    () => () => {
      for (const url of drafts.keys()) URL.revokeObjectURL(url);
    },
    [],
  );
  useEffect(() => {
    for (const [url, draft] of drafts)
      if (draft.url && record?.image_urls.includes(draft.url)) {
        URL.revokeObjectURL(url);
        drafts.delete(url);
      }
  }, [record]);
  const execute = async (
    payload: Record<string, any>,
    token: string,
  ): Promise<Row> => {
    const values: Record<string, any> = {
      ...payload,
      id: savedId || payload.id,
      specs: payload.specs.map((s: string) => s.trim()).filter(Boolean),
    };
    const selected: string[] = values.image_urls;
    const metadata = {
      ...values,
      image_urls: selected
        .map((url) => drafts.get(url)?.url || url)
        .filter((url) => !url.startsWith("blob:")),
    };
    const result = await command("style", metadata, token);
    setSavedId(result.id);
    if (!selected.some((url) => drafts.has(url))) return result;
    try {
      for (const url of selected) {
        const draft = drafts.get(url);
        if (!draft || draft.url) continue;
        if (draft.uncertain) {
          try {
            draft.url = (
              await request<{ url: string }>(
                `/admin/catalog/styles/${result.id}/images/${draft.id}/status`,
              )
            ).url;
            continue;
          } catch (e) {
            if (!(e instanceof ApiError) || e.status !== 404) throw e;
          }
        }
        try {
          draft.url = (
            await uploadStyleImage(result.id, draft.id, draft.file)
          ).url;
          draft.uncertain = false;
        } catch (e) {
          draft.uncertain = unknown(e);
          throw e;
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) throw e;
      setPartial(true);
      throw new ApiError(
        409,
        "style_images_pending",
        "款式资料已保存，图片尚未全部提交。输入和选图已保留；再次保存将先核对未知上传，不会重复创建款式。",
      );
    }
    const final = await command(
      "style",
      {
        ...values,
        id: result.id,
        image_urls: selected.map((url) => drafts.get(url)?.url || url),
      },
      crypto.randomUUID(),
    );
    setPartial(false);
    return final;
  };
  return (
    <ActionForm
      title="维护款式共用资料"
      action="style"
      page={page}
      width={1120}
      className="page-stack form-page"
      footerNote={
        savedId
          ? `共用资料 · 引用 ${record?.item_count || 0} 件物品`
          : "先建立款式资料，再维护发行约定"
      }
      submitText="保存共用资料"
      initial={record || { project: "fashion", specs: [], image_urls: [] }}
      beforeSubmit={async (values) => {
        if (!savedId) return true;
        const impact = await read("styles", savedId);
        if (!impact.item_count) return true;
        const accepted = await new Promise<boolean>((resolve) =>
          modal.confirm({
            title: "确认同步共用商品资料？",
            content: `将影响${impact.item_count}件引用该款式的物品，其中${impact.active_item_count}件已启用，不修改发行与物品历史。`,
            okText: "确认同步保存",
            cancelText: "取消",
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          }),
        );
        if (accepted) values.shared_confirmed = true;
        return accepted;
      }}
      execute={execute}
      onReceipt={(result) => {
        setSavedId(result.id);
        return drafts.size === 0;
      }}
      onClose={onClose}
      onDone={onDone}
    >
      {partial && (
        <Alert
          type="warning"
          title="款式资料已保存，仍有图片待保存；请继续完成或明确放弃未保存部分。"
        />
      )}
      <Fields record={record} drafts={drafts} />
    </ActionForm>
  );
}
