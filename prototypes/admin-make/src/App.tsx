import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  App as AntdApp,
  Badge,
  Button,
  Card,
  Col,
  ConfigProvider,
  Divider,
  Dropdown,
  Modal,
  Form,
  Input,
  Layout,
  Menu,
  Row,
  Space,
  Switch,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import zhCN from 'antd/locale/zh_CN';
import {
  AppstoreOutlined,
  AuditOutlined,
  CheckCircleOutlined,
  CloudServerOutlined,
  LinkOutlined,
  LockOutlined,
  LogoutOutlined,
  ReloadOutlined,
  ShoppingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  INITIAL_AUDIT_LOGS,
  INITIAL_CHIPS,
  INITIAL_ITEMS,
  INITIAL_TAP_EVENTS,
  type AuditLogEntry,
  type ChipView,
  type FashionProfile,
  type ItemImageAsset,
  type ItemStatus,
  type ItemView,
  type ProjectCode,
  type RegistrationSource,
  type TapEventRecord,
} from './data/mockBackend';
import {
  OverviewPage,
  type ChipPresetFilter,
  type ItemPresetFilter,
} from './components/OverviewPage';
import { ChipManagementPage } from './components/ChipManagementPage';
import {CatalogPage} from './components/CatalogManagement';
import {AfterSalesRecords} from './components/WorkRecordsPage';
import {FirstSalesPage} from './components/FirstSalesPage';
import {BusinessOverview,SaleWorkspace} from './components/SaleWorkspace';
import type {FirstDelivery} from './data/firstSales';
import { ItemManagementPage } from './components/ItemManagementPage';
import {PrototypeProvider,usePrototype} from './data/prototypeStore';
import {PrototypeOverlays,pendingPolicy} from './components/PrototypeItemDetails';
import {LifecyclePage} from './components/LifecyclePage';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

type NavPageKey = 'overview' | 'commerce' | 'delivery' | 'chips' | 'items' | 'audit' | 'checks';

const PAGE_TITLES: Record<NavPageKey, { title: string; subtitle: string }> = {
  commerce:{title:'商品与发售',subtitle:'商品准备、发行规则、多店销售与期末封版'},
  delivery:{title:'交付与售后',subtitle:'按任务处理生产、验收、配卡、发货与接续'},
  overview: {
    title: '工作台总览',
    subtitle: '全局库存概况与有效触碰统计',
  },
  chips: {
    title: '物品与芯片',
    subtitle: '芯片登记、批次维护、关联引用与配置核验',
  },
  items: {
    title: '物品与芯片',
    subtitle: '数字物品、共用款式、发行约定与办理记录',
  },
  audit: {
    title: '系统管理',
    subtitle: '管理员关键操作审计记录',
  },
  checks: {
    title: '系统管理',
    subtitle: '服务进程与数据库连接状态检查',
  },
};

const UNIFIED_FONT_FAMILY =
  'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif';

// 旧工作区链接指向重组后的业务位置，保留既有查询参数。
function routePage(key:string,query:URLSearchParams):NavPageKey {
  if(key==='items'&&['styles','issues'].includes(query.get('view')||''))return 'commerce';
  if(key==='items'&&query.get('view')==='works')return 'delivery';
  return ['overview','commerce','delivery','chips','items','audit','checks'].includes(key)?key as NavPageKey:'overview';
}
function AppCore() {
  const proto=usePrototype();
  // 登录会话状态（默认已作为管理员 cece 登录，支持退出返回登录页完整验证登录流程）
  const [authenticatedUser, setAuthenticatedUser] = useState<string | null>(null);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [loginError, setLoginError] = useState('');

  // 导航与跨页抽屉联动状态
  const [currentPage, setCurrentPage] = useState<NavPageKey>(()=>routePage(location.hash.slice(1).split('?')[0],new URLSearchParams(location.hash.split('?')[1])));
  const [saleId,setSaleId]=useState<string|null>(()=>new URLSearchParams(location.hash.split('?')[1]).get('sale'));
  const [saleTab,setSaleTab]=useState(()=>new URLSearchParams(location.hash.split('?')[1]).get('saleTab')||'overview');
  const [commerceView,setCommerceView]=useState(()=>new URLSearchParams(location.hash.split('?')[1]).get('commerceView')||(['styles','issues'].includes(new URLSearchParams(location.hash.split('?')[1]).get('view')||'')?new URLSearchParams(location.hash.split('?')[1]).get('view')!:'sales'));
  const [newSaleStyle,setNewSaleStyle]=useState<string|undefined>();
  const [firstRecordId,setFirstRecordId]=useState<string|null>(()=>new URLSearchParams(location.hash.split('?')[1]).get('first'));
  const [deliveryView,setDeliveryView]=useState(()=>new URLSearchParams(location.hash.split('?')[1]).get('deliveryView')||'first');
  const [taskReturn,setTaskReturn]=useState<{page:'commerce'|'delivery';saleId?:string|null;recordId?:string|null;itemId?:number}|null>(()=>{try{return JSON.parse(sessionStorage.getItem('bumbum-task-return')||'null');}catch{return null;}});
  useEffect(()=>{sessionStorage.setItem('bumbum-task-return',JSON.stringify(taskReturn));},[taskReturn]);
  const selectSale=(id:string|null,tab='overview')=>{setSaleId(id);setSaleTab(tab);setCommerceView('sales');setCurrentPage('commerce');};
  const captureTask=(record?:FirstDelivery)=>{if(currentPage==='commerce'||currentPage==='delivery')setTaskReturn({page:currentPage,saleId:record?.planId||saleId,recordId:record?.id||firstRecordId,itemId:record?.itemId});};
  const returnToTask=()=>{if(!taskReturn)return;setCurrentPage(taskReturn.page);setSaleId(taskReturn.saleId||null);setSaleTab('orders');setCommerceView('sales');setFirstRecordId(taskReturn.recordId||null);setTaskReturn(null);};
  const [activeChipId, setActiveChipId] = useState<number | null>(()=>Number(new URLSearchParams(location.hash.split('?')[1]).get('chip'))||null);
  const [activeItemId, setActiveItemId] = useState<number | null>(()=>Number(new URLSearchParams(location.hash.split('?')[1]).get('item'))||null);
  const [chipPresetFilter, setChipPresetFilter] = useState<{
    type: ChipPresetFilter;
    nonce: number;
  } | null>(null);
  const [itemPresetFilter, setItemPresetFilter] = useState<{
    type: ItemPresetFilter;
    nonce: number;
  } | null>(null);

  // 核心业务状态
  const {chips,setChips}=proto;
  const {items,setItems}=proto;
  const [tapEvents, setTapEvents] = useState<TapEventRecord[]>(()=>INITIAL_TAP_EVENTS.map(e=>({...e,beijing_date:new Date(new Date(e.beijing_date+'T00:00:00Z').getTime()+8*86400000).toISOString().slice(0,10),tapped_at:new Date(new Date(e.tapped_at).getTime()+8*86400000).toISOString()})));
  const {auditLogs,setAuditLogs}=proto;
  const [excludeValidationInStats, setExcludeValidationInStats] = useState<boolean>(false);

  // 服务与数据库检查状态
  const [healthChecking, setHealthChecking] = useState(false);
  const [simulateApiError, setSimulateApiError] = useState(false);
  const [simulateLoading,setSimulateLoading]=useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<string>(() =>
    new Date().toLocaleTimeString('zh-CN', { hour12: false })
  );

  const workOrigin=useRef<'detail'|'records'>('detail');
  useEffect(()=>{if(proto.activeWorkId||proto.activeDraft){workOrigin.current=currentPage==='delivery'&&!activeItemId?'records':'detail';setActiveChipId(null);setActiveItemId(null);}},[proto.activeWorkId,proto.activeDraft]);
  const lastUrl=useRef(location.hash), routeReady=useRef(false), fromHistory=useRef(false);
  useEffect(()=>{
    const params=new URLSearchParams(location.hash.split('?')[1]);
    activeItemId?params.set('item',String(activeItemId)):params.delete('item');
    activeChipId?params.set('chip',String(activeChipId)):params.delete('chip');
    params.delete('view');
    params.set('commerceView',commerceView);params.set('deliveryView',deliveryView);
    saleId?params.set('sale',saleId):params.delete('sale');params.set('saleTab',saleTab);firstRecordId?params.set('first',firstRecordId):params.delete('first');
    const next='#'+currentPage+(params.size?'?'+params.toString():'');
    const oldParams=new URLSearchParams(location.hash.split('?')[1]);
    const changed=location.hash.slice(1).split('?')[0]!==currentPage||oldParams.get('item')!==params.get('item')||oldParams.get('chip')!==params.get('chip')||oldParams.get('view')!==params.get('view')||oldParams.get('sale')!==params.get('sale')||oldParams.get('saleTab')!==params.get('saleTab')||oldParams.get('first')!==params.get('first')||oldParams.get('commerceView')!==commerceView||oldParams.get('deliveryView')!==deliveryView;
    if(routeReady.current&&changed&&!fromHistory.current)history.pushState(null,'',next);else history.replaceState(null,'',next);
    lastUrl.current=next;routeReady.current=true;fromHistory.current=false;
  },[currentPage,activeItemId,activeChipId,saleId,saleTab,firstRecordId,commerceView,deliveryView]);
  useEffect(()=>{const move=()=>{
    const requested=location.hash,[key,query]=requested.slice(1).split('?');
    if(!['overview','commerce','delivery','chips','items','audit','checks'].includes(key))return;
    history.replaceState(null,'',lastUrl.current||'#overview');
    proto.guard(()=>{fromHistory.current=true;history.replaceState(null,'',requested);proto.closeWork();const q=new URLSearchParams(query);setCurrentPage(routePage(key,q));setCommerceView(q.get('commerceView')||(['styles','issues'].includes(q.get('view')||'')?q.get('view')!:'sales'));setDeliveryView(q.get('deliveryView')||'first');setSaleId(q.get('sale'));setSaleTab(q.get('saleTab')||'overview');setFirstRecordId(q.get('first'));setActiveItemId(Number(q.get('item'))||null);setActiveChipId(Number(q.get('chip'))||null);});
  };window.addEventListener('popstate',move);return()=>window.removeEventListener('popstate',move);},[]);
  useEffect(()=>{if(proto.catalogOpen){proto.setCatalogOpen(false);proto.setIssuanceItemId(null);setActiveItemId(null);setCurrentPage('commerce');setCommerceView('styles');}},[proto.catalogOpen]);
  const appendAudit = (
    category: AuditLogEntry['category'],
    action: string,
    target: string,
    detail: string
  ) => {
    const entry: AuditLogEntry = {
      id: `aud-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date().toISOString(),
      operator: authenticatedUser || 'cece',
      category,
      action,
      target,
      detail,
    };
    setAuditLogs((prev) => [entry, ...prev]);
  };

  // 双向跳转：从任意位置打开某个芯片详情抽屉
  const handleOpenChipDetailFromAnywhere = (chipId: number) => {
    setActiveItemId(null);
    setCurrentPage('chips');
    setActiveChipId(chipId);
  };

  // 双向跳转：从任意位置打开某个物品详情抽屉
  const handleOpenItemDetailFromAnywhere = (itemId: number) => {
    captureTask();
    setActiveChipId(null);
    setCurrentPage('items');
    setActiveItemId(itemId);
  };

  const handleNavigateChipsWithPreset = (preset: ChipPresetFilter) => {
    setChipPresetFilter({ type: preset, nonce: Date.now() });
    setCurrentPage('chips');
  };

  const handleNavigateItemsWithPreset = (preset: ItemPresetFilter) => {
    setItemPresetFilter({ type: preset, nonce: Date.now() });
    setCurrentPage('items');
  };

  // ==================== 芯片操作处理 ====================
  const handleRegisterChip = (payload: {
    chip_uid: string;
    batch_no: string | null;
    source?: RegistrationSource;
    is_validation_object?: boolean;
  }): { chip: ChipView; is_new: boolean; error?: string } => {
    const existing = chips.find((c) => c.chip_uid === payload.chip_uid);
    if (existing) return {chip:existing,is_new:false};
    const now = new Date().toISOString();
    const newChip: ChipView = {
      id: Math.max(0, ...chips.map((c) => c.id)) + 1,
      chip_uid: payload.chip_uid,
      project: null,
      chip_status: 'pending',
      item_id: null,
      item_uid: null,
      batch_no: payload.batch_no,
      registration_source: payload.source || 'manual',
      provisioned_at: null,
      keys_generated: false,
      key_version: null,
      created_at: now,
      updated_at: now,
      is_validation_object: Boolean(payload.is_validation_object),
    };
    setChips((prev) => [newChip, ...prev]);
    appendAudit(
      'chip',
      payload.source === 'nfc_cool' ? 'webhook.admin.scan' : 'chip.register',
      newChip.chip_uid,
      `登记新芯片（来源：${newChip.registration_source}，项目：${
        newChip.project || '未分配'
      }，批次：${newChip.batch_no || '未填写'}）`
    );
    return { chip: newChip, is_new: true };
  };

  const handleUpdateChipMaintenance = (
    chipId: number,
    payload: {
      batch_no: string | null;
      is_validation_object: boolean;
      validation_note: string | null;
    }
  ) => {
    const targetBefore = chips.find(c=>c.id===chipId);
    const markerLocked=!!targetBefore?.keys_generated||!!targetBefore?.provisioned_at||!!targetBefore?.item_id;
    const now = new Date().toISOString();
    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId
          ? {
              ...c,
              batch_no: payload.batch_no,
              is_validation_object: markerLocked?c.is_validation_object:payload.is_validation_object,
              validation_note: payload.validation_note,
              updated_at: now,
            }
          : c
      )
    );
    const target = chips.find((c) => c.id === chipId);
    if (target) {
      appendAudit(
        'chip',
        'chip.maintenance.update',
        target.chip_uid,
        `更新芯片日常维护属性：batch_no=${payload.batch_no || '空'}，验证对象标识=${
          payload.is_validation_object ? '是' : '否'
        }`
      );
    }
  };

  const handleBindChipToItem = (
    chipId: number,
    itemId: number
  ): { ok: boolean; error?: string; chip?: ChipView } => {
    const chip = chips.find((c) => c.id === chipId);
    const item = items.find((i) => i.id === itemId);
    if (!chip || !item) return { ok: false, error: '找不到目标芯片或物品' };
    if (chip.chip_status !== 'pending' || chip.item_id !== null) {
      return { ok: false, error: '只有「待绑定」且未关联物品的芯片可以执行首次绑定。' };
    }
    if (item.bound_chip_id !== null) {
      return { ok: false, error: '目标物品已被其他芯片占用，不能重复绑定。' };
    }

    const now = new Date().toISOString();
    const updatedChip: ChipView = {
      ...chip,
      project: item.project,
      chip_status: 'bound',
      item_id: item.id,
      item_uid: item.item_uid,
      updated_at: now,
    };

    setChips((prev) => prev.map((c) => (c.id === chipId ? updatedChip : c)));
    setItems((prev) =>
      prev.map((i) =>
        i.id === itemId
          ? {
              ...i,
              bound_chip_id: updatedChip.id,
              bound_chip_uid: updatedChip.chip_uid,
              bound_chip_status: 'bound',
              bound_chip_keys_generated: updatedChip.keys_generated,
              bound_chip_provisioned_at: updatedChip.provisioned_at,
              carrier_generation: Math.max(1, i.carrier_generation || 1),
              carrier_history: [
                ...(i.carrier_history || []),
                {
                  id: `ch-${Date.now()}`,
                  chip_uid: updatedChip.chip_uid,
                  action: 'initial_bind',
                  timestamp: now,
                  operator: authenticatedUser || 'cece',
                  summary: `首次绑定载体芯片 ${updatedChip.chip_uid}`,
                  is_current_active: true,
                },
              ],
              updated_at: now,
            }
          : i
      )
    );

    appendAudit(
      'chip',
      'chip.bind_item',
      `${updatedChip.chip_uid} → ${item.item_uid}`,
      `完成首次绑定，芯片项目引用物品项目： ${item.project}`
    );
    return { ok: true, chip: updatedChip };
  };

  const handleGenerateChipKeys = (chipId: number): { ok: boolean; error?: string } => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip) return { ok: false, error: '芯片不存在' };
    if (chip.chip_status !== 'bound' || !chip.item_id) {
      return { ok: false, error: '请先绑定数字物品后再生成密钥。' };
    }
    if (chip.keys_generated) {
      return { ok: false, error: '该芯片已生成密钥，禁止覆盖已有密钥。' };
    }
    const now = new Date().toISOString();
    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId
          ? { ...c, keys_generated: true, key_version: 'v1', updated_at: now }
          : c
      )
    );
    setItems((prev) =>
      prev.map((i) =>
        i.id === chip.item_id
          ? { ...i, bound_chip_keys_generated: true, updated_at: now }
          : i
      )
    );
    appendAudit(
      'key_provision',
      'chip.generate_keys',
      chip.chip_uid,
      `〔演示〕仅更新密钥已准备标记，未派生、保存或操作真实密钥`
    );
    return { ok: true };
  };

  const handleConfirmChipProvisioning = (chipId: number): { ok: boolean; error?: string } => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip) return { ok: false, error: '芯片不存在' };
    if (!chip.keys_generated) return { ok: false, error: '请先生成芯片密钥' };
    const now = new Date().toISOString();
    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId
          ? { ...c, provisioned_at: now, last_counter: 2, updated_at: now }
          : c
      )
    );
    setItems((prev) =>
      prev.map((i) =>
        i.id === chip.item_id
          ? {
              ...i,
              bound_chip_provisioned_at: now,
              carrier_history: [
                ...(i.carrier_history || []),
                {
                  id: `ch-${Date.now()}`,
                  chip_uid: chip.chip_uid,
                  action: 'provisioned',
                  timestamp: now,
                  operator: authenticatedUser || 'cece',
                  summary: `〔演示〕配置核验通过样例，不构成实卡证据`,
                  is_current_active: true,
                },
              ],
              updated_at: now,
            }
          : i
      )
    );
    appendAudit(
      'key_provision',
      'chip.confirm_provisioning',
      chip.chip_uid,
      `〔演示〕仅标记配置核验结果，未执行真实实卡检查`
    );
    return { ok: true };
  };

  const handleToggleChipTempStatus = (
    chipId: number,
    targetStatus: 'disabled' | 'bound' | 'pending'
  ) => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip) return;
    const now = new Date().toISOString();
    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId ? { ...c, chip_status: targetStatus, updated_at: now } : c
      )
    );
    if (chip.item_id) {
      setItems((prev) =>
        prev.map((i) =>
          i.id === chip.item_id
            ? { ...i, bound_chip_status: targetStatus, updated_at: now }
            : i
        )
      );
    }
    appendAudit(
      'chip',
      targetStatus === 'disabled' ? 'chip.temp_disable' : 'chip.restore',
      chip.chip_uid,
      `芯片状态由 ${chip.chip_status} 切换为 ${targetStatus}（保留原绑定关联）`
    );
  };

  // ==================== 物品操作处理 ====================
  const handleCreateItemDraft = (payload: {
    project: ProjectCode;
    item_uid: string;
    sku_code: string | null;
    issuanceId:string;editionNumber:number|null;firstDeliveryId?:string;
    is_validation_object?: boolean;
  }): { ok: boolean; item?: ItemView; error?: string } => {
    const style=proto.styles.find(s=>s.code===payload.sku_code&&s.project===payload.project);
    if(!style)return{ok:false,error:'请先选择已有款式，类别从款式引用。'};
    const dup = items.find(
      (i) => i.project === payload.project && i.item_uid === payload.item_uid
    );
    if (dup) {
      return { ok: false, error: `该项目下已存在编号为 ${payload.item_uid} 的物品，不能重复创建。` };
    }
    const now = new Date().toISOString();
    const newItem: ItemView = {
      id: Math.max(0, ...items.map((i) => i.id)) + 1,
      project: payload.project,
      item_uid: payload.item_uid,
      sku_code: style.code,
      style_id:style.id,
      status: 'draft',
      created_at: now,
      updated_at: now,
      profile: style.profile,
      bound_chip_id: null,
      bound_chip_uid: null,
      bound_chip_status: null,
      bound_chip_keys_generated: false,
      bound_chip_provisioned_at: null,
      is_validation_object: Boolean(payload.is_validation_object),
      owner_status: 'unclaimed',
      carrier_generation: 0,
    };
    const saved=proto.createIdentityItem(newItem,payload.issuanceId,payload.editionNumber,payload.firstDeliveryId);
    if(!saved.ok)return saved;
    appendAudit(
      'item',
      'item.create_draft',
      newItem.item_uid,
      `创建 ${payload.project} 物品草稿（发行：${payload.issuanceId}，本件序号：${payload.editionNumber}）`
    );
    return { ok: true, item: newItem };
  };

  const handleUpdateItemMaintenance = (
    itemId: number,
    payload: {
      sku_code: string | null;
      status: ItemStatus;
      is_validation_object: boolean;
    }
  ) => {
    const now = new Date().toISOString();
    setItems((prev) =>
      prev.map((i) =>
        i.id === itemId
          ? {
              ...i,
              sku_code: payload.sku_code,
              status: payload.status,
              is_validation_object: payload.is_validation_object,
              updated_at: now,
            }
          : i
      )
    );
    const target = items.find((i) => i.id === itemId);
    if (target) {
      appendAudit(
        'item',
        'item.maintenance.update',
        target.item_uid,
        `更新物品维护字段：sku_code=${payload.sku_code || '空'}，status=${payload.status}`
      );
    }
  };

  const handleSaveFashionProfile = (
    itemId: number,
    profile: FashionProfile,
    options?: {
      sku_code?: string | null;
      image_assets?: ItemImageAsset[];
      retired_count?: number;
    }
  ): { ok: boolean; error?: string } => {
    const item = items.find((i) => i.id === itemId);
    if (!item) return { ok: false, error: '物品不存在' };
    if (item.project !== 'fashion') {
      return { ok: false, error: '仅服装项目支持服装五项基础资料编辑器' };
    }
    const now = new Date().toISOString();
    const existingSizeChart = (item.profile as FashionProfile | null)?.size_chart ?? null;
    const mergedProfile: FashionProfile = {
      ...profile,
      ...(existingSizeChart ? { size_chart: existingSizeChart } : {}),
    };
    const nextSku =
      options && options.sku_code !== undefined ? options.sku_code : item.sku_code;
    const nextAssets = options?.image_assets
      ? options.image_assets.map((a) => ({
          ...a,
          state: 'attached' as const,
          expires_at: null,
        }))
      : item.image_assets;

    setItems((prev) =>
      prev.map((i) =>
        i.id === itemId
          ? {
              ...i,
              sku_code: nextSku,
              profile: mergedProfile,
              image_assets: nextAssets,
              updated_at: now,
            }
          : i
      )
    );
    appendAudit(
      'item',
      'item.details.update',
      item.item_uid,
      `原子保存款式与服装资料：sku=${nextSku || '空'}，名称「${profile.name}」，关联图片 ${
        profile.image_urls.length
      } 张（pending→attached${
        options?.retired_count ? `，移除转 retired ${options.retired_count} 张` : ''
      }）`
    );
    return { ok: true };
  };

  const prepareFirstItem=(id:string)=>{
    const record=proto.firstDeliveries.find(r=>r.id===id),plan=proto.salesPlans.find(s=>s.id===record?.planId),issue=proto.issuances.find(i=>i.id===plan?.issuanceId),style=proto.styles.find(s=>s.id===plan?.styleId);
    if(!record||!plan||!issue||!style||record.stage!==3||record.itemId||record.saleState==='review'||record.saleState==='excluded')return{ok:false,error:'请从合格验收后的本件任务准备数字身份。'};
    const occupied=new Set(Object.values(proto.identities).filter(m=>m.issuanceId===issue.id).map(m=>m.editionNumber));let number=record.editionNumber||1;if(record.editionNumber&&occupied.has(number))return{ok:false,error:'本件正式序号与已有身份冲突，请核对原记录。'};while(occupied.has(number))number++;
    const prefix=style.project==='fashion'?'FASH-2026-':'JEW-2026-';let uidNumber=Math.max(0,...items.filter(i=>i.item_uid.startsWith(prefix)).map(i=>Number(i.item_uid.slice(prefix.length))).filter(n=>n<900000))+1;while(items.some(i=>i.item_uid===prefix+String(uidNumber).padStart(6,'0')))uidNumber++;
    const result=handleCreateItemDraft({project:style.project,sku_code:style.code,item_uid:prefix+String(uidNumber).padStart(6,'0'),issuanceId:issue.id,firstDeliveryId:record.id,editionNumber:issue.mode==='timed'&&!issue.sealedAt?null:number});
    if(result.ok&&result.item)proto.setFirstDeliveries(prev=>prev.map(r=>r.id===id?{...r,itemId:result.item!.id,history:[...r.history,{time:new Date().toISOString(),text:'从本次交付建立并关联稳定数字身份；未配卡或认领'}]}:r));
    return result;
  };
  const renderFirstDeliveries=(planId?:string)=>simulateApiError?<Alert type="error" title="交付任务读取失败" action={<Button onClick={()=>setSimulateApiError(false)}>重试读取</Button>}/>:<FirstSalesPage planId={planId} initialRecordId={firstRecordId} onRecordChange={setFirstRecordId} onPrepareItem={prepareFirstItem} onOpenSale={id=>{setFirstRecordId(null);selectSale(id,'overview');}} onOpenItem={handleOpenItemDetailFromAnywhere} onManageItems={()=>{captureTask();setCurrentPage('items');}} onManageChips={record=>{captureTask(record);setCurrentPage('chips');if(record?.itemId){const i=items.find(i=>i.id===record.itemId);setActiveChipId(i?.bound_chip_id||null);}}}/>;

  // ==================== B / C / D 治理动作实现 ====================
  const handleDeleteL1Chip = (chipId: number, reason: string) => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip) return { ok: false, error: '芯片不存在' };
    if (chip.item_id !== null || chip.keys_generated || chip.provisioned_at) {
      return { ok: false, error: '该芯片存在绑定或密钥依赖，不属于 L1，禁止直接删除。' };
    }
    setChips((prev) => prev.filter((c) => c.id !== chipId));
    appendAudit('cleanup', 'b.cleanup.l1_chip', chip.chip_uid, `L1 无依赖芯片直接清理：${reason}`);
    return { ok: true };
  };

  const handleDeleteL1Item = (itemId: number, reason: string) => {
    const item = items.find((i) => i.id === itemId);
    if (!item) return { ok: false, error: '物品不存在' };
    if (item.bound_chip_id !== null || item.status !== 'draft') {
      return { ok: false, error: '该物品存在芯片绑定或非草稿状态，禁止直接删除。' };
    }
    setItems((prev) => prev.filter((i) => i.id !== itemId));
    appendAudit('cleanup', 'b.cleanup.l1_item', item.item_uid, `L1 无依赖草稿物品清理：${reason}`);
    return { ok: true };
  };

  const handleExitL2ValidationChip = (chipId: number, reason: string) => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip) return { ok: false, error: '芯片不存在' };
    const now = new Date().toISOString();
    const oldItemId = chip.item_id;
    const oldItemUid = chip.item_uid;
    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId
          ? {
              ...c,
              chip_status: 'retired',
              item_id: null,
              item_uid: null,
              updated_at: now,
            }
          : c
      )
    );
    if (oldItemId) {
      setItems((prev) =>
        prev.map((i) =>
          i.id === oldItemId
            ? {
                ...i,
                status: 'disabled',
                bound_chip_id: null,
                bound_chip_uid: null,
                bound_chip_status: null,
                updated_at: now,
              }
            : i
        )
      );
    }
    appendAudit(
      'cleanup',
      'b.exit_validation.l2_chip',
      chip.chip_uid,
      `L2 生产验证对象退出验证服务并解除对测试物品 ${oldItemUid || ''} 的占用（保留安全计数历史）：${reason}`
    );
    return { ok: true };
  };

  const handleCorrectItemIdentity = (
    itemId: number,
    newProject: ProjectCode,
    newItemUid: string,
    reason: string
  ) => {
    const item = items.find((i) => i.id === itemId);
    if (!item) return { ok: false, error: '物品不存在' };
    if (item.status !== 'draft' || item.bound_chip_id !== null) {
      return { ok: false, error: '仅未绑定芯片的草稿物品允许修正身份编号或项目。' };
    }
    const conflict = items.find(
      (i) => i.id !== itemId && i.project === newProject && i.item_uid === newItemUid
    );
    if (conflict) {
      return { ok: false, error: `目标编号 ${newItemUid} 已存在，不能冲突。` };
    }
    const now = new Date().toISOString();
    setItems((prev) =>
      prev.map((i) =>
        i.id === itemId
          ? { ...i, project: newProject, item_uid: newItemUid, updated_at: now }
          : i
      )
    );
    appendAudit(
      'correction',
      'c.correct.item_identity',
      `${item.item_uid} → ${newItemUid}`,
      `草稿物品身份纠错（项目：${newProject}）。原因：${reason}`
    );
    return { ok: true };
  };

  const handleUnbindOrRebindMisboundChip = (
    chipId: number,
    mode: 'unbind_to_pending' | 'rebind_to_target',
    targetItemId: number | null,
    reason: string
  ) => {
    const chip = chips.find((c) => c.id === chipId);
    if (!chip || !chip.item_id) return { ok: false, error: '芯片当前未绑定物品' };
    const tapCnt = chip.item_uid
      ? tapEvents.filter((e) => e.item_uid === chip.item_uid).length
      : 0;
    if (chip.provisioned_at || tapCnt > 0) {
      return {
        ok: false,
        error: '已完成实卡配置核验或已产生外部真实触碰记录的芯片禁止按误绑定解绑，请走 D 工作流。',
      };
    }
    const oldItemId = chip.item_id;
    const oldItemUid = chip.item_uid;
    const now = new Date().toISOString();

    if (mode === 'unbind_to_pending') {
      setChips((prev) =>
        prev.map((c) =>
          c.id === chipId
            ? {
                ...c,
                chip_status: 'pending',
                item_id: null,
                item_uid: null,
                updated_at: now,
              }
            : c
        )
      );
      setItems((prev) =>
        prev.map((i) =>
          i.id === oldItemId
            ? {
                ...i,
                bound_chip_id: null,
                bound_chip_uid: null,
                bound_chip_status: null,
                bound_chip_keys_generated: false,
                bound_chip_provisioned_at: null,
                updated_at: now,
              }
            : i
        )
      );
      appendAudit(
        'correction',
        'c.correct.unbind_misbound',
        chip.chip_uid,
        `解除与 ${oldItemUid} 的错误绑定，芯片回退为 pending。原因：${reason}`
      );
      return { ok: true };
    }

    const newTarget = items.find((i) => i.id === targetItemId);
    if (!newTarget || newTarget.bound_chip_id !== null) {
      return { ok: false, error: '目标物品不存在或已被占用' };
    }

    setChips((prev) =>
      prev.map((c) =>
        c.id === chipId
          ? {
              ...c,
              project: newTarget.project,
              item_id: newTarget.id,
              item_uid: newTarget.item_uid,
              updated_at: now,
            }
          : c
      )
    );
    setItems((prev) =>
      prev.map((i) => {
        if (i.id === oldItemId) {
          return {
            ...i,
            bound_chip_id: null,
            bound_chip_uid: null,
            bound_chip_status: null,
            bound_chip_keys_generated: false,
            bound_chip_provisioned_at: null,
            updated_at: now,
          };
        }
        if (i.id === newTarget.id) {
          return {
            ...i,
            bound_chip_id: chip.id,
            bound_chip_uid: chip.chip_uid,
            bound_chip_status: 'bound',
            bound_chip_keys_generated: chip.keys_generated,
            bound_chip_provisioned_at: null,
            updated_at: now,
          };
        }
        return i;
      })
    );
    appendAudit(
      'correction',
      'c.correct.rebind_misbound',
      `${chip.chip_uid}: ${oldItemUid} → ${newTarget.item_uid}`,
      `误绑定改绑至正确物品 ${newTarget.item_uid}。原因：${reason}`
    );
    return { ok: true };
  };

  const handleReportChipLost = (chipId:number,reason:string)=>proto.reportLost(chipId,reason);

  const handleExecuteCarrierReplacement = (payload: {
    itemId: number;
    newChipId: number;
    scenario: 'loss_replacement' | 'resale_new_carrier';
    reason: string;
  }) => {
    const item = items.find((i) => i.id === payload.itemId);
    const newChip = chips.find((c) => c.id === payload.newChipId);
    if (!item || !newChip) return { ok: false, error: '物品或新芯片不存在' };
    if (newChip.chip_status !== 'pending' || newChip.item_id !== null) {
      return { ok: false, error: '新芯片必须处于待绑定且未占用状态' };
    }
    const oldChipId = item.bound_chip_id;
    const oldChipUid = item.bound_chip_uid;
    const now = new Date().toISOString();
    const nextGen = (item.carrier_generation || 1) + 1;

    setChips((prev) =>
      prev.map((c) => {
        if (c.id === oldChipId) {
          return {
            ...c,
            chip_status: 'retired',
            replaced_by_chip_uid: newChip.chip_uid,
            updated_at: now,
          };
        }
        if (c.id === newChip.id) {
          return {
            ...c,
            project: item.project,
            chip_status: 'bound',
            item_id: item.id,
            item_uid: item.item_uid,
            keys_generated: true,
            key_version: 'v1',
            provisioned_at: now,
            replaces_chip_uid: oldChipUid,
            last_counter: 2,
            updated_at: now,
          };
        }
        return c;
      })
    );

    setItems((prev) =>
      prev.map((i) =>
        i.id === item.id
          ? {
              ...i,
              bound_chip_id: newChip.id,
              bound_chip_uid: newChip.chip_uid,
              bound_chip_status: 'bound',
              bound_chip_keys_generated: true,
              bound_chip_provisioned_at: now,
              carrier_generation: nextGen,
              carrier_history: [
                ...(i.carrier_history || []).map((h) => ({ ...h, is_current_active: false })),
                {
                  id: `ch-${Date.now()}`,
                  chip_uid: newChip.chip_uid,
                  action:
                    payload.scenario === 'loss_replacement'
                      ? 'replacement_activate'
                      : 'resale_new_carrier',
                  timestamp: now,
                  operator: authenticatedUser || 'cece',
                  summary: `完成第 ${nextGen} 代新载体芯片 ${newChip.chip_uid} 正式接续（原芯片 ${oldChipUid} 已永久退役）：${payload.reason}`,
                  is_current_active: true,
                },
              ],
              updated_at: now,
            }
          : i
      )
    );

    appendAudit(
      'replacement',
      payload.scenario === 'loss_replacement'
        ? 'd.carrier.loss_replacement'
        : 'd.carrier.resale_new_carrier',
      `${item.item_uid}: ${oldChipUid} (retired) → ${newChip.chip_uid} (active)`,
      payload.reason
    );
    return { ok: true };
  };

  const handleSimulateNewTap = () => {
    const now = new Date();
    const newTap: TapEventRecord = {
      id: `t-sim-${Date.now()}`,
      item_id: 1,
      item_uid: 'FASH-2026-000001',
      project: 'fashion',
      beijing_date: '2026-10-27',
      tapped_at: now.toISOString(),
    };
    setTapEvents((prev) => [...prev, newTap]);
    message.success(
      '〔演示〕已添加合成触碰样例，未请求真实验证接口。'
    );
  };

  // ==================== 未登录状态：管理后台登录页 ====================
  if (!authenticatedUser) {
    const handleLoginSubmit = () => {
      const u = loginUsername.trim();
      const code = totpCode.trim();
      if (!u || !loginPassword) {
        setLoginError('请输入管理员账号和密码。');
        return;
      }
      if ([...u].length > 64) {
        setLoginError('管理员账号最多 64 个字符。');
        return;
      }
      if ([...loginPassword].length > 128) {
        setLoginError('密码最多 128 个字符。');
        return;
      }
      if (!/^\d{6}$/.test(code)) {
        setLoginError('请输入 6 位数字验证码。');
        return;
      }
      setLoginError('');
      setAuthenticatedUser(u);setLoginPassword('');setTotpCode('');
      appendAudit('auth', 'admin.auth.login', u, '原型演示登录，未连接真实认证服务');
      message.success(`欢迎回来，${u}`);
    };

    return (
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            colorPrimary: '#1677ff',
            borderRadius: 8,
            fontFamily: UNIFIED_FONT_FAMILY,
            fontFamilyCode: UNIFIED_FONT_FAMILY,
          },
        }}
      >
        <AntdApp>
          <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6">
            <Card style={{ width: 420, maxWidth: '100%' }} className="shadow-lg">
              <div className="space-y-4">
                <Space size={10}>
                  <div className="w-9 h-9 rounded-lg bg-blue-600 text-white font-bold flex items-center justify-center">
                    BB
                  </div>
                  <div>
                    <div className="font-bold text-base text-slate-900">BUMBUM 管理后台</div>
                    <div className="text-xs text-slate-500">
                      NFC 防伪配卡与数字物品管理系统
                    </div>
                  </div>
                </Space>

                <Divider style={{ margin: '4px 0' }} />

                <Alert style={{marginBottom:20}} type="info" showIcon title="高保真交互原型 · 请勿输入真实凭据" description="本页面仅演示登录及错误反馈，不连接管理员认证服务。"/>
              <Button block style={{marginBottom:20}} onClick={()=>{setAuthenticatedUser('演示管理员');setLoginError('');}}>使用演示身份进入</Button>
              <Form layout="vertical" onFinish={handleLoginSubmit}>
                  <Form.Item
                    label="管理员账号"
                    validateStatus={[...loginUsername.trim()].length > 64 ? 'error' : undefined}
                    help={
                      [...loginUsername.trim()].length > 64
                        ? `最多 64 个字符（当前 ${[...loginUsername.trim()].length}/64）`
                        : undefined
                    }
                  >
                    <Input
                      prefix={<UserOutlined />}
                      value={loginUsername}
                      onChange={(e) => {
                        setLoginUsername(e.target.value);
                        setLoginError('');
                      }}
                      placeholder="请输入管理员账号"
                    />
                  </Form.Item>
                  <Form.Item
                    label="管理员密码"
                    validateStatus={[...loginPassword].length > 128 ? 'error' : undefined}
                    help={
                      [...loginPassword].length > 128
                        ? `最多 128 个字符（当前 ${[...loginPassword].length}/128）`
                        : undefined
                    }
                  >
                    <Input.Password
                      prefix={<LockOutlined />}
                      value={loginPassword}
                      onChange={(e) => {
                        setLoginPassword(e.target.value);
                        setLoginError('');
                      }}
                      placeholder="请输入密码"
                    />
                  </Form.Item>
                  <Form.Item label="Authenticator 6位验证码">
                    <Input.OTP
                      length={6}
                      value={totpCode}
                      formatter={(str) => str.replace(/\D/g, '')}
                      onChange={(val) => {
                        setTotpCode(val);
                        setLoginError('');
                      }}
                    />
                  </Form.Item>
                  {loginError && (
                    <Form.Item style={{ marginBottom: 16 }}>
                      <Alert type="error" showIcon message={loginError} />
                    </Form.Item>
                  )}
                  <Form.Item style={{ marginBottom: 0 }}>
                    <Button type="primary" htmlType="submit" block>
                      登录
                    </Button>
                  </Form.Item>
                </Form>
              </div>
            </Card>
          </div>
        </AntdApp>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
          fontFamily: UNIFIED_FONT_FAMILY,
          fontFamilyCode: UNIFIED_FONT_FAMILY,
        },
      }}
    >
      <AntdApp>
        <Layout className="admin-layout-shell">
        {/* 左侧真实导航栏：严格移除所有无效假按钮（无设置、无通知、无导出） */}
        <Sider
          width={248}
          theme="light"
          className="admin-sider border-r border-slate-200 shrink-0"
        >
          <div className="flex flex-col h-full">
            <div className="p-4 border-b border-slate-200/80">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-600 text-white font-bold text-sm flex items-center justify-center shadow-sm">
                  BB
                </div>
                <div>
                  <div className="font-bold text-slate-900 text-sm leading-tight">
                    BUMBUM 管理后台
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    NFC 防伪配卡与数字物品中心
                  </div>
                </div>
              </div>
            </div>

            <div className="flex-1 py-2 overflow-y-auto">
              <Menu
                mode="inline"
                selectedKeys={[(currentPage==='items'||currentPage==='chips')?'assets':(currentPage==='audit'||currentPage==='checks')?'system':currentPage]}
                style={{ borderInlineEnd: 0 }}
                onClick={({key})=>proto.guard(()=>{proto.closeWork();setActiveItemId(null);setActiveChipId(null);setFirstRecordId(null);setTaskReturn(null);setCurrentPage(key==='assets'?'items':key==='system'?'audit':key as NavPageKey);})}
                items={[
                  {key:'overview',icon:<AppstoreOutlined/>,label:'工作台'},
                  {key:'commerce',icon:<ShoppingOutlined/>,label:'商品与发售'},
                  {key:'delivery',icon:<CheckCircleOutlined/>,label:'交付与售后'},
                  {key:'assets',icon:<LinkOutlined/>,label:'物品与芯片'},
                  {key:'system',icon:<CloudServerOutlined/>,label:'系统管理'},
                ]}
              />
            </div>

            <div className="px-4 py-3 border-t border-slate-200/80 bg-slate-50/60">
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>物品类别：服装 / 饰品</span>
                <Text code style={{ fontSize: 11 }}>
                  SUN v1
                </Text>
              </div>
            </div>
          </div>
        </Sider>

        {/* 右侧主区域 */}
        <Layout className="admin-main-layout">
          {/* 顶栏：左侧当前页面上下文，右上角统一收拢管理员身份、会话状态与退出登录 */}
          <Header
            style={{
              background: '#ffffff',
              height: 58,
              lineHeight: 'normal',
              padding: '0 24px',
            }}
            className="border-b border-slate-200 flex items-center justify-between shrink-0"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="font-semibold text-slate-900 text-base truncate">
                {PAGE_TITLES[currentPage].title}
              </span>
              <span className="hidden xl:inline-block text-xs text-slate-400 truncate">
                — {PAGE_TITLES[currentPage].subtitle}
              </span>
            </div>

            <Space size={10} split={<Divider type="vertical" style={{ margin: 0 }} />}>
              <Dropdown trigger={['click']} menu={{items:[{key:'normal',label:'恢复正常演示'},{key:'loading',label:'〔演示〕列表加载中'},{key:'read',label:'列表读取失败'},{key:'save',label:'保存失败'},{key:'unknown',label:'保存结果未知'},{key:'upload',label:'图片上传失败'},{type:'divider'},{key:'tap',label:'添加触碰样例'},{key:'reset',label:'重置样例与办理记录'}],onClick:({key})=>{if(key==='reset'){setSimulateLoading(false);setSimulateApiError(false);proto.reset();return;}if(key==='tap'){handleSimulateNewTap();return;}setSimulateLoading(key==='loading');setSimulateApiError(key==='read');proto.setFailureMode(key==='save'?'save':key==='unknown'?'unknown':key==='upload'?'upload':'none');}}}><Button size="small">原型演示 · 样例数据</Button></Dropdown>
              <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200/90 rounded-full pl-2.5 pr-1.5 py-1">
                <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-semibold flex items-center justify-center">
                  {authenticatedUser.slice(0, 1).toUpperCase()}
                </div>
                <span className="text-xs font-medium text-slate-700">
                  管理员：{authenticatedUser}
                </span>
                <Badge status="success" text={<span className="text-[11px] text-slate-500">演示会话</span>} />
                <Button
                  size="small"
                  type="text"
                  danger
                  icon={<LogoutOutlined />}
                  onClick={() => {
                    proto.guard(()=>{setAuthenticatedUser(null);setLoginPassword('');setTotpCode('');proto.closeWork();});
                    message.info('已安全退出管理后台会话');
                  }}
                >
                  退出登录
                </Button>
              </div>
            </Space>
          </Header>

          {/* 主内容滚动区（P1-3：使用 display 保活挂载，跨页跳转后返回原页面时筛选条件与页码 100% 保留） */}
          <Content className="admin-content-scroll p-5">
            <div className="max-w-[1440px] mx-auto">
              <PrototypeOverlays/>
              {(proto.activeWorkId||proto.activeDraft)&&<Modal open centered width={1120} title="业务办理" zIndex={1600} footer={null} mask={{closable:false}} onCancel={()=>proto.guard(()=>{const id=proto.activeDraft?.itemId||proto.works.find(w=>w.id===proto.activeWorkId)?.itemId;proto.closeWork();if(id&&workOrigin.current==='detail'){setCurrentPage('items');setActiveItemId(id);}})} styles={{body:{maxHeight:'calc(100dvh - 190px)',overflowY:'auto'}}}>
                <LifecyclePage onBack={itemId=>{proto.closeWork();setCurrentPage('items');setActiveItemId(itemId);}}/>
              </Modal>}
              <Spin spinning={simulateLoading} tip="〔演示〕正在读取样例"><div>
              {taskReturn&&(currentPage==='items'||currentPage==='chips')&&<Alert style={{marginBottom:16}} type="info" showIcon title={'当前任务：'+(proto.salesPlans.find(s=>s.id===taskReturn.saleId)?.name||'交付办理')+(taskReturn.itemId?' · '+items.find(i=>i.id===taskReturn.itemId)?.item_uid:'')} description="登记、绑定和配置仍使用已有流程；完成后回到本次交付继续。" action={<Button type="primary" onClick={returnToTask}>返回本次交付</Button>}/>}
              {(currentPage==='items'||currentPage==='chips')&&<Tabs activeKey={currentPage} onChange={key=>proto.guard(()=>setCurrentPage(key as NavPageKey))} items={[{key:'items',label:'数字物品档案'},{key:'chips',label:'芯片库存与配卡'}]}/>}
              {(currentPage==='audit'||currentPage==='checks')&&<Tabs activeKey={currentPage} onChange={key=>setCurrentPage(key as NavPageKey)} items={[{key:'audit',label:'操作日志'},{key:'checks',label:'系统与环境'}]}/>}
              {currentPage==='commerce'&&<div className="proto-stack">{!saleId&&<Tabs activeKey={commerceView} onChange={key=>proto.guard(()=>setCommerceView(key))} items={[{key:'sales',label:'发售批次'},{key:'styles',label:'商品款式'},{key:'issues',label:'发行档案'}]}/>}{commerceView==='sales'?<SaleWorkspace tapEvents={tapEvents} saleId={saleId} tab={saleTab} initialStyleId={newSaleStyle} onSelect={selectSale} onOpenItem={handleOpenItemDetailFromAnywhere} orders={id=>renderFirstDeliveries(id)}/>:<CatalogPage key={commerceView} onOpenSale={id=>selectSale(id,'product')} kind={commerceView==='styles'?'styles':'issues'} onStartSale={styleId=>{setNewSaleStyle(styleId);selectSale('new');}} onOpenItem={handleOpenItemDetailFromAnywhere} readError={simulateApiError} onRetry={()=>setSimulateApiError(false)}/>}</div>}
              {currentPage==='delivery'&&<div className="proto-stack"><Tabs activeKey={deliveryView} onChange={key=>proto.guard(()=>setDeliveryView(key))} items={[{key:'first',label:'首次交付任务'},{key:'after',label:'换新与转售'}]}/>{deliveryView==='first'?renderFirstDeliveries():<AfterSalesRecords onOpenItem={handleOpenItemDetailFromAnywhere} readError={simulateApiError} onRetry={()=>setSimulateApiError(false)}/>}</div>}
              <div style={{ display: currentPage === 'overview' ? 'block' : 'none' }}>
                <BusinessOverview onNew={()=>{setNewSaleStyle(undefined);selectSale('new');}} onSale={id=>selectSale(id)} onDelivery={()=>{setDeliveryView('first');setCurrentPage('delivery');}}/>

                <OverviewPage
                  chips={chips}
                  items={items}
                  tapEvents={tapEvents}
                  excludeValidationInStats={excludeValidationInStats}
                  onToggleExcludeValidationInStats={()=>pendingPolicy('清理')}
                  simulateApiError={simulateApiError}
                  onRecoverApiError={() => {
                    setSimulateApiError(false);
                    message.success('接口重试成功，已恢复最新数据');
                  }}
                  onNavigate={(p) => setCurrentPage(p)}
                  onNavigateChipsWithPreset={handleNavigateChipsWithPreset}
                  onNavigateItemsWithPreset={handleNavigateItemsWithPreset}
                  onOpenItemDetail={handleOpenItemDetailFromAnywhere}
                  onOpenChipDetail={handleOpenChipDetailFromAnywhere}
                  onSimulateNewTap={handleSimulateNewTap}
                />

              </div>

              <div style={{ display: currentPage === 'chips' ? 'block' : 'none' }}>
                <ChipManagementPage
                  contextItemId={taskReturn?.itemId}
                  chips={chips}
                  items={items}
                  tapEvents={tapEvents}
                  activeChipId={activeChipId}
                  presetFilter={chipPresetFilter}
                  simulateApiError={simulateApiError}
                  onRecoverApiError={() => {
                    setSimulateApiError(false);
                    message.success('芯片列表重试加载成功');
                  }}
                  onSelectChipId={setActiveChipId}
                  onOpenItemDetail={handleOpenItemDetailFromAnywhere}
                  onRegisterChip={handleRegisterChip}
                  onUpdateChipMaintenance={handleUpdateChipMaintenance}
                  onBindChipToItem={handleBindChipToItem}
                  onGenerateChipKeys={handleGenerateChipKeys}
                  onConfirmChipProvisioning={handleConfirmChipProvisioning}
                  onToggleChipTempStatus={handleToggleChipTempStatus}
                  onCorrectPendingChipProject={()=>({ok:false,error:'项目纠错规则待审核，未修改样例。'})}
                  onUnbindOrRebindMisboundChip={()=>({ok:false,error:'解绑/改绑规则待审核，未修改样例。'})}
                  onReportChipLost={(id,reason)=>{proto.reportLost(id,reason);return {ok:true};}}
                  onExecuteCarrierReplacement={()=>({ok:false,error:'请从物品权益进入换新或转售办理，不直接覆盖关联。'})}
                  onDeleteL1Chip={()=>({ok:false,error:'清理资格与编号政策待审核，不执行删除。'})}
                  onExitL2ValidationChip={()=>({ok:false,error:'退出验证及关联释放规则待审核。'})}
                />
              </div>

              <div style={{ display: currentPage === 'items' ? 'block' : 'none' }}>
<ItemManagementPage
                  items={items}
                  chips={chips}
                  activeItemId={activeItemId}
                  presetFilter={itemPresetFilter}
                  simulateApiError={simulateApiError}
                  onRecoverApiError={() => {
                    setSimulateApiError(false);
                    message.success('物品列表重试加载成功');
                  }}
                  onSelectItemId={setActiveItemId}
                  onOpenChipDetail={handleOpenChipDetailFromAnywhere}
                  onBindChipToItem={handleBindChipToItem}
                  onCreateItemDraft={handleCreateItemDraft}
                  onUpdateItemMaintenance={handleUpdateItemMaintenance}
                  onSaveFashionProfile={handleSaveFashionProfile}
                  onCorrectItemIdentity={()=>({ok:false,error:'编号与项目纠错待审核，未修改样例。'})}
                  onDeleteL1Item={()=>({ok:false,error:'清理资格与编号政策待审核，不执行删除。'})}
                  onUnbindOrRebindMisboundChip={()=>({ok:false,error:'解绑/改绑规则待审核，未修改样例。'})}
                  onReportChipLost={(id,reason)=>{proto.reportLost(id,reason);return {ok:true};}}
                  onExecuteCarrierReplacement={()=>({ok:false,error:'请从物品权益进入换新或转售办理，不直接覆盖关联。'})}
                />
              </div>

              <div style={{ display: currentPage === 'audit' ? 'block' : 'none' }}>
                <Card
                  size="small"
                  title={
                    <Space>
                      <span>操作日志</span>
                      <Tag color="blue">共 {auditLogs.length} 条</Tag>
                    </Space>
                  }
                >
                  <Table
                    rowKey="id"
                    size="middle"
                    dataSource={auditLogs}
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    columns={[
                      {
                        title: '时间',
                        dataIndex: 'timestamp',
                        width: 170,
                        render: (t: string) =>
                          new Date(t).toLocaleString('zh-CN', { hour12: false }),
                      },
                      {
                        title: '管理员',
                        dataIndex: 'operator',
                        width: 120,
                        render: (o: string) => <Tag color="blue">{o}</Tag>,
                      },
                      {
                        title: '操作动作',
                        dataIndex: 'action',
                        width: 210,
                        render: (a: string) => <Tooltip title={a}><span>{({'chip.register':'登记芯片','item.create':'创建物品草稿','chip.bind':'首次绑定','admin.auth.login':'管理员登录','chip.keys.generate':'生成密钥','item.profile.save':'保存商品资料'} as Record<string,string>)[a]||(a.includes('.')?'历史操作':a)}</span></Tooltip>,
                      },
                      {
                        title: '操作对象',
                        dataIndex: 'target',
                        width: 240,
                        render: (tg: string) => <Text strong>{tg}</Text>,
                      },
                      {
                        title: '详情说明',
                        dataIndex: 'detail',
                      },
                    ]}
                  />
                </Card>
              </div>

              <div style={{ display: currentPage === 'checks' ? 'block' : 'none' }}>
                <Alert style={{marginBottom:16}} showIcon type="info" title="运行诊断演示" description="未连接真实服务或数据库；正常/检查中状态仅是样例，不构成环境验收证据。"/>
                <div className="space-y-4">
                  <Card
                    size="small"
                    title="服务与数据库健康检查 (/healthz & /readyz)"
                    extra={
                      <Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          最近检查时间：{lastCheckTime}
                        </Text>
                        <Button
                          type="primary"
                          icon={<ReloadOutlined spin={healthChecking} />}
                          onClick={() => {
                            setHealthChecking(true);
                            setTimeout(() => {
                              setLastCheckTime(
                                new Date().toLocaleTimeString('zh-CN', { hour12: false })
                              );
                              setHealthChecking(false);
                              message.success('诊断样例已刷新（未访问真实服务）');
                            }, 250);
                          }}
                        >
                          〔演示〕重新执行检查
                        </Button>
                      </Space>
                    }
                  >
                    <Row gutter={[16, 16]}>
                      <Col xs={24} md={12}>
                        <Card size="small" className="bg-emerald-50/40 border-emerald-200">
                          <Space align="start" size={12}>
                            <CheckCircleOutlined
                              style={{ fontSize: 24, color: '#16a34a', marginTop: 4 }}
                            />
                            <div>
                              <div className="font-semibold text-slate-900">
                                服务进程检查 (GET /healthz)
                              </div>
                              <div className="text-lg font-bold text-emerald-700 mt-1">
                                样例：正常状态
                              </div>
                              <div className="text-xs text-slate-500 mt-1">
                                管理后台与 NFC 验签主进程响应正常，未进行实时测量。
                              </div>
                            </div>
                          </Space>
                        </Card>
                      </Col>
                      <Col xs={24} md={12}>
                        <Card size="small" className="bg-emerald-50/40 border-emerald-200">
                          <Space align="start" size={12}>
                            <CheckCircleOutlined
                              style={{ fontSize: 24, color: '#16a34a', marginTop: 4 }}
                            />
                            <div>
                              <div className="font-semibold text-slate-900">
                                数据库与结构检查 (GET /readyz)
                              </div>
                              <div className="text-lg font-bold text-emerald-700 mt-1">
                                200 OK · PostgreSQL 就绪
                              </div>
                              <div className="text-xs text-slate-500 mt-1">
                                RDS MySQL 连接池、芯片密钥信封加密主密钥 (v1) 与表结构校验通过。
                              </div>
                            </div>
                          </Space>
                        </Card>
                      </Col>
                    </Row>
                  </Card>
                </div>
              </div>
            </div></Spin>
            </div>
          </Content>
        </Layout>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  );
}

export default function App(){return <PrototypeProvider><AppCore/></PrototypeProvider>;}
