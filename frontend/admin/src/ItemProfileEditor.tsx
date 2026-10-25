import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";
import type { FormEvent } from "react";
import {
  ApiError,
  changeItemStatus,
  readItem,
  saveFashionProfile,
} from "./api";
import type { FashionProfile, ItemView } from "./api";

type Form = {
  name: string;
  description: string;
  material: string;
  care_instructions: string;
  images: string;
};
const EMPTY: Form = {
  name: "",
  description: "",
  material: "",
  care_instructions: "",
  images: "",
};
const STATUSES = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
};

function fields(
  profile: Record<string, unknown> | FashionProfile | null,
): Form {
  return profile
    ? {
        name: String(profile.name || ""),
        description: String(profile.description || ""),
        material: String(profile.material || ""),
        care_instructions: String(profile.care_instructions || ""),
        images: Array.isArray(profile.image_urls)
          ? profile.image_urls.join("\n")
          : "",
      }
    : { ...EMPTY };
}

function prepare(form: Form): FashionProfile {
  const profile: FashionProfile = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    material: form.material.trim() || null,
    care_instructions: form.care_instructions.trim() || null,
    image_urls: form.images
      .split(/\r?\n/)
      .map((url) => url.trim())
      .filter(Boolean),
  };
  for (const [key, limit] of [
    ["name", 128],
    ["description", 4000],
    ["material", 256],
    ["care_instructions", 2000],
  ] as const) {
    if ([...(profile[key] || "")].length > limit)
      throw new Error(`${key}最多${limit}个字符。`);
  }
  if (!profile.name) throw new Error("请填写服装名称。");
  if (profile.image_urls.length > 20) throw new Error("图片最多20张。");
  for (const value of profile.image_urls) {
    let valid = false;
    try {
      const url = new URL(value);
      valid =
        /^https?:\/\//i.test(value) &&
        ["http:", "https:"].includes(url.protocol) &&
        !!url.hostname &&
        !url.username &&
        !url.password &&
        url.port !== "0";
    } catch {
      /* 地址不合法时统一在下面提示。 */
    }
    if (!valid || [...value].length > 2048 || /[\s\x00-\x1f\x7f\\]/.test(value))
      throw new Error(
        "图片须为最多2048字符的完整HTTP/HTTPS地址，不含账号密码或空白。",
      );
  }
  return profile;
}

function Preview({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  try {
    const parsed = new URL(url);
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username ||
      parsed.password
    )
      return <p>图片地址格式不正确。</p>;
  } catch {
    return <p>图片地址格式不正确。</p>;
  }
  return (
    <figure>
      {failed ? (
        <p>图片暂无法加载</p>
      ) : (
        <img
          src={url}
          alt="服装图片预览"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      )}
      <figcaption>{url}</figcaption>
    </figure>
  );
}

export function ItemProfileEditor({
  id,
  onClose,
  onSessionExpired,
  onGuard,
  onSaved,
}: {
  id: number;
  onClose: () => void;
  onSessionExpired: () => void;
  onGuard: (dirty: boolean, busy: boolean) => void;
  onSaved: () => void;
}) {
  const [item, setItem] = useState<ItemView | null>(null);
  const [form, setForm] = useState<Form>({ ...EMPTY });
  const [baseline, setBaseline] = useState<Form>({ ...EMPTY });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const dirty = JSON.stringify(form) !== JSON.stringify(baseline);
  const editable = item?.project === "fashion" && item.status !== "archived";

  useEffect(() => {
    onGuard(dirty, busy || loading);
    return () => onGuard(false, false);
  }, [dirty, busy, loading, onGuard]);
  useEffect(() => {
    if (!dirty && !busy) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, busy]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setMessage("");
    readItem(id)
      .then((result) => {
        if (cancelled) return;
        setItem(result);
        const next = fields(result.profile);
        setForm(next);
        setBaseline(next);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setItem(null);
        if (reason instanceof ApiError && reason.status === 401)
          onSessionExpired();
        else
          setError(
            reason instanceof Error ? reason.message : "资料读取失败，请重试。",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, revision, onSessionExpired]);

  function failure(reason: unknown) {
    if (reason instanceof ApiError && reason.status === 401) onSessionExpired();
    else if (reason instanceof ApiError && reason.code === "csrf_failed")
      setError("操作口令已失效，请刷新页面后重新提交；没有自动重发请求。");
    else
      setError(
        reason instanceof ApiError
          ? reason.message
          : "保存结果未确认，请重新读取核对；没有自动重发请求。",
      );
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !editable) return;
    let profile: FashionProfile;
    try {
      profile = prepare(form);
    } catch (reason) {
      setError((reason as Error).message);
      return;
    }
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const saved = await saveFashionProfile(id, profile);
      const next = fields(saved);
      setForm(next);
      setBaseline(next);
      setItem(
        (current) =>
          current && { ...current, profile: { ...current.profile, ...saved } },
      );
      setMessage("资料已保存；物品状态未改变。");
      onSaved();
    } catch (reason) {
      failure(reason);
    } finally {
      setBusy(false);
    }
  }

  async function statusChange(status: "active" | "disabled") {
    if (busy || !editable) return;
    if (dirty && !window.confirm("有未保存修改，是否放弃修改并操作状态？"))
      return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const next = await changeItemStatus(id, status);
      setItem(next);
      const values = fields(next.profile);
      setForm(values);
      setBaseline(values);
      setMessage(
        status === "active"
          ? "物品已启用；不代表已绑定芯片或通过防伪验证。"
          : "物品已停用，资料与关联保留。",
      );
      onSaved();
    } catch (reason) {
      failure(reason);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="profile-dialog">
        <DialogHeader>
          <DialogTitle>服装基础资料</DialogTitle>
          <DialogDescription>
            资料保存与启用停用分别操作，不包含尺码表。
          </DialogDescription>
        </DialogHeader>
        <section
          className="profile-editor"
          aria-label="服装基础资料编辑"
          aria-busy={loading || busy}
        >
          <p>
            保存和启停分别操作。多人编辑以最后成功保存的整份资料为准，请先读取最新资料。
          </p>
          <div className="actions">
            <button
              type="button"
              disabled={busy || loading}
              onClick={() => {
                if (
                  !dirty ||
                  window.confirm("重新读取会替换未保存修改，是否继续？")
                )
                  setRevision((value) => value + 1);
              }}
            >
              重新读取资料
            </button>
            <button type="button" disabled={busy || loading} onClick={onClose}>
              关闭编辑
            </button>
          </div>
          {loading && <p>正在读取资料…</p>}
          {error && (
            <p role="alert" className="notice">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="success-notice">
              {message}
            </p>
          )}
          {!loading && item && (
            <>
              <p>
                项目：{item.project === "fashion" ? "服装" : "饰品"}；物品编号：
                {item.item_uid}；款式编号：{item.sku_code || "—"}；状态：
                {STATUSES[item.status]}
              </p>
              {!editable ? (
                <p>本次只编辑未归档的服装物品。</p>
              ) : (
                <>
                  <div className="profile-layout">
                    <form
                      aria-label="服装资料表单"
                      onSubmit={(event) => void save(event)}
                    >
                      <fieldset disabled={busy}>
                        {(
                          [
                            ["name", "名称（必填，最多128字符）"],
                            ["description", "介绍（最多4000字符）"],
                            ["material", "材质（最多256字符）"],
                            ["care_instructions", "洗护说明（最多2000字符）"],
                            ["images", "图片地址（每行一个，最多20张）"],
                          ] as const
                        ).map(([key, label]) => (
                          <label key={key}>
                            {label}
                            {key === "name" || key === "material" ? (
                              <input
                                aria-label={label}
                                required={key === "name"}
                                value={form[key]}
                                onChange={(event) =>
                                  setForm({
                                    ...form,
                                    [key]: event.target.value,
                                  })
                                }
                              />
                            ) : (
                              <textarea
                                aria-label={label}
                                rows={key === "images" ? 5 : 3}
                                value={form[key]}
                                onChange={(event) =>
                                  setForm({
                                    ...form,
                                    [key]: event.target.value,
                                  })
                                }
                              />
                            )}
                          </label>
                        ))}
                        <p>
                          可选内容清空后保存会移除原值。图片建议使用可公开访问的HTTPS地址；本次不上传图片。
                        </p>
                        <button type="submit">
                          {busy ? "正在处理…" : "保存资料"}
                        </button>
                      </fieldset>
                    </form>
                    <div className="image-previews preview-grid">
                      {form.images
                        .split(/\r?\n/)
                        .map((url) => url.trim())
                        .filter(Boolean)
                        .slice(0, 20)
                        .map((url, index) => (
                          <Preview key={`${index}:${url}`} url={url} />
                        ))}
                    </div>
                  </div>
                  <div className="actions dialog-footer">
                    {item.status !== "active" ? (
                      <button
                        type="button"
                        disabled={
                          busy || !String(item.profile?.name || "").trim()
                        }
                        onClick={() => void statusChange("active")}
                      >
                        启用物品
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void statusChange("disabled")}
                      >
                        停用物品
                      </button>
                    )}
                  </div>
                  {!item.profile && <p>请先保存名称，再启用物品。</p>}
                  <p>
                    启用只改变物品状态，芯片绑定、写卡和防伪验证仍须分别完成。
                  </p>
                </>
              )}
            </>
          )}
        </section>
      </DialogContent>
    </Dialog>
  );
}
