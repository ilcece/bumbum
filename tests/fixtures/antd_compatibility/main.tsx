// 仅使用合成数据验证官方组件，不能作为真实上传或业务权限验收。
import '@ant-design/v5-patch-for-react-19';
import React, { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App, Button, ConfigProvider, Form, Modal, notification, Select, Space, Upload } from 'antd';
import type { UploadFile, UploadProps } from 'antd';
import { ProForm, ProFormText } from '@ant-design/pro-components';
import zhCN from 'antd/locale/zh_CN';
import 'antd/dist/reset.css';

function Smoke() {
  const app = App.useApp();
  const [hookModal, modalHolder] = Modal.useModal();
  const [hookNotification, notificationHolder] = notification.useNotification();
  const [event, setEvent] = useState('就绪');
  const [form] = Form.useForm();
  const [readonly, setReadonly] = useState(false);
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [uploadMode, setUploadMode] = useState('success');
  const modalRef = useRef<ReturnType<typeof Modal.confirm> | null>(null);

  function openModal(mode: 'static' | 'app' | 'hook', trigger: HTMLElement) {
    const api = mode === 'static' ? Modal : mode === 'app' ? app.modal : hookModal;
    modalRef.current = api.confirm({
      title: `${mode}弹层`, okText: '确认', cancelText: '取消',
      content: <Space><span>初始内容</span>
        <Button onClick={() => modalRef.current?.update({ content: '更新后的内容' })}>更新当前弹层</Button>
        <Button onClick={() => modalRef.current?.destroy()}>销毁当前弹层</Button>
      </Space>,
      onOk: () => { setEvent(`${mode}确认`); },
      onCancel: () => { setEvent(`${mode}取消`); },
      afterClose: () => trigger.focus(),
    });
  }
  function notify(mode: 'static' | 'app' | 'hook', action: 'open' | 'success' | 'update' | 'destroy') {
    const api = mode === 'static' ? notification : mode === 'app' ? app.notification : hookNotification;
    if (action === 'destroy') { api.destroy('smoke'); return; }
    const options = { key: 'smoke', message: action === 'update' ? '更新后的通知' : `${mode}通知`, description: '合成内容', duration: 0 };
    if (action === 'success') api.success(options);
    else api.open(options);
  }
  const upload: UploadProps = {
    fileList: files,
    customRequest: options => {
      const controller = new AbortController();
      const body = new FormData();
      body.append('file', options.file as Blob);
      fetch(`/_smoke/upload?mode=${uploadMode}`, { method: 'POST', body, signal: controller.signal })
        .then(async response => {
          const result = await response.json();
          if (!response.ok || !result.bytes) throw new Error('合成上传失败');
          options.onSuccess?.(result);
          setEvent('上传回调成功');
        })
        .catch(reason => {
          if (reason.name !== 'AbortError') { options.onError?.(reason); setEvent('上传回调失败'); }
        });
      return { abort: () => { controller.abort(); setEvent('上传请求已取消'); } };
    },
    onChange: info => setFiles(info.fileList),
  };
  return <main style={{ padding: 24 }}>
    <h1>隔离组件验证 · 合成数据</h1><p role="status">{event}</p>
    {modalHolder}{notificationHolder}
    <section aria-label="弹层验证"><h2>Modal</h2><Space>
      {(['static', 'app', 'hook'] as const).map(mode => <Button key={mode} onClick={e => openModal(mode, e.currentTarget)}>{mode}打开弹层</Button>)}
    </Space></section>
    <section aria-label="通知验证"><h2>Notification</h2>
      {(['static', 'app', 'hook'] as const).map(mode => <Space key={mode}>
        {(['open', 'success', 'update', 'destroy'] as const).map(action => <Button key={action} onClick={() => notify(mode, action)}>{mode}通知{action}</Button>)}
      </Space>)}
    </section>
    <section aria-label="上传验证"><h2>Upload</h2>
      <Select aria-label="上传结果" value={uploadMode} onChange={setUploadMode} style={{ width: 160 }} options={[
        { value: 'success', label: '成功' }, { value: 'error', label: '失败' }, { value: 'slow', label: '延迟后成功' },
      ]} />
      <Upload {...upload}><Button>选择合成图片</Button></Upload>
    </section>
    <section aria-label="表单验证"><h2>Form</h2>
      <ProForm form={form} name="compat" readonly={readonly} initialValues={{ name: '', uid: '04:A2:7F:1B:5E:80:00' }} submitter={false}
        onFinish={async values => { setEvent(`已提交:${values.name}`); return true; }}>
        <ProFormText name="name" label="名称" rules={[{ required: true, message: '请填写名称' }]} />
        <ProFormText name="uid" label="芯片身份" readonly />
      </ProForm>
      <Space>
        <Button onClick={async () => { try { await form.validateFields(); setEvent('校验通过'); } catch { form.scrollToField('name', { focus: true }); setEvent('校验拒绝'); } }}>校验并定位</Button>
        <Button onClick={() => form.setFieldsValue({ name: '记录B' })}>载入记录B</Button>
        <Button onClick={() => form.resetFields()}>重置表单</Button>
        <Button onClick={() => form.submit()}>提交表单</Button>
        <Button onClick={() => setReadonly(value => !value)}>切换只读</Button>
      </Space>
    </section>
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><ConfigProvider locale={zhCN}><App><Smoke /></App></ConfigProvider></React.StrictMode>);
