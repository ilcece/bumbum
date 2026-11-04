import {usePrototype,userName} from '../data/prototypeStore';
import {PrototypeItemDetails} from './PrototypeItemDetails';
import {readFilters,writeFilters} from '../data/prototypeNavigation';
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  DownOutlined,
  EditOutlined,
  EyeOutlined,
  FileTextOutlined,
  LinkOutlined,
  MobileOutlined,
  PlusOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  ShoppingOutlined,
  SwapOutlined,
  SyncOutlined,
  ToolOutlined,
  UpOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  CHIP_STATUS_META,
  ITEM_STATUS_META,
  PROJECT_SHORT_LABELS,
  validateItemUid,
  type ChipView,
  type FashionProfile,
  type ItemImageAsset,
  type ItemStatus,
  type ItemView,
  type JewelryProfile,
  type ProjectCode,
} from '../data/mockBackend';

const { Text } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

interface ItemManagementPageProps {
  items: ItemView[];
  chips: ChipView[];
  activeItemId: number | null;
  presetFilter?: { type: 'all' | 'draft'; nonce: number } | null;
  simulateApiError?: boolean;
  onRecoverApiError?: () => void;
  onSelectItemId: (itemId: number | null) => void;
  onOpenChipDetail: (chipId: number) => void;
  onBindChipToItem: (
    chipId: number,
    itemId: number
  ) => { ok: boolean; error?: string; chip?: ChipView };
  onCreateItemDraft: (payload: {
    project: ProjectCode;
    item_uid: string;
    sku_code: string | null;
    is_validation_object?: boolean;
  }) => { ok: boolean; item?: ItemView; error?: string };
  onUpdateItemMaintenance: (
    itemId: number,
    payload: {
      sku_code: string | null;
      status: ItemStatus;
      is_validation_object: boolean;
    }
  ) => void;
  onSaveFashionProfile: (
    itemId: number,
    profile: FashionProfile,
    options?: {
      sku_code?: string | null;
      image_assets?: ItemImageAsset[];
      retired_count?: number;
    }
  ) => { ok: boolean; error?: string };
  onCorrectItemIdentity: (
    itemId: number,
    newProject: ProjectCode,
    newItemUid: string,
    reason: string
  ) => { ok: boolean; error?: string };
  onDeleteL1Item: (itemId: number, reason: string) => { ok: boolean; error?: string };
  onUnbindOrRebindMisboundChip: (
    chipId: number,
    mode: 'unbind_to_pending' | 'rebind_to_target',
    targetItemId: number | null,
    reason: string
  ) => { ok: boolean; error?: string };
  onReportChipLost: (chipId: number, reason: string) => { ok: boolean; error?: string };
  onExecuteCarrierReplacement: (payload: {
    itemId: number;
    newChipId: number;
    scenario: 'loss_replacement' | 'resale_new_carrier';
    reason: string;
  }) => { ok: boolean; error?: string };
}

interface ItemFilterState {
  keyword: string;
  project: '' | ProjectCode;
  status: '' | ItemStatus;
  skuKeyword: string;
  bindState: '' | 'bound' | 'unbound';
  profileState: '' | 'has_name' | 'empty_name';
  validationScope: '' | 'formal_only' | 'validation_only';
  dateField: 'created_at' | 'updated_at';
  dateFrom: string;
  dateTo: string;
}

const INITIAL_ITEM_FILTERS: ItemFilterState = {
  keyword: '',
  project: '',
  status: '',
  skuKeyword: '',
  bindState: '',
  profileState: '',
  validationScope: '',
  dateField: 'created_at',
  dateFrom: '',
  dateTo: '',
};

const DEMO_MANAGED_PHOTOS = [
  {
    preview:
      'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80',
    filename: 'lookbook-front-2048.webp',
    size_kb: 386,
    dimensions: '1536×2048 · WebP 去EXIF',
  },
  {
    preview:
      'https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=900&q=80',
    filename: 'detail-cuff-nfc-zone.webp',
    size_kb: 294,
    dimensions: '1600×2048 · WebP 去EXIF',
  },
  {
    preview:
      'https://images.unsplash.com/photo-1539533018447-63fcce2678e3?auto=format&fit=crop&w=900&q=80',
    filename: 'fabric-texture-closeup.webp',
    size_kb: 440,
    dimensions: '2048×1536 · WebP 去EXIF',
  },
];

function randomHex32(): string {
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
}

function buildInitialAssetsFromItem(item: ItemView): ItemImageAsset[] {
  if (item.image_assets && item.image_assets.length > 0) {
    return item.image_assets.map((a) => ({ ...a }));
  }
  const urls = item.profile?.image_urls || [];
  return urls.map((u, idx) => ({
    asset_id: `ext_${item.id}_${idx}_${randomHex32().slice(0, 16)}`,
    client_upload_id: randomHex32(),
    state: 'attached',
    url: u,
    preview_url: u,
    source_type: u.startsWith('/api/') ? 'managed' : 'external_url',
    filename: u.startsWith('/api/') ? `item-${item.id}-img-${idx + 1}.webp` : '外部 HTTPS 图片',
    expires_at: null,
  }));
}

export const ItemManagementPage: React.FC<ItemManagementPageProps> = ({
  items,
  chips,
  activeItemId,
  presetFilter,
  simulateApiError = false,
  onRecoverApiError,
  onSelectItemId,
  onOpenChipDetail,
  onBindChipToItem,
  onCreateItemDraft,
  onUpdateItemMaintenance,
  onSaveFashionProfile,
  onCorrectItemIdentity,
  onDeleteL1Item,
  onUnbindOrRebindMisboundChip,
  onReportChipLost,
  onExecuteCarrierReplacement,
}) => {
  const proto=usePrototype();
  const [filters, setFilters] = useState<ItemFilterState>(()=>readFilters("items",INITIAL_ITEM_FILTERS));
  const [appliedFilters, setAppliedFilters] = useState<ItemFilterState>(()=>readFilters("items",INITIAL_ITEM_FILTERS));
  const [expandAdvanced, setExpandAdvanced] = useState(false);
  const [currentPage, setCurrentPage] = useState(()=>Number(new URLSearchParams(location.hash.split("?")[1]).get("itemsPage"))||1);
  useEffect(()=>writeFilters("items",appliedFilters,currentPage),[appliedFilters,currentPage]);
  const [dateRangeResetKey, setDateRangeResetKey] = useState(0);

  // 从物品侧直接发起绑定待分配芯片弹窗
  const [bindChipForItemId, setBindChipForItemId] = useState<number | null>(null);
  const [selectedPendingChipId, setSelectedPendingChipId] = useState<number | null>(null);

  useEffect(() => {
    if (!presetFilter) return;
    if (presetFilter.type === 'all') {
      setFilters(INITIAL_ITEM_FILTERS);
      setAppliedFilters(INITIAL_ITEM_FILTERS);
      setCurrentPage(1);
    } else if (presetFilter.type === 'draft') {
      const next: ItemFilterState = { ...INITIAL_ITEM_FILTERS, status: 'draft' };
      setFilters(next);
      setAppliedFilters(next);
      setCurrentPage(1);
    }
  }, [presetFilter]);

  // 新建成功保留条件并提供连续动作横幅
  const [recentCreatedBanner, setRecentCreatedBanner] = useState<ItemView | null>(null);

  // 创建物品草稿弹窗
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createProject, setCreateProject] = useState<ProjectCode>('fashion');
  const [createItemUid, setCreateItemUid] = useState('');
  const [createSkuCode, setCreateSkuCode] = useState('');
  const [createIsValidation, setCreateIsValidation] = useState(false);
  const [createError, setCreateError] = useState('');

  // 服装基础资料编辑独立弹窗（也可从详情抽屉或行操作直接呼出）
  const [profileModalItemId, setProfileModalItemId] = useState<number | null>(null);
  const [profSkuCode, setProfSkuCode] = useState('');
  const [profName, setProfName] = useState('');
  const [profDesc, setProfDesc] = useState('');
  const [profMaterial, setProfMaterial] = useState('');
  const [profCare, setProfCare] = useState('');
  const [profAssets, setProfAssets] = useState<ItemImageAsset[]>([]);
  const [externalUrlInput, setExternalUrlInput] = useState('');
  const [mediaEnabledSim, setMediaEnabledSim] = useState(true);
  const [profError, setProfError] = useState('');
  const [profDirty, setProfDirty] = useState(false);

  // 详情抽屉内可编辑字段状态
  const [drawerSkuInput, setDrawerSkuInput] = useState('');
  const [drawerStatus, setDrawerStatus] = useState<ItemStatus>('draft');
  const [drawerIsValidation, setDrawerIsValidation] = useState(false);

  // 详情抽屉内直接触发的修改身份、删除草稿、解绑、挂失、更换新芯片弹窗状态
  const [editIdentityModalOpen, setEditIdentityModalOpen] = useState(false);
  const [editIdentityProject, setEditIdentityProject] = useState<ProjectCode>('fashion');
  const [editIdentityUid, setEditIdentityUid] = useState('');
  const [editIdentityReason, setEditIdentityReason] = useState('');
  const [editIdentityError, setEditIdentityError] = useState('');

  const [deleteDraftModalOpen, setDeleteDraftModalOpen] = useState(false);
  const [deleteDraftReason, setDeleteDraftReason] = useState('');

  const [unbindChipModalOpen, setUnbindChipModalOpen] = useState(false);
  const [unbindChipReason, setUnbindChipReason] = useState('');

  const [lostChipModalOpen, setLostChipModalOpen] = useState(false);
  const [lostChipReason, setLostChipReason] = useState('');

  const [replaceChipModalOpen, setReplaceChipModalOpen] = useState(false);
  const [replaceScenario, setReplaceScenario] = useState<
    'loss_replacement' | 'resale_new_carrier'
  >('loss_replacement');
  const [replaceNewChipId, setReplaceNewChipId] = useState<number | null>(null);
  const [replaceReason, setReplaceReason] = useState('');

  const activeItem = useMemo(
    () => items.find((i) => i.id === activeItemId) || null,
    [items, activeItemId]
  );

  const profileModalItem = useMemo(
    () => items.find((i) => i.id === profileModalItemId) || null,
    [items, profileModalItemId]
  );

  const bindChipTargetItem = useMemo(
    () => items.find((i) => i.id === bindChipForItemId) || null,
    [items, bindChipForItemId]
  );

  const candidatePendingChipsForItem = useMemo(() => {
    if (!bindChipTargetItem) return [];
    return chips.filter(
      (c) =>
        c.chip_status === 'pending' &&
        c.item_id === null &&
        (c.project === null || c.project === bindChipTargetItem.project)
    );
  }, [chips, bindChipTargetItem]);

  const candidatePendingChipsForActiveItem = useMemo(() => {
    if (!activeItem) return [];
    return chips.filter(
      (c) =>
        c.chip_status === 'pending' &&
        c.item_id === null &&
        (c.project === null || c.project === activeItem.project)
    );
  }, [chips, activeItem]);

  useEffect(() => {
    if (activeItem) {
      setDrawerSkuInput(activeItem.sku_code || '');
      setDrawerStatus(activeItem.status);
      setDrawerIsValidation(Boolean(activeItem.is_validation_object));
    }
  }, [activeItem]);

  // P0-1：计算物品详情抽屉是否存在未保存的维护字段修改
  const drawerDirty = useMemo(() => {
    if (!activeItem) return false;
    const origSku = activeItem.sku_code || '';
    const origStatus = activeItem.status;
    const origVal = Boolean(activeItem.is_validation_object);
    return (
      drawerSkuInput.trim() !== origSku ||
      drawerStatus !== origStatus ||
      drawerIsValidation !== origVal
    );
  }, [activeItem, drawerSkuInput, drawerStatus, drawerIsValidation]);

  // P0-1：抽屉未保存离开或切换拦截
  const guardDrawerBeforeAction = (action: () => void) => {
    if (!drawerDirty) {
      action();
      return;
    }
    Modal.confirm({
      title: '放弃物品详情中未保存的修改？',
      content: `物品 ${activeItem?.item_uid} 的款式编号、状态或验证标识已修改但尚未点击「保存维护设置」，确定放弃修改并离开吗？`,
      okText: '放弃修改并离开',
      okButtonProps: { danger: true },
      cancelText: '留在当前抽屉',
      onOk: () => action(),
    });
  };

  const handleOpenProfileEditor = (item: ItemView) => {
    proto.setEditItemId(item.id);return;
    setProfileModalItemId(item.id);
    setProfSkuCode(item.sku_code || '');
    const p = item.profile as FashionProfile | null;
    setProfName(p?.name || '');
    setProfDesc(p?.description || '');
    setProfMaterial(p?.material || '');
    setProfCare(p?.care_instructions || '');
    setProfAssets(buildInitialAssetsFromItem(item));
    setExternalUrlInput('');
    setProfError('');
    setProfDirty(false);
  };

  const getItemKeywordMatches = (item: ItemView, rawKeyword: string): string[] => {
    const q = rawKeyword.trim().toLowerCase();
    if (!q) return [];
    const qNoColon = q.replace(/:/g, '');
    const matches: string[] = [];
    if (item.item_uid.toLowerCase().includes(q)) matches.push('物品编号');
    if (item.sku_code && item.sku_code.toLowerCase().includes(q)) matches.push('款式编号');
    if (
      item.profile &&
      typeof item.profile.name === 'string' &&
      item.profile.name.toLowerCase().includes(q)
    ) {
      matches.push('物品名称');
    }
    if (item.bound_chip_uid) {
      const chipClean = item.bound_chip_uid.toLowerCase().replace(/:/g, '');
      if (item.bound_chip_uid.toLowerCase().includes(q) || chipClean.includes(qNoColon)) {
        matches.push('关联芯片UID');
      }
    }
    return matches;
  };

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (appliedFilters.keyword.trim()) {
        const matches = getItemKeywordMatches(item, appliedFilters.keyword);
        if (matches.length === 0) return false;
      }
      if (appliedFilters.project && item.project !== appliedFilters.project) return false;
      if (appliedFilters.status && item.status !== appliedFilters.status) return false;
      if (appliedFilters.skuKeyword.trim()) {
        const sq = appliedFilters.skuKeyword.trim().toLowerCase();
        if (!item.sku_code || !item.sku_code.toLowerCase().includes(sq)) return false;
      }
      if (appliedFilters.bindState === 'bound' && item.bound_chip_id === null) return false;
      if (appliedFilters.bindState === 'unbound' && item.bound_chip_id !== null) return false;
      const hasName = Boolean(item.profile && item.profile.name && item.profile.name.trim());
      if (appliedFilters.profileState === 'has_name' && !hasName) return false;
      if (appliedFilters.profileState === 'empty_name' && hasName) return false;
      if (appliedFilters.validationScope === 'formal_only' && item.is_validation_object)
        return false;
      if (appliedFilters.validationScope === 'validation_only' && !item.is_validation_object)
        return false;
      if (appliedFilters.dateFrom || appliedFilters.dateTo) {
        const rawTime =
          appliedFilters.dateField === 'updated_at' ? item.updated_at : item.created_at;
        const dateOnly = rawTime.slice(0, 10);
        if (appliedFilters.dateFrom && dateOnly < appliedFilters.dateFrom) return false;
        if (appliedFilters.dateTo && dateOnly > appliedFilters.dateTo) return false;
      }
      return true;
    });
  }, [items, appliedFilters]);

  useEffect(()=>{const last=Math.max(1,Math.ceil(filteredItems.length/10));if(currentPage>last)setCurrentPage(last);},[filteredItems.length,currentPage]);

  const filtersDirty = JSON.stringify(filters) !== JSON.stringify(appliedFilters);

  const handleApplyFilters = () => {
    setAppliedFilters({ ...filters });
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_ITEM_FILTERS);
    setAppliedFilters(INITIAL_ITEM_FILTERS);
    setDateRangeResetKey((k) => k + 1);
    setCurrentPage(1);
  };

  const suggestNextItemUid = (proj: ProjectCode) => {
    const prefix = proj === 'fashion' ? 'FASH-2026-' : 'JEW-2026-';
    const existingNums = items
      .filter((i) => i.project === proj && i.item_uid.startsWith(prefix))
      .map((i) => parseInt(i.item_uid.slice(prefix.length), 10))
      .filter((n) => !Number.isNaN(n) && n < 900000);
    const nextNum = (existingNums.length > 0 ? Math.max(...existingNums) : 0) + 1;
    return `${prefix}${String(nextNum).padStart(6, '0')}`;
  };

  const handleSubmitCreateItem = (openEditorImmediately: boolean) => {
    setCreateError('');
    if(!createSkuCode){setCreateError('请选择已有款式；类别只从款式引用。');return;}
    const check = validateItemUid(createProject, createItemUid);
    if (!check.ok) {
      setCreateError(check.error);
      return;
    }
    const skuTrimmed = createSkuCode.trim() || null;
    if (skuTrimmed && [...skuTrimmed].length > 64) {
      return;
    }
    const res = onCreateItemDraft({
      project: createProject,
      item_uid: check.item_uid,
      sku_code: skuTrimmed,
      is_validation_object: createIsValidation,
    });
    if (!res.ok || !res.item) {
      setCreateError(res.error || '创建失败');
      return;
    }

    setRecentCreatedBanner(res.item);
    setCreateItemUid('');
    setCreateSkuCode('');
    if(openEditorImmediately)setCreateModalOpen(false);
    message.success(`已创建样例 ${res.item.item_uid}，可继续录入下一件。`);

    if (openEditorImmediately) {
      onSelectItemId(res.item.id);
      proto.setIdentityEditorId(res.item.id);
    }
  };

  const validateAndSubmitFashionProfile = () => {
    if (!profileModalItem) return;
    setProfError('');
    const skuTrim = profSkuCode.trim() || null;
    const nameTrim = profName.trim();
    const descTrim = profDesc.trim();
    const matTrim = profMaterial.trim();
    const careTrim = profCare.trim();

    if (skuTrim && [...skuTrim].length > 64) {
      setProfError('款式编号 sku_code 最多 64 个字符。');
      return;
    }
    if (!nameTrim) {
      setProfError('请填写服装名称（必填，1–128 字符）。');
      return;
    }
    if ([...nameTrim].length > 128) {
      setProfError('服装名称最多 128 个字符。');
      return;
    }
    if ([...descTrim].length > 4000) {
      setProfError('服装介绍最多 4000 个字符。');
      return;
    }
    if ([...matTrim].length > 256) {
      setProfError('材质说明最多 256 个字符。');
      return;
    }
    if ([...careTrim].length > 2000) {
      setProfError('洗护说明最多 2000 个字符。');
      return;
    }
    if (profAssets.length > 20) {
      setProfError('图片最多 20 张。');
      return;
    }
    const unresolvedAsset = profAssets.find((a) => a.state === 'unknown_status');
    if (unresolvedAsset) {
      setProfError(
        `图片「${unresolvedAsset.filename || unresolvedAsset.asset_id.slice(0, 8)}」处于回执未知状态，请先点击「核对状态」确认完成后再保存。`
      );
      return;
    }
    for (let i = 0; i < profAssets.length; i++) {
      const asset = profAssets[i];
      if (asset.url.length > 2048) {
        setProfError(`第 ${i + 1} 张图片引用超过 2048 字符上限。`);
        return;
      }
    }

    const origAttachedIds = new Set(
      buildInitialAssetsFromItem(profileModalItem)
        .filter((a) => a.state === 'attached')
        .map((a) => a.asset_id)
    );
    const currentIds = new Set(profAssets.map((a) => a.asset_id));
    let retiredCount = 0;
    origAttachedIds.forEach((id) => {
      if (!currentIds.has(id)) retiredCount += 1;
    });

    const pendingCount = profAssets.filter((a) => a.state === 'pending').length;
    const cleanedUrls = profAssets.map((a) => a.preview_url || a.url);

    const res = onSaveFashionProfile(
      profileModalItem.id,
      {
        name: nameTrim,
        description: descTrim || null,
        material: matTrim || null,
        care_instructions: careTrim || null,
        image_urls: cleanedUrls,
      },
      {
        sku_code: skuTrim,
        image_assets: profAssets,
        retired_count: retiredCount,
      }
    );
    if (!res.ok) {
      setProfError(res.error || '保存失败');
      return;
    }
    message.success(
      `已原子保存 ${profileModalItem.item_uid} 的款式与服装资料${
        pendingCount > 0 ? `（${pendingCount} 张暂存图已转为 attached）` : ''
      }${retiredCount > 0 ? `（${retiredCount} 张移除图已转为 retired 7天保留）` : ''}`
    );
    setProfDirty(false);
    setProfileModalItemId(null);
  };

  // 处理本地文件通过 Upload 受控暂存上传
  const handleLocalFileUpload = (file: File) => {
    if (!profileModalItem) return false;
    setProfError('');
    if (!mediaEnabledSim) {
      setProfError(
        '当前环境已关闭新图片上传（MEDIA_ENABLED=false），请求在接收前已拦截；已关联图片仍可正常读取预览。'
      );
      return false;
    }
    if (profAssets.length >= 20) {
      setProfError('单个服装物品最多关联 20 张图片，已达数量上限。');
      return false;
    }
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setProfError('图片格式不支持：仅接收静态 JPEG / PNG（≤1600万像素）或 WebP（≤800万像素）。');
      return false;
    }
    if (file.size > 8 * 1024 * 1024 || file.size < 1) {
      setProfError('单张图片文件大小不能超过 8 MiB。');
      return false;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === 'string' ? reader.result : '';
      const assetId = randomHex32();
      const clientUploadId = randomHex32();
      const expiresAt = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
      const newAsset: ItemImageAsset = {
        asset_id: assetId,
        client_upload_id: clientUploadId,
        state: 'pending',
        url: `/api/admin/items/${profileModalItem.id}/images/${assetId}`,
        preview_url: dataUrl,
        source_type: 'managed',
        filename: file.name.replace(/\.[^.]+$/, '') + '.webp',
        size_kb: Math.max(12, Math.round((file.size / 1024) * 0.68)),
        dimensions: '≤2048px · WebP 去元数据',
        expires_at: expiresAt,
      };
      setProfAssets((prev) => [...prev, newAsset]);
      setProfDirty(true);
      message.success(
        `已上传并建立 Pending 暂存 (${newAsset.filename})，点击底部「原子保存」后正式关联`
      );
    };
    reader.readAsDataURL(file);
    return false;
  };

  // 模拟上传实拍图（生成 pending 或 unknown_status）
  const handleSimulateManagedUpload = (simulateUnknownReceipt: boolean) => {
    if (!profileModalItem) return;
    setProfError('');
    if (!mediaEnabledSim) {
      setProfError(
        '当前环境已关闭新图片上传（MEDIA_ENABLED=false），请求在接收前已拦截；已有图片仍可正常读取。'
      );
      return;
    }
    if (profAssets.length >= 20) {
      setProfError('单个服装物品最多关联 20 张图片，已达数量上限。');
      return;
    }
    const sample = DEMO_MANAGED_PHOTOS[profAssets.length % DEMO_MANAGED_PHOTOS.length];
    const assetId = randomHex32();
    const clientUploadId = randomHex32();
    const expiresAt = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
    const newAsset: ItemImageAsset = {
      asset_id: assetId,
      client_upload_id: clientUploadId,
      state: simulateUnknownReceipt ? 'unknown_status' : 'pending',
      url: `/api/admin/items/${profileModalItem.id}/images/${assetId}`,
      preview_url: sample.preview,
      source_type: 'managed',
      filename: sample.filename,
      size_kb: sample.size_kb,
      dimensions: sample.dimensions,
      expires_at: expiresAt,
    };
    setProfAssets((prev) => [...prev, newAsset]);
    setProfDirty(true);
    if (simulateUnknownReceipt) {
      message.warning(
        '模拟上传网关超时未收到回执：请点击该图右侧「核对状态」复用已完成结果，无需重传文件'
      );
    } else {
      message.success('已上传并生成 Pending 暂存图片（24小时租约，保存资料时原子关联）');
    }
  };

  // 添加兼容外部 HTTP/HTTPS URL
  const handleAddExternalUrl = () => {
    setProfError('');
    const raw = externalUrlInput.trim();
    if (!raw) {
      setProfError('请输入外部图片 HTTP/HTTPS 完整链接。');
      return;
    }
    if (profAssets.length >= 20) {
      setProfError('图片数量已达 20 张上限。');
      return;
    }
    if (raw.length > 2048 || /[\s\\]/.test(raw)) {
      setProfError('外部图片 URL 长度不能超过 2048 字符，且不能包含空白或反斜杠。');
      return;
    }
    try {
      const parsed = new URL(raw);
      if (
        (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') ||
        !parsed.hostname ||
        parsed.username ||
        parsed.password
      ) {
        setProfError('外部图片链接须为合法的 HTTP/HTTPS URL，且不含账号密码。');
        return;
      }
    } catch {
      setProfError('输入的外部图片地址不是合法的 URL。');
      return;
    }
    const assetId = `ext_${Date.now()}_${randomHex32().slice(0, 12)}`;
    setProfAssets((prev) => [
      ...prev,
      {
        asset_id: assetId,
        client_upload_id: randomHex32(),
        state: 'pending',
        url: raw,
        preview_url: raw,
        source_type: 'external_url',
        filename: '外部兼容 URL 图片',
        expires_at: null,
      },
    ]);
    setExternalUrlInput('');
    setProfDirty(true);
  };

  const moveAsset = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= profAssets.length) return;
    const next = [...profAssets];
    const temp = next[index];
    next[index] = next[target];
    next[target] = temp;
    setProfAssets(next);
    setProfDirty(true);
  };

  const closeCreate = () => {if(createSkuCode.trim()||(createItemUid.trim()&&createItemUid!==suggestNextItemUid(createProject))){Modal.confirm({title:'放弃未提交的物品草稿？',content:'本次输入尚未保存，确定关闭吗？',okText:'确认关闭',cancelText:'继续填写',onOk:()=>setCreateModalOpen(false)});}else setCreateModalOpen(false);};
  const columns: ColumnsType<ItemView> = [
    {title:'限定编号／持有人',key:'identity',width:175,render:(_,record)=><div><div>{proto.identity(record).edition||'非限定／未设定'}</div><Text type="secondary" style={{fontSize:12}}>{userName(proto.identity(record).ownerId)}</Text></div>},
    {
      title: '物品编号',
      dataIndex: 'item_uid',
      key: 'item_uid',
      width: 175,
      fixed: 'left',
      render: (uid: string, record) => {
        const kwMatches = getItemKeywordMatches(record, appliedFilters.keyword);
        return (
          <div>
            <Space size={4}>
              <Button
                type="link"
                style={{
                  padding: 0,
                  fontWeight: 600,
                  fontSize: 13,
                }}
                onClick={() => {
                  if (record.id === activeItemId) return;
                  guardDrawerBeforeAction(() => onSelectItemId(record.id));
                }}
              >
                {uid}
              </Button>
              <Text copyable={{ text: uid, tooltips: ['复制物品编号', '已复制'] }} />
            </Space>
            <div className="mt-0.5 flex flex-wrap gap-1">
              {record.is_validation_object && (
                <Tag color="orange" style={{ fontSize: 11, lineHeight: '16px', margin: 0 }}>
                  生产验证对象
                </Tag>
              )}
              {kwMatches.length > 0 && (
                <Tag color="geekblue" style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>
                  命中: {kwMatches.join('/')}
                </Tag>
              )}
            </div>
          </div>
        );
      },
    },
    {
      title: '物品类别',
      dataIndex: 'project',
      key: 'project',
      width: 86,
      render: (proj: ProjectCode) => (
        <Tag color={proj === 'fashion' ? 'blue' : 'gold'}>{PROJECT_SHORT_LABELS[proj]}</Tag>
      ),
    },
    {
      title: '商品名称',
      key: 'name',
      width: 250,
      render: (_, record) =>
        record.profile?.name ? (
          <div>
            <div className="font-medium text-slate-800 truncate max-w-[230px]">
              {record.profile.name}
            </div>
            <div className="text-xs text-slate-500 truncate max-w-[230px]">
              {record.profile.material || '未填材质'} · 图片 {record.profile.image_urls.length} 张
            </div>
          </div>
        ) : (
          <Space size={6}>
            <Tag color="default">未填写名称</Tag>
            {record.project === 'fashion' && (
              <Button
                type="link"
                size="small"
                style={{ padding: 0, fontSize: 12 }}
                onClick={() => handleOpenProfileEditor(record)}
              >
                去补充资料
              </Button>
            )}
          </Space>
        ),
    },
    {
      title: '款式编号',
      dataIndex: 'sku_code',
      key: 'sku_code',
      width: 165,
      render: (sku: string | null, record) =>
        sku ? (
          <Space size={4}>
            <Text code>{sku}</Text>
            <Tooltip title="查看款式关联；草稿可在详情维护关联">
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={() => {
                  if (record.id === activeItemId) return;
                  guardDrawerBeforeAction(() => onSelectItemId(record.id));
                }}
              />
            </Tooltip>
          </Space>
        ) : (
          <Button
            type="link"
            size="small"
            style={{ padding: 0, fontSize: 12 }}
            onClick={() => {
              if (record.id === activeItemId) return;
              guardDrawerBeforeAction(() => onSelectItemId(record.id));
            }}
          >
            + 关联款式资料
          </Button>
        ),
    },
    {
      title: '物品启用状态',
      dataIndex: 'status',
      key: 'status',
      width: 96,
      render: (st: ItemStatus) => {
        const meta = ITEM_STATUS_META[st];
        return (
          <Tooltip title={meta.desc}>
            <Badge status={meta.badge} text={<Tag color={meta.tagColor}>{meta.label}</Tag>} />
          </Tooltip>
        );
      },
    },
    {
      title: '关联芯片',
      key: 'chip',
      width: 205,
      render: (_, record) => {
        if (!record.bound_chip_id || !record.bound_chip_uid) {
          return (
            <Space size={6}>
              <Tag color="default">未绑定芯片</Tag>
              {record.status !== 'archived' && (
                <Button
                  type="link"
                  size="small"
                  style={{ padding: 0, fontSize: 12 }}
                  onClick={() => {
                    setBindChipForItemId(record.id);
                    setSelectedPendingChipId(null);
                  }}
                >
                  + 绑定芯片
                </Button>
              )}
            </Space>
          );
        }
        return (
          <div>
            <Space size={4}>
              <Button
                type="link"
                size="small"
                icon={<LinkOutlined />}
                style={{
                  padding: 0,
                }}
                onClick={() =>
                  guardDrawerBeforeAction(() => onOpenChipDetail(record.bound_chip_id!))
                }
              >
                {record.bound_chip_uid}
              </Button>
              {record.bound_chip_status && (
                <Tag
                  color={CHIP_STATUS_META[record.bound_chip_status].tagColor}
                  style={{ margin: 0, fontSize: 11 }}
                >
                  {CHIP_STATUS_META[record.bound_chip_status].label}
                </Tag>
              )}
            </Space>
            <div className="mt-0.5 text-xs text-slate-500">
              {record.bound_chip_provisioned_at
                ? '实卡配置已核验'
                : record.bound_chip_keys_generated
                  ? '已生密钥 · 待双链接核验'
                  : '未生密钥'}
            </div>
          </div>
        );
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 148,
      render: (val: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {new Date(val).toLocaleString('zh-CN', { hour12: false })}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 110,
      fixed: 'right',
      render: (_, record) => (
        <Space size={6} wrap>
          {record.project === 'fashion' ? (
            <Button
              size="small"
              type="primary"
              ghost
              icon={<FileTextOutlined />}
              disabled={record.status === 'archived'}
              onClick={() => handleOpenProfileEditor(record)}
            >
              编辑资料
            </Button>
          ) : (
            <Text type="secondary" style={{ fontSize: 12 }}>
              —
            </Text>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {simulateApiError && (
        <Alert
          type="error"
          showIcon
          icon={<WarningOutlined />}
          message="数字物品档案列表读取失败 (500 Internal Server Error)"
          description="未能从数据库读取最新物品列表，请检查后端连接或点击重试恢复。"
          action={
            <Button size="small" type="primary" danger onClick={onRecoverApiError}>
              立即重试
            </Button>
          }
        />
      )}

      {/* 新建成功后保留原筛选并给出连续操作反馈 */}
      {recentCreatedBanner && (
        <Alert
          type="success"
          showIcon
          closable
          onClose={() => setRecentCreatedBanner(null)}
          message={
            <Text strong>
              已创建数字物品草稿：{recentCreatedBanner.item_uid}（
              {PROJECT_SHORT_LABELS[recentCreatedBanner.project]}）
            </Text>
          }
          description={
            <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
              <span>
                当前列表筛选条件已为您保留。您可以直接查看该物品详情、补充服装资料，或继续创建下一件物品。
              </span>
              <Space wrap>
                <Button
                  size="small"
                  type="primary"
                  onClick={() =>
                    guardDrawerBeforeAction(() => onSelectItemId(recentCreatedBanner.id))
                  }
                >
                  查看物品详情与维护
                </Button>
                {recentCreatedBanner.project === 'fashion' && (
                  <Button
                    size="small"
                    icon={<FileTextOutlined />}
                    onClick={() => handleOpenProfileEditor(recentCreatedBanner)}
                  >
                    立即编辑服装五项资料
                  </Button>
                )}
                <Button
                  size="small"
                  onClick={() => {
                    setCreateItemUid(suggestNextItemUid(recentCreatedBanner.project));
                    setCreateModalOpen(true);
                  }}
                >
                  继续创建下一件
                </Button>
              </Space>
            </div>
          }
        />
      )}

      {/* 筛选栏（常用筛选 + 可展开高级筛选） */}
      <Card size="small" styles={{ body: { padding: '16px 20px' } }}>
        <Row gutter={[12, 12]} align="bottom">
          <Col xs={24} md={8} lg={7}>
            <div className="text-xs font-medium text-slate-600 mb-1">关键词</div>
            <Input
              allowClear
              placeholder="搜索物品编号、款式、名称或芯片 UID"
              value={filters.keyword}
              onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              onPressEnter={handleApplyFilters}
            />
          </Col>
          <Col xs={12} md={5} lg={4}>
            <div className="text-xs font-medium text-slate-600 mb-1">物品类别</div>
            <Select
              style={{ width: '100%' }}
              value={filters.project}
              onChange={(val) => setFilters({ ...filters, project: val })}
              options={[
                { value: '', label: '全部类别' },
                { value: 'fashion', label: '服装' },
                { value: 'jewelry', label: '饰品' },
              ]}
            />
          </Col>
          <Col xs={12} md={5} lg={4}>
            <div className="text-xs font-medium text-slate-600 mb-1">物品启用状态</div>
            <Select
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(val) => setFilters({ ...filters, status: val })}
              options={[
                { value: '', label: '全部状态' },
                { value: 'draft', label: '草稿' },
                { value: 'active', label: '启用' },
                { value: 'disabled', label: '停用' },
                { value: 'archived', label: '归档' },
              ]}
            />
          </Col>
          <Col xs={24} md={6} lg={9}>
            <Space wrap>
              <Button type="primary" icon={<SearchOutlined />} onClick={handleApplyFilters}>
                查询
              </Button>
              <Button icon={<ReloadOutlined />} onClick={handleResetFilters}>
                重置
              </Button>
              <Button
                type="link"
                icon={expandAdvanced ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setExpandAdvanced(!expandAdvanced)}
              >
                {expandAdvanced ? '收起筛选' : '更多筛选'}
              </Button>
            </Space>
          </Col>
        </Row>

        {expandAdvanced && (
          <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
            <Row gutter={[12, 12]}>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">款式编号</div>
                <Input
                  allowClear
                  placeholder="输入款式编号如 BB-AW26"
                  value={filters.skuKeyword}
                  onChange={(e) => setFilters({ ...filters, skuKeyword: e.target.value })}
                  onPressEnter={handleApplyFilters}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">绑定状态</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.bindState}
                  onChange={(val) => setFilters({ ...filters, bindState: val })}
                  options={[
                    { value: '', label: '全部' },
                    { value: 'bound', label: '已绑定芯片' },
                    { value: 'unbound', label: '未绑定芯片' },
                  ]}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">物品启用状态</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.profileState}
                  onChange={(val) => setFilters({ ...filters, profileState: val })}
                  options={[
                    { value: '', label: '全部' },
                    { value: 'has_name', label: '已填写名称' },
                    { value: 'empty_name', label: '未填写名称' },
                  ]}
                />
              </Col>
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">数据性质</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.validationScope}
                  onChange={(val) => setFilters({ ...filters, validationScope: val })}
                  options={[
                    { value: '', label: '全部记录' },
                    { value: 'formal_only', label: '仅正式业务物品' },
                    { value: 'validation_only', label: '仅生产验证测试对象' },
                  ]}
                />
              </Col>
            </Row>

            <Row gutter={[12, 12]} align="bottom">
              <Col xs={24} sm={6}>
                <div className="text-xs font-medium text-slate-600 mb-1">日期类型</div>
                <Select
                  style={{ width: '100%' }}
                  value={filters.dateField}
                  onChange={(val) => setFilters({ ...filters, dateField: val })}
                  options={[
                    { value: 'created_at', label: '创建日期' },
                    { value: 'updated_at', label: '更新日期' },
                  ]}
                />
              </Col>
              <Col xs={24} sm={10}>
                <div className="text-xs font-medium text-slate-600 mb-1">日期范围</div>
                <RangePicker
                  key={dateRangeResetKey}
                  style={{ width: '100%' }}
                  onChange={(_, dateStrings) => {
                    const [start, end] = Array.isArray(dateStrings) ? dateStrings : ['', ''];
                    setFilters({
                      ...filters,
                      dateFrom: start || '',
                      dateTo: end || '',
                    });
                  }}
                />
              </Col>
            </Row>
          </div>
        )}

        {filtersDirty && (
          <Alert
            className="mt-3"
            type="info"
            showIcon
            message="筛选条件已更改，请点击「查询物品」或按回车应用筛选。"
          />
        )}

        {!expandAdvanced &&
          (appliedFilters.skuKeyword ||
            appliedFilters.bindState ||
            appliedFilters.profileState ||
            appliedFilters.validationScope ||
            appliedFilters.dateFrom ||
            appliedFilters.dateTo) && (
            <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              <span>已生效高级筛选（收起后仍保留）：</span>
              {appliedFilters.skuKeyword && (
                <Tag color="blue">款式含: {appliedFilters.skuKeyword}</Tag>
              )}
              {appliedFilters.bindState && (
                <Tag color="blue">
                  绑定: {appliedFilters.bindState === 'bound' ? '已绑定芯片' : '未绑定芯片'}
                </Tag>
              )}
              {appliedFilters.profileState && (
                <Tag color="blue">
                  资料: {appliedFilters.profileState === 'has_name' ? '已填名称' : '未填名称'}
                </Tag>
              )}
              {appliedFilters.validationScope && (
                <Tag color="blue">
                  性质: {appliedFilters.validationScope === 'formal_only' ? '仅正式' : '仅验证'}
                </Tag>
              )}
              {(appliedFilters.dateFrom || appliedFilters.dateTo) && (
                <Tag color="blue">
                  {appliedFilters.dateField === 'updated_at' ? '更新日期' : '创建日期'}:{' '}
                  {appliedFilters.dateFrom || '不限'} ~ {appliedFilters.dateTo || '不限'}
                </Tag>
              )}
            </div>
          )}
      </Card>

      {/* 物品表格 */}
      <Card
        size="small"
        title={
          <Space>
            <span>物品列表</span>
            <Tag color="blue">共 {filteredItems.length} 件</Tag>
          </Space>
        }
        extra={
          <Button
            size="small"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateProject('fashion');
              setCreateItemUid(suggestNextItemUid('fashion'));
              setCreateSkuCode('');
              setCreateIsValidation(false);
              setCreateError('');
              setCreateModalOpen(true);
            }}
          >
            创建物品草稿
          </Button>
        }
      >
        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={filteredItems}
          scroll={{ x: 1020 }}
          pagination={{
            current: currentPage,
            pageSize: 10,
            total: filteredItems.length,
            showSizeChanger: false,
            onChange: (p) => setCurrentPage(p),
            showTotal: (total) => `共 ${total} 件数字物品（每页固定 10 条）`,
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="没有符合当前筛选条件的物品记录"
              >
                <Space>
                  <Button size="small" onClick={handleResetFilters}>
                    清空筛选条件
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      setCreateItemUid(suggestNextItemUid('fashion'));
                      setCreateModalOpen(true);
                    }}
                  >
                    创建物品草稿
                  </Button>
                </Space>
              </Empty>
            ),
          }}
        />
      </Card>

      {/* 创建物品草稿弹窗 */}
      <Modal
        title="创建物品"
        open={createModalOpen}
        onCancel={closeCreate}
        width={520}
        footer={[
          <Button key="cancel" onClick={closeCreate}>
            取消
          </Button>,
          <Button key="createOnly" onClick={() => handleSubmitCreateItem(false)}>
            创建并继续
          </Button>,
          <Button
            key="createAndEdit"
            type="primary"
            onClick={() => handleSubmitCreateItem(true)}
          >
            {createProject === 'fashion' ? '创建并完善身份' : '创建并打开详情'}
          </Button>,
        ]}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="物品类别（款式引用）" extra="类别只在款式维护，创建物品不单独选择。"><Input readOnly value={createSkuCode?(createProject==='fashion'?'服装':'饰品'):'选择款式后确定'}/></Form.Item>

          <Form.Item
            label="物品编号"
            extra={
              <Button
                type="link"
                size="small"
                style={{ padding: 0 }}
                onClick={() => {
                  setCreateItemUid(suggestNextItemUid(createProject));
                  setCreateError('');
                }}
              >
                〔演示〕填入建议编号
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Input
              placeholder={
                createProject === 'fashion' ? 'FASH-2026-000007' : 'JEW-2026-000003'
              }
              value={createItemUid}
              onChange={(e) => {
                setCreateItemUid(e.target.value);
                setCreateError('');
              }}
            />
          </Form.Item>

          <Form.Item label="关联款式商品资料" required extra="本轮原型先选择已有款式再创建；款式在“款式资料”工作区维护。无款式草稿流程待确认。">
            <Select allowClear showSearch optionFilterProp="label" placeholder="选择已有款式" value={proto.styles.find(s=>s.code===createSkuCode&&s.project===createProject)?.id} onChange={value=>{const style=proto.styles.find(s=>s.id===value);setCreateSkuCode(style?.code||'');if(style){setCreateProject(style.project);setCreateItemUid(suggestNextItemUid(style.project));}setCreateError('');}} options={proto.styles.map(s=>({value:s.id,label:s.code+' · '+s.profile.name+' · '+(s.project==='fashion'?'服装':'饰品')}))}/>
          </Form.Item>

          <Form.Item label="生产验证测试对象" style={{ marginBottom: createError ? 16 : 0 }}>
            <Space>
              <Switch checked={createIsValidation} onChange={setCreateIsValidation} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                仅标记与筛选；不直接赋予删除资格
              </Text>
            </Space>
          </Form.Item>

          {createError && <Alert type="error" showIcon message={createError} />}
        </Form>
      </Modal>

      {/* 服装基础资料编辑弹窗（5项字段 + 右侧实时手机端预览） */}
      <Modal
        title={
          profileModalItem ? (
            <Space>
              <span>编辑服装资料</span>
              <Text code>{profileModalItem.item_uid}</Text>
            </Space>
          ) : (
            '编辑服装资料'
          )
        }
        open={profileModalItem !== null}
        onCancel={() => {
          if (profDirty) {
            Modal.confirm({
              title: '放弃未保存的服装资料修改？',
              content:
                '当前款式编号、服装资料或新上传的 Pending 暂存图片尚未保存；关闭后已关联原图不会被删除，确定关闭吗？',
              okText: '确认放弃',
              cancelText: '返回保存',
              onOk: () => setProfileModalItemId(null),
            });
            return;
          }
          setProfileModalItemId(null);
        }}
        width={1040}
        footer={[
          <Button
            key="cancel"
            onClick={() => {
              if (profDirty) {
                Modal.confirm({
                  title: '放弃未保存的服装资料修改？',
                  content:
                    '当前款式编号、服装资料或新上传的 Pending 暂存图片尚未保存；关闭后已关联原图不会被删除，确定关闭吗？',
                  okText: '确认放弃',
                  cancelText: '返回保存',
                  onOk: () => setProfileModalItemId(null),
                });
                return;
              }
              setProfileModalItemId(null);
            }}
          >
            取消
          </Button>,
          <Button key="save" type="primary" onClick={validateAndSubmitFashionProfile}>
            保存
          </Button>,
        ]}
      >
        {profileModalItem && (
          <Row gutter={24} className="pt-2">
            <Col xs={24} lg={14}>
              <Form layout="vertical">
                <Row gutter={12}>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="款式编号"
                      validateStatus={[...profSkuCode.trim()].length > 64 ? 'error' : undefined}
                      help={
                        [...profSkuCode.trim()].length > 64
                          ? `最多 64 个字符（当前 ${[...profSkuCode.trim()].length}/64）`
                          : undefined
                      }
                      style={{ marginBottom: 14 }}
                    >
                      <Input
                        allowClear
                        placeholder="选填，如 BB-AW26-BLAZER-BLK-M"
                        value={profSkuCode}
                        onChange={(e) => {
                          setProfSkuCode(e.target.value);
                          setProfDirty(true);
                        }}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="服装名称"
                      required
                      validateStatus={[...profName.trim()].length > 128 ? 'error' : undefined}
                      help={
                        [...profName.trim()].length > 128
                          ? `最多 128 个字符（当前 ${[...profName.trim()].length}/128）`
                          : undefined
                      }
                      style={{ marginBottom: 14 }}
                    >
                      <Input
                        allowClear
                        placeholder="如 BUMBUM 解构重磅羊毛西装外套 · 曜石黑"
                        value={profName}
                        onChange={(e) => {
                          setProfName(e.target.value);
                          setProfDirty(true);
                        }}
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item
                  label="服装介绍"
                  validateStatus={[...profDesc.trim()].length > 4000 ? 'error' : undefined}
                  help={
                    [...profDesc.trim()].length > 4000
                      ? `最多 4000 个字符（当前 ${[...profDesc.trim()].length}/4000）`
                      : undefined
                  }
                  style={{ marginBottom: 14 }}
                >
                  <TextArea
                    rows={2}
                    placeholder="选填，填写单品设计灵感、版型特点与数字防伪说明"
                    value={profDesc}
                    onChange={(e) => {
                      setProfDesc(e.target.value);
                      setProfDirty(true);
                    }}
                  />
                </Form.Item>

                <Row gutter={12}>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="材质说明"
                      validateStatus={[...profMaterial.trim()].length > 256 ? 'error' : undefined}
                      help={
                        [...profMaterial.trim()].length > 256
                          ? `最多 256 个字符（当前 ${[...profMaterial.trim()].length}/256）`
                          : undefined
                      }
                      style={{ marginBottom: 14 }}
                    >
                      <Input
                        allowClear
                        placeholder="选填，如 92% 澳洲美利奴初剪羊毛"
                        value={profMaterial}
                        onChange={(e) => {
                          setProfMaterial(e.target.value);
                          setProfDirty(true);
                        }}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={12}>
                    <Form.Item
                      label="洗护说明"
                      validateStatus={[...profCare.trim()].length > 2000 ? 'error' : undefined}
                      help={
                        [...profCare.trim()].length > 2000
                          ? `最多 2000 个字符（当前 ${[...profCare.trim()].length}/2000）`
                          : undefined
                      }
                      style={{ marginBottom: 14 }}
                    >
                      <Input
                        allowClear
                        placeholder="选填，填写干洗、水温及熨烫养护提示"
                        value={profCare}
                        onChange={(e) => {
                          setProfCare(e.target.value);
                          setProfDirty(true);
                        }}
                      />
                    </Form.Item>
                  </Col>
                </Row>

                {(profileModalItem.profile as FashionProfile | null)?.size_chart && (
                  <div className="p-2.5 rounded bg-slate-50 border border-slate-200 text-xs mb-3">
                    <div className="text-slate-500 mb-0.5">尺码表</div>
                    <div className="font-mono text-slate-700">
                      {(profileModalItem.profile as FashionProfile).size_chart}
                    </div>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-medium">
                      商品图片 ({profAssets.length}/20)
                    </span>
                    <Space size={6}>
                      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-purple-50 border border-dashed border-purple-200">
                        <Tag color="purple" style={{ margin: 0, fontSize: 10 }}>
                          图片上传服务
                        </Tag>
                        <Switch
                          size="small"
                          checked={mediaEnabledSim}
                          onChange={(checked) => setMediaEnabledSim(checked)}
                        />
                      </div>
                    </Space>
                  </div>

                  {/* Ant Design Upload 受控上传区 */}
                  <div className="p-3 rounded-lg bg-slate-50 border border-dashed border-slate-300 mb-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Upload
                        accept="image/jpeg,image/png,image/webp"
                        multiple
                        showUploadList={false}
                        beforeUpload={handleLocalFileUpload}
                      >
                        <Button
                          size="small"
                          type="primary"
                          ghost
                          icon={<CloudUploadOutlined />}
                          disabled={profAssets.length >= 20}
                        >
                          上传本地图片
                        </Button>
                      </Upload>
                      <Space size={6} wrap>
                        <Button
                          size="small"
                          onClick={() => handleSimulateManagedUpload(false)}
                          disabled={profAssets.length >= 20}
                        >
                          + 示例实拍图
                        </Button>
                        <Tooltip title="模拟上传网关超时未收到回执，演示先通过 GET /status 核对并复用已完成结果">
                          <Button
                            size="small"
                            onClick={() => handleSimulateManagedUpload(true)}
                            disabled={profAssets.length >= 20}
                          >
                            + 模拟超时核对
                          </Button>
                        </Tooltip>
                      </Space>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        placeholder="或输入外部 HTTP/HTTPS 图片链接..."
                        value={externalUrlInput}
                        onChange={(e) => setExternalUrlInput(e.target.value)}
                        onPressEnter={handleAddExternalUrl}
                      />
                      <Button
                        icon={<PlusOutlined />}
                        disabled={profAssets.length >= 20}
                        onClick={handleAddExternalUrl}
                      >
                        添加链接
                      </Button>
                    </div>
                  </div>

                  {profAssets.length === 0 ? (
                    <div className="p-3 rounded bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
                      暂未关联任何图片，可点击上方「选择本地图片上传暂存」或「演示上传实拍图」
                    </div>
                  ) : (
                    <div className="space-y-1.5 max-h-[210px] overflow-y-auto pr-1">
                      {profAssets.map((asset, idx) => (
                        <div
                          key={asset.asset_id}
                          className="flex items-center justify-between gap-2 p-2 rounded border border-slate-200 bg-white"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <Tag color={idx === 0 ? 'blue' : 'default'} style={{ margin: 0 }}>
                              #{idx + 1}
                            </Tag>
                            <img
                              src={asset.preview_url || asset.url}
                              alt=""
                              referrerPolicy="no-referrer"
                              className="w-10 h-10 object-cover rounded border border-slate-200 shrink-0 bg-slate-100"
                            />
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-xs font-medium text-slate-800 truncate max-w-[180px]">
                                  {asset.filename || '图片资源'}
                                </span>
                                {asset.state === 'attached' && (
                                  <Tag color="success" style={{ margin: 0, fontSize: 10 }}>
                                    已关联 (Attached)
                                  </Tag>
                                )}
                                {asset.state === 'pending' && (
                                  <Tag color="processing" style={{ margin: 0, fontSize: 10 }}>
                                    暂存待保存 (Pending)
                                  </Tag>
                                )}
                                {asset.state === 'unknown_status' && (
                                  <Tag color="warning" style={{ margin: 0, fontSize: 10 }}>
                                    回执未知 · 待核对
                                  </Tag>
                                )}
                                <Tag style={{ margin: 0, fontSize: 10 }}>
                                  {asset.source_type === 'managed' ? '私有WebP' : '外部URL'}
                                </Tag>
                              </div>
                              <div className="text-[11px] text-slate-400 font-mono truncate max-w-[300px]">
                                {asset.dimensions
                                  ? `${asset.dimensions} · ${asset.size_kb || 320} KB`
                                  : asset.url}
                              </div>
                            </div>
                          </div>
                          <Space size={4}>
                            {asset.state === 'unknown_status' && (
                              <Button
                                size="small"
                                type="primary"
                                ghost
                                icon={<SyncOutlined />}
                                onClick={() => {
                                  setProfAssets((prev) =>
                                    prev.map((a) =>
                                      a.asset_id === asset.asset_id
                                        ? { ...a, state: 'pending' }
                                        : a
                                    )
                                  );
                                  setProfError('');
                                  message.success(
                                    'GET .../status 核对成功：服务端已完成 WebP 转码，已复用该 Pending 暂存结果'
                                  );
                                }}
                              >
                                核对状态
                              </Button>
                            )}
                            <Tooltip title="上移顺序">
                              <Button
                                size="small"
                                icon={<ArrowUpOutlined />}
                                disabled={idx === 0}
                                onClick={() => moveAsset(idx, -1)}
                              />
                            </Tooltip>
                            <Tooltip title="下移顺序">
                              <Button
                                size="small"
                                icon={<ArrowDownOutlined />}
                                disabled={idx === profAssets.length - 1}
                                onClick={() => moveAsset(idx, 1)}
                              />
                            </Tooltip>
                            <Tooltip
                              title={
                                asset.state === 'attached'
                                  ? '从当前列表移除（保存后转入 retired 保留 7 天）'
                                  : '取消本次暂存图'
                              }
                            >
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() => {
                                  setProfAssets(profAssets.filter((_, i) => i !== idx));
                                  setProfDirty(true);
                                }}
                              />
                            </Tooltip>
                          </Space>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {profError && <Alert className="mt-3" type="error" showIcon message={profError} />}
              </Form>
            </Col>

            {/* 右侧：手机端碰一碰实时预览卡片 */}
            <Col xs={24} lg={10}>
              <div className="p-4 rounded-xl bg-slate-900 text-white space-y-3 h-full">
                <div className="flex items-center justify-between border-b border-slate-700 pb-2">
                  <Space size={6}>
                    <MobileOutlined className="text-blue-400" />
                    <span className="text-xs font-medium text-slate-300">
                      手机碰一碰验证页实时预览
                    </span>
                  </Space>
                  <Tag color="success" style={{ margin: 0, fontSize: 11 }}>
                    正品已核验
                  </Tag>
                </div>

                {profAssets.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2">
                    {profAssets.slice(0, 2).map((asset, i) => (
                      <div key={asset.asset_id} className="relative">
                        <img
                          src={asset.preview_url || asset.url}
                          alt={`预览图 ${i + 1}`}
                          referrerPolicy="no-referrer"
                          className="w-full h-28 object-cover rounded-lg bg-slate-800 border border-slate-700"
                        />
                        <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[10px] bg-black/65 text-white">
                          {asset.state === 'pending' ? '暂存预览' : `#${i + 1}`}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-28 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-xs text-slate-400">
                    暂无图片预览（支持受控私有 WebP 与外部 URL）
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between text-xs text-blue-400 font-mono">
                    <span>{profileModalItem.item_uid}</span>
                    {profSkuCode.trim() && (
                      <span className="text-slate-400">SKU: {profSkuCode.trim()}</span>
                    )}
                  </div>
                  <div className="text-base font-semibold mt-0.5">
                    {profName.trim() || '（请填写服装名称）'}
                  </div>
                </div>

                <div className="space-y-2 text-xs text-slate-300 bg-slate-800/90 p-3 rounded-lg">
                  <div>
                    <span className="text-slate-400 block mb-0.5">单品介绍：</span>
                    <p className="whitespace-pre-wrap text-slate-200">
                      {profDesc.trim() || '暂无介绍'}
                    </p>
                  </div>
                  <Divider style={{ margin: '8px 0', borderColor: '#334155' }} />
                  <div>
                    <span className="text-slate-400">材质成分：</span>
                    <span className="text-slate-200">{profMaterial.trim() || '暂无材质说明'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">洗护指南：</span>
                    <p className="whitespace-pre-wrap text-slate-200">
                      {profCare.trim() || '暂无洗护说明'}
                    </p>
                  </div>
                </div>
              </div>
            </Col>
          </Row>
        )}
      </Modal>

      {/* 统一的物品详情与维护抽屉 */}
      <PrototypeItemDetails item={activeItem} onClose={()=>onSelectItemId(null)} onOpenChip={onOpenChipDetail}/>


      {/* 1. 修改未绑定草稿物品编号/项目弹窗 */}
      <Modal
        title="修改物品编号 ／ 物品类别"
        open={editIdentityModalOpen && activeItem !== null}
        onCancel={() => setEditIdentityModalOpen(false)}
        okText="确认修改"
        okButtonProps={{ disabled: !editIdentityUid.trim() || !editIdentityReason.trim() }}
        onOk={() => {
          if (!activeItem) return;
          setEditIdentityError('');
          const check = validateItemUid(editIdentityProject, editIdentityUid);
          if (!check.ok) {
            setEditIdentityError(check.error);
            return;
          }
          const res = onCorrectItemIdentity(
            activeItem.id,
            editIdentityProject,
            check.item_uid,
            editIdentityReason.trim()
          );
          if (!res.ok) {
            setEditIdentityError(res.error || '修改失败');
            return;
          }
          message.success(`已修改物品身份为 ${check.item_uid}`);
          setEditIdentityModalOpen(false);
        }}
        width={480}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Row gutter={12}>
            <Col span={9}>
              <Form.Item label="物品类别" style={{ marginBottom: 16 }}>
                <Select
                  style={{ width: '100%' }}
                  value={editIdentityProject}
                  onChange={(val) => {
                    setEditIdentityProject(val);
                    setEditIdentityUid(suggestNextItemUid(val));
                    setEditIdentityError('');
                  }}
                  options={[
                    { value: 'fashion', label: '服装' },
                    { value: 'jewelry', label: '饰品' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={15}>
              <Form.Item label="修正后物品编号" required style={{ marginBottom: 16 }}>
                <Input
                  value={editIdentityUid}
                  onChange={(e) => {
                    setEditIdentityUid(e.target.value);
                    setEditIdentityError('');
                  }}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="修改原因"
            required
            style={{ marginBottom: editIdentityError ? 16 : 0 }}
          >
            <Input
              allowClear
              placeholder="如：建档时录入错序号，尚未绑卡，现修正编号"
              value={editIdentityReason}
              onChange={(e) => setEditIdentityReason(e.target.value)}
            />
          </Form.Item>
          {editIdentityError && <Alert type="error" showIcon message={editIdentityError} />}
        </Form>
      </Modal>

      {/* 2. 删除未绑定草稿物品弹窗 */}
      <Modal
        title="删除物品草稿"
        open={deleteDraftModalOpen && activeItem !== null}
        onCancel={() => setDeleteDraftModalOpen(false)}
        okText="确认删除"
        okButtonProps={{ danger: true, disabled: !deleteDraftReason.trim() }}
        onOk={() => {
          if (!activeItem) return;
          const res = onDeleteL1Item(activeItem.id, deleteDraftReason.trim());
          if (res.ok) {
            message.success(`已删除物品草稿 ${activeItem.item_uid}`);
            setDeleteDraftModalOpen(false);
            onSelectItemId(null);
          } else {
            message.error(res.error || '删除失败');
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="删除原因" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：测试建档或重复创建的空草稿"
              value={deleteDraftReason}
              onChange={(e) => setDeleteDraftReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 3. 从物品详情解绑未核验芯片弹窗 */}
      <Modal
        title="解绑关联芯片"
        open={unbindChipModalOpen && activeItem !== null}
        onCancel={() => setUnbindChipModalOpen(false)}
        okText="确认解绑"
        okButtonProps={{ disabled: !unbindChipReason.trim() }}
        onOk={() => {
          if (!activeItem?.bound_chip_id) return;
          const res = onUnbindOrRebindMisboundChip(
            activeItem.bound_chip_id,
            'unbind_to_pending',
            null,
            unbindChipReason.trim()
          );
          if (res.ok) {
            message.success('已解除与芯片的绑定');
            setUnbindChipModalOpen(false);
          } else {
            message.error(res.error || '解绑失败');
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="解绑原因" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：配卡前发现绑错芯片，解除关联重新绑定"
              value={unbindChipReason}
              onChange={(e) => setUnbindChipReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 4. 从物品详情挂失芯片弹窗 */}
      <Modal
        title="挂失关联芯片"
        open={lostChipModalOpen && activeItem !== null}
        onCancel={() => setLostChipModalOpen(false)}
        okText="确认挂失"
        okButtonProps={{ danger: true, disabled: !lostChipReason.trim() }}
        onOk={() => {
          if (!activeItem?.bound_chip_id) return;
          const res = onReportChipLost(activeItem.bound_chip_id, lostChipReason.trim());
          if (res.ok) {
            message.warning(`已将芯片 ${activeItem.bound_chip_uid} 标记为挂失`);
            setLostChipModalOpen(false);
          } else {
            message.error(res.error || '挂失失败');
          }
        }}
        width={460}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item style={{ marginBottom: 16 }}>
            <Alert
              type="warning"
              showIcon
              message={`挂失后将立即阻断原芯片 ${activeItem?.bound_chip_uid} 的碰卡验证与持续查看会话，本物品档案与持有人权益保留，随后可点击「更换新芯片」完成接续。`}
            />
          </Form.Item>
          <Form.Item label="挂失原因" required style={{ marginBottom: 0 }}>
            <Input
              allowClear
              placeholder="如：客户反馈干洗后芯片损坏无法感应"
              value={lostChipReason}
              onChange={(e) => setLostChipReason(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 5. 从物品详情更换新芯片弹窗 */}
      <Modal
        title={activeItem ? `更换新芯片 · ${activeItem.item_uid}` : '更换新芯片'}
        open={replaceChipModalOpen && activeItem !== null}
        onCancel={() => setReplaceChipModalOpen(false)}
        okText="确认换卡并退役旧卡"
        okButtonProps={{ disabled: !replaceNewChipId || !replaceReason.trim() }}
        onOk={() => {
          if (!activeItem || !replaceNewChipId) return;
          const res = onExecuteCarrierReplacement({
            itemId: activeItem.id,
            newChipId: replaceNewChipId,
            scenario: replaceScenario,
            reason: replaceReason.trim(),
          });
          if (res.ok) {
            message.success('已完成新芯片接续，原芯片已退役');
            setReplaceChipModalOpen(false);
          } else {
            message.error(res.error || '换卡失败');
          }
        }}
        width={540}
      >
        {activeItem && (
          <Form layout="vertical" style={{ marginTop: 12 }}>
            <Form.Item label="换卡场景" style={{ marginBottom: 16 }}>
              <Radio.Group
                value={replaceScenario}
                onChange={(e) => setReplaceScenario(e.target.value)}
              >
                <Radio value="loss_replacement">损坏/遗失补卡（保持原持有人权益）</Radio>
                <Radio value="resale_new_carrier">官方回收转售换新卡</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item label="选择接续的待绑定新芯片" required style={{ marginBottom: 16 }}>
              <Select
                style={{ width: '100%' }}
                placeholder="请选择一枚待绑定芯片"
                value={replaceNewChipId}
                onChange={(val) => setReplaceNewChipId(val)}
                options={candidatePendingChipsForActiveItem.map((c) => ({
                  value: c.id,
                  label: `${c.chip_uid}（${
                    c.project ? PROJECT_SHORT_LABELS[c.project] : '未关联物品'
                  }${c.batch_no ? ` · 批次 ${c.batch_no}` : ''}）`,
                }))}
              />
            </Form.Item>

            <Form.Item label="换卡原因" required style={{ marginBottom: 0 }}>
              <Input
                allowClear
                placeholder="请填写换卡原因"
                value={replaceReason}
                onChange={(e) => setReplaceReason(e.target.value)}
              />
            </Form.Item>
          </Form>
        )}
      </Modal>

      {/* 从物品直接选择待绑定芯片的弹窗 */}
      <Modal
        title={
          bindChipTargetItem
            ? `为物品 ${bindChipTargetItem.item_uid} 绑定实体芯片`
            : '绑定实体芯片'
        }
        open={bindChipTargetItem !== null}
        onCancel={() => setBindChipForItemId(null)}
        okText="确认绑定所选芯片"
        okButtonProps={{ disabled: !selectedPendingChipId }}
        onOk={() => {
          if (!bindChipTargetItem || !selectedPendingChipId) return;
          const res = onBindChipToItem(selectedPendingChipId, bindChipTargetItem.id);
          if (res.ok) {
            message.success(
              `已将芯片 ${res.chip?.chip_uid} 绑定至物品 ${bindChipTargetItem.item_uid}`
            );
            setBindChipForItemId(null);
          } else {
            message.error(res.error || '绑定失败');
          }
        }}
        width={640}
      >
        {bindChipTargetItem && (
          <div className="space-y-3 pt-2">
            <Alert
              type="info"
              showIcon
              message={`仅展示同类别 (${PROJECT_SHORT_LABELS[bindChipTargetItem.project]}) 或未关联物品的「待绑定」芯片（共 ${candidatePendingChipsForItem.length} 枚可选）`}
            />
            <Table
              rowKey="id"
              size="small"
              pagination={{ pageSize: 5, showSizeChanger: false }}
              dataSource={candidatePendingChipsForItem}
              onRow={(record) => ({
                onClick: () => setSelectedPendingChipId(record.id),
                style: {
                  cursor: 'pointer',
                  background: selectedPendingChipId === record.id ? '#eff6ff' : undefined,
                },
              })}
              columns={[
                {
                  title: '选择',
                  width: 60,
                  render: (_, r) => (
                    <Radio
                      checked={selectedPendingChipId === r.id}
                      aria-label={`选择待绑定芯片 ${r.chip_uid}`}
                      onChange={() => setSelectedPendingChipId(r.id)}
                    />
                  ),
                },
                {
                  title: '芯片 UID',
                  dataIndex: 'chip_uid',
                  render: (u: string) => <Text code>{u}</Text>,
                },
                {
                  title: '物品类别（引用）',
                  dataIndex: 'project',
                  render: (p: ProjectCode | null) =>
                    p ? <Tag color="blue">{PROJECT_SHORT_LABELS[p]}</Tag> : <Tag>未分配</Tag>,
                },
                {
                  title: '批次号',
                  dataIndex: 'batch_no',
                  render: (b: string | null) => b || '未填写',
                },
              ]}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};
