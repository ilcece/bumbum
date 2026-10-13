import { safeErrorDetails } from "./diagnostics.js";
import express, { Request, Response, NextFunction } from "express";
import { z } from "zod";
import { randomUUID, randomBytes, createHash } from "node:crypto";
import { db, rows, tx, Conn } from "./db.js";
import { hashPassword, verifyPassword, tokenHash } from "./security.js";
export const app = express();
const prod = process.env.NODE_ENV === "production";
const base = new URL(process.env.PUBLIC_BASE_URL || "http://localhost:3000");
if (prod && base.protocol !== "https:")
  throw Error("Production PUBLIC_BASE_URL requires https");
if (
  base.pathname !== "/" ||
  base.search ||
  base.hash ||
  base.username ||
  base.password
)
  throw Error("PUBLIC_BASE_URL must be an origin");
if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 64)
  throw Error("SESSION_SECRET needs at least 64 characters");
app.disable("x-powered-by");
app.set("trust proxy", prod ? 1 : false);
app.use((req, res, next) => {
  res.locals.requestId = randomUUID();
  res.set({
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy":
      "default-src 'self'; img-src https: 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
  });
  next();
});
app.use(express.json({ limit: "32kb" }));
const fail = (status: number, code: string, message: string) =>
  Object.assign(new Error(message), { status, code });
const uuid = z.string().uuid(),
  version = z.number().int().positive();
const fields = {
  item_code: z
    .string()
    .trim()
    .min(1)
    .max(64)
    .transform((x) => x.toUpperCase()),
  name: z.string().trim().min(1).max(100),
  brand: z.string().max(100).nullable().optional(),
  style_code: z.string().max(100).nullable().optional(),
  color: z.string().max(100).nullable().optional(),
  size: z.string().max(100).nullable().optional(),
  material: z.string().max(100).nullable().optional(),
  description: z.string().max(2000).nullable().optional(),
  care_instructions: z.string().max(1000).nullable().optional(),
  image_url: z
    .union([
      z.literal(""),
      z
        .string()
        .url()
        .max(2048)
        .refine(
          (x) =>
            new URL(x).protocol === "https:" &&
            !new URL(x).username &&
            !new URL(x).password,
        ),
    ])
    .nullable()
    .optional(),
  status: z.enum(["DRAFT", "PUBLISHED", "ARCHIVED"]).optional(),
};
const garmentCreate = z.object(fields).strict();
const garmentPatch = z.object(fields).partial().extend({ version }).strict();
const bindingSchema = z
  .object({
    garmentId: uuid.nullable(),
    reason: z.string().trim().min(1).max(200),
    version,
  })
  .strict();
const normalizeUid = (x: string) => x.replace(/[\s:-]/g, "").toUpperCase();
const tagCreate = z
  .object({
    uid: z
      .string()
      .transform(normalizeUid)
      .pipe(z.string().regex(/^[0-9A-F]{14}$/)),
    notes: z.string().max(500).optional(),
    garmentId: uuid.nullable().optional(),
  })
  .strict();
function pagination(req: Request) {
  return z
    .object({
      page: z.coerce.number().int().min(1).default(1),
      pageSize: z.coerce.number().int().min(1).max(100).default(20),
    })
    .parse(req.query);
}
const esc = (s: any) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (x) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        x
      ]!,
  );
function html(title: string, content: string) {
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)} · bumbum</title><link rel="stylesheet" href="/style.css"></head><body><header><a href="/">bumbum</a><span>服装档案</span></header><main>${content}</main></body></html>`;
}
const publicFields = (g: any) => ({
  id: g.id,
  item_code: g.item_code,
  name: g.name,
  brand: g.brand,
  style_code: g.style_code,
  color: g.color,
  size: g.size,
  material: g.material,
  description: g.description,
  care_instructions: g.care_instructions,
  image_url: g.image_url,
  ownerRegistered: !!g.owner_phone,
});
const mask = (p: string | null) =>
  p ? `${p.slice(0, 3)}****${p.slice(-4)}` : null;
async function audit(
  c: Conn,
  res: Response,
  action: string,
  type: string,
  id: string,
  before: any,
  after: any,
  reason: string | null = null,
) {
  await c.execute(
    "INSERT INTO audit_logs(id,admin_id,action,entity_type,entity_id,before_json,after_json,reason,request_id) VALUES(?,?,?,?,?,?,?,?,?)",
    [
      randomUUID(),
      res.locals.admin.id,
      action,
      type,
      id,
      JSON.stringify(before),
      JSON.stringify(after),
      reason,
      res.locals.requestId,
    ],
  );
}
async function locked(
  c: Conn,
  table: "garments" | "tags",
  id: string,
  v: number,
) {
  uuid.parse(id);
  const r = await rows(`SELECT * FROM ${table} WHERE id=? FOR UPDATE`, [id], c);
  if (!r[0]) throw fail(404, "NOT_FOUND", "记录不存在");
  if (r[0].version !== v)
    throw fail(409, "VERSION_CONFLICT", "信息已被更新，请刷新后重试");
  return r[0];
}
function sessionToken(req: Request) {
  return (
    req.headers.cookie
      ?.split(";")
      .map((x) => x.trim())
      .find((x) => x.startsWith("session="))
      ?.slice(8) || ""
  );
}
async function auth(req: Request, res: Response, next: NextFunction) {
  try {
    const t = sessionToken(req);
    const s =
      t.length === 64
        ? await rows(
            "SELECT s.id,s.admin_id,a.username FROM admin_sessions s JOIN admins a ON a.id=s.admin_id WHERE token_hash=? AND expires_at>UTC_TIMESTAMP(3)",
            [tokenHash(t)],
          )
        : [];
    if (!s[0]) {
      if (req.originalUrl.startsWith("/api/"))
        throw fail(401, "UNAUTHORIZED", "请先登录");
      res.redirect("/admin/login");
      return;
    }
    const [result]: any = await db.execute(
      "UPDATE admin_sessions SET last_seen_at=UTC_TIMESTAMP(3),expires_at=DATE_ADD(UTC_TIMESTAMP(3),INTERVAL 30 MINUTE) WHERE id=? AND expires_at>UTC_TIMESTAMP(3)",
      [s[0].id],
    );
    if (!result.affectedRows) throw fail(401, "UNAUTHORIZED", "会话已过期");
    res.locals.admin = { id: s[0].admin_id, username: s[0].username };
    res.locals.session = s[0].id;
    next();
  } catch (e) {
    next(e);
  }
}
app.use((req, res, next) => {
  if (
    req.path.startsWith("/api/admin/") &&
    !["GET", "HEAD", "OPTIONS"].includes(req.method) &&
    req.get("origin") !== base.origin
  ) {
    next(fail(403, "BAD_ORIGIN", "请求来源不受信任"));
    return;
  }
  next();
});
const dummy = hashPassword(randomBytes(32).toString("hex"));
app.post("/api/admin/login", async (req, res) => {
  const { username, password } = z
    .object({
      username: z.string().trim().min(1).max(100),
      password: z.string().min(1).max(128),
    })
    .strict()
    .parse(req.body);
  const key = createHash("sha256")
    .update(`${req.ip}\0${username}`)
    .digest("hex");
  const result = await tx(async (c) => {
    await c.execute(
      "INSERT IGNORE INTO login_attempts VALUES (?,0,UTC_TIMESTAMP(3))",
      [key],
    );
    const [a] = await rows(
      "SELECT * FROM login_attempts WHERE attempt_key=? FOR UPDATE",
      [key],
      c,
    );
    let count = a.failures;
    if (new Date(a.window_start).getTime() < Date.now() - 900000) {
      count = 0;
      await c.execute(
        "UPDATE login_attempts SET failures=0,window_start=UTC_TIMESTAMP(3) WHERE attempt_key=?",
        [key],
      );
    }
    if (count >= 5) return { limited: true };
    const [admin] = await rows(
      "SELECT * FROM admins WHERE username=?",
      [username],
      c,
    );
    const valid = verifyPassword(password, admin?.password_hash || dummy);
    if (!admin || !valid) {
      await c.execute(
        "UPDATE login_attempts SET failures=failures+1 WHERE attempt_key=?",
        [key],
      );
      return { invalid: true };
    }
    await c.execute("DELETE FROM login_attempts WHERE attempt_key=?", [key]);
    const token = randomBytes(32).toString("hex");
    await c.execute(
      "INSERT INTO admin_sessions VALUES (?,?,?,DATE_ADD(UTC_TIMESTAMP(3),INTERVAL 30 MINUTE),UTC_TIMESTAMP(3))",
      [randomUUID(), admin.id, tokenHash(token)],
    );
    return { token };
  });
  if (result.limited) {
    res.set("Retry-After", "900");
    throw fail(429, "RATE_LIMITED", "登录失败过多，请15分钟后重试");
  }
  if (result.invalid) throw fail(401, "BAD_LOGIN", "账号或密码错误");
  res.cookie("session", result.token, {
    httpOnly: true,
    secure: prod,
    sameSite: "strict",
    path: "/",
  });
  res.json({ ok: true });
});
app.use("/api/admin", auth);
app.get("/api/admin/me", (req, res) => res.json(res.locals.admin));
app.post("/api/admin/logout", async (req, res) => {
  await db.execute("DELETE FROM admin_sessions WHERE id=?", [
    res.locals.session,
  ]);
  res.clearCookie("session", {
    path: "/",
    httpOnly: true,
    secure: prod,
    sameSite: "strict",
  });
  res.json({ ok: true });
});
app.get("/api/admin/garments", async (req, res) => {
  const { page, pageSize } = pagination(req);
  const q = z
    .string()
    .max(100)
    .parse(req.query.q || "");
  const pattern = `%${q.replace(/[!%_]/g, "!$&")}%`;
  const args = [pattern, `%${q.toUpperCase().replace(/[!%_]/g, "!$&")}%`];
  const where =
    "WHERE g.name LIKE ? ESCAPE '!' OR g.item_code LIKE ? ESCAPE '!'";
  const [{ total }] = await rows(
    `SELECT COUNT(*) total FROM garments g ${where}`,
    args,
  );
  const list = await rows(
    `SELECT g.*,t.uid bound_uid,t.enabled tag_enabled FROM garments g LEFT JOIN tags t ON t.garment_id=g.id ${where} ORDER BY g.updated_at DESC,g.id LIMIT ${pageSize} OFFSET ${(page - 1) * pageSize}`,
    args,
  );
  res.json({
    items: list.map((g) => ({ ...g, owner_phone: mask(g.owner_phone) })),
    total,
    page,
    pageSize,
  });
});
app.post("/api/admin/garments", async (req, res) => {
  const data = garmentCreate.parse(req.body),
    id = randomUUID();
  await tx(async (c) => {
    const keys = Object.keys(data);
    await c.execute(
      `INSERT INTO garments(id,${keys.join(",")}) VALUES (?,${keys.map(() => "?").join(",")})`,
      [id, ...Object.values(data)],
    );
    await audit(c, res, "CREATE", "garment", id, null, data);
  });
  res
    .status(201)
    .json((await rows("SELECT * FROM garments WHERE id=?", [id]))[0]);
});
app.get("/api/admin/garments/:id", async (req, res) => {
  const [g] = await rows("SELECT * FROM garments WHERE id=?", [
    uuid.parse(req.params.id),
  ]);
  if (!g) throw fail(404, "NOT_FOUND", "记录不存在");
  res.json(g);
});
app.patch("/api/admin/garments/:id", async (req, res) => {
  const { version: v, ...data } = garmentPatch.parse(req.body);
  const id = uuid.parse(req.params.id);
  if (!Object.keys(data).length)
    throw fail(400, "EMPTY_UPDATE", "请输入修改内容");
  await tx(async (c) => {
    const before = await locked(c, "garments", id, v);
    const keys = Object.keys(data);
    await c.execute(
      `UPDATE garments SET ${keys.map((k) => `${k}=?`).join(",")},version=version+1 WHERE id=?`,
      [...Object.values(data), id],
    );
    await audit(
      c,
      res,
      "UPDATE",
      "garment",
      id,
      Object.fromEntries(keys.map((k) => [k, before[k]])),
      data,
    );
  });
  res.json((await rows("SELECT * FROM garments WHERE id=?", [id]))[0]);
});
app.patch("/api/admin/garments/:id/owner", async (req, res) => {
  const {
    phone,
    reason,
    version: v,
  } = z
    .object({
      phone: z
        .string()
        .regex(/^1\d{10}$/)
        .nullable(),
      reason: z.string().trim().min(1).max(200),
      version,
    })
    .strict()
    .parse(req.body);
  const id = uuid.parse(req.params.id);
  await tx(async (c) => {
    const before = await locked(c, "garments", id, v);
    if (before.owner_phone === phone) return;
    await c.execute(
      "UPDATE garments SET owner_phone=?,version=version+1 WHERE id=?",
      [phone, id],
    );
    await audit(
      c,
      res,
      "OWNER_CHANGE",
      "garment",
      id,
      { phone: before.owner_phone },
      { phone },
      reason,
    );
  });
  res.json((await rows("SELECT * FROM garments WHERE id=?", [id]))[0]);
});
function tagView(t: any) {
  return { ...t, entryUrl: `${base.origin}/t/${t.entry_code}` };
}
app.get("/api/admin/tags", async (req, res) => {
  const { page, pageSize } = pagination(req);
  const [{ total }] = await rows("SELECT COUNT(*) total FROM tags");
  const items = await rows(
    `SELECT t.*,g.name garment_name,g.status garment_status FROM tags t LEFT JOIN garments g ON g.id=t.garment_id ORDER BY t.updated_at DESC,t.id LIMIT ${pageSize} OFFSET ${(page - 1) * pageSize}`,
  );
  res.json({ items: items.map(tagView), total, page, pageSize });
});
app.post("/api/admin/tags", async (req, res) => {
  const data = tagCreate.parse(req.body),
    id = randomUUID(),
    entry = randomBytes(16).toString("hex");
  await tx(async (c) => {
    if (data.garmentId) {
      const target = await rows(
        "SELECT id FROM garments WHERE id=? FOR UPDATE",
        [data.garmentId],
        c,
      );
      if (!target.length) throw fail(404, "NOT_FOUND", "服装不存在");
    }
    await c.execute(
      "INSERT INTO tags(id,uid,entry_code,notes,garment_id) VALUES (?,?,?,?,?)",
      [id, data.uid, entry, data.notes || null, data.garmentId || null],
    );
    await audit(c, res, "CREATE", "tag", id, null, {
      uid: data.uid,
      garmentId: data.garmentId || null,
    });
  });
  res
    .status(201)
    .json(tagView((await rows("SELECT * FROM tags WHERE id=?", [id]))[0]));
});
app.get("/api/admin/tags/:id", async (req, res) => {
  const [t] = await rows(
    "SELECT t.*,g.name garment_name,g.status garment_status FROM tags t LEFT JOIN garments g ON g.id=t.garment_id WHERE t.id=?",
    [uuid.parse(req.params.id)],
  );
  if (!t) throw fail(404, "NOT_FOUND", "记录不存在");
  res.json(tagView(t));
});
app.patch("/api/admin/tags/:id", async (req, res) => {
  const { version: v, ...data } = z
      .object({
        enabled: z.boolean().optional(),
        notes: z.string().max(500).nullable().optional(),
        version,
      })
      .strict()
      .parse(req.body),
    id = uuid.parse(req.params.id);
  if (!Object.keys(data).length)
    throw fail(400, "EMPTY_UPDATE", "请输入修改内容");
  await tx(async (c) => {
    const before = await locked(c, "tags", id, v);
    const keys = Object.keys(data);
    await c.execute(
      `UPDATE tags SET ${keys.map((k) => `${k}=?`).join(",")},version=version+1 WHERE id=?`,
      [...Object.values(data), id],
    );
    await audit(
      c,
      res,
      "UPDATE",
      "tag",
      id,
      Object.fromEntries(keys.map((k) => [k, before[k]])),
      data,
    );
  });
  res.json(tagView((await rows("SELECT * FROM tags WHERE id=?", [id]))[0]));
});
app.put("/api/admin/tags/:id/binding", async (req, res) => {
  const { garmentId, reason, version: v } = bindingSchema.parse(req.body),
    id = uuid.parse(req.params.id);
  await tx(async (c) => {
    const before = await locked(c, "tags", id, v);
    if (garmentId) {
      const target = await rows(
        "SELECT id FROM garments WHERE id=? FOR UPDATE",
        [garmentId],
        c,
      );
      if (!target.length) throw fail(404, "NOT_FOUND", "服装不存在");
    }
    if (before.garment_id === garmentId) return;
    await c.execute(
      "UPDATE tags SET garment_id=?,version=version+1 WHERE id=?",
      [garmentId, id],
    );
    await audit(
      c,
      res,
      "BINDING_CHANGE",
      "tag",
      id,
      { garmentId: before.garment_id },
      { garmentId },
      reason,
    );
  });
  res.json(tagView((await rows("SELECT * FROM tags WHERE id=?", [id]))[0]));
});
app.post("/api/admin/tags/:id/write-verification", async (req, res) => {
  const { version: v } = z.object({ version }).strict().parse(req.body),
    id = uuid.parse(req.params.id);
  await tx(async (c) => {
    const before = await locked(c, "tags", id, v);
    await c.execute(
      "UPDATE tags SET write_verified_at=UTC_TIMESTAMP(3),version=version+1 WHERE id=?",
      [id],
    );
    await audit(
      c,
      res,
      "WRITE_VERIFIED",
      "tag",
      id,
      { write_verified_at: before.write_verified_at },
      { manual: true },
    );
  });
  res.json(tagView((await rows("SELECT * FROM tags WHERE id=?", [id]))[0]));
});
app.get("/api/admin/audit-logs", async (req, res) => {
  const { page, pageSize } = pagination(req);
  const filter = z
    .object({
      entityType: z.enum(["garment", "tag"]).optional(),
      entityId: uuid.optional(),
    })
    .parse(req.query);
  const predicates: string[] = [],
    args: string[] = [];
  if (filter.entityType) {
    predicates.push("entity_type=?");
    args.push(filter.entityType);
  }
  if (filter.entityId) {
    predicates.push("entity_id=?");
    args.push(filter.entityId);
  }
  const where = predicates.length ? " WHERE " + predicates.join(" AND ") : "";
  const [{ total }] = await rows(
    "SELECT COUNT(*) total FROM audit_logs" + where,
    args,
  );
  const list = await rows(
    `SELECT * FROM audit_logs${where} ORDER BY created_at DESC,id LIMIT ${pageSize} OFFSET ${(page - 1) * pageSize}`,
    args,
  );
  res.json({
    items: list.map((a) => ({
      ...a,
      before_json: redact(a.before_json),
      after_json: redact(a.after_json),
    })),
    total,
    page,
    pageSize,
  });
});
function redact(data: any): any {
  if (typeof data === "string") data = JSON.parse(data);
  if (!data || typeof data !== "object") return data;
  return Object.fromEntries(
    Object.entries(data).map(([k, v]) => [
      k,
      k === "phone" ? mask(v as string) : v,
    ]),
  );
}
app.get("/api/admin/audit-logs/:id", async (req, res) => {
  const [a] = await rows("SELECT * FROM audit_logs WHERE id=?", [
    uuid.parse(req.params.id),
  ]);
  if (!a) throw fail(404, "NOT_FOUND", "记录不存在");
  res.json(a);
});
async function publicGarment(id: string) {
  if (!uuid.safeParse(id).success)
    throw fail(404, "NOT_FOUND", "未找到服装信息");
  const [g] = await rows(
    "SELECT * FROM garments WHERE id=? AND status='PUBLISHED'",
    [id],
  );
  if (!g) throw fail(404, "NOT_FOUND", "此服装信息暂不可用");
  return publicFields(g);
}
app.get("/api/public/garments/:id", async (req, res) =>
  res.json(await publicGarment(String(req.params.id))),
);
app.get("/t/:entryCode", async (req, res) => {
  const code = String(req.params.entryCode);
  if (!/^[a-f0-9]{32}$/.test(code))
    throw fail(404, "NOT_FOUND", "未找到服装信息");
  const [t] = await rows(
    "SELECT t.enabled,t.garment_id,g.status FROM tags t LEFT JOIN garments g ON g.id=t.garment_id WHERE t.entry_code=?",
    [code],
  );
  if (!t) throw fail(404, "NOT_FOUND", "未找到服装信息");
  if (!t.enabled) throw fail(410, "TAG_DISABLED", "此服装标签已停用");
  if (!t.garment_id) throw fail(409, "TAG_UNBOUND", "此标签尚未关联服装");
  if (t.status !== "PUBLISHED")
    throw fail(404, "NOT_FOUND", "此服装信息暂不可用");
  res.redirect(302, `/g/${t.garment_id}`);
});
app.get("/g/:id", async (req, res) => {
  const g = await publicGarment(String(req.params.id));
  const labels: Record<string, string> = {
    brand: "品牌",
    style_code: "款式编号",
    color: "颜色",
    size: "尺码",
    material: "材质",
    description: "简介",
    care_instructions: "养护说明",
  };
  res.send(
    html(
      g.name,
      `<article class="garment"><p class="eyebrow">服装信息 · ${esc(g.item_code)}</p><h1>${esc(g.name)}</h1><div class="image">${g.image_url ? `<img src="${esc(g.image_url)}" alt="${esc(g.name)}"><div class="placeholder" hidden>暂无可用图片</div>` : '<div class="placeholder">暂无图片</div>'}</div><p class="badge">${g.ownerRegistered ? "后台已登记所有者" : "未登记所有者"}</p>${Object.entries(
        labels,
      )
        .filter(([k]) => (g as any)[k])
        .map(
          ([k, v]) =>
            `<section><h2>${v}</h2><p class="text">${esc((g as any)[k])}</p></section>`,
        )
        .join(
          "",
        )}<p class="note">本页展示后台登记的服装信息；普通网址可复制，不提供防伪认证。</p></article><script src="/public.js" defer></script>`,
    ),
  );
});
app.get("/health", async (req, res) => {
  await db
    .execute("SELECT 1 FROM schema_migrations WHERE completed=FALSE LIMIT 1")
    .then(([r]: any) => {
      if (r.length) throw fail(503, "NOT_READY", "服务暂不可用");
    });
  await db.execute("SELECT id FROM garments LIMIT 1");
  res.json({ status: "ok" });
});
app.get("/", (req, res) =>
  res.send(
    html(
      "服装信息",
      '<h1>每件服装，都有自己的档案。</h1><p>触碰服装上的 NFC 标签，按手机提示打开对应服装信息。</p><a class="button" href="/admin/garments">管理员后台</a><p class="note">本服务不提供防伪认证或用户自助认领。</p>',
    ),
  ),
);
app.get("/admin/login", (req, res) =>
  res.send(
    html(
      "管理员登录",
      '<h1>管理员登录</h1><form id="login"><label>账号<input name="username" autocomplete="username" required maxlength="100"></label><label>密码<input name="password" type="password" autocomplete="current-password" required maxlength="128"></label><button>登录</button></form><p id="message" role="status"></p><script src="/admin.js" defer></script>',
    ),
  ),
);
app.use("/admin", auth);
app.get(
  [
    "/admin",
    "/admin/garments",
    "/admin/garments/new",
    "/admin/garments/:id",
    "/admin/tags",
    "/admin/tags/new",
    "/admin/tags/:id",
    "/admin/audit-logs",
  ],
  (req, res) =>
    res.send(
      html(
        "管理后台",
        '<nav><a href="/admin/garments">服装</a><a href="/admin/tags">标签</a><a href="/admin/audit-logs">审计记录</a><button id="logout">退出</button></nav><p id="message" role="status"></p><div id="content" aria-live="polite">正在加载…</div><script src="/admin.js" defer></script>',
      ),
    ),
);
app.use(
  express.static("public", { etag: false, lastModified: false, maxAge: 0 }),
);
app.use((req, res, next) => next(fail(404, "NOT_FOUND", "未找到页面")));
app.use((e: any, req: Request, res: Response, next: NextFunction) => {
  let status = e.status || 500,
    code = e.code || "INTERNAL_ERROR",
    message = e.status ? e.message : "服务暂时无法处理请求";
  if (e instanceof z.ZodError) {
    status = 400;
    code = "VALIDATION_ERROR";
    message =
      "输入不符合要求：" +
      e.issues.map((x) => `${x.path.join(".")} ${x.message}`).join("；");
  } else if (e.code === "ER_DUP_ENTRY") {
    status = 409;
    code = "UNIQUE_CONFLICT";
    message = "UID、实例编号或服装绑定已存在，请刷新核对";
  } else if (
    e.code === "ER_LOCK_DEADLOCK" ||
    e.code === "ER_LOCK_WAIT_TIMEOUT"
  ) {
    status = 409;
    code = "VERSION_CONFLICT";
    message = "信息已被更新，请刷新后重试";
  } else if (
    [
      "ECONNREFUSED",
      "ETIMEDOUT",
      "ENOTFOUND",
      "PROTOCOL_CONNECTION_LOST",
      "ER_ACCESS_DENIED_ERROR",
      "ER_BAD_DB_ERROR",
      "ER_NO_SUCH_TABLE",
      "HANDSHAKE_SSL_ERROR",
      "ERR_TLS_CERT_ALTNAME_INVALID",
      "SELF_SIGNED_CERT_IN_CHAIN",
      "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
      "DEPTH_ZERO_SELF_SIGNED_CERT",
      "CERT_HAS_EXPIRED",
    ].includes(e.code) ||
    e.code?.startsWith("CERT_")
  ) {
    status = 503;
    code = "UNAVAILABLE";
    message = "暂时无法加载，请稍后重试";
  } else if (
    e.type === "entity.parse.failed" ||
    e.type === "entity.too.large"
  ) {
    status = 400;
    code = "INVALID_BODY";
    message = "请求内容无效或过大";
  }
  if (status >= 500)
    console.error(
      JSON.stringify({
        requestId: res.locals.requestId,
        code: status === 503 ? "DEPENDENCY_ERROR" : "INTERNAL_ERROR",
        ...safeErrorDetails(e),
      }),
    );
  res.status(status);
  if (req.path.startsWith("/api/"))
    res.json({ error: { code, message, requestId: res.locals.requestId } });
  else if (req.path === "/health") res.json({ status: "unavailable" });
  else
    res.send(
      html(
        "暂时无法显示",
        `<h1>${esc(message)}</h1><p>请刷新或联系管理员。</p><p class="note">请求编号：${esc(res.locals.requestId)}</p>`,
      ),
    );
});
