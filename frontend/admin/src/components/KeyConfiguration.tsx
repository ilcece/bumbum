import { useEffect, useState } from "react";
import { Alert, Button, Spin } from "antd";
import { history } from "@umijs/max";
import { readChip, ChipView, sessionIsExpired } from "../api";
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
  const [chip, setChip] = useState<ChipView>(),
    [error, setError] = useState(""),
    [interaction, setInteraction] = useState({ busy: false, dirty: false });
  useEffect(() => {
    let live = true;
    readChip(id)
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
      if (sessionIsExpired()) {
        unblock();
        tx.retry();
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
