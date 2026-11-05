// 合成数据与业务校验只供隔离原型；不得作为真实认证、密钥或所有权服务。
export type Category = "fashion" | "jewelry";
export type Mode = "fixed" | "timed" | "unlimited";
export interface Style {
  id: string;
  code: string;
  category: Category;
  name: string;
  description: string;
  material: string;
  care: string;
  specs: string[];
  pictures: string[];
}
export interface Issue {
  id: string;
  styleId: string;
  name: string;
  series: string;
  mode: Mode;
  total: number | null;
  description: string;
  rights: string[];
  status: "draft" | "confirmed";
  startsAt?: string;
  endsAt?: string;
  basis?: string;
  confirmedAt?: string;
  sealedAt?: string;
  sealEvidence?: string;
  everReferenced?: boolean;
}
export interface Entity {
  id: string;
  chipId: number;
  spec: string;
  from: string;
  to?: string;
  reason?: string;
}
export interface Item {
  id: number;
  uid: string;
  issueId: string | null;
  styleId: string;
  number: number | null;
  status: "draft" | "active" | "disabled" | "archived";
  createdAt: string;
  updatedAt: string;
  sold: boolean;
  firstSoldAt?: string;
  ownerId: string | null;
  firstOwnerAt?: string;
  owners: { ownerId: string; from: string; to?: string }[];
  entities: Entity[];
  used: number;
  quotaReview?: boolean;
}
export interface Chip {
  id: number;
  uid: string;
  batch: string;
  source: "manual" | "nfc_cool" | "unknown";
  state: "pending" | "bound" | "disabled" | "lost" | "retired";
  itemId: number | null;
  keys: boolean;
  configuredAt?: string;
  createdAt: string;
  counter: number;
  candidateFor?: string;
}
export interface Handover {
  id: string;
  itemId: number;
  kind: "periodic" | "loss" | "resale";
  ownerId: string;
  recipientId: string;
  chipId: number;
  spec: string;
  evidence: string;
  createdAt: string;
  completedAt?: string;
  deliveryEvidence?: string;
  legacy?: boolean;
}
export interface Touch {
  id: string;
  itemId: number;
  chipId: number;
  counter: number;
  at: string;
  kind: "touch" | "validation";
  valid: boolean;
  reason?: string;
}
export interface Audit {
  id: string;
  at: string;
  action: string;
  target: string;
  detail: string;
}
export interface Data {
  version: 6;
  revision: number;
  styles: Style[];
  issues: Issue[];
  items: Item[];
  chips: Chip[];
  handovers: Handover[];
  touches: Touch[];
  audits: Audit[];
  importNote?: string;
}
export const users = [
  { value: "DEMO-A", label: "持有人甲 · 演示账户" },
  { value: "DEMO-B", label: "持有人乙 · 演示账户" },
  { value: "DEMO-C", label: "持有人丙 · 演示账户" },
];
export const stamp = () => new Date().toISOString();
export const atDays = (days: number) =>
  new Date(Date.now() + days * 86400000).toISOString();
export const timeText = (value?: string) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        hour12: false,
      })
    : "未记录";
export const userName = (id: string | null) =>
  users.find((u) => u.value === id)?.label || id || "未认领";
export const edition = (item: Item, issue?: Issue) =>
  !issue
    ? "未关联发行"
    : issue.mode === "timed" && !issue.sealedAt
      ? "正式编号待封版"
      : item.number
        ? `#${String(item.number).padStart(3, "0")}${issue.total == null ? "" : "/" + issue.total}`
        : "未分配";
export const issueText = (i: Issue) =>
  i.mode === "timed" && !i.sealedAt
    ? "限时定量 · 总量待核定"
    : i.total == null
      ? "非限定 · 总量不限"
      : `限定${i.total}个身份`;
export const categoryNames = { fashion: "服装", jewelry: "饰品" };
export const modeNames = {
  fixed: "固定总量",
  timed: "限时按销量定量",
  unlimited: "非限定",
};
export const itemStates = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
};
export const chipStates = {
  pending: "待绑定",
  bound: "已绑定",
  disabled: "临时停用",
  lost: "已挂失",
  retired: "已退役",
};
export const kindNames = {
  periodic: "定期换新",
  loss: "挂失换新",
  resale: "后台转售",
};
export const illustration =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect width="640" height="480" fill="#f5f7fa"/><path d="M230 90 190 110 110 210 180 260 210 220 210 400 430 400 430 220 460 260 530 210 450 110 410 90Q320 160 230 90" fill="#283244"/><text x="320" y="280" text-anchor="middle" fill="white" font-family="sans-serif" font-size="28">BUMBUM</text></svg>',
  );
export function seed(): Data {
  const styles: Style[] = [
    {
      id: "TEE",
      code: "BB-TEE-BLK",
      category: "fashion",
      name: "BUMBUM 经典T恤",
      description: "独立数字身份，实体换新后收藏档案延续。",
      material: "100%棉",
      care: "冷水轻柔洗涤",
      specs: ["S · 黑色", "M · 黑色", "L · 黑色"],
      pictures: [illustration],
    },
    {
      id: "BRACELET",
      code: "BB-ZT-01",
      category: "jewelry",
      name: "紫檀手串",
      description: "限量50个数字身份，换新不增加发行量。",
      material: "紫檀木",
      care: "避免长时间浸水",
      specs: ["手围16cm · 原木色", "手围18cm · 原木色"],
      pictures: [],
    },
    {
      id: "CAP",
      code: "BB-CAP-01",
      category: "fashion",
      name: "BUMBUM 棒球帽",
      description: "限时销售后核定发行总量。",
      material: "棉",
      care: "手洗阴干",
      specs: ["帽围56–60cm · 蓝色"],
      pictures: [],
    },
  ];
  const issues: Issue[] = [
    {
      id: "ISS-TEE",
      styleId: "TEE",
      name: "经典T恤 · 首次发行",
      series: "经典系列",
      mode: "fixed",
      total: 100,
      description: "固定100个身份；换新可选尺码，颜色仅黑色；旧实体无需回收。",
      rights: ["renewal", "resale"],
      status: "confirmed",
      confirmedAt: atDays(-30),
      everReferenced: true,
    },
    {
      id: "ISS-BR",
      styleId: "BRACELET",
      name: "紫檀手串 · 限定50",
      series: "木作系列",
      mode: "fixed",
      total: 50,
      description: "限量50个数字身份，实体换新不增发；颜色按原发行承诺。",
      rights: ["renewal"],
      status: "confirmed",
      confirmedAt: atDays(-20),
      everReferenced: true,
    },
    {
      id: "ISS-CAP",
      styleId: "CAP",
      name: "棒球帽 · 限时发行",
      series: "日常系列",
      mode: "timed",
      total: null,
      description: "销售期内按约定有效销量核定总量，正式编号待封版。",
      rights: [],
      status: "confirmed",
      startsAt: atDays(-31),
      endsAt: atDays(-1),
      basis:
        "约定窗口内有效付款，截止核定时已取消/全额退款的排除，待核事项先处理。",
      confirmedAt: atDays(-32),
    },
  ];
  const chips: Chip[] = Array.from({ length: 11 }, (_, n) => ({
    id: n + 1,
    uid: "04:BB:00:00:00:00:" + String(n + 1).padStart(2, "0"),
    batch: n < 5 ? "DEMO-001" : "DEMO-002",
    source: n % 2 ? "manual" : "nfc_cool",
    state: n < 2 ? "retired" : n < 5 ? "bound" : "pending",
    itemId: n < 3 ? 1 : n === 3 ? 2 : n === 4 ? 3 : null,
    keys: n < 5,
    configuredAt: n < 5 ? atDays(-10) : undefined,
    createdAt: atDays(-20 + n),
    counter: n === 0 ? 15 : n === 1 ? 6 : n === 2 ? 4 : n === 3 ? 2 : 0,
  }));
  const base = {
    status: "active" as const,
    createdAt: atDays(-20),
    updatedAt: atDays(-1),
    used: 0,
  };
  const items: Item[] = [
    {
      ...base,
      id: 1,
      uid: "FASH-2026-000001",
      issueId: "ISS-TEE",
      styleId: "TEE",
      number: 1,
      sold: true,
      firstSoldAt: atDays(-7),
      ownerId: "DEMO-B",
      firstOwnerAt: atDays(-7),
      owners: [
        { ownerId: "DEMO-A", from: atDays(-7), to: atDays(-2) },
        { ownerId: "DEMO-B", from: atDays(-2) },
      ],
      entities: [
        {
          id: "ENTITY-1-A",
          chipId: 1,
          spec: "S · 黑色",
          from: atDays(-20),
          to: atDays(-4),
          reason: "定期换新",
        },
        {
          id: "ENTITY-1-B",
          chipId: 2,
          spec: "M · 黑色",
          from: atDays(-4),
          to: atDays(-2),
          reason: "后台转售",
        },
        { id: "ENTITY-1-C", chipId: 3, spec: "L · 黑色", from: atDays(-2) },
      ],
    },
    {
      ...base,
      id: 2,
      uid: "FASH-2026-000002",
      issueId: "ISS-TEE",
      styleId: "TEE",
      number: 2,
      sold: true,
      firstSoldAt: atDays(-3),
      ownerId: null,
      owners: [],
      entities: [
        { id: "ENTITY-2", chipId: 4, spec: "M · 黑色", from: atDays(-4) },
      ],
    },
    {
      ...base,
      id: 3,
      uid: "JEW-2026-000001",
      issueId: "ISS-BR",
      styleId: "BRACELET",
      number: 1,
      sold: false,
      ownerId: "DEMO-C",
      firstOwnerAt: atDays(-2),
      owners: [{ ownerId: "DEMO-C", from: atDays(-2) }],
      entities: [
        {
          id: "ENTITY-3",
          chipId: 5,
          spec: "手围16cm · 原木色",
          from: atDays(-3),
        },
      ],
    },
    {
      ...base,
      id: 4,
      uid: "FASH-2026-000003",
      issueId: "ISS-TEE",
      styleId: "TEE",
      number: 3,
      status: "draft",
      sold: false,
      ownerId: null,
      owners: [],
      entities: [],
    },
  ];
  const touches: Touch[] = [];
  for (const [chipId, count, day, start] of [
    [1, 5, -9, 1],
    [1, 10, -6, 6],
    [2, 6, -3, 1],
    [3, 4, -1, 1],
    [4, 2, -1, 1],
  ])
    for (let n = 0; n < count; n++)
      touches.push({
        id: `SEED-${chipId}-${start + n}`,
        itemId: chipId === 4 ? 2 : 1,
        chipId,
        counter: start + n,
        at: new Date(Date.now() + day * 86400000 + n * 1000).toISOString(),
        kind: "touch",
        valid: true,
      });
  return {
    version: 6,
    revision: 0,
    styles,
    issues,
    items,
    chips,
    handovers: [],
    touches,
    audits: [],
  };
}
export function migrateV5(old: any): Data {
  const styles: Style[] = (old.styles || []).map((s: any) => ({
    id: s.id,
    code: s.code,
    category: s.project,
    name: s.profile?.name || s.code,
    description: s.profile?.description || "",
    material: s.profile?.material || "",
    care: s.profile?.care_instructions || s.profile?.meaning || "",
    specs: s.sizes || [],
    pictures: s.profile?.image_urls || [],
  }));
  const issues: Issue[] = (old.issuances || []).map((i: any) => ({
    ...i,
    startsAt: (old.salesPlans || []).find((p: any) => p.issuanceId === i.id)
      ?.startAt,
    endsAt: (old.salesPlans || []).find((p: any) => p.issuanceId === i.id)
      ?.endAt,
    basis: (old.salesPlans || []).find((p: any) => p.issuanceId === i.id)
      ?.basis,
    sealEvidence: (old.salesPlans || []).find((p: any) => p.issuanceId === i.id)
      ?.sealEvidence,
    mode: i.mode || (i.total == null ? "unlimited" : "fixed"),
    series: i.series || "",
    rights: (i.rightIds || [])
      .map(
        (id: string) =>
          (old.rightsRules || []).find((r: any) => r.id === id)?.kind,
      )
      .filter(Boolean),
    status: i.status === "issued" ? "confirmed" : "draft",
  }));
  const items: Item[] = (old.items || []).map((i: any) => {
    const m = old.identities?.[i.id] || {};
    return {
      id: i.id,
      uid: i.item_uid,
      styleId: i.styleId,
      issueId: m.issuanceId || null,
      number: m.editionNumber || null,
      status: i.status,
      createdAt: i.created_at,
      updatedAt: i.updated_at,
      sold: false,
      ownerId: m.ownerId || null,
      firstOwnerAt: m.firstOwnerAt,
      owners: m.ownership || [],
      used: m.used || 0,
      quotaReview: m.quotaReview,
      entities: (m.entities || [])
        .filter((e: any) => e.chipId)
        .map((e: any) => ({
          id: e.id,
          chipId: e.chipId,
          spec: [e.size, e.color].filter(Boolean).join(" · "),
          from: e.activatedAt || i.created_at,
          to: e.exitedAt,
          reason: e.reason,
        })),
    };
  });
  const chips: Chip[] = (old.chips || []).map((c: any) => ({
    id: c.id,
    uid: c.chip_uid,
    batch: c.batch_no || "",
    source: c.registration_source || "unknown",
    state: c.chip_status,
    itemId: c.item_id,
    keys: c.keys_generated,
    configuredAt: c.provisioned_at || undefined,
    createdAt: c.created_at,
    counter: c.last_counter || 0,
  }));
  return {
    version: 6,
    revision: 0,
    styles,
    issues,
    items,
    chips,
    handovers: (old.works || []).map((w: any) => ({
      id: w.id,
      itemId: w.itemId,
      kind: w.kind,
      ownerId: w.ownerId,
      recipientId: w.recipientId,
      chipId: w.candidateChipId || 0,
      spec: [w.size, w.color].filter(Boolean).join(" · "),
      evidence: w.evidence || "",
      createdAt: w.createdAt,
      completedAt:
        w.status === "completed" ? w.history?.at(-1)?.time : undefined,
      legacy: true,
    })),
    touches: [],
    audits: [],
    importNote:
      "已复制导入旧版核心档案，原v5会话未改动。售出事实不从持有人猜测，待你确认；旧版未持久化触碰事件，不补造次数。旧长流程记录仍保留在原会话，旧办理仅供历史核对。",
  };
}
export function validateNumber(
  d: Data,
  issue: Issue,
  number: number | null,
  exceptId?: number,
) {
  if (issue.status !== "confirmed") throw Error("请选择已确认的发行约定。");
  if (issue.mode === "timed" && !issue.sealedAt) {
    if (number !== null)
      throw Error("限时封版前只准备稳定身份，正式编号待封版。");
    return;
  }
  if (number == null || !Number.isSafeInteger(number) || number < 1)
    throw Error("本件序号须为正整数。");
  if (issue.total != null && number > issue.total)
    throw Error("本件序号超出发行总量。");
  if (
    d.items.some(
      (i) => i.id !== exceptId && i.issueId === issue.id && i.number === number,
    )
  )
    throw Error("该发行内本件序号已占用。");
}
export interface Command {
  type: string;
  payload: any;
}
export function operate(source: Data, command: Command): Data {
  const d = structuredClone(source),
    v = command.payload || {},
    when = stamp();
  let auditDetail = "";
  const item = () => {
    const i = d.items.find((x) => x.id === v.itemId);
    if (!i) throw Error("物品不存在。");
    return i;
  };
  const chip = () => {
    const c = d.chips.find((x) => x.id === v.chipId);
    if (!c) throw Error("芯片不存在。");
    return c;
  };
  const issue = () => {
    const i = d.issues.find((x) => x.id === v.issueId);
    if (!i) throw Error("发行约定不存在。");
    return i;
  };
  const required = (x: unknown, label: string) => {
    if (typeof x !== "string" || !x.trim())
      throw Error("请填写" + label + "。");
  };
  const currentChip = (i: Item) =>
    d.chips.find(
      (c) =>
        c.itemId === i.id &&
        c.state !== "retired" &&
        i.entities.some((e) => !e.to && e.chipId === c.id),
    );
  switch (command.type) {
    case "style": {
      required(v.name, "款式名称");
      required(v.code, "款式编号");
      if (!["fashion", "jewelry"].includes(v.category))
        throw Error("请选择物品类别。");
      const old = d.styles.find((s) => s.id === v.id);
      if (
        d.styles.some(
          (s) =>
            s.id !== v.id &&
            s.code === v.code.trim() &&
            s.category === v.category,
        )
      )
        throw Error("同类别款式编号已存在。");
      if (
        old &&
        old.category !== v.category &&
        (d.items.some((i) => i.styleId === old.id) ||
          d.issues.some((i) => i.styleId === old.id))
      )
        throw Error("已有引用的款式不能普通改类别。");
      const record: Style = {
        ...v,
        id: v.id || crypto.randomUUID(),
        code: v.code.trim(),
        name: v.name.trim(),
        specs: v.specs || [],
        pictures: v.pictures || [],
      };
      old
        ? d.styles.splice(d.styles.indexOf(old), 1, record)
        : d.styles.push(record);
      break;
    }
    case "issue": {
      const old = d.issues.find((i) => i.id === v.id);
      if (old?.status === "confirmed") throw Error("已确认发行承诺只读。");
      required(v.name, "发行名称");
      required(v.description, "发行说明");
      if (
        !d.styles.some((s) => s.id === v.styleId) ||
        !["fixed", "timed", "unlimited"].includes(v.mode)
      )
        throw Error("请选择款式和发行方式。");
      if (v.mode === "fixed" && (!Number.isSafeInteger(v.total) || v.total < 1))
        throw Error("固定总量须为正整数。");
      if (v.mode === "timed") {
        required(v.startsAt, "销售开始时间");
        required(v.endsAt, "销售结束时间");
        required(v.basis, "有效数量核定规则");
        if (
          !Number.isFinite(Date.parse(v.startsAt)) ||
          !Number.isFinite(Date.parse(v.endsAt)) ||
          Date.parse(v.endsAt) <= Date.parse(v.startsAt)
        )
          throw Error("销售结束时间须晚于开始时间。");
      }
      const record: Issue = {
        ...v,
        id: v.id || crypto.randomUUID(),
        series: v.series || "",
        rights: v.rights || [],
        total: v.mode === "fixed" ? v.total : null,
        status: "draft",
      };
      old
        ? d.issues.splice(d.issues.indexOf(old), 1, record)
        : d.issues.push(record);
      break;
    }
    case "confirmIssue": {
      const i = issue();
      if (i.status !== "draft") throw Error("请选择草案。");
      i.status = "confirmed";
      i.confirmedAt = when;
      break;
    }
    case "deleteIssue": {
      const i = issue();
      if (i.everReferenced || d.items.some((x) => x.issueId === i.id))
        throw Error("当前或历史曾被引用的约定禁止硬删。");
      auditDetail = JSON.stringify(i);
      d.issues = d.issues.filter((x) => x.id !== i.id);
      break;
    }
    case "seal": {
      const i = issue();
      if (i.mode !== "timed" || i.status !== "confirmed" || i.sealedAt)
        throw Error("此发行不允许再次封版。");
      if (!Number.isFinite(Date.parse(i.endsAt || "")))
        throw Error("原销售时窗缺失，请先按原始依据核对，不自动猜测封版时间。");
      if (Date.parse(i.endsAt || "") > Date.now())
        throw Error("尚未到销售期满，不能提前确认最终结果。");
      if (!Number.isSafeInteger(v.total) || v.total < 1)
        throw Error("核定数量须为正整数；零销售请保留待核，不虚造发行。");
      required(v.evidence, "数量核定依据");
      const own = d.items
        .filter((x) => x.issueId === i.id)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id - b.id);
      if (own.length > v.total)
        throw Error("已建身份超过核定数量，请核对，不能自动删身份凑数。");
      i.total = v.total;
      i.sealedAt = when;
      i.sealEvidence = v.evidence;
      own.forEach((x, n) => {
        x.number = n + 1;
      });
      break;
    }
    case "item": {
      const s = issue();
      required(v.uid, "系统物品编号");
      const category = d.styles.find((x) => x.id === s.styleId)?.category;
      const prefix = category === "fashion" ? "FASH" : "JEW";
      if (!new RegExp("^" + prefix + "-\\d{4}-\\d{6}$").test(v.uid))
        throw Error("编号格式应为" + prefix + "-年份-六位数字。");
      if (d.items.some((i) => i.uid === v.uid))
        throw Error("系统物品编号已存在。");
      validateNumber(d, s, v.number ?? null);
      d.items.push({
        id: Math.max(0, ...d.items.map((i) => i.id)) + 1,
        uid: v.uid,
        issueId: s.id,
        styleId: s.styleId,
        number: v.number ?? null,
        status: "draft",
        createdAt: when,
        updatedAt: when,
        sold: false,
        ownerId: null,
        owners: [],
        entities: [],
        used: 0,
      });
      s.everReferenced = true;
      break;
    }
    case "assignIssue": {
      const i = item(),
        s = issue();
      if (i.status === "archived" || i.issueId)
        throw Error("已有发行或已归档身份不可重分配。");
      if (i.styleId !== s.styleId) throw Error("只能补齐原款式的发行。");
      required(v.evidence, "原发行核对依据");
      validateNumber(d, s, v.number ?? null, i.id);
      i.issueId = s.id;
      i.number = v.number ?? null;
      s.everReferenced = true;
      break;
    }
    case "register": {
      const uid = String(v.uid || "")
        .replace(/[^0-9a-f]/gi, "")
        .toUpperCase();
      if (uid.length !== 14) throw Error("芯片UID须为7字节十六进制。");
      const normalized = uid.match(/../g)!.join(":");
      if (d.chips.some((c) => c.uid === normalized))
        throw Error("芯片已登记，不新增或覆盖原批次。");
      if (String(v.batch || "").length > 64)
        throw Error("批次不能超过64字符。");
      d.chips.unshift({
        id: Math.max(0, ...d.chips.map((c) => c.id)) + 1,
        uid: normalized,
        batch: v.batch || "",
        source: v.source === "nfc_cool" ? "nfc_cool" : "manual",
        state: "pending",
        itemId: null,
        keys: false,
        createdAt: when,
        counter: 0,
      });
      break;
    }
    case "batch": {
      const c = chip();
      if (String(v.batch || "").length > 64)
        throw Error("批次不能超过64字符。");
      c.batch = v.batch || "";
      break;
    }
    case "bind": {
      const i = item(),
        c = chip();
      if (i.status === "archived" || !i.issueId)
        throw Error("请先完善物品发行身份。");
      if (c.itemId != null || c.state !== "pending" || c.candidateFor)
        throw Error("芯片已关联、停用或被接续任务占用。");
      if (
        i.entities.some((e) => !e.to) ||
        d.chips.some((x) => x.itemId === i.id && x.state !== "retired")
      )
        throw Error("物品已有当前关联，请从换新/转售接续，不能覆盖绑定。");
      required(v.spec, "实际实体规格");
      c.itemId = i.id;
      c.state = "bound";
      i.entities.push({
        id: crypto.randomUUID(),
        chipId: c.id,
        spec: v.spec,
        from: when,
      });
      i.updatedAt = when;
      break;
    }
    case "keys": {
      const c = chip();
      if (c.state === "retired" || (!c.itemId && !c.candidateFor))
        throw Error("请先关联物品或保存候选准备。");
      c.keys = true;
      break;
    }
    case "configure": {
      const c = chip();
      if (!c.keys || c.state === "retired")
        throw Error("请先准备密钥标记并核对候选。");
      if (!v.checked || !v.checked2)
        throw Error("请核对密钥/模板及两条递增链接的演示证据。");
      c.configuredAt = when;
      break;
    }
    case "toggleItem": {
      const i = item(),
        c = currentChip(i);
      if (i.status === "archived") throw Error("归档物品只读。");
      if (
        i.status !== "active" &&
        (!i.issueId || !c?.configuredAt || c.state !== "bound")
      )
        throw Error("启用前需要发行、有效芯片及配置核验。");
      i.status = i.status === "active" ? "disabled" : "active";
      i.updatedAt = when;
      break;
    }
    case "sale": {
      required(v.evidence, "销售确认/更正依据");
      const ids: number[] = v.ids || [v.itemId];
      if (!ids.length) throw Error("请选择物品。");
      const date = v.at ? new Date(v.at).toISOString() : when;
      if (Date.parse(date) > Date.now())
        throw Error("首次售出时间不能晚于当前时间。");
      for (const id of ids) {
        const i = d.items.find((x) => x.id === id);
        if (!i || i.status === "archived") throw Error("包含不可维护的物品。");
        i.sold = v.confirmed;
        i.firstSoldAt = i.firstSoldAt || (v.confirmed ? date : undefined);
        i.updatedAt = when;
      }
      break;
    }
    case "demoClaim": {
      const i = item();
      if (i.ownerId || i.status !== "active")
        throw Error("仅能模拟已启用且未认领的物品。");
      if (!users.some((u) => u.value === v.ownerId))
        throw Error("请选择演示账户。");
      i.ownerId = v.ownerId;
      i.firstOwnerAt = when;
      i.owners.push({ ownerId: v.ownerId, from: when });
      break;
    }
    case "chipState": {
      const c = chip();
      required(v.evidence, "状态操作依据");
      if (c.state === "retired" || c.candidateFor)
        throw Error("退役或候选芯片不能普通恢复/改状态。");
      if (v.action === "restore") {
        if (c.state !== "disabled")
          throw Error("仅临时停用芯片可普通恢复；挂失解除须另审。");
        if (
          c.itemId &&
          !d.items.some(
            (i) =>
              i.id === c.itemId &&
              i.entities.some((e) => !e.to && e.chipId === c.id),
          )
        )
          throw Error("当前授权已变化，禁止恢复。");
        c.state = c.itemId ? "bound" : "pending";
      } else if (v.action === "lost") {
        if (!c.itemId || !["bound", "disabled"].includes(c.state))
          throw Error("只能挂失当前关联芯片。");
        c.state = "lost";
      } else {
        if (!["pending", "bound"].includes(c.state))
          throw Error("当前状态不能临时停用。");
        c.state = "disabled";
      }
      break;
    }
    case "prepare": {
      const i = item(),
        c = chip();
      if (!i.ownerId || i.status === "archived" || !i.issueId)
        throw Error("请先确认物品、持有人和发行。");
      const old = currentChip(i);
      if (!old)
        throw Error("当前实体/芯片关系缺失，须先核对，不能直接换新或转售。");
      const iss = d.issues.find((s) => s.id === i.issueId)!;
      if (!iss.rights.includes(v.kind === "resale" ? "resale" : "renewal"))
        throw Error("本次发行未约定该权益。");
      if (
        d.handovers.some(
          (w) => w.itemId === i.id && !w.completedAt && !w.legacy,
        )
      )
        throw Error("本物品已有未完成接续，请继续原记录。");
      if (v.kind !== "resale" && (i.used >= 1 || i.quotaReview))
        throw Error("年度余额不足或上次计次待核，不能重复申请换新。");
      if (
        (v.kind === "loss" && old?.state !== "lost") ||
        (v.kind === "periodic" && old?.state === "lost")
      )
        throw Error("请按当前挂失状态选择换新类型。");
      if (c.itemId != null || c.state !== "pending" || c.candidateFor)
        throw Error("候选芯片已占用或不可用。");
      required(v.spec, "新实体实际规格");
      required(v.evidence, "资格/接收对象核对依据");
      const receiver = v.kind === "resale" ? v.recipientId : i.ownerId;
      if (
        !receiver ||
        (receiver === i.ownerId && v.kind === "resale") ||
        (v.kind === "resale" && !users.some((u) => u.value === receiver))
      )
        throw Error("请选择与原持有人不同的已核对接收账户。");
      const w: Handover = {
        id: crypto.randomUUID(),
        itemId: i.id,
        kind: v.kind,
        ownerId: i.ownerId,
        recipientId: receiver,
        chipId: c.id,
        spec: v.spec,
        evidence: v.evidence,
        createdAt: when,
      };
      d.handovers.push(w);
      c.candidateFor = w.id;
      break;
    }
    case "complete": {
      const w = d.handovers.find((x) => x.id === v.workId);
      if (!w || w.completedAt || w.legacy)
        throw Error("记录不存在、只读或已完成。");
      const i = d.items.find((x) => x.id === w.itemId)!,
        c = d.chips.find((x) => x.id === w.chipId)!;
      if (
        i.status === "archived" ||
        i.ownerId !== w.ownerId ||
        c.itemId != null ||
        c.state !== "pending" ||
        c.candidateFor !== w.id ||
        !c.keys ||
        !c.configuredAt
      )
        throw Error("持有人、候选占用或配置条件变化，请重新核对。");
      required(v.evidence, "实际交付核验依据");
      if (!v.checked) throw Error("请确认实际交付、接收对象与新旧实体对应。");
      for (const e of i.entities)
        if (!e.to) {
          e.to = when;
          e.reason = kindNames[w.kind];
          const old = d.chips.find((x) => x.id === e.chipId);
          if (old) old.state = "retired";
        }
      c.itemId = i.id;
      c.state = "bound";
      delete c.candidateFor;
      i.entities.push({
        id: crypto.randomUUID(),
        chipId: c.id,
        spec: w.spec,
        from: when,
      });
      if (w.kind === "resale") {
        i.owners.forEach((o) => {
          if (!o.to) o.to = when;
        });
        i.ownerId = w.recipientId;
        i.owners.push({ ownerId: w.recipientId, from: when });
      } else i.quotaReview = true;
      i.updatedAt = when;
      w.completedAt = when;
      w.deliveryEvidence = v.evidence;
      break;
    }
    case "touch": {
      const c = chip(),
        i = d.items.find((x) => x.id === c.itemId);
      const counter = v.counter ?? c.counter + 1;
      if (
        !i ||
        i.status !== "active" ||
        c.state !== "bound" ||
        !c.keys ||
        !c.configuredAt ||
        !i.entities.some((e) => !e.to && e.chipId === c.id)
      )
        throw Error(
          "当前芯片/物品不可提供有效触碰；退役、停用或候选卡不会增加次数。",
        );
      if (
        !Number.isSafeInteger(counter) ||
        counter <= c.counter ||
        d.touches.some(
          (t) => t.chipId === c.id && t.counter === counter && t.valid,
        )
      )
        throw Error("同一芯片的已用读数或重复刷新不重复计次。");
      c.counter = counter;
      d.touches.push({
        id: crypto.randomUUID(),
        itemId: i.id,
        chipId: c.id,
        counter,
        at: when,
        kind: "touch",
        valid: true,
      });
      break;
    }
    default:
      throw Error("不支持的操作。");
  }
  d.revision++;
  d.audits.unshift({
    id: crypto.randomUUID(),
    at: when,
    action: command.type,
    target: String(
      v.itemId ||
        v.chipId ||
        v.issueId ||
        v.uid ||
        v.id ||
        (v.ids ? v.ids.join(", ") : "") ||
        v.workId ||
        v.name ||
        "",
    ),
    detail:
      auditDetail ||
      (command.type === "keys"
        ? "仅演示密钥准备标记，不生成真实密钥"
        : command.type === "configure"
          ? "仅演示配置证据，不验证实卡"
          : v.evidence || "合成数据操作，未请求真实业务API"),
  });
  return d;
}
export interface StatsFilter {
  scope: "sold" | "all";
  range: "7d" | "30d" | "all";
  styleId?: string;
  issueId?: string;
  itemId?: number;
  chipId?: number;
}
export function statistics(d: Data, filter: StatsFilter) {
  const today = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
  }).format(new Date());
  const from =
    filter.range === "all"
      ? null
      : Date.parse(today + "T00:00:00+08:00") -
        (filter.range === "7d" ? 6 : 29) * 86400000;
  const items = d.items.filter(
    (i) =>
      (!filter.styleId || i.styleId === filter.styleId) &&
      (!filter.issueId || i.issueId === filter.issueId) &&
      (!filter.itemId || i.id === filter.itemId),
  );
  const eligible = items.filter((i) => filter.scope === "all" || i.sold);
  const seen = new Set<string>();
  const events = d.touches.filter((e) => {
    const i = eligible.find((x) => x.id === e.itemId),
      key = e.chipId + ":" + e.counter;
    if (
      !e.valid ||
      e.kind !== "touch" ||
      !i ||
      seen.has(key) ||
      (filter.chipId && e.chipId !== filter.chipId)
    )
      return false;
    seen.add(key);
    return (
      Date.parse(e.at) <= Date.now() &&
      (!from || Date.parse(e.at) >= from) &&
      (filter.scope === "all" || (!!i.firstSoldAt && e.at >= i.firstSoldAt))
    );
  });
  const days = new Map<string, number>();
  const dateKey = (s: string) =>
    new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(
      new Date(s),
    );
  if (from)
    for (
      let day = from;
      day <= Date.parse(today + "T00:00:00+08:00");
      day += 86400000
    )
      days.set(dateKey(new Date(day).toISOString()), 0);
  for (const e of events)
    days.set(dateKey(e.at), (days.get(dateKey(e.at)) || 0) + 1);
  const daily = [...days.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }));
  return {
    items,
    events,
    daily,
    total: events.length,
    touched: new Set(events.map((e) => e.itemId)).size,
    sold: items.filter((i) => i.sold).length,
    claimed: items.filter((i) => i.ownerId).length,
    owners: new Set(items.flatMap((i) => (i.ownerId ? [i.ownerId] : []))).size,
    rows: eligible.map((i) => ({
      item: i,
      count: events.filter((e) => e.itemId === i.id).length,
      last: events.filter((e) => e.itemId === i.id).at(-1)?.at,
    })),
  };
}
