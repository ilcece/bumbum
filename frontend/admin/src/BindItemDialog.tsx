import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Checkbox, Form, Input, Modal, Select, Space, Table, Typography } from "antd";
import { ApiError, bindChipItem, listChips, listItems } from "./api";
import type { ChipView, ItemList, ItemQuery, ItemView } from "./api";

const PROJECTS = { fashion: "服装", jewelry: "饰品" };
const STATES = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
};
const safeId = (id: number) => Number.isSafeInteger(id) && id > 0;

export function BindItemDialog({
  chip,
  onClose,
  onBound,
  onSessionExpired,
  onInteraction,
}: {
  chip: ChipView;
  onClose: () => void;
  onBound: (chip: ChipView, recovered: boolean) => void;
  onSessionExpired: () => void;
  onInteraction: (state: { dirty: boolean; busy: boolean }) => void;
}) {
  const { modal } = App.useApp();
  const [filters, setFilters] = useState({
    project: chip.project || "fashion",
    keyword: "",
  });
  const [query, setQuery] = useState<ItemQuery | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ItemList | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selected, setSelected] = useState<ItemView | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [unknown, setUnknown] = useState(false);
  const [retryAllowed, setRetryAllowed] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    onInteraction({ dirty: selected !== null, busy: sending || checking });
    return () => onInteraction({ dirty: false, busy: false });
  }, [selected, sending, checking, onInteraction]);

  useEffect(() => {
    if (!query) return;
    let cancelled = false;
    setLoading(true);
    setResult(null);
    setSearchError("");
    listItems(query)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((failure) => {
        if (cancelled) return;
        if (failure instanceof ApiError && failure.status === 401)
          onSessionExpired();
        else
          setSearchError(
            failure instanceof ApiError
              ? failure.message
              : "候选物品读取失败，请重新查询。",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, onSessionExpired]);

  function changeFilters(next: typeof filters) {
    setFilters(next);
    setPending(true);
    setSelected(null);
    setConfirmed(false);
    setError("");
  }
  function runQuery(page = 1) {
    setSelected(null);
    setConfirmed(false);
    setPending(false);
    setError("");
    setQuery({ ...filters, status: "", page, unbound_only: true });
  }
  function close() {
    if (inFlight.current) return;
    if (selected || unknown) {
      modal.confirm({ title: "放弃本次绑定选择？", content: unknown ? "绑定结果尚未确认，关闭后须按芯片ID核对。" : "关闭不会提交绑定。",
        okText: "放弃并关闭", cancelText: "继续核对", onOk: onClose });
      return;
    }
    onClose();
  }
  function reportBusy(busy: boolean) {
    inFlight.current = busy;
    onInteraction({ dirty: selected !== null, busy });
  }
  async function submit() {
    if (
      inFlight.current ||
      !selected ||
      !confirmed ||
      pending ||
      loading ||
      blocked ||
      (unknown && !retryAllowed)
    )
      return;
    if (!safeId(chip.id) || !safeId(selected.id)) {
      setError("记录编号超出当前页面可处理范围，未提交绑定，请反馈。");
      return;
    }
    reportBusy(true);
    setSending(true);
    setError("");
    setRetryAllowed(false);
    try {
      const bound = await bindChipItem(chip.id, selected.id);
      if (mounted.current) {
        onInteraction({ dirty: false, busy: false });
        onBound(bound, false);
      }
    } catch (failure) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        setBlocked(true);
        setError("页面防冒用校验失效，请刷新页面后重新核对提交；未自动重发。");
      } else if (
        failure instanceof ApiError &&
        failure.status < 500 &&
        failure.code !== "unexpected_response"
      ) {
        setError(failure.message);
      } else {
        setUnknown(true);
        setConfirmed(false);
        setError(
          `${failure instanceof ApiError ? failure.message + " " : ""}结果尚未确认，请查询此芯片；不会自动重发。`,
        );
      }
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setSending(false);
        onInteraction({ dirty: selected !== null, busy: false });
      }
    }
  }
  async function verify() {
    if (inFlight.current || !selected) return;
    reportBusy(true);
    setChecking(true);
    setRetryAllowed(false);
    setConfirmed(false);
    try {
      const data = await listChips({
        page: 1,
        project: "",
        status: "",
        keyword: chip.chip_uid,
      });
      if (!mounted.current) return;
      const found = data.items.find(
        (row) => row.id === chip.id && row.chip_uid === chip.chip_uid,
      );
      if (!found) setError("尚未查到该芯片，结果仍未确认，请稍后查询或反馈。");
      else if (found.chip_status === "bound" && found.item_id === selected.id) {
        onInteraction({ dirty: false, busy: false });
        onBound(found, true);
      } else if (found.item_id !== null) {
        setBlocked(true);
        setError(
          `芯片当前关联物品：${found.item_uid || "编号暂不可读"}，状态为${found.chip_status === "bound" ? "已绑定" : "不可绑定"}。与本次目标不符，未覆盖，请反馈。`,
        );
      } else if (found.chip_status !== "pending") {
        setBlocked(true);
        setError("芯片当前已停用或标记丢失，不能提交绑定。");
      } else {
        setRetryAllowed(true);
        setError(
          "目前尚未查到绑定，原请求仍可能处理中。核对原目标并重新勾选后，可手动重试同一目标；不会自动重发。",
        );
      }
    } catch (failure) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else
        setError(
          `${failure instanceof ApiError ? failure.message : "查询失败。"} 绑定结果仍未确认，请稍后再查。`,
        );
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setChecking(false);
        onInteraction({ dirty: selected !== null, busy: false });
      }
    }
  }

  const busy = sending || checking;
  const canSubmit = Boolean(
    selected &&
      confirmed &&
      !pending &&
      !loading &&
      !busy &&
      !blocked &&
      (!unknown || retryAllowed),
  );
  return <Modal open title="绑定物品" onCancel={close} maskClosable={false} closable={!busy} width={900}
    footer={<Space>
      {unknown && <Button loading={checking} disabled={busy} onClick={() => void verify()}>查询此芯片</Button>}
      <Button disabled={busy} onClick={close}>取消绑定</Button>
      <Button aria-label={unknown ? "重试原目标绑定" : "确认绑定"} type="primary" loading={sending} disabled={!canSubmit} onClick={() => void submit()}>{unknown ? "重试原目标绑定" : "确认绑定"}</Button>
    </Space>}>
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Alert type="info" showIcon message="绑定只建立关联，不生成密钥或写卡。本版本暂不提供解绑或换绑。" />
      <Typography.Text>芯片UID：{chip.chip_uid}；当前项目：{chip.project ? PROJECTS[chip.project] : "未分配，绑定时按目标物品确定"}；批次：{chip.batch_no || "未填写"}</Typography.Text>
      {!safeId(chip.id) && <Alert type="error" message="芯片记录编号超出当前页面可处理范围，不能选择或绑定，请反馈。" />}
      <Form layout="inline" disabled={busy || unknown} aria-label="查询绑定候选物品" onFinish={() => { if (!busy && !unknown) runQuery(); }}>
        <Form.Item label="候选项目" htmlFor="candidate-project"><Select id="candidate-project" style={{ width: 150 }}
          value={filters.project} disabled={busy || unknown || chip.project !== null}
          options={Object.entries(PROJECTS).map(([value, label]) => ({ value, label }))}
          onChange={value => changeFilters({ ...filters, project: value })} /></Form.Item>
        <Form.Item label="物品关键词" htmlFor="candidate-keyword"><Input id="candidate-keyword" maxLength={128} value={filters.keyword}
          placeholder="物品编号或款式编号" onChange={event => changeFilters({ ...filters, keyword: event.target.value })} /></Form.Item>
        <Form.Item><Button htmlType="submit" disabled={busy || unknown}>查询物品</Button></Form.Item>
      </Form>
      {pending && <Alert type="info" message="条件已改变，请点击“查询物品”；旧结果不可选。" />}
      {searchError && <Alert type="error" showIcon message={searchError} />}
      {!query && <Typography.Text>可输入编号或款式后查询，也可直接查询所选项目。</Typography.Text>}
      {result && !searchError && <>
        <Typography.Text>共 {result.total} 件未被芯片占用的物品；最终能否绑定以提交时检查为准。</Typography.Text>
        {result.items.some(item => !safeId(item.id)) && <Alert type="error" message="有物品记录编号超出当前页面可处理范围，该行不能选择，请反馈。" />}
        <Table<ItemView> aria-label="绑定候选物品" rowKey="id" loading={loading} dataSource={result.items} scroll={{ x: 700 }}
          columns={[
            { title: "项目", dataIndex: "project", render: (value: ItemView["project"]) => PROJECTS[value] },
            { title: "物品编号", dataIndex: "item_uid" }, { title: "款式编号", dataIndex: "sku_code", render: value => value || "未填写" },
            { title: "名称", render: (_, item) => typeof item.profile?.name === "string" ? item.profile.name : "未填写" },
            { title: "状态", dataIndex: "status", render: (value: ItemView["status"]) => STATES[value] },
          ]}
          rowSelection={{ type: "radio", selectedRowKeys: selected ? [selected.id] : [],
            getCheckboxProps: item => ({ disabled: busy || unknown || pending || item.status === "archived" || !safeId(item.id) || !safeId(chip.id), "aria-label": `选择物品 ${item.item_uid}` }),
            onChange: (_, rows) => { setSelected(rows[0] || null); setConfirmed(false); setError(""); } }}
          pagination={{ current: query?.page, pageSize: result.page_size, total: result.total, showSizeChanger: false,
            disabled: busy || unknown || pending, onChange: page => runQuery(page) }} locale={{ emptyText: "没有符合条件的可绑定物品。" }} />
      </>}
      {selected && <Alert type="warning" showIcon message={`核对芯片 ${chip.chip_uid} → ${PROJECTS[selected.project]}物品 ${selected.item_uid}`}
        description={<Space direction="vertical">
          {chip.project === null && <span>芯片项目将确定为：{PROJECTS[selected.project]}</span>}
          <Checkbox checked={confirmed} disabled={busy || blocked || (unknown && !retryAllowed)} onChange={event => setConfirmed(event.target.checked)}>
            我已核对芯片与物品编号，理解本版本暂不提供解绑或换绑。
          </Checkbox>
        </Space>} />}
      {error && <Alert type="error" showIcon message={error} />}
    </Space>
  </Modal>;
}
