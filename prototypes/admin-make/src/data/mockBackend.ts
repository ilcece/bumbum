// 原始Make的样例类型与本地演示数据；不代表现行后端已交付这些能力。
// 已确认规则和待审边界由仓库提案说明，样例不得接入正式服务。

export type ProjectCode = 'fashion' | 'jewelry';
export type RegistrationSource = 'nfc_cool' | 'manual' | 'unknown';
export type ChipStatus = 'pending' | 'bound' | 'disabled' | 'lost' | 'retired';
export type ItemStatus = 'draft' | 'active' | 'disabled' | 'archived';
export type LifecycleLevel = 'L3_production' | 'L2_validation' | 'L1_draft_test';

export interface ChipView {
  id: number;
  chip_uid: string;
  project: ProjectCode | null;
  chip_status: ChipStatus;
  item_id: number | null;
  item_uid: string | null;
  batch_no: string | null;
  registration_source: RegistrationSource;
  provisioned_at: string | null;
  keys_generated: boolean;
  key_version: string | null;
  created_at: string;
  updated_at: string;
  is_validation_object?: boolean;
  validation_note?: string | null;
  last_counter?: number;
  replaced_by_chip_uid?: string | null;
  replaces_chip_uid?: string | null;
}

export interface FashionProfile {
  name: string;
  description: string | null;
  material: string | null;
  care_instructions: string | null;
  image_urls: string[];
  size_chart?: string | null;
}

export type ImageAssetState = 'uploading' | 'pending' | 'attached' | 'retired' | 'unknown_status';

export interface ItemImageAsset {
  asset_id: string;
  client_upload_id: string;
  state: ImageAssetState;
  url: string;
  preview_url: string;
  source_type: 'managed' | 'external_url';
  filename?: string;
  size_kb?: number;
  dimensions?: string;
  expires_at?: string | null;
}

export interface JewelryProfile {
  name: string;
  description: string | null;
  material: string | null;
  meaning: string | null;
  image_urls: string[];
}

export interface CarrierHistoryEntry {
  id: string;
  chip_uid: string;
  action:
    | 'initial_bind'
    | 'provisioned'
    | 'temp_disable'
    | 'restore'
    | 'report_lost'
    | 'replacement_activate'
    | 'resale_new_carrier'
    | 'unbind_correction';
  timestamp: string;
  operator: string;
  summary: string;
  is_current_active: boolean;
}

export interface ItemView {
  style_id?:string|null;
  id: number;
  project: ProjectCode;
  item_uid: string;
  sku_code: string | null;
  status: ItemStatus;
  created_at: string;
  updated_at: string;
  profile: FashionProfile | JewelryProfile | null;
  image_assets?: ItemImageAsset[];
  bound_chip_id: number | null;
  bound_chip_uid: string | null;
  bound_chip_status: ChipStatus | null;
  bound_chip_keys_generated: boolean;
  bound_chip_provisioned_at: string | null;
  is_validation_object?: boolean;
  owner_status?: 'unclaimed' | 'claimed' | 'transferring';
  owner_masked_phone?: string | null;
  owner_account_id?: string | null;
  carrier_generation?: number;
  carrier_history?: CarrierHistoryEntry[];
}

export interface ChipKeys {
  chip_uid: string;
  key_version: string;
  keys: {
    K0: string;
    K1: string;
    K2: string;
    K3: string;
    K4: string;
  };
  sun_url_template: string;
}

export interface TapStatsQuery {
  project: '' | ProjectCode;
  range: '7d' | '30d' | 'all';
  q: string;
  page: number;
}

export interface TapStatsItemRow {
  item_id: number;
  project: ProjectCode;
  item_uid: string;
  name: string | null;
  valid_taps: number;
  last_tap_at: string;
}

export interface TapStats {
  filters: {
    project: ProjectCode | null;
    range: '7d' | '30d' | 'all';
    q: string;
  };
  timezone: 'Asia/Shanghai';
  as_of: string;
  period: {
    from_date: string | null;
    to_date: string;
  };
  first_recorded_at: string | null;
  summary: {
    valid_taps: number;
    touched_items: number;
  };
  daily: {
    date: string;
    valid_taps: number;
  }[];
  items: TapStatsItemRow[];
  total_items: number;
  page: number;
  page_size: number;
  total_pages: number;
  page_adjusted: boolean;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  operator: string;
  category: 'chip' | 'item' | 'key_provision' | 'correction' | 'cleanup' | 'replacement' | 'auth';
  action: string;
  target: string;
  detail: string;
}

export const PROJECT_LABELS: Record<ProjectCode, string> = {
  fashion: '服装 (Fashion)',
  jewelry: '饰品 (Jewelry)',
};

export const PROJECT_SHORT_LABELS: Record<ProjectCode, string> = {
  fashion: '服装',
  jewelry: '饰品',
};

export const CHIP_STATUS_META: Record<
  ChipStatus,
  { label: string; badge: 'default' | 'processing' | 'success' | 'warning' | 'error'; tagColor: string; desc: string }
> = {
  pending: {
    label: '待绑定',
    badge: 'processing',
    tagColor: 'blue',
    desc: '已登记真实硬件 UID，尚未关联数字物品',
  },
  bound: {
    label: '已绑定',
    badge: 'success',
    tagColor: 'green',
    desc: '已关联数字物品；需核对密钥生成与实卡配置状态',
  },
  disabled: {
    label: '已停用',
    badge: 'warning',
    tagColor: 'orange',
    desc: '临时阻断该芯片验证服务，保留原有关联关系',
  },
  lost: {
    label: '已挂失',
    badge: 'error',
    tagColor: 'red',
    desc: '芯片丢失/损坏已挂失，旧凭证与持续查看资格已阻断，等待新卡接续',
  },
  retired: {
    label: '已退役',
    badge: 'default',
    tagColor: 'default',
    desc: '已完成换新或转售新载体接续，原芯片永久退出授权且不可普通恢复',
  },
};

export const ITEM_STATUS_META: Record<
  ItemStatus,
  { label: string; badge: 'default' | 'processing' | 'success' | 'warning' | 'error'; tagColor: string; desc: string }
> = {
  draft: {
    label: '草稿',
    badge: 'default',
    tagColor: 'default',
    desc: '已建立物品唯一身份编号，尚未对用户启用',
  },
  active: {
    label: '启用',
    badge: 'success',
    tagColor: 'green',
    desc: '允许通过已核验芯片向用户展示资料（仍需芯片与配置均有效）',
  },
  disabled: {
    label: '停用',
    badge: 'warning',
    tagColor: 'orange',
    desc: '暂停用户端资料展示与验证通过，保留资料及芯片关联',
  },
  archived: {
    label: '归档',
    badge: 'error',
    tagColor: 'purple',
    desc: '历史归档只读状态，不可绑定新芯片或直接编辑',
  },
};

export const REGISTRATION_SOURCE_LABELS: Record<RegistrationSource, { label: string; color: string; tip: string }> = {
  nfc_cool: {
    label: '手机扫描 (NFC.cool)',
    color: 'cyan',
    tip: '通过单台手机 NFC.cool 批量读取真实 7 字节 UID 并经 HTTPS Basic Auth 回调自动登记',
  },
  manual: {
    label: '网页手工',
    color: 'geekblue',
    tip: '由管理员在桌面管理后台手动录入 7 字节 UID 登记',
  },
  unknown: {
    label: '历史未知',
    color: 'default',
    tip: '早期建库或迁移前记录，未标记具体入口来源',
  },
};

// 校验并规范化 7 字节 NTAG424 DNA UID
export function normalizeAndValidateChipUid(raw: string): { ok: true; uid: string } | { ok: false; error: string } {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { ok: false, error: '请填写芯片 UID（7字节十六进制，如 04:A2:7F:1B:5E:80:00）。' };
  }
  const clean = trimmed.replace(/:/g, '').toUpperCase();
  if (!/^[0-9A-F]{14}$/.test(clean)) {
    if (/^[0-9A-F]{8}$/.test(clean)) {
      return {
        ok: false,
        error: '检测到 4 字节随机 UID (8位十六进制)。系统仅接受 NTAG424 DNA 真实 7 字节固定 UID（14位十六进制）。',
      };
    }
    return {
      ok: false,
      error: 'UID 格式不合法：必须为 7 字节十六进制（如 04:A2:7F:1B:5E:80:00 或连续 14 位十六进制字符）。',
    };
  }
  const formatted = clean.match(/.{1,2}/g)!.join(':');
  return { ok: true, uid: formatted };
}

// 校验物品编号 FASH-YYYY-NNNNNN 或 JEW-YYYY-NNNNNN
export function validateItemUid(
  project: ProjectCode,
  rawUid: string
): { ok: true; item_uid: string } | { ok: false; error: string } {
  const trimmed = rawUid.trim();
  const expectedPrefix = project === 'fashion' ? 'FASH' : 'JEW';
  const regex = project === 'fashion' ? /^FASH-[0-9]{4}-[0-9]{6}$/ : /^JEW-[0-9]{4}-[0-9]{6}$/;
  if (!regex.test(trimmed)) {
    return {
      ok: false,
      error: `物品编号格式须严格为 ${expectedPrefix}-YYYY-NNNNNN（半角大写前缀、4位年份、6位数字序号，如 ${expectedPrefix}-2026-000001），不接受小写或全角字符。`,
    };
  }
  return { ok: true, item_uid: trimmed };
}

// 校验实卡配置核验的触碰链接
export function validateSunTapLinks(link1: string, link2: string): {
  ok: boolean;
  error?: string;
  parsed?: { picc1: string; cmac1: string; picc2: string; cmac2: string };
} {
  const parseOne = (val: string, idx: number) => {
    let url: URL;
    try {
      url = new URL(val.trim());
    } catch {
      throw new Error(`第 ${idx} 条触碰链接不是合法的完整 URL。`);
    }
    if (url.origin !== 'https://nfc.bumbum.cc' || url.pathname !== '/tap') {
      throw new Error(`第 ${idx} 条链接域名或路径不符，必须为 https://nfc.bumbum.cc/tap`);
    }
    const keys = [...url.searchParams.keys()].sort().join(',');
    if (keys !== 'cmac,picc_data') {
      throw new Error(`第 ${idx} 条链接参数必须且只能包含 picc_data 与 cmac。`);
    }
    const picc_data = url.searchParams.get('picc_data') || '';
    const cmac = url.searchParams.get('cmac') || '';
    if (!/^[0-9A-F]{32}$/i.test(picc_data) || !/^[0-9A-F]{16}$/i.test(cmac)) {
      throw new Error(`第 ${idx} 条链接的 picc_data (需32位十六进制) 或 cmac (需16位十六进制) 长度/格式不正确。`);
    }
    return { picc_data: picc_data.toUpperCase(), cmac: cmac.toUpperCase() };
  };

  try {
    const r1 = parseOne(link1, 1);
    const r2 = parseOne(link2, 2);
    if (r1.picc_data === r2.picc_data || r1.cmac === r2.cmac) {
      return {
        ok: false,
        error: '两条触碰链接的动态读数相同！请用手机分别触碰芯片两次，确保 SDM 读取计数器递增。',
      };
    }
    return {
      ok: true,
      parsed: {
        picc1: r1.picc_data,
        cmac1: r1.cmac,
        picc2: r2.picc_data,
        cmac2: r2.cmac,
      },
    };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

// 初始芯片列表（贴合仓库真实 NFC.cool 扫码记录与多种业务状态）
export const INITIAL_CHIPS: ChipView[] = [
  {
    id: 101,
    chip_uid: '04:A2:7F:1B:5E:80:01',
    project: 'fashion',
    chip_status: 'bound',
    item_id: 1,
    item_uid: 'FASH-2026-000001',
    batch_no: 'HZ-202610-F01',
    registration_source: 'nfc_cool',
    provisioned_at: '2026-10-25T09:30:00Z',
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-24T06:15:00Z',
    updated_at: '2026-10-25T09:30:00Z',
    is_validation_object: false,
    last_counter: 18,
  },
  {
    id: 102,
    chip_uid: '04:A2:7F:1B:5E:80:02',
    project: 'fashion',
    chip_status: 'bound',
    item_id: 2,
    item_uid: 'FASH-2026-000002',
    batch_no: 'HZ-202610-F01',
    registration_source: 'nfc_cool',
    provisioned_at: '2026-10-25T11:20:00Z',
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-24T06:15:12Z',
    updated_at: '2026-10-25T11:20:00Z',
    is_validation_object: false,
    last_counter: 11,
  },
  {
    id: 103,
    chip_uid: '04:B8:3C:91:2A:80:03',
    project: 'fashion',
    chip_status: 'bound',
    item_id: 3,
    item_uid: 'FASH-2026-000003',
    batch_no: 'HZ-202610-F02',
    registration_source: 'nfc_cool',
    provisioned_at: null,
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-26T03:40:00Z',
    updated_at: '2026-10-26T08:10:00Z',
    is_validation_object: false,
    last_counter: 0,
  },
  {
    id: 104,
    chip_uid: '04:C1:5D:44:7E:80:04',
    project: null,
    chip_status: 'pending',
    item_id: null,
    item_uid: null,
    batch_no: null,
    registration_source: 'nfc_cool',
    provisioned_at: null,
    keys_generated: false,
    key_version: null,
    created_at: '2026-10-26T14:22:10Z',
    updated_at: '2026-10-26T14:22:10Z',
    is_validation_object: false,
  },
  {
    id: 105,
    chip_uid: '04:C1:5D:44:7E:80:05',
    project: null,
    chip_status: 'pending',
    item_id: null,
    item_uid: null,
    batch_no: null,
    registration_source: 'nfc_cool',
    provisioned_at: null,
    keys_generated: false,
    key_version: null,
    created_at: '2026-10-26T14:22:18Z',
    updated_at: '2026-10-26T14:22:18Z',
    is_validation_object: false,
  },
  {
    id: 106,
    chip_uid: '04:D9:12:6F:33:80:06',
    project: 'jewelry',
    chip_status: 'bound',
    item_id: 5,
    item_uid: 'JEW-2026-000001',
    batch_no: 'WTS-SAMPLE-01',
    registration_source: 'manual',
    provisioned_at: '2026-10-26T16:05:00Z',
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-25T10:00:00Z',
    updated_at: '2026-10-26T16:05:00Z',
    is_validation_object: false,
    last_counter: 6,
  },
  {
    id: 107,
    chip_uid: '04:E4:88:0A:19:80:07',
    project: 'fashion',
    chip_status: 'bound',
    item_id: 4,
    item_uid: 'FASH-2026-000004',
    batch_no: 'HZ-202610-F02',
    registration_source: 'manual',
    provisioned_at: null,
    keys_generated: false,
    key_version: null,
    created_at: '2026-10-27T01:15:00Z',
    updated_at: '2026-10-27T01:30:00Z',
    is_validation_object: false,
  },
  {
    id: 108,
    chip_uid: '04:F0:99:B2:4C:80:08',
    project: 'fashion',
    chip_status: 'bound',
    item_id: 7,
    item_uid: 'FASH-2026-990001',
    batch_no: 'PROD-VAL-1027',
    registration_source: 'nfc_cool',
    provisioned_at: '2026-10-27T02:00:00Z',
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-27T01:40:00Z',
    updated_at: '2026-10-27T02:00:00Z',
    is_validation_object: true,
    validation_note: '杭州正式入口切换后首轮线上真卡验证样卡',
    last_counter: 3,
  },
  {
    id: 109,
    chip_uid: '04:AA:11:22:33:80:09',
    project: 'jewelry',
    chip_status: 'pending',
    item_id: null,
    item_uid: null,
    batch_no: 'TEST-DRAFT-ERR',
    registration_source: 'manual',
    provisioned_at: null,
    keys_generated: false,
    key_version: null,
    created_at: '2026-10-27T02:30:00Z',
    updated_at: '2026-10-27T02:30:00Z',
    is_validation_object: true,
    validation_note: '手工录入测试登记，无实卡关联',
  },
  {
    id: 110,
    chip_uid: '04:77:66:55:44:80:10',
    project: 'fashion',
    chip_status: 'lost',
    item_id: 8,
    item_uid: 'FASH-2026-000005',
    batch_no: 'HZ-202610-F01',
    registration_source: 'nfc_cool',
    provisioned_at: '2026-10-24T12:00:00Z',
    keys_generated: true,
    key_version: 'v1',
    created_at: '2026-10-23T09:00:00Z',
    updated_at: '2026-10-27T03:10:00Z',
    is_validation_object: false,
    last_counter: 9,
  },
];

// 初始物品列表
export const INITIAL_ITEMS: ItemView[] = [
  {
    id: 1,
    project: 'fashion',
    item_uid: 'FASH-2026-000001',
    sku_code: 'BB-AW26-BLAZER-BLK-M',
    status: 'active',
    created_at: '2026-10-24T05:00:00Z',
    updated_at: '2026-10-25T10:00:00Z',
    profile: {
      name: 'BUMBUM 解构重磅羊毛西装外套 · 曜石黑',
      description:
        '2026 秋冬先锋档案系列第 001 号单品。采用双面高支澳洲美利奴羊毛混纺面料，左袖内嵌隐藏式 NTAG424 DNA 防伪芯片感应区。\n碰一碰即可查验单品独立数字身份与养护档案。',
      material: '92% 澳洲美利奴初剪羊毛，8% 桑蚕丝；内衬 100% 铜氨丝',
      care_instructions:
        '1. 仅限专业轻柔干洗，不可水洗或漂白；\n2. 低温垫布蒸汽熨烫（不超过 110°C），请避开左袖袖口 NFC 芯片织唛区域直接重压熨烫；\n3. 建议使用宽肩西装衣架悬挂于阴凉干燥处。',
      image_urls: [
        'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=900&q=80',
      ],
      size_chart: 'S: 衣长72 胸围108 肩宽46 | M: 衣长74 胸围112 肩宽48 | L: 衣长76 胸围116 肩宽50',
    },
    image_assets: [
      {
        asset_id: 'a10f9c82e41b70539d28c6140fa83e11',
        client_upload_id: 'c10f9c82e41b70539d28c6140fa83e11',
        state: 'attached',
        url: '/api/admin/items/1/images/a10f9c82e41b70539d28c6140fa83e11',
        preview_url:
          'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80',
        source_type: 'managed',
        filename: 'blazer-front-main.webp',
        size_kb: 412,
        dimensions: '1536×2048 · WebP 去元数据',
        expires_at: null,
      },
      {
        asset_id: 'b29e4d17a83c60428f19d7251eb94f22',
        client_upload_id: 'd29e4d17a83c60428f19d7251eb94f22',
        state: 'attached',
        url: 'https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=900&q=80',
        preview_url:
          'https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=900&q=80',
        source_type: 'external_url',
        filename: '外部 HTTPS 历史图',
        expires_at: null,
      },
    ],
    bound_chip_id: 101,
    bound_chip_uid: '04:A2:7F:1B:5E:80:01',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: '2026-10-25T09:30:00Z',
    is_validation_object: false,
    owner_status: 'claimed',
    owner_masked_phone: '138****8021',
    owner_account_id: 'USR-2026-0089',
    carrier_generation: 1,
    carrier_history: [
      {
        id: 'ch-1',
        chip_uid: '04:A2:7F:1B:5E:80:01',
        action: 'initial_bind',
        timestamp: '2026-10-24T08:20:00Z',
        operator: 'cece',
        summary: '首次绑定实体载体芯片 04:A2:7F:1B:5E:80:01',
        is_current_active: true,
      },
      {
        id: 'ch-2',
        chip_uid: '04:A2:7F:1B:5E:80:01',
        action: 'provisioned',
        timestamp: '2026-10-25T09:30:00Z',
        operator: 'cece',
        summary: '通过双链接动态读数与 K0 权限核验，正式激活载体认证',
        is_current_active: true,
      },
    ],
  },
  {
    id: 2,
    project: 'fashion',
    item_uid: 'FASH-2026-000002',
    sku_code: 'BB-AW26-TRENCH-GRY-L',
    status: 'active',
    created_at: '2026-10-24T05:10:00Z',
    updated_at: '2026-10-25T11:30:00Z',
    profile: {
      name: 'BUMBUM 三防机能立体剪裁长款风衣 · 岩灰',
      description:
        '全压胶防风防泼水复合面料，领口防风片内嵌 NFC 数字身份芯片。支持手机碰一碰验证真伪与持续 24 小时浏览器免重碰查看。',
      material: '100% 聚酯高密三防复合面料（疏水涂层）',
      care_instructions: '手洗最高水温 30°C，使用中性洗涤剂；不可机洗甩干，自然悬挂滴干。',
      image_urls: [
        'https://images.unsplash.com/photo-1539533018447-63fcce2678e3?auto=format&fit=crop&w=900&q=80',
      ],
    },
    bound_chip_id: 102,
    bound_chip_uid: '04:A2:7F:1B:5E:80:02',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: '2026-10-25T11:20:00Z',
    is_validation_object: false,
    owner_status: 'claimed',
    owner_masked_phone: '139****3310',
    owner_account_id: 'USR-2026-0102',
    carrier_generation: 1,
    carrier_history: [
      {
        id: 'ch-3',
        chip_uid: '04:A2:7F:1B:5E:80:02',
        action: 'initial_bind',
        timestamp: '2026-10-24T09:10:00Z',
        operator: 'cece',
        summary: '首次绑定实体载体芯片 04:A2:7F:1B:5E:80:02',
        is_current_active: true,
      },
      {
        id: 'ch-4',
        chip_uid: '04:A2:7F:1B:5E:80:02',
        action: 'provisioned',
        timestamp: '2026-10-25T11:20:00Z',
        operator: 'cece',
        summary: '完成实卡配置核验',
        is_current_active: true,
      },
    ],
  },
  {
    id: 3,
    project: 'fashion',
    item_uid: 'FASH-2026-000003',
    sku_code: 'BB-AW26-DENIM-IND-M',
    status: 'draft',
    created_at: '2026-10-26T03:00:00Z',
    updated_at: '2026-10-26T08:10:00Z',
    profile: {
      name: 'BUMBUM 14oz 原色赤耳丹宁夹克 · 深靛蓝',
      description: '冈山重磅赤耳丹宁面料，随穿着时间自然落色养成。已生成芯片密钥，等待 NFC.cool 写卡与双链接核验后启用。',
      material: '100% 新疆长绒棉（14oz 赤耳丹宁）',
      care_instructions: '建议前 6 个月尽量减少洗涤以保留自然猫须落色；洗涤时请反面冷水手洗，单独浸泡。',
      image_urls: [
        'https://images.unsplash.com/photo-1551537482-f2075a1d41f2?auto=format&fit=crop&w=900&q=80',
      ],
    },
    bound_chip_id: 103,
    bound_chip_uid: '04:B8:3C:91:2A:80:03',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: null,
    is_validation_object: false,
    owner_status: 'unclaimed',
    carrier_generation: 1,
    carrier_history: [
      {
        id: 'ch-5',
        chip_uid: '04:B8:3C:91:2A:80:03',
        action: 'initial_bind',
        timestamp: '2026-10-26T08:10:00Z',
        operator: 'cece',
        summary: '首次绑定芯片 04:B8:3C:91:2A:80:03，已生成密钥待写卡核验',
        is_current_active: true,
      },
    ],
  },
  {
    id: 4,
    project: 'fashion',
    item_uid: 'FASH-2026-000004',
    sku_code: null,
    status: 'draft',
    created_at: '2026-10-26T15:00:00Z',
    updated_at: '2026-10-26T15:00:00Z',
    profile: null,
    bound_chip_id: 107,
    bound_chip_uid: '04:E4:88:0A:19:80:07',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: false,
    bound_chip_provisioned_at: null,
    is_validation_object: false,
    owner_status: 'unclaimed',
    carrier_generation: 1,
    carrier_history: [
      {
        id: 'ch-6',
        chip_uid: '04:E4:88:0A:19:80:07',
        action: 'initial_bind',
        timestamp: '2026-10-27T01:30:00Z',
        operator: 'cece',
        summary: '绑定芯片 04:E4:88:0A:19:80:07（尚未生成密钥与配置）',
        is_current_active: true,
      },
    ],
  },
  {
    id: 5,
    project: 'jewelry',
    item_uid: 'JEW-2026-000001',
    sku_code: 'BB-JW26-OBSIDIAN-10MM',
    status: 'draft',
    created_at: '2026-10-25T09:30:00Z',
    updated_at: '2026-10-26T16:05:00Z',
    profile: {
      name: 'BUMBUM 黑曜石鎏金主珠手串 · 10mm 探索样卡',
      description: '普通手串 NFC 数字体验与权益探索样品。主珠内嵌微型 NTAG424 DNA 芯片。',
      material: '天然金曜石 / 925银镀厚金隔珠',
      meaning: '数字价值探索样品（新体验方案评审中）',
      image_urls: [
        'https://images.unsplash.com/photo-1611591437281-460bfbe1220a?auto=format&fit=crop&w=900&q=80',
      ],
    },
    bound_chip_id: 106,
    bound_chip_uid: '04:D9:12:6F:33:80:06',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: '2026-10-26T16:05:00Z',
    is_validation_object: false,
    owner_status: 'unclaimed',
    carrier_generation: 1,
  },
  {
    id: 6,
    project: 'fashion',
    item_uid: 'FASH-2026-000006',
    sku_code: 'BB-AW26-KNIT-CRM-S',
    status: 'draft',
    created_at: '2026-10-27T01:00:00Z',
    updated_at: '2026-10-27T01:00:00Z',
    profile: {
      name: 'BUMBUM 山羊绒绞花高领毛衣 · 燕麦奶白',
      description: '100% 阿拉善盟山羊绒，立体粗针绞花织法。等待绑定待分配芯片。',
      material: '100% 山羊绒',
      care_instructions: '干洗或冷水羊绒专用洗涤剂轻柔手洗，平铺晾干，切勿悬挂以防变形。',
      image_urls: [
        'https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=900&q=80',
      ],
    },
    bound_chip_id: null,
    bound_chip_uid: null,
    bound_chip_status: null,
    bound_chip_keys_generated: false,
    bound_chip_provisioned_at: null,
    is_validation_object: false,
    owner_status: 'unclaimed',
    carrier_generation: 0,
  },
  {
    id: 7,
    project: 'fashion',
    item_uid: 'FASH-2026-990001',
    sku_code: 'VAL-TEST-SAMPLE',
    status: 'disabled',
    created_at: '2026-10-27T01:35:00Z',
    updated_at: '2026-10-27T02:10:00Z',
    profile: {
      name: '[生产验证] 杭州公网切换链路验证样衣',
      description: '用于验证杭州 ECS + RDS 正式入口切换后的实卡动态验签闭环，验证完毕后按 B 提案走 L2 退出与清理。',
      material: '测试样衣',
      care_instructions: '测试验证专用，非对外销售商品',
      image_urls: [],
    },
    bound_chip_id: 108,
    bound_chip_uid: '04:F0:99:B2:4C:80:08',
    bound_chip_status: 'bound',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: '2026-10-27T02:00:00Z',
    is_validation_object: true,
    owner_status: 'unclaimed',
    carrier_generation: 1,
  },
  {
    id: 8,
    project: 'fashion',
    item_uid: 'FASH-2026-000005',
    sku_code: 'BB-AW26-COAT-CAM-M',
    status: 'active',
    created_at: '2026-10-23T08:30:00Z',
    updated_at: '2026-10-27T03:10:00Z',
    profile: {
      name: 'BUMBUM 双排扣驼绒大衣 · 经典驼色',
      description: '原配芯片因用户干洗不当损坏已申请挂失，当前等待新实体/新芯片（如 04:C1:5D:44:7E:80:04）完成准备并执行 D 方案正式接续。',
      material: '85% 驼绒，15% 桑蚕丝',
      care_instructions: '仅限专业干洗，不可水洗。',
      image_urls: [
        'https://images.unsplash.com/photo-1548624313-0396c75e4b1a?auto=format&fit=crop&w=900&q=80',
      ],
    },
    bound_chip_id: 110,
    bound_chip_uid: '04:77:66:55:44:80:10',
    bound_chip_status: 'lost',
    bound_chip_keys_generated: true,
    bound_chip_provisioned_at: '2026-10-24T12:00:00Z',
    is_validation_object: false,
    owner_status: 'claimed',
    owner_masked_phone: '186****9901',
    owner_account_id: 'USR-2026-0041',
    carrier_generation: 1,
    carrier_history: [
      {
        id: 'ch-8-1',
        chip_uid: '04:77:66:55:44:80:10',
        action: 'initial_bind',
        timestamp: '2026-10-23T09:15:00Z',
        operator: 'cece',
        summary: '首次绑定第 1 代载体芯片 04:77:66:55:44:80:10',
        is_current_active: false,
      },
      {
        id: 'ch-8-2',
        chip_uid: '04:77:66:55:44:80:10',
        action: 'report_lost',
        timestamp: '2026-10-27T03:10:00Z',
        operator: 'cece',
        summary: '持有人反馈原芯片损坏，执行挂失并冻结旧短凭证与持续查看 Cookie，等待新卡接续',
        is_current_active: false,
      },
    ],
  },
  {
    id: 9,
    project: 'jewelry',
    item_uid: 'JEW-2026-000002',
    sku_code: 'BB-JW26-AGATE-08MM',
    status: 'draft',
    created_at: '2026-10-27T02:15:00Z',
    updated_at: '2026-10-27T02:15:00Z',
    profile: null,
    bound_chip_id: null,
    bound_chip_uid: null,
    bound_chip_status: null,
    bound_chip_keys_generated: false,
    bound_chip_provisioned_at: null,
    is_validation_object: true,
    owner_status: 'unclaimed',
    carrier_generation: 0,
  },
];

export const INITIAL_AUDIT_LOGS: AuditLogEntry[] = [
  {
    id: 'aud-1008',
    timestamp: '2026-10-27T03:10:00Z',
    operator: 'cece',
    category: 'replacement',
    action: 'chip.report_lost',
    target: '04:77:66:55:44:80:10 (FASH-2026-000005)',
    detail: '标记芯片挂失，立即阻断旧卡动态验证与已签发 browser_view 持续查看资格',
  },
  {
    id: 'aud-1007',
    timestamp: '2026-10-27T02:00:00Z',
    operator: 'cece',
    category: 'key_provision',
    action: 'chip.confirm_provisioning',
    target: '04:F0:99:B2:4C:80:08',
    detail: '通过两条递增 SUN 动态读数与人工 K0 核验，保存计数基线',
  },
  {
    id: 'aud-1006',
    timestamp: '2026-10-27T01:30:00Z',
    operator: 'cece',
    category: 'chip',
    action: 'chip.bind_item',
    target: '04:E4:88:0A:19:80:07 → FASH-2026-000004',
    detail: '首次建立芯片与服装草稿关联，项目确定为 fashion',
  },
  {
    id: 'aud-1005',
    timestamp: '2026-10-26T16:05:00Z',
    operator: 'cece',
    category: 'key_provision',
    action: 'chip.confirm_provisioning',
    target: '04:D9:12:6F:33:80:06',
    detail: '饰品样卡 JEW-2026-000001 实卡配置核验完成',
  },
  {
    id: 'aud-1004',
    timestamp: '2026-10-26T14:22:18Z',
    operator: 'cece (nfc_cool)',
    category: 'chip',
    action: 'webhook.admin.scan',
    target: '04:C1:5D:44:7E:80:05',
    detail: '手机 NFC.cool 批量扫描回调登记（registration_source=nfc_cool）',
  },
  {
    id: 'aud-1003',
    timestamp: '2026-10-25T11:30:00Z',
    operator: 'cece',
    category: 'item',
    action: 'item.status.change',
    target: 'FASH-2026-000002',
    detail: '服装状态由 draft 变更为 active',
  },
  {
    id: 'aud-1002',
    timestamp: '2026-10-25T10:00:00Z',
    operator: 'cece',
    category: 'item',
    action: 'item.profile.save',
    target: 'FASH-2026-000001',
    detail: '保存服装五项基础资料（名称、介绍、材质、洗护说明、2张HTTPS图片）',
  },
];

export interface TapEventRecord {
  id: string;
  item_id: number;
  item_uid: string;
  project: ProjectCode;
  beijing_date: string;
  tapped_at: string;
  is_validation?: boolean;
}

export const INITIAL_TAP_EVENTS: TapEventRecord[] = [
  { id: 't-1', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-21', tapped_at: '2026-10-21T03:12:00Z' },
  { id: 't-2', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-21', tapped_at: '2026-10-21T07:45:00Z' },
  { id: 't-3', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-22', tapped_at: '2026-10-22T02:18:00Z' },
  { id: 't-4', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-22', tapped_at: '2026-10-22T09:05:00Z' },
  { id: 't-5', item_id: 8, item_uid: 'FASH-2026-000005', project: 'fashion', beijing_date: '2026-10-22', tapped_at: '2026-10-22T11:30:00Z' },
  { id: 't-6', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-23', tapped_at: '2026-10-23T04:20:00Z' },
  { id: 't-7', item_id: 8, item_uid: 'FASH-2026-000005', project: 'fashion', beijing_date: '2026-10-23', tapped_at: '2026-10-23T08:11:00Z' },
  { id: 't-8', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-24', tapped_at: '2026-10-24T05:00:00Z' },
  { id: 't-9', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-24', tapped_at: '2026-10-24T06:40:00Z' },
  { id: 't-10', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-24', tapped_at: '2026-10-24T10:15:00Z' },
  { id: 't-11', item_id: 5, item_uid: 'JEW-2026-000001', project: 'jewelry', beijing_date: '2026-10-24', tapped_at: '2026-10-24T13:20:00Z' },
  { id: 't-12', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-25', tapped_at: '2026-10-25T01:50:00Z' },
  { id: 't-13', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-25', tapped_at: '2026-10-25T04:10:00Z' },
  { id: 't-14', item_id: 5, item_uid: 'JEW-2026-000001', project: 'jewelry', beijing_date: '2026-10-25', tapped_at: '2026-10-25T07:30:00Z' },
  { id: 't-15', item_id: 5, item_uid: 'JEW-2026-000001', project: 'jewelry', beijing_date: '2026-10-25', tapped_at: '2026-10-25T09:45:00Z' },
  { id: 't-16', item_id: 8, item_uid: 'FASH-2026-000005', project: 'fashion', beijing_date: '2026-10-25', tapped_at: '2026-10-25T12:05:00Z' },
  { id: 't-17', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-26', tapped_at: '2026-10-26T02:30:00Z' },
  { id: 't-18', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-26', tapped_at: '2026-10-26T05:12:00Z' },
  { id: 't-19', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-26', tapped_at: '2026-10-26T08:40:00Z' },
  { id: 't-20', item_id: 5, item_uid: 'JEW-2026-000001', project: 'jewelry', beijing_date: '2026-10-26', tapped_at: '2026-10-26T16:20:00Z' },
  { id: 't-21', item_id: 1, item_uid: 'FASH-2026-000001', project: 'fashion', beijing_date: '2026-10-27', tapped_at: '2026-10-27T01:15:00Z' },
  { id: 't-22', item_id: 2, item_uid: 'FASH-2026-000002', project: 'fashion', beijing_date: '2026-10-27', tapped_at: '2026-10-27T02:05:00Z' },
  { id: 't-23', item_id: 7, item_uid: 'FASH-2026-990001', project: 'fashion', beijing_date: '2026-10-27', tapped_at: '2026-10-27T02:08:00Z', is_validation: true },
  { id: 't-24', item_id: 5, item_uid: 'JEW-2026-000001', project: 'jewelry', beijing_date: '2026-10-27', tapped_at: '2026-10-27T03:25:00Z' },
];

export function computeTapStatsSnapshot(
  query: TapStatsQuery,
  items: ItemView[],
  events: TapEventRecord[],
  excludeValidation = false
): TapStats {
  const todayStr = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const asOf = new Date().toISOString();

  const projectEvents = events.filter((e) => {
    if (excludeValidation && e.is_validation) return false;
    if (query.project && e.project !== query.project) return false;
    return true;
  });

  const sortedAll = [...projectEvents].sort((a, b) => Date.parse(a.tapped_at) - Date.parse(b.tapped_at));
  const firstRecordedAt = sortedAll.length > 0 ? sortedAll[0].tapped_at : null;

  let startStr: string | null = null;
  if (query.range === '7d') {
    startStr = new Date(Date.parse(todayStr+'T00:00:00Z')-6*86400000).toISOString().slice(0,10);
  } else if (query.range === '30d') {
    startStr = new Date(Date.parse(todayStr+'T00:00:00Z')-29*86400000).toISOString().slice(0,10);
  } else {
    startStr = firstRecordedAt ? sortedAll[0].beijing_date : null;
  }

  const rangedEvents = startStr
    ? projectEvents.filter((e) => e.beijing_date >= startStr! && e.beijing_date <= todayStr)
    : [];

  const daily: { date: string; valid_taps: number }[] = [];
  if (startStr) {
    const startMs = Date.parse(startStr + 'T00:00:00Z');
    const endMs = Date.parse(todayStr + 'T00:00:00Z');
    const daysCount = Math.round((endMs - startMs) / 86400000) + 1;
    const map = new Map<string, number>();
    for (const ev of rangedEvents) {
      map.set(ev.beijing_date, (map.get(ev.beijing_date) || 0) + 1);
    }
    for (let i = 0; i < daysCount; i++) {
      const d = new Date(startMs + i * 86400000).toISOString().slice(0, 10);
      daily.push({ date: d, valid_taps: map.get(d) || 0 });
    }
  }

  const itemAgg = new Map<
    string,
    { item_id: number; project: ProjectCode; item_uid: string; valid_taps: number; last_tap_at: string }
  >();
  for (const ev of rangedEvents) {
    const existing = itemAgg.get(ev.item_uid);
    if (!existing) {
      itemAgg.set(ev.item_uid, {
        item_id: ev.item_id,
        project: ev.project,
        item_uid: ev.item_uid,
        valid_taps: 1,
        last_tap_at: ev.tapped_at,
      });
    } else {
      existing.valid_taps += 1;
      if (Date.parse(ev.tapped_at) > Date.parse(existing.last_tap_at)) {
        existing.last_tap_at = ev.tapped_at;
      }
    }
  }

  const itemMapByUid = new Map(items.map((it) => [it.item_uid, it]));
  let allTouchedRows: TapStatsItemRow[] = Array.from(itemAgg.values()).map((row) => {
    const currentItem = itemMapByUid.get(row.item_uid);
    const currentName =
      currentItem?.profile && typeof currentItem.profile.name === 'string' && currentItem.profile.name.trim()
        ? currentItem.profile.name.trim()
        : null;
    return {
      item_id: row.item_id,
      project: row.project,
      item_uid: row.item_uid,
      name: currentName,
      valid_taps: row.valid_taps,
      last_tap_at: row.last_tap_at,
    };
  });

  allTouchedRows.sort((a, b) => {
    if (b.valid_taps !== a.valid_taps) return b.valid_taps - a.valid_taps;
    const tDiff = Date.parse(b.last_tap_at) - Date.parse(a.last_tap_at);
    if (tDiff !== 0) return tDiff;
    return a.item_uid.localeCompare(b.item_uid);
  });

  const summary = {
    valid_taps: rangedEvents.length,
    touched_items: allTouchedRows.length,
  };

  const normalizedQ = query.q.trim().toLowerCase();
  if (normalizedQ) {
    allTouchedRows = allTouchedRows.filter(
      (r) =>
        r.item_uid.toLowerCase().includes(normalizedQ) ||
        (r.name && r.name.toLowerCase().includes(normalizedQ))
    );
  }

  const totalItems = allTouchedRows.length;
  const pageSize = 10;
  const totalPages = Math.ceil(totalItems / pageSize);
  const effectivePage = totalPages === 0 ? 1 : Math.min(Math.max(1, query.page), totalPages);
  const pageAdjusted = effectivePage !== query.page;
  const pagedRows = allTouchedRows.slice((effectivePage - 1) * pageSize, effectivePage * pageSize);

  return {
    filters: {
      project: query.project || null,
      range: query.range,
      q: query.q.trim(),
    },
    timezone: 'Asia/Shanghai',
    as_of: asOf,
    period: {
      from_date: startStr,
      to_date: todayStr,
    },
    first_recorded_at: firstRecordedAt,
    summary,
    daily,
    items: pagedRows,
    total_items: totalItems,
    page: effectivePage,
    page_size: pageSize,
    total_pages: totalPages,
    page_adjusted: pageAdjusted,
  };
}

export function evaluateChipLifecycleLevel(chip: ChipView, events: TapEventRecord[]): {
  level: LifecycleLevel;
  label: string;
  color: string;
  canDeleteDirectly: boolean;
  canExitValidation: boolean;
  dependencies: string[];
  reason: string;
} {
  const tapCount = chip.item_uid ? events.filter((e) => e.item_uid === chip.item_uid).length : 0;
  const deps: string[] = [];
  if (chip.item_uid) deps.push(`关联物品 ${chip.item_uid}`);
  if (chip.keys_generated) deps.push('已生成加密密钥记录');
  if (chip.provisioned_at) deps.push('已完成实卡配置核验与计数基线');
  if (tapCount > 0) deps.push(`存在 ${tapCount} 次有效触碰记录`);

  if (chip.item_id === null && !chip.keys_generated && !chip.provisioned_at && tapCount === 0) {
    return {
      level: 'L1_draft_test',
      label: 'L1 · 无依赖草稿/登记',
      color: 'cyan',
      canDeleteDirectly: true,
      canExitValidation: false,
      dependencies: [],
      reason: '无关联物品、未生成密钥、无实卡核验及触碰历史，支持受限直接清理。',
    };
  }

  if (chip.is_validation_object) {
    return {
      level: 'L2_validation',
      label: 'L2 · 生产验证对象',
      color: 'orange',
      canDeleteDirectly: false,
      canExitValidation: true,
      dependencies: deps,
      reason: '已绑定或完成实卡验证的生产验证对象。不可简单硬删抹除安全计数，须执行「退出验证服务并清理测试关联」。',
    };
  }

  return {
    level: 'L3_production',
    label: 'L3 · 正式业务对象',
      color: 'green',
    canDeleteDirectly: false,
    canExitValidation: false,
    dependencies: deps,
    reason: '已承载正式业务关联或用户权益，禁止纳入测试删除；请使用停用、挂失或换新接续流程。',
  };
}
