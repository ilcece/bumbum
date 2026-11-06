import { useState } from "react";
import { PageContainer, ProColumns } from "@ant-design/pro-components";
import { Button, Drawer, Form, Input, InputNumber, Select, Switch } from "antd";
import { history } from "@umijs/max";
import { Row, statusNames, time } from "../catalog";
import { ActionForm, Copy, State, required } from "../components/CatalogUI";
import ServerTable from "../components/ServerTable";
import KeyConfiguration from "../components/KeyConfiguration";
import ChipDetail from "./ChipDetail";
export default function Chips() {
  const [keyChip, setKeyChip] = useState<number>();
  const [id, setId] = useState<number>(),
    [create, setCreate] = useState(false),
    [rev, setRev] = useState(0);
  const columns: ProColumns<Row>[] = [
    {
      title: "关键词",
      dataIndex: "keyword",
      hideInTable: true,
      fieldProps: { placeholder: "芯片UID、物品编号或批次" },
    },
    {
      title: "芯片编号",
      dataIndex: "chip_uid",
      search: false,
      render: (_, r) => (
        <div>
          <Copy value={r.chip_uid} onClick={() => setId(r.id)} />
          {r.is_validation && (
            <div>
              <State value="生产验证对象" />
            </div>
          )}
        </div>
      ),
    },
    {
      title: "批次",
      dataIndex: "batch_no",
      search: false,
      render: (_, r) => <Copy value={r.batch_no} />,
    },
    {
      title: "首次来源",
      dataIndex: "registration_source",
      valueEnum: { manual: "手工", nfc_cool: "NFC.cool", unknown: "未记录" },
    },
    {
      title: "服务状态",
      dataIndex: "status",
      valueEnum: {
        pending: "待绑定",
        bound: "已绑定",
        disabled: "临时停用",
        lost: "随物品挂失停用",
        retired: "已退役",
      },
      render: (_, r) => <State value={statusNames[r.chip_status]} />,
    },
    {
      title: "配置状态",
      dataIndex: "configured",
      valueEnum: { yes: "已核验", no: "待核验" },
      render: (_, r) => (
        <State
          value={
            r.provisioned_at
              ? "核验就绪"
              : r.keys_generated
                ? "待核验"
                : "待配置"
          }
        />
      ),
    },
    {
      title: "物品关联",
      search: false,
      render: (_, r) =>
        r.item_uid ? (
          <Copy
            value={r.item_uid}
            onClick={() => history.push("/items/" + r.item_id)}
          />
        ) : r.candidate_id ? (
          <State value="候选未生效" />
        ) : (
          <State value="未关联" />
        ),
    },
    {
      title: "数据性质",
      hideInTable: true,
      dataIndex: "is_validation",
      valueEnum: { true: "生产验证", false: "正常业务" },
      render: (_, r) =>
        r.is_validation ? <State value="生产验证对象" /> : "—",
    },
    { title: "登记时间", search: false, render: (_, r) => time(r.created_at) },
    {
      title: "操作",
      valueType: "option",
      fixed: "right",
      render: (_, r) => [
        <Button key="view" type="link" onClick={() => setId(r.id)}>
          查看
        </Button>,
        <Button
          key="keys"
          type="link"
          disabled={
            (!r.item_id && !r.candidate_id) ||
            !["bound", "pending"].includes(r.chip_status)
          }
          onClick={() => setKeyChip(r.id)}
        >
          密钥与配置
        </Button>,
      ],
    },
  ];
  return (
    <PageContainer title={false}>
      <ServerTable
        resource="chips"
        columns={columns}
        refresh={rev}
        extra={[
          <Button key="create" type="primary" onClick={() => setCreate(true)}>
            手工登记芯片
          </Button>,
        ]}
      />
      <Drawer
        width={900}
        open={!!id}
        title="芯片详情"
        destroyOnHidden
        onClose={() => {
          setId(undefined);
          setRev((n) => n + 1);
        }}
        extra={
          <Button
            onClick={() =>
              history.push(
                `/chips/${id}?from=${encodeURIComponent(location.pathname + location.search)}`,
              )
            }
          >
            打开完整详情
          </Button>
        }
      >
        {id && (
          <ChipDetail
            id={id}
            embedded
            onDeleted={() => {
              setId(undefined);
              setRev((n) => n + 1);
            }}
          />
        )}
      </Drawer>
      {keyChip && (
        <KeyConfiguration
          id={keyChip}
          onClose={() => setKeyChip(undefined)}
          onUpdated={() => {
            setRev((n) => n + 1);
          }}
        />
      )}
      {create && (
        <ActionForm
          title="登记芯片"
          action="register"
          initial={{ is_validation: false }}
          onClose={() => setCreate(false)}
          onDone={(r) => {
            setCreate(false);
            setId(r.id);
            setRev((n) => n + 1);
          }}
        >
          <Form.Item name="chip_uid" label="芯片编号 UID" rules={required}>
            <Input maxLength={32} placeholder="7字节真实UID" />
          </Form.Item>
          <Form.Item name="project" label="物品类别">
            <Select
              allowClear
              options={[
                { value: "fashion", label: "服装" },
                { value: "jewelry", label: "饰品" },
              ]}
            />
          </Form.Item>
          <Form.Item name="batch_no" label="批次">
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item
            name="is_validation"
            label="生产验证对象"
            valuePropName="checked"
          >
            <Switch aria-label="芯片生产验证对象" />
          </Form.Item>
        </ActionForm>
      )}
    </PageContainer>
  );
}
