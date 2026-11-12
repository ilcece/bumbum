import { useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Space,
  Steps,
  Typography,
} from "antd";
import { ApiError, chipKeyRequest, readConfigurationChip } from "./api";
import { ProCard, ProDescriptions } from "@ant-design/pro-components";
import { Copy, State } from "./components/CatalogUI";
import { time } from "./catalog";
import type { ChipKeys, ChipView, SunReading } from "./api";

function parseReading(value: string, publicOrigin: string): SunReading {
  const url = new URL(value.trim());
  if (
    url.origin !== publicOrigin ||
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
  const publicOrigin = window.location.hostname === "test.bumbum.cc"
    ? "https://nfc-test.bumbum.cc"
    : "https://nfc.bumbum.cc";
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
          readings: links.map((link) => parseReading(link, publicOrigin)),
          management_confirmed: management,
        };
    } catch {
      setError(
        `请填写两条正确的系统触碰链接，地址须为 ${publicOrigin}/tap 并包含完整动态参数。`,
      );
      return;
    }
    inFlight.current = true;
    setBusy(true);
    onInteraction({ dirty: dirty || unknown, busy: true });
    setKeys(null);
    if (action !== "keys") setViewConfirmed(false);
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
          result.sun_url_template !== `${publicOrigin}/tap?picc_data={picc}&cmac={cmac}` ||
          Object.keys(result.keys).sort().join(",") !== "K0,K1,K2,K3,K4" ||
          Object.values(result.keys).some(
            (value) =>
              typeof value !== "string" || !/^[0-9A-F]{32}$/.test(value),
          )
        )
          throw new Error("密钥返回结果无法核对。");
        if (mounted.current)
          setKeys({
            ...result,
            sun_url_template: result.sun_url_template
              .replace("{picc}", "0".repeat(32))
              .replace("{cmac}", "0".repeat(16)),
          });
      } else if (action === "query") {
        const actual = await readConfigurationChip(chip.id);
        if (
          !actual ||
          actual.item_id !== initialChip.item_id ||
          actual.candidate_id !== initialChip.candidate_id ||
          actual.candidate_item_id !== initialChip.candidate_item_id ||
          !["bound", "pending"].includes(actual.chip_status)
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
          update({ ...chip, ...result });
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
  const eligible =
    !!chip.project &&
    ((!!chip.item_id && chip.chip_status === "bound") ||
      (!!chip.candidate_id && chip.chip_status === "pending"));
  const blockedActions = busy || blocked || unknown || !safe || !eligible;
  const blockedReadings =
    blockedActions || !chip.keys_generated || !!chip.provisioned_at;
  return (
    <Modal
      open
      title="密钥与配置"
      onCancel={close}
      mask={{ closable: false }}
      closable={!busy}
      width={820}
      styles={{
        body: { maxHeight: "calc(100dvh - 210px)", overflowY: "auto" },
      }}
      footer={
        <Button disabled={busy} onClick={close}>
          关闭
        </Button>
      }
      destroyOnHidden
    >
      <div className="page-stack">
        <Alert
          type="info"
          showIcon
          title="生成、工具配卡和配置核验分别完成"
          description="本窗口使用正式受控服务；候选芯片核验不会提前替换当前芯片，生成密钥不会自动启用物品。"
        />
        <ProDescriptions
          size="small"
          bordered
          column={2}
          columns={[
            { title: "芯片 UID", render: () => <Copy value={chip.chip_uid} /> },
            {
              title: chip.candidate_id ? "候选关联数字物品" : "关联数字物品",
              render: () => (
                <Copy value={chip.item_uid || chip.candidate_item_uid} />
              ),
            },
            {
              title: "密钥状态",
              render: () => (
                <State value={chip.keys_generated ? "已生成" : "未准备"} />
              ),
            },
            {
              title: "配置状态",
              render: () => (
                <State value={chip.provisioned_at ? "配置已核验" : "待配置"} />
              ),
            },
          ]}
        />
        <Steps
          size="small"
          current={
            chip.provisioned_at ? 3 : !chip.keys_generated ? 0 : keys ? 2 : 1
          }
          items={[
            { title: "生成密钥" },
            { title: "受控查看与配卡" },
            { title: "双链接核验" },
          ]}
        />
        {!eligible && (
          <Alert
            type="warning"
            title="当前关联或状态不允许配卡，请先核对物品与芯片状态。"
          />
        )}
        {!safe && (
          <Alert type="error" title="记录编号超出页面可处理范围，不能提交。" />
        )}
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="1. 生成并保存芯片密钥"
        >
          <div className="page-stack">
            <Typography.Text type="secondary">
              生成不代表写卡完成，已有密钥不可覆盖。
            </Typography.Text>
            <div>
              <Button
                type="primary"
                disabled={
                  blockedActions || chip.keys_generated || !!chip.provisioned_at
                }
                onClick={() => void run("generate-keys")}
              >
                生成密钥
              </Button>
            </div>
          </div>
        </ProCard>
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="2. 受控查看 K0–K4 与 SUN 模板"
        >
          <div className="page-stack">
            <Checkbox
              checked={viewConfirmed}
              disabled={blockedActions || !chip.keys_generated}
              onChange={(event) => {
                setViewConfirmed(event.target.checked);
                if (!event.target.checked) setKeys(null);
              }}
            >
              我确认查看密钥；K1 是同版本全局秘密，影响所有项目的对应芯片。
            </Checkbox>
            <div>
              <Button
                disabled={
                  blockedActions || !chip.keys_generated || !viewConfirmed
                }
                onClick={() => (keys ? setKeys(null) : void run("keys"))}
              >
                {keys ? "隐藏并清除密钥" : "查看密钥"}
              </Button>
            </div>
            {keys && (
              <section
                className="key-values"
                data-private="true"
                aria-label="芯片密钥"
              >
                <Typography.Text>
                  仅用于当前卡配卡，关闭后清除展示值。
                </Typography.Text>
                {Object.entries(keys.keys).map(([name, value]) => (
                  <div className="key-row" key={name}>
                    <Space>
                      <strong style={{ color: "#93c5fd" }}>{name}</strong>
                      {name === "K1" && <State value="全局共享" />}
                      {name === "K2" && <State value="单卡独立" />}
                    </Space>
                    <Copy value={value} />
                  </div>
                ))}
                <div className="template-value">
                  <Typography.Text>固定 NDEF URL 模板</Typography.Text>
                  <br />
                  <Copy value={keys.sun_url_template} />
                </div>
              </section>
            )}
            <Typography.Text type="secondary">
              按既定 NFC.cool 手册配置：SUN 加密、Meta Read Key 1、File Read Key
              2；管理权限由 K0 控制。
            </Typography.Text>
          </div>
        </ProCard>
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="3. 配卡后双链接动态读数核验"
        >
          {chip.provisioned_at ? (
            <Alert
              type="success"
              showIcon
              title="配置已核验"
              description={`核验时间：${time(chip.provisioned_at)}；不允许重复确认或重置计数基线。`}
            />
          ) : (
            <div className="page-stack">
              <Typography.Text type="secondary">
                通过系统触碰通知打开浏览器，依次复制两条新链接；服务端核对目标
                UID、验签和计数递增，无需恰好加一。
              </Typography.Text>
              <Form layout="vertical" className="key-inputs">
                {links.map((value, index) => (
                  <Form.Item
                    key={index}
                    label={`第${index + 1}条触碰链接`}
                    htmlFor={`reading-${index}`}
                  >
                    <Input.TextArea
                      id={`reading-${index}`}
                      data-private="true"
                      autoComplete="off"
                      spellCheck={false}
                      rows={2}
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
              </Form>
              <Checkbox
                checked={management}
                disabled={blockedReadings}
                onChange={(event) => setManagement(event.target.checked)}
              >
                我已人工核对新 K0 可以认证，文件权限符合手册。SUN
                验签不替代这项检查。
              </Checkbox>
              <div>
                <Button
                  type="primary"
                  disabled={
                    blockedReadings ||
                    !management ||
                    links.some((value) => !value)
                  }
                  onClick={() => void run("confirm-provisioning")}
                >
                  确认配置核验
                </Button>
              </div>
            </div>
          )}
        </ProCard>
        <div>
          <Button disabled={busy || !safe} onClick={() => void run("query")}>
            查询实际记录
          </Button>
        </div>
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
      </div>
    </Modal>
  );
}
