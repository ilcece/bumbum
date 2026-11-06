import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Divider,
  Form,
  Input,
  Modal,
  Space,
  Typography,
} from "antd";
import { ApiError, chipKeyRequest, listChips } from "./api";
import type { ChipKeys, ChipView, SunReading } from "./api";

function parseReading(value: string): SunReading {
  const url = new URL(value.trim());
  if (
    url.origin !== "https://nfc.bumbum.cc" ||
    url.pathname !== "/tap" ||
    url.hash ||
    url.username ||
    url.password ||
    [...url.searchParams.keys()].sort().join(",") !== "cmac,picc_data"
  )
    throw new Error(
      "请填写目标域名 /tap 的完整触碰链接，只包含 picc_data、cmac。",
    );
  const picc_data = url.searchParams.get("picc_data") || "",
    cmac = url.searchParams.get("cmac") || "";
  if (!/^[\da-f]{32}$/i.test(picc_data) || !/^[\da-f]{16}$/i.test(cmac))
    throw new Error("动态参数不完整，请重新复制链接。");
  return { picc_data, cmac };
}

export function ChipKeysDialog({
  chip: initialChip,
  onClose,
  onUpdated,
  onSessionExpired,
  onInteraction,
}: {
  chip: ChipView;
  onClose: () => void;
  onUpdated: (chip: ChipView) => void;
  onSessionExpired: () => void;
  onInteraction: (state: { dirty: boolean; busy: boolean }) => void;
}) {
  const { modal } = App.useApp();
  const [chip, setChip] = useState(initialChip);
  const [keys, setKeys] = useState<ChipKeys | null>(null);
  const [viewConfirmed, setViewConfirmed] = useState(false);
  const [management, setManagement] = useState(false);
  const [links, setLinks] = useState(["", ""]);
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const dirty = links.some(Boolean) || management;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    onInteraction({ dirty: dirty || unknown, busy });
    return () => onInteraction({ dirty: false, busy: false });
  }, [dirty, busy, unknown, onInteraction]);

  function update(next: ChipView) {
    setChip(next);
    onUpdated(next);
  }
  function close() {
    if (inFlight.current) return;
    function finish() {
      setKeys(null);
      setLinks(["", ""]);
      onClose();
    }
    if (dirty || unknown) {
      modal.confirm({
        title: "放弃输入并关闭？",
        content: "有未提交读数或待核对结果，关闭后须按芯片ID核对。",
        okText: "放弃并关闭",
        cancelText: "继续核对",
        onOk: finish,
      });
      return;
    }
    finish();
  }
  async function run(
    action: "generate-keys" | "keys" | "confirm-provisioning" | "query",
  ) {
    if (inFlight.current || (blocked && action !== "query")) return;
    let body: Record<string, unknown> = {};
    try {
      if (action === "confirm-provisioning")
        body = {
          readings: links.map(parseReading),
          management_confirmed: management,
        };
    } catch {
      setError(
        "请填写两条正确的系统触碰链接，地址须为 https://nfc.bumbum.cc/tap 并包含完整动态参数。",
      );
      return;
    }
    inFlight.current = true;
    setBusy(true);
    onInteraction({ dirty: dirty || unknown, busy: true });
    setKeys(null);
    setViewConfirmed(false);
    setError("");
    setNotice("");
    try {
      if (action === "keys") {
        const result = await chipKeyRequest<ChipKeys>(chip.id, action, {
          confirm: true,
        });
        if (
          result.chip_uid !== chip.chip_uid ||
          !result.keys ||
          Object.keys(result.keys).sort().join(",") !== "K0,K1,K2,K3,K4" ||
          Object.values(result.keys).some(
            (value) =>
              typeof value !== "string" || !/^[0-9A-F]{32}$/.test(value),
          )
        )
          throw new Error("密钥返回结果无法核对。");
        if (mounted.current) setKeys(result);
      } else if (action === "query") {
        const result = await listChips({
          page: 1,
          project: "",
          status: "",
          keyword: chip.chip_uid,
        });
        const actual = result.items.find(
          (value) => value.id === chip.id && value.chip_uid === chip.chip_uid,
        );
        if (
          !actual ||
          actual.item_id !== initialChip.item_id ||
          actual.chip_status !== "bound"
        ) {
          setBlocked(true);
          throw new Error("芯片关联或状态已改变，请关闭弹窗并重新查询。");
        }
        if (mounted.current) {
          update(actual);
          setUnknown(false);
          if (actual.provisioned_at) {
            setLinks(["", ""]);
            setManagement(false);
          }
          setNotice(
            actual.provisioned_at
              ? "已查到配置核验完成记录。"
              : actual.keys_generated
                ? "已查到密钥生成记录；实卡配置尚未确认。"
                : "尚未查到生成记录；原请求可能仍在处理，可稍后再查询。只有人工再次点击才提交请求。",
          );
        }
      } else if (action === "generate-keys") {
        const result = await chipKeyRequest<{
          chip_id: number;
          generated: boolean;
          key_version: string;
        }>(chip.id, action, {});
        if (
          result.chip_id !== chip.id ||
          result.generated !== true ||
          result.key_version !== "v1"
        )
          throw new Error("密钥生成结果无法核对。");
        if (mounted.current) {
          update({ ...chip, keys_generated: true });
          setNotice(
            "密钥已生成并加密保存，尚未写入卡片。请受控查看后按手册配置。",
          );
        }
      } else {
        const result = await chipKeyRequest<ChipView>(chip.id, action, body);
        if (
          result.id !== chip.id ||
          result.item_id !== initialChip.item_id ||
          !result.provisioned_at ||
          !result.keys_generated
        )
          throw new Error("配置核验结果无法核对。");
        if (mounted.current) {
          update(result);
          setLinks(["", ""]);
          setManagement(false);
          setNotice(
            "配置核验通过，已保存完成时间及计数基线；不会自动启用物品。",
          );
        }
      }
    } catch (failure) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401) {
        setKeys(null);
        setLinks(["", ""]);
        onSessionExpired();
      } else {
        const uncertain =
          action !== "query" &&
          (!(failure instanceof ApiError) ||
            failure.status >= 500 ||
            failure.code === "unexpected_response");
        if (uncertain) setUnknown(true);
        if (failure instanceof ApiError && failure.code === "csrf_failed")
          setBlocked(true);
        setError(
          failure instanceof ApiError
            ? failure.code === "csrf_failed"
              ? "操作口令已失效，请刷新页面后重新核对，不会自动重发。"
              : failure.message
            : action === "query"
              ? "查询未完成，请稍后查询实际结果。"
              : "操作结果无法确认，请先查询实际记录，不会自动重发。",
        );
      }
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setBusy(false);
        onInteraction({ dirty: dirty || unknown, busy: false });
      }
    }
  }
  const safe = Number.isSafeInteger(chip.id) && chip.id > 0;
  const blockedActions = busy || blocked || unknown || !safe;
  const blockedReadings =
    blockedActions || !chip.keys_generated || !!chip.provisioned_at;
  return (
    <Modal
      open
      title="密钥与配置"
      onCancel={close}
      mask={{ closable: false }}
      closable={!busy}
      width={720}
      footer={
        <Button disabled={busy} onClick={close}>
          关闭
        </Button>
      }
    >
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          title="生成、工具配卡和配置核验是三个不同步骤；处理当前绑定或已保存整套准备中的配套芯片；候选核验不提前生效。"
        />
        <Typography.Text>
          芯片：{chip.chip_uid}；关联物品：{chip.item_uid}
        </Typography.Text>
        <div role="status">
          {chip.keys_generated ? "密钥已生成" : "密钥未生成"}；
          {chip.provisioned_at ? "配置已核验" : "配置未核验"}
        </div>
        {!safe && (
          <Alert type="error" title="记录编号超出页面可处理范围，不能提交。" />
        )}
        <Divider titlePlacement="start">1. 生成与受控查看</Divider>
        <Button
          disabled={blockedActions || chip.keys_generated}
          onClick={() => void run("generate-keys")}
        >
          生成密钥
        </Button>
        <Checkbox
          checked={viewConfirmed}
          disabled={blockedActions}
          onChange={(event) => setViewConfirmed(event.target.checked)}
        >
          我确认查看密钥；K1 是同版本全局秘密，影响所有项目的对应芯片。
        </Checkbox>
        <Button
          disabled={blockedActions || !chip.keys_generated || !viewConfirmed}
          onClick={() => void run("keys")}
        >
          查看密钥
        </Button>
        {keys && (
          <section data-private="true" aria-label="芯片密钥">
            <Alert
              type="warning"
              title="仅用于核对这枚卡并按已确认步骤配置。关闭后清除，不下载或自动复制。"
            />
            {Object.entries(keys.keys).map(([name, value]) => (
              <Form.Item key={name} label={name} htmlFor={`secret-${name}`}>
                <Input
                  id={`secret-${name}`}
                  readOnly
                  autoComplete="off"
                  spellCheck={false}
                  value={value}
                  onFocus={(event) => event.currentTarget.select()}
                />
              </Form.Item>
            ))}
            <Typography.Paragraph>
              固定地址：https://nfc.bumbum.cc/tap；加密 SUN，元数据 Key 1，文件
              Key 2。
            </Typography.Paragraph>
            <Button onClick={() => setKeys(null)}>隐藏并清除密钥</Button>
          </section>
        )}
        <Divider titlePlacement="start">2. 实卡配置后核验</Divider>
        <Typography.Paragraph>
          按手册完成配卡后，通过系统触碰通知打开浏览器，依次复制两条新链接。无需计数恰好加一。
        </Typography.Paragraph>
        {links.map((value, index) => (
          <Form.Item
            key={index}
            label={`第${index + 1}条触碰链接`}
            htmlFor={`reading-${index}`}
          >
            <Input
              id={`reading-${index}`}
              data-private="true"
              type="url"
              autoComplete="off"
              spellCheck={false}
              maxLength={512}
              value={value}
              disabled={blockedReadings}
              onChange={(event) => {
                setKeys(null);
                setLinks((current) =>
                  current.map((entry, i) =>
                    i === index ? event.target.value : entry,
                  ),
                );
              }}
            />
          </Form.Item>
        ))}
        <Checkbox
          checked={management}
          disabled={blockedReadings}
          onChange={(event) => setManagement(event.target.checked)}
        >
          我已人工核对新 K0 可以认证，文件权限符合手册。SUN 验签不替代这项检查。
        </Checkbox>
        <Button
          type="primary"
          disabled={
            blockedReadings || !management || links.some((value) => !value)
          }
          onClick={() => void run("confirm-provisioning")}
        >
          确认配置核验
        </Button>
        <Button disabled={busy || !safe} onClick={() => void run("query")}>
          查询实际记录
        </Button>
        {busy && <div role="status">正在处理，请勿重复提交或关闭。</div>}
        {unknown && (
          <Alert
            type="warning"
            title="结果暂未确认，请先查询实际记录；不会自动重发或重新生成密钥。"
          />
        )}
        {notice && (
          <div role="status">
            <Alert type="success" showIcon title={notice} />
          </div>
        )}
        {error && <Alert type="error" showIcon title={error} />}
      </Space>
    </Modal>
  );
}
