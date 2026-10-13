"use strict";
const $ = (s) => document.querySelector(s),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (x) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[x],
    );
const date = (x) =>
  x ? new Date(x).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" }) : "—";
const msg = (t) => {
  $("#message").textContent = t;
};
async function api(path, method = "GET", body) {
  const r = await fetch("/api/admin" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json();
  if (!r.ok) {
    if (r.status === 401 && path !== "/login") location.href = "/admin/login";
    throw Error(data.error?.message || "请求失败");
  }
  return data;
}
function onForm(id, fn) {
  const form = $("#" + id);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (form.dataset.busy) return;
    form.dataset.busy = "1";
    const b = form.querySelector("button[type=submit],button:not([type])");
    if (b) b.disabled = true;
    msg("正在保存…");
    try {
      await fn(new FormData(form));
    } catch (e) {
      msg(e.message);
    } finally {
      delete form.dataset.busy;
      if (b) b.disabled = false;
    }
  });
}
function input(
  name,
  label,
  value = "",
  max = 100,
  type = "text",
  required = false,
) {
  return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" maxlength="${max}" ${required ? "required" : ""}></label>`;
}
function select(name, label, value, items) {
  return `<label for="field-${name}">${label}</label><select id="field-${name}" name="${name}">${items.map(([v, l]) => `<option value="${esc(v)}" ${String(value) === String(v) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
}
const statuses = [
  ["DRAFT", "草稿"],
  ["PUBLISHED", "已发布"],
  ["ARCHIVED", "已下架"],
];
function pager(total, page, size, path) {
  return `<div class="pagination">${page > 1 ? `<a href="${path}page=${page - 1}">上一页</a>` : ""}<span>第 ${page} 页 · 共 ${total} 条</span>${page * size < total ? `<a href="${path}page=${page + 1}">下一页</a>` : ""}</div>`;
}
if ($("#login")) {
  onForm("login", async (f) => {
    await api("/login", "POST", Object.fromEntries(f));
    location.href = "/admin/garments";
  });
} else if ($("#content")) {
  if (sessionStorage.getItem("notice")) {
    msg(sessionStorage.getItem("notice"));
    sessionStorage.removeItem("notice");
  }
  $("#logout").onclick = async () => {
    try {
      await api("/logout", "POST", {});
      location.href = "/admin/login";
    } catch (e) {
      msg(e.message);
    }
  };
  load().catch((e) => msg(e.message));
}
function done(path, text = "保存成功") {
  sessionStorage.setItem("notice", text);
  location.href = path;
}
async function load() {
  const path = location.pathname,
    params = new URLSearchParams(location.search),
    page = Number(params.get("page") || 1),
    content = $("#content");
  if (path === "/admin" || path === "/admin/garments") {
    const q = params.get("q") || "",
      data = await api(
        "/garments?" + new URLSearchParams({ page: String(page), q }),
      );
    content.innerHTML = `<h1>服装档案</h1><p class="note">一件实体服装对应一个实例编号。所有者仅为后台登记。</p><a class="button" href="/admin/garments/new">新增服装</a><form action="/admin/garments" method="get">${input("q", "搜索名称或实例编号", q)}<button>搜索</button></form><div class="grid">${data.items.map((g) => `<div class="card"><h2><a href="/admin/garments/${g.id}">${esc(g.name)}</a></h2><p>${esc(g.item_code)} · ${statuses.find((s) => s[0] === g.status)?.[1]}</p><p>所有者：${esc(g.owner_phone || "未登记")}</p><p>标签：${esc(g.bound_uid || "未绑定")} ${g.bound_uid ? (g.tag_enabled ? "启用" : "停用") : ""}</p><small>更新于 ${date(g.updated_at)}</small></div>`).join("")}</div>${pager(data.total, page, data.pageSize, "/admin/garments?q=" + encodeURIComponent(q) + "&")}`;
    return;
  }
  if (path.startsWith("/admin/garments/")) {
    const id = path.split("/")[3],
      isNew = id === "new",
      g = isNew ? { status: "DRAFT" } : await api("/garments/" + id);
    content.innerHTML = `<h1>${isNew ? "新增服装" : "编辑服装"}</h1><form id="garment">${input("name", "名称（必填）", g.name, 100, "text", true)}${input("item_code", "唯一实例编号（自动转大写）", g.item_code, 64, "text", true)}${["brand", "style_code", "color", "size", "material"].map((k, i) => input(k, ["品牌", "款式编号", "颜色", "尺码", "材质"][i], g[k])).join("")}${input("image_url", "可信 HTTPS 图片 URL", g.image_url, 2048, "url")}${["description", "care_instructions"].map((k, i) => `<label>${i ? "养护说明" : "简介"}<textarea name="${k}" maxlength="${i ? 1000 : 2000}">${esc(g[k])}</textarea></label>`).join("")}${select("status", "公开状态", g.status, statuses)}<button type="submit">保存服装</button></form>${isNew ? "" : `<section class="card"><h2>独立修改所有者</h2><p>当前完整手机号：<strong>${esc(g.owner_phone || "未登记")}</strong></p><p class="note">登记不证明身份或所有权；触碰标签不会修改所有者。</p><form id="owner">${input("phone", "新手机号（留空表示未登记）", g.owner_phone, 11, "tel")}${input("reason", "变更原因（必填）", "", 200, "text", true)}<button type="submit">确认修改所有者</button></form></section><a href="/g/${g.id}" target="_blank" rel="noopener">查看公开页</a> · <a href="/admin/audit-logs?entityType=garment&entityId=${g.id}">查看变更记录</a>`}`;
    onForm("garment", async (f) => {
      const body = Object.fromEntries(f);
      if (!isNew) body.version = g.version;
      const result = await api(
        "/garments" + (isNew ? "" : "/" + id),
        isNew ? "POST" : "PATCH",
        body,
      );
      done("/admin/garments/" + result.id);
    });
    if (!isNew)
      onForm("owner", async (f) => {
        const phone = String(f.get("phone")).trim() || null,
          reason = String(f.get("reason"));
        if (phone && !/^1\d{10}$/.test(phone))
          throw Error("手机号应为以1开头的11位数字");
        if (
          !confirm(
            `将所有者从 ${g.owner_phone || "未登记"} 修改为 ${phone || "未登记"}？\n原因：${reason}`,
          )
        ) {
          msg("已取消");
          return;
        }
        await api(`/garments/${id}/owner`, "PATCH", {
          phone,
          reason,
          version: g.version,
        });
        done(path, "所有者已保存，变更已留痕");
      });
    return;
  }
  if (path === "/admin/tags") {
    const data = await api("/tags?page=" + page);
    content.innerHTML = `<h1>NFC 标签</h1><a class="button" href="/admin/tags/new">登记标签</a><p class="note">软件生成网址，不执行写卡。模拟 UID 需标注测试；真实 UID 必须由硬件回读。</p><div class="grid">${data.items.map((t) => `<div class="card"><h2><a href="/admin/tags/${t.id}">${esc(t.uid)}</a></h2><p>${t.enabled ? "启用" : "停用"} · ${t.write_verified_at ? "已人工核对" : "未核对写入"}</p><p>关联服装：${esc(t.garment_name || "未绑定")}</p><p>${t.garment_status && t.garment_status !== "PUBLISHED" ? "尚未公开，触碰不会显示详情" : ""}</p><small>${date(t.updated_at)}</small></div>`).join("")}</div>${pager(data.total, page, data.pageSize, "/admin/tags?")}`;
    return;
  }
  if (path.startsWith("/admin/tags/")) {
    const id = path.split("/")[3],
      isNew = id === "new",
      t = isNew ? { enabled: true } : await api("/tags/" + id);
    content.innerHTML = `<h1>${isNew ? "登记标签" : "标签详情"}</h1><p class="note">真实 UID：7 字节，14 位十六进制。UID 和入口码创建后不可更改。</p><form id="tag">${
      isNew
        ? input("uid", "UID（必填）", "", 40, "text", true)
        : `<h2>${esc(t.uid)}</h2>${select("enabled", "状态", !!t.enabled, [
            ["true", "启用"],
            ["false", "停用"],
          ])}`
    }<label>备注<textarea name="notes" maxlength="500">${esc(t.notes)}</textarea></label><button type="submit">${isNew ? "创建标签" : "保存状态与备注"}</button></form>${isNew ? "" : `<section class="card"><h2>固定入口</h2><input id="entry" readonly value="${esc(t.entryUrl)}"><div class="actions"><button id="copy" type="button">复制网址</button><a href="${esc(t.entryUrl)}" target="_blank" rel="noopener">打开模拟入口</a></div><p>${t.write_verified_at ? "已人工核对：" + date(t.write_verified_at) : "未人工核对写入"}</p><p class="note" id="ndef"></p><button id="verified" type="button">已回读 URL 并实际打开，标记人工核对</button></section><section class="card"><h2>绑定 / 解绑</h2><p>当前服装：${esc(t.garment_name || "未绑定")}<br>${t.garment_status && t.garment_status !== "PUBLISHED" ? "尚未公开，触碰不会显示详情" : ""}</p><p class="note">先搜索并选定目标。已绑定其他标签时会拒绝；更换标签须先解绑。</p><form id="find-garment">${input("q", "按服装名称 / 实例编号搜索")}<button type="submit">查找</button></form><form id="binding"><label>目标服装<select name="garmentId" id="targets"><option value="">解绑</option>${t.garment_id ? `<option value="${t.garment_id}" selected>${esc(t.garment_name)}（当前）</option>` : ""}</select></label>${input("reason", "绑定变更原因（必填）", "", 200, "text", true)}<button type="submit">确认绑定变更</button></form></section><a href="/admin/audit-logs?entityType=tag&entityId=${t.id}">查看标签审计记录</a>`}`;
    onForm("tag", async (f) => {
      const body = Object.fromEntries(f);
      if (!isNew) {
        body.enabled = body.enabled === "true";
        body.version = t.version;
      }
      const result = await api(
        "/tags" + (isNew ? "" : "/" + id),
        isNew ? "POST" : "PATCH",
        body,
      );
      done(
        "/admin/tags/" + result.id,
        isNew ? "标签已创建；请先绑定服装，再实际写卡" : "保存成功",
      );
    });
    if (!isNew) {
      $("#copy").onclick = async () => {
        try {
          await navigator.clipboard.writeText(t.entryUrl);
          msg("网址已复制");
        } catch {
          msg("自动复制不可用，请选中上方网址手动复制");
        }
      };
      // Single short URI record: header/type/payload-length/type + URI prefix + UTF-8 remainder.
      const uri = t.entryUrl.startsWith("https://")
        ? t.entryUrl.slice(8)
        : t.entryUrl;
      const bytes = new TextEncoder().encode(uri).length + 5;
      $("#ndef").textContent =
        `单条 URI NDEF 消息估算 ${bytes} 字节（不含文件2字节长度）；${bytes + 2 <= 256 ? "在256字节文件容量内，仍需用工具回读核对。" : "超过容量，请勿截断入口码或写卡。"}`;
      $("#verified").onclick = async () => {
        if (
          !confirm(
            "确认已在实体标签回读完整 URL，并实际打开正确页面？\n仅点击此按钮不会写入芯片。",
          )
        )
          return;
        $("#verified").disabled = true;
        try {
          await api(`/tags/${id}/write-verification`, "POST", {
            version: t.version,
          });
          done(path, "人工核对已记录");
        } catch (e) {
          msg(e.message);
          $("#verified").disabled = false;
        }
      };
      onForm("find-garment", async (f) => {
        const data = await api(
          "/garments?q=" + encodeURIComponent(f.get("q")) + "&pageSize=100",
        );
        $("#targets").innerHTML =
          '<option value="">解绑</option>' +
          data.items
            .map(
              (g) =>
                `<option value="${g.id}" ${t.garment_id === g.id ? "selected" : ""}>${esc(g.name)} · ${esc(g.item_code)} · ${statuses.find((s) => s[0] === g.status)?.[1]}${g.bound_uid ? "（已有标签）" : ""}</option>`,
            )
            .join("");
        msg(`找到 ${data.total} 条；最多显示100条，请缩小搜索范围。`);
      });
      onForm("binding", async (f) => {
        const target = $("#targets").selectedOptions[0];
        if (
          !confirm(
            `标签 ${t.uid}\n从 ${t.garment_name || "未绑定"} 改为 ${target.textContent}？`,
          )
        ) {
          msg("已取消");
          return;
        }
        await api(`/tags/${id}/binding`, "PUT", {
          garmentId: f.get("garmentId") || null,
          reason: f.get("reason"),
          version: t.version,
        });
        done(path, "绑定已保存");
      });
    }
    return;
  }
  if (path === "/admin/audit-logs") {
    const query = new URLSearchParams(params);
    query.set("page", String(page));
    const data = await api("/audit-logs?" + query);
    query.delete("page");
    const prefix =
      "/admin/audit-logs?" + query.toString() + (query.size ? "&" : "");
    content.innerHTML = `<h1>审计记录</h1><p class="note">时间：北京时间。列表手机号脱敏；完整详情仅管理员可访问。</p>${data.items.map((a) => `<div class="card"><strong>${esc(a.action)} · ${esc(a.entity_type)}</strong><p>${date(a.created_at)} · ${esc(a.reason || "")}</p><pre>${esc(JSON.stringify({ before: a.before_json, after: a.after_json }, null, 2))}</pre><button type="button" data-audit="${a.id}">查看完整详情</button><pre id="audit-${a.id}" hidden></pre></div>`).join("")}${pager(data.total, page, data.pageSize, prefix)}`;
    document.querySelectorAll("[data-audit]").forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            const d = await api("/audit-logs/" + b.dataset.audit);
            const p = $("#audit-" + d.id);
            p.textContent = JSON.stringify(d, null, 2);
            p.hidden = false;
          } catch (e) {
            msg(e.message);
          }
        }),
    );
    return;
  }
}
