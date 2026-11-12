import { useEffect, useState } from "react";
import { Alert, App, Button, Spin } from "antd";
import { history } from "@umijs/max";
import { readConfigurationChip, ChipView, sessionIsExpired } from "../api";
import { ChipKeysDialog } from "../ChipKeysDialog";
export default function KeyConfiguration({
  id,
  onClose,
  onUpdated,
}: {
  id: number;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const { modal } = App.useApp();
  const [chip, setChip] = useState<ChipView>(),
    [error, setError] = useState(""),
    [interaction, setInteraction] = useState({ busy: false, dirty: false });
  useEffect(() => {
    let live = true;
    setChip(undefined);
    setError("");
    readConfigurationChip(id)
      .then((c) => {
        if (live) setChip(c);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [id]);
  useEffect(() => {
    const unblock = history.block((tx: any) => {
      if (sessionIsExpired() || (!interaction.busy && !interaction.dirty)) {
        unblock();
        tx.retry();
      } else if (!interaction.busy) {
        modal.confirm({
          title: "放弃未提交的配置核验？",
          content: "离开将清除展示值和输入，已保存记录保留。",
          okText: "放弃并离开",
          cancelText: "继续核验",
          onOk: () => {
            unblock();
            onClose();
            tx.retry();
          },
        });
      }
    });
    const unload = (e: BeforeUnloadEvent) => {
      if (!sessionIsExpired() && (interaction.busy || interaction.dirty)) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      unblock();
      window.removeEventListener("beforeunload", unload);
    };
  }, [interaction]);
  return error ? (
    <Alert
      type="error"
      title={error}
      action={<Button onClick={onClose}>关闭</Button>}
    />
  ) : chip ? (
    <ChipKeysDialog
      chip={chip}
      onClose={onClose}
      onUpdated={(v) => {
        setChip(v);
        onUpdated();
      }}
      onSessionExpired={() => {
        onClose();
        history.replace("/login");
      }}
      onInteraction={setInteraction}
    />
  ) : (
    <Spin />
  );
}
